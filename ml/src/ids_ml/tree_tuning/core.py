"""Core preprocessing, search-space, training, and prediction contracts."""

from __future__ import annotations

import gc
import json
from dataclasses import dataclass
from time import perf_counter

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from lightgbm.callback import CallbackEnv, EarlyStopException
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import FunctionTransformer

from ..data import (
    LABEL_ORDER,
    RANDOM_STATE,
    InnerSplit,
    balanced_sample_weights,
    decode_labels,
    encode_labels,
    make_inner_split,
    transformed_feature_count,
)
from ..preprocessing import make_one_hot_protocol_preprocessor
from .search_space import validate_resolved_parameters

FEATURE_SET = "all_71"
WEIGHTING_MODE = "balanced"
TARGET_TRIALS = 20
TOP_TRIALS = 3
MAX_BOOSTING_ROUNDS = 1_500
EARLY_STOPPING_PATIENCE = 75
MACRO_F1_MIN_DELTA = 1e-4
LOG_LOSS_MIN_DELTA = 1e-5
MONITORING_SAMPLE_ROWS = 50_000
STABILITY_SEEDS = (42, 123, 2025)
TUNING_EXPERIMENT = "cicids2017-tree-tuning"
VERIFICATION_EXPERIMENT = "cicids2017-tree-tuning-verification"


@dataclass
class PreparedMatrices:
    """Preprocessed matrices fitted exclusively from one training partition."""

    preprocessor: object
    transformed_names: np.ndarray
    X_training: np.ndarray
    y_training: np.ndarray
    training_weights: np.ndarray
    X_stopping: np.ndarray
    y_stopping: np.ndarray
    X_monitoring: np.ndarray
    y_monitoring: np.ndarray
    split: InnerSplit
    preprocessing_time_seconds: float


@dataclass
class BoosterFit:
    booster: xgb.Booster | lgb.Booster
    history: pd.DataFrame
    best_macro_iteration: int
    best_loss_iteration: int
    best_macro_f1: float
    best_validation_log_loss: float
    training_time_seconds: float


def _as_float32(values: pd.DataFrame | np.ndarray) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def make_tuning_preprocessor(selected_features: list[str]):
    return make_one_hot_protocol_preprocessor(
        selected_features,
        FunctionTransformer(_as_float32, feature_names_out="one-to-one"),
        np.float32,
    )


def _monitoring_positions(
    labels: pd.Series, maximum_rows: int = MONITORING_SAMPLE_ROWS
) -> np.ndarray:
    positions = np.arange(len(labels), dtype=np.int64)
    if len(positions) <= maximum_rows:
        return positions
    selected, _ = train_test_split(
        positions,
        train_size=maximum_rows,
        random_state=RANDOM_STATE,
        stratify=labels,
    )
    return np.sort(selected)


def prepare_matrices(
    X_fit: pd.DataFrame,
    y_fit: pd.Series,
    selected_features: list[str],
    *,
    inner_test_size: float = 0.10,
) -> PreparedMatrices:
    split = make_inner_split(y_fit, test_size=inner_test_size)
    X_training_raw = X_fit.iloc[split.training_positions]
    y_training_raw = y_fit.iloc[split.training_positions]
    X_stopping_raw = X_fit.iloc[split.stopping_positions]
    y_stopping_raw = y_fit.iloc[split.stopping_positions]

    preprocessing_started = perf_counter()
    preprocessor = make_tuning_preprocessor(selected_features)
    X_training = np.asarray(
        preprocessor.fit_transform(X_training_raw[selected_features]), dtype=np.float32
    )
    X_stopping = np.asarray(
        preprocessor.transform(X_stopping_raw[selected_features]), dtype=np.float32
    )
    transformed_names = preprocessor.get_feature_names_out()
    expected_count = transformed_feature_count(len(selected_features), "one_hot")
    if X_training.shape[1] != expected_count or len(transformed_names) != expected_count:
        raise AssertionError("The tuning preprocessor violated the 73-feature contract.")
    preprocessing_time_seconds = perf_counter() - preprocessing_started

    monitoring_positions = _monitoring_positions(y_training_raw)
    return PreparedMatrices(
        preprocessor=preprocessor,
        transformed_names=transformed_names,
        X_training=X_training,
        y_training=encode_labels(y_training_raw),
        training_weights=balanced_sample_weights(y_training_raw),
        X_stopping=X_stopping,
        y_stopping=encode_labels(y_stopping_raw),
        X_monitoring=X_training[monitoring_positions],
        y_monitoring=encode_labels(y_training_raw.iloc[monitoring_positions]),
        split=split,
        preprocessing_time_seconds=float(preprocessing_time_seconds),
    )


def _prediction_matrix(predictions: np.ndarray) -> np.ndarray:
    values = np.asarray(predictions)
    if values.ndim == 1:
        values = values.reshape(-1, len(LABEL_ORDER))
    if values.ndim != 2 or values.shape[1] != len(LABEL_ORDER):
        raise AssertionError(f"Unexpected multiclass prediction shape: {values.shape}")
    return values


def _macro_f1_metric(predictions: np.ndarray, dataset: object) -> tuple[str, float]:
    probabilities = _prediction_matrix(predictions)
    labels = np.asarray(dataset.get_label(), dtype=np.int64)
    score = f1_score(
        labels,
        probabilities.argmax(axis=1),
        labels=np.arange(len(LABEL_ORDER)),
        average="macro",
        zero_division=0,
    )
    return "macro_f1", float(score)


def _lightgbm_macro_f1_metric(
    predictions: np.ndarray, dataset: object
) -> tuple[str, float, bool]:
    name, score = _macro_f1_metric(predictions, dataset)
    return name, score, True


class IterationMonitor:
    """Shared history and combined patience state for both boosting libraries."""

    def __init__(
        self,
        patience: int,
        macro_min_delta: float = MACRO_F1_MIN_DELTA,
        loss_min_delta: float = LOG_LOSS_MIN_DELTA,
    ) -> None:
        self.patience = patience
        self.macro_min_delta = macro_min_delta
        self.loss_min_delta = loss_min_delta
        self.records: list[dict[str, float | int]] = []
        self.best_macro_f1 = -np.inf
        self.best_macro_iteration = 0
        self.best_validation_loss = np.inf
        self.best_loss_iteration = 0
        self._macro_anchor = -np.inf
        self._loss_anchor = np.inf
        self._last_meaningful_macro = 0
        self._last_meaningful_loss = 0
        self._last_time = perf_counter()

    def record(
        self,
        iteration: int,
        training_loss: float,
        validation_loss: float,
        macro_f1: float,
    ) -> bool:
        iteration_number = iteration + 1
        now = perf_counter()
        self.records.append(
            {
                "iteration": iteration_number,
                "training_monitor_log_loss": float(training_loss),
                "inner_validation_log_loss": float(validation_loss),
                "inner_validation_macro_f1": float(macro_f1),
                "iteration_time_seconds": float(now - self._last_time),
            }
        )
        self._last_time = now

        if macro_f1 > self.best_macro_f1:
            self.best_macro_f1 = float(macro_f1)
            self.best_macro_iteration = iteration_number
        if validation_loss < self.best_validation_loss:
            self.best_validation_loss = float(validation_loss)
            self.best_loss_iteration = iteration_number

        if macro_f1 >= self._macro_anchor + self.macro_min_delta:
            self._macro_anchor = float(macro_f1)
            self._last_meaningful_macro = iteration_number
        if validation_loss <= self._loss_anchor - self.loss_min_delta:
            self._loss_anchor = float(validation_loss)
            self._last_meaningful_loss = iteration_number
        latest_progress = max(
            self._last_meaningful_macro, self._last_meaningful_loss
        )
        return iteration_number - latest_progress >= self.patience

    def history(self) -> pd.DataFrame:
        frame = pd.DataFrame(self.records).set_index("iteration")
        frame.index.name = "iteration"
        return frame

    def reset_timer(self) -> None:
        self._last_time = perf_counter()


class XGBoostHistoryCallback(xgb.callback.TrainingCallback):
    def __init__(self, monitor: IterationMonitor) -> None:
        self.monitor = monitor

    def after_iteration(
        self,
        model: xgb.Booster,
        epoch: int,
        evals_log: xgb.callback.TrainingCallback.EvalsLog,
    ) -> bool:
        return self.monitor.record(
            epoch,
            float(evals_log["training_monitor"]["mlogloss"][-1]),
            float(evals_log["inner_validation"]["mlogloss"][-1]),
            float(evals_log["inner_validation"]["macro_f1"][-1]),
        )


class LightGBMHistoryCallback:
    order = 50
    before_iteration = False

    def __init__(self, monitor: IterationMonitor) -> None:
        self.monitor = monitor

    def __call__(self, environment: CallbackEnv) -> None:
        results = {
            (dataset, metric): float(value)
            for dataset, metric, value, *_ in environment.evaluation_result_list or []
        }
        should_stop = self.monitor.record(
            environment.iteration,
            results[("training_monitor", "multi_logloss")],
            results[("inner_validation", "multi_logloss")],
            results[("inner_validation", "macro_f1")],
        )
        if should_stop:
            raise EarlyStopException(
                self.monitor.best_macro_iteration - 1,
                environment.evaluation_result_list or [],
            )


def base_parameters(model_key: str) -> dict[str, object]:
    if model_key == "xgboost":
        return {
            "objective": "multi:softprob",
            "num_class": len(LABEL_ORDER),
            "eval_metric": "mlogloss",
            "tree_method": "hist",
            "device": "cuda",
            "seed": RANDOM_STATE,
            "nthread": -1,
        }
    if model_key == "lightgbm":
        return {
            "objective": "multiclass",
            "num_class": len(LABEL_ORDER),
            "metric": "multi_logloss",
            "device_type": "cpu",
            "deterministic": True,
            "force_col_wise": True,
            "feature_pre_filter": False,
            "verbosity": -1,
            "seed": RANDOM_STATE,
            "num_threads": -1,
        }
    raise ValueError(f"Unknown tuning model: {model_key}")


def train_booster(
    model_key: str,
    resolved_params: dict[str, object],
    matrices: PreparedMatrices,
    *,
    maximum_rounds: int = MAX_BOOSTING_ROUNDS,
    patience: int = EARLY_STOPPING_PATIENCE,
) -> BoosterFit:
    validate_resolved_parameters(model_key, resolved_params)
    monitor = IterationMonitor(patience)
    parameters = {**base_parameters(model_key), **resolved_params}
    started = perf_counter()
    if model_key == "xgboost":
        training = xgb.DMatrix(
            matrices.X_training,
            label=matrices.y_training,
            weight=matrices.training_weights,
            feature_names=matrices.transformed_names.tolist(),
        )
        monitoring = xgb.DMatrix(
            matrices.X_monitoring,
            label=matrices.y_monitoring,
            feature_names=matrices.transformed_names.tolist(),
        )
        stopping = xgb.DMatrix(
            matrices.X_stopping,
            label=matrices.y_stopping,
            feature_names=matrices.transformed_names.tolist(),
        )
        monitor.reset_timer()
        booster = xgb.train(
            parameters,
            training,
            num_boost_round=maximum_rounds,
            evals=[(monitoring, "training_monitor"), (stopping, "inner_validation")],
            custom_metric=_macro_f1_metric,
            callbacks=[XGBoostHistoryCallback(monitor)],
            verbose_eval=False,
        )
        device = json.loads(booster.save_config())["learner"]["generic_param"]["device"]
        if not str(device).startswith("cuda"):
            raise AssertionError(f"XGBoost did not train with CUDA: {device}")
    else:
        training = lgb.Dataset(
            matrices.X_training,
            label=matrices.y_training,
            weight=matrices.training_weights,
            feature_name=matrices.transformed_names.tolist(),
            params=parameters,
            free_raw_data=False,
        )
        monitoring = lgb.Dataset(
            matrices.X_monitoring,
            label=matrices.y_monitoring,
            reference=training,
            feature_name=matrices.transformed_names.tolist(),
            params=parameters,
            free_raw_data=False,
        )
        stopping = lgb.Dataset(
            matrices.X_stopping,
            label=matrices.y_stopping,
            reference=training,
            feature_name=matrices.transformed_names.tolist(),
            params=parameters,
            free_raw_data=False,
        )
        training.construct()
        monitoring.construct()
        stopping.construct()
        monitor.reset_timer()
        booster = lgb.train(
            parameters,
            training,
            num_boost_round=maximum_rounds,
            valid_sets=[monitoring, stopping],
            valid_names=["training_monitor", "inner_validation"],
            feval=_lightgbm_macro_f1_metric,
            callbacks=[LightGBMHistoryCallback(monitor)],
        )
        if str(booster.params.get("device_type")) != "cpu":
            raise AssertionError("LightGBM did not use its required CPU learner.")

    training_seconds = perf_counter() - started
    if monitor.best_macro_iteration < 1 or monitor.best_loss_iteration < 1:
        raise AssertionError("Boosting did not produce a valid monitored iteration.")
    return BoosterFit(
        booster=booster,
        history=monitor.history(),
        best_macro_iteration=monitor.best_macro_iteration,
        best_loss_iteration=monitor.best_loss_iteration,
        best_macro_f1=monitor.best_macro_f1,
        best_validation_log_loss=monitor.best_validation_loss,
        training_time_seconds=float(training_seconds),
    )


def predict_probabilities(
    model_key: str,
    booster: xgb.Booster | lgb.Booster,
    matrix: np.ndarray,
    iteration_count: int,
    *,
    cpu_inference: bool = False,
) -> np.ndarray:
    if model_key == "xgboost":
        if cpu_inference:
            booster.set_param({"device": "cpu"})
        values = booster.predict(
            xgb.DMatrix(matrix, feature_names=booster.feature_names),
            iteration_range=(0, iteration_count),
        )
    elif model_key == "lightgbm":
        values = booster.predict(matrix, num_iteration=iteration_count)
    else:
        raise ValueError(f"Unknown tuning model: {model_key}")
    return _prediction_matrix(np.asarray(values))


class TunedTreePredictor:
    """Complete raw-data preprocessing and CPU prediction path."""

    def __init__(
        self,
        model_key: str,
        preprocessor: object,
        booster: xgb.Booster | lgb.Booster,
        selected_features: list[str],
        iteration_count: int,
    ) -> None:
        self.model_key = model_key
        self.preprocessor = preprocessor
        self.booster: xgb.Booster | lgb.Booster | None = booster
        self.selected_features = selected_features
        self.iteration_count = iteration_count
        if model_key == "xgboost":
            booster.set_param({"device": "cpu"})

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("The tuned predictor has been released.")
        transformed = np.asarray(
            self.preprocessor.transform(X[self.selected_features]), dtype=np.float32
        )
        probabilities = predict_probabilities(
            self.model_key,
            self.booster,
            transformed,
            self.iteration_count,
            cpu_inference=True,
        )
        return decode_labels(probabilities.argmax(axis=1))

    def cleanup(self) -> None:
        self.booster = None
        self.preprocessor = None
        gc.collect()
