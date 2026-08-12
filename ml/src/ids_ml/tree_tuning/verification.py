"""Outer-validation refits, stability checks, diagnostics, and CPU timing."""

from __future__ import annotations

import gc
import json
import platform
from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
import xgboost as xgb
from optuna.trial import FrozenTrial
from ..data import (
    LABEL_ORDER,
    RANDOM_STATE,
    ExperimentData,
    balanced_sample_weights,
    encode_labels,
    find_project_root,
    index_fingerprint,
    make_development_split,
)
from ..evaluation import (
    TimingInputs,
    calculate_metrics_and_diagnostics,
    log_evaluation_artifacts,
    make_timing_inputs,
    measure_predictor_speed,
)
from ..tracking import setup_mlflow_experiment
from ..tree_models import log_tree_importance
from .training import (
    FEATURE_SET,
    STABILITY_SEEDS,
    TOP_TRIALS,
    VERIFICATION_EXPERIMENT,
    WEIGHTING_MODE,
    TunedTreePredictor,
    base_parameters,
    make_tuning_preprocessor,
)
from .search_space import validate_resolved_parameters
from .search import (
    create_or_load_study,
    resolved_trial_parameters,
    top_complete_trials,
)


@dataclass
class VerificationCandidate:
    model_key: str
    trial_number: int
    run_id: str
    params: dict[str, object]
    iteration_count: int
    macro_f1: float
    predictor: TunedTreePredictor


def fit_fixed_predictor(
    model_key: str,
    params: dict[str, object],
    iteration_count: int,
    X_training: pd.DataFrame,
    y_training: pd.Series,
    selected_features: list[str],
) -> tuple[TunedTreePredictor, float, np.ndarray]:
    validate_resolved_parameters(model_key, params)
    started = perf_counter()
    preprocessor = make_tuning_preprocessor(selected_features)
    transformed = np.asarray(
        preprocessor.fit_transform(X_training[selected_features]), dtype=np.float32
    )
    transformed_names = preprocessor.get_feature_names_out()
    weights = balanced_sample_weights(y_training)
    encoded = encode_labels(y_training)
    parameters = {**base_parameters(model_key), **params}
    if model_key == "xgboost":
        training = xgb.DMatrix(
            transformed,
            label=encoded,
            weight=weights,
            feature_names=transformed_names.tolist(),
        )
        booster: xgb.Booster | lgb.Booster = xgb.train(
            parameters,
            training,
            num_boost_round=iteration_count,
            verbose_eval=False,
        )
        device = json.loads(booster.save_config())["learner"]["generic_param"]["device"]
        if not str(device).startswith("cuda"):
            raise AssertionError(f"XGBoost verification did not train on CUDA: {device}")
    else:
        training = lgb.Dataset(
            transformed,
            label=encoded,
            weight=weights,
            feature_name=transformed_names.tolist(),
            free_raw_data=False,
        )
        booster = lgb.train(
            parameters,
            training,
            num_boost_round=iteration_count,
        )
        if str(booster.params.get("device_type")) != "cpu":
            raise AssertionError("LightGBM verification did not train on CPU.")
    training_seconds = perf_counter() - started
    predictor = TunedTreePredictor(
        model_key,
        preprocessor,
        booster,
        selected_features,
        iteration_count,
    )
    return predictor, float(training_seconds), transformed_names


def importance_values(
    predictor: TunedTreePredictor, transformed_names: np.ndarray
) -> np.ndarray:
    if predictor.booster is None:
        raise RuntimeError("Cannot inspect a released predictor.")
    if predictor.model_key == "xgboost":
        scores = predictor.booster.get_score(importance_type="gain")
        return np.asarray([scores.get(name, 0.0) for name in transformed_names])
    return np.asarray(predictor.booster.feature_importance(importance_type="gain"))


def _verification_tags(
    model_key: str,
    data: ExperimentData,
    trial_number: int,
    split_seed: int,
    fit_fingerprint: str,
    validation_fingerprint: str,
    evaluation_stage: str,
) -> dict[str, str]:
    return {
        "model_key": model_key,
        "model_family": "XGBClassifier" if model_key == "xgboost" else "LGBMClassifier",
        "feature_set": FEATURE_SET,
        "weighting_mode": WEIGHTING_MODE,
        "weighting_mechanism": "balanced_sample_weight",
        "source_feature_count": "71",
        "transformed_feature_count": "73",
        "training_device": "cuda" if model_key == "xgboost" else "cpu",
        "inference_device": "cpu",
        "evaluation_stage": evaluation_stage,
        "source_trial_number": str(trial_number),
        "dataset_version": data.contract.dataset_version,
        "fit_split_fingerprint": fit_fingerprint,
        "evaluation_split_fingerprint": validation_fingerprint,
        "test_split_fingerprint": data.contract.test_fingerprint,
        "split_seed": str(split_seed),
        "python_version": platform.python_version(),
    }


def run_verification_fit(
    model_key: str,
    trial: FrozenTrial,
    data: ExperimentData,
    X_training: pd.DataFrame,
    y_training: pd.Series,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
    split_seed: int,
    evaluation_stage: str,
) -> VerificationCandidate:
    params = resolved_trial_parameters(trial)
    iteration_count = int(trial.user_attrs["best_macro_iteration"])
    tags = _verification_tags(
        model_key,
        data,
        trial.number,
        split_seed,
        index_fingerprint(X_training.index),
        index_fingerprint(X_validation.index),
        evaluation_stage,
    )
    run_name = f"verify__{model_key}__trial_{trial.number:04d}__seed_{split_seed}"
    with mlflow.start_run(run_name=run_name, tags=tags) as active_run:
        predictor, training_seconds, transformed_names = fit_fixed_predictor(
            model_key,
            params,
            iteration_count,
            X_training,
            y_training,
            data.feature_sets[FEATURE_SET],
        )
        predictions = predictor.predict(X_validation)
        metrics, report, raw_matrix, normalized_matrix = (
            calculate_metrics_and_diagnostics(y_validation, predictions)
        )
        metrics["training_time_seconds"] = training_seconds
        metrics["selected_boosting_iterations"] = float(iteration_count)
        mlflow.log_params(
            {
                "model_key": model_key,
                "source_trial_number": trial.number,
                "feature_set": FEATURE_SET,
                "weighting_mode": WEIGHTING_MODE,
                "random_state": split_seed,
                "selected_boosting_iterations": iteration_count,
                **params,
            }
        )
        mlflow.log_metrics(metrics)
        log_evaluation_artifacts(
            report,
            raw_matrix,
            normalized_matrix,
            {
                "dataset_sha256": data.contract.dataset_sha256,
                "label_order": LABEL_ORDER,
                "selected_source_features": data.feature_sets[FEATURE_SET],
                "source_feature_count": 71,
                "transformed_feature_count": 73,
                "evaluation_stage": evaluation_stage,
                "fit_rows": len(X_training),
                "evaluation_rows": len(X_validation),
                "test_rows_not_evaluated": len(data.X_test),
                "training_device": tags["training_device"],
                "inference_device": "cpu",
            },
        )
        log_tree_importance(
            transformed_names,
            importance_values(predictor, transformed_names),
            tags["model_family"],
        )
        return VerificationCandidate(
            model_key=model_key,
            trial_number=trial.number,
            run_id=active_run.info.run_id,
            params=params,
            iteration_count=iteration_count,
            macro_f1=float(metrics["macro_f1"]),
            predictor=predictor,
        )


def log_speed_for_candidate(
    candidate: VerificationCandidate, timing_inputs: TimingInputs
) -> dict[str, float]:
    speed = measure_predictor_speed(candidate.predictor, timing_inputs)
    with mlflow.start_run(run_id=candidate.run_id):
        mlflow.log_metrics(speed)
        mlflow.set_tag("selected_for_stability", "true")
    return speed


def run_verification(data: ExperimentData, model_keys: Sequence[str]) -> bool:
    setup_mlflow_experiment(VERIFICATION_EXPERIMENT)
    timing_inputs = make_timing_inputs(data.X_validation)
    stability_records: list[dict[str, object]] = []
    successful = True
    for model_key in model_keys:
        study = create_or_load_study(model_key, data.contract.dataset_sha256)
        trials = top_complete_trials(study, TOP_TRIALS)
        if len(trials) < TOP_TRIALS:
            print(
                f"{model_key}: requires {TOP_TRIALS} completed trials before verification; "
                f"found {len(trials)}."
            )
            successful = False
            continue

        winner: VerificationCandidate | None = None
        for trial in trials:
            candidate = run_verification_fit(
                model_key,
                trial,
                data,
                data.X_fit,
                data.y_fit,
                data.X_validation,
                data.y_validation,
                RANDOM_STATE,
                "outer_validation_top_trial",
            )
            print(
                f"{model_key} trial {trial.number}: outer macro F1 "
                f"{candidate.macro_f1:.6f}"
            )
            candidate_rank = (-candidate.macro_f1, candidate.trial_number)
            winner_rank = (
                (-winner.macro_f1, winner.trial_number)
                if winner is not None
                else None
            )
            if winner_rank is None or candidate_rank < winner_rank:
                if winner is not None:
                    winner.predictor.cleanup()
                winner = candidate
            else:
                candidate.predictor.cleanup()
        if winner is None:
            raise AssertionError(f"No verification candidate was produced for {model_key}.")

        log_speed_for_candidate(winner, timing_inputs)
        stability_records.append(
            {
                "model_key": model_key,
                "trial_number": winner.trial_number,
                "split_seed": RANDOM_STATE,
                "macro_f1": winner.macro_f1,
                "run_id": winner.run_id,
            }
        )
        winner_trial = next(
            trial for trial in trials if trial.number == winner.trial_number
        )
        for seed in STABILITY_SEEDS[1:]:
            X_training, X_validation, y_training, y_validation = (
                make_development_split(data, seed)
            )
            repeated = run_verification_fit(
                model_key,
                winner_trial,
                data,
                X_training,
                y_training,
                X_validation,
                y_validation,
                seed,
                "development_split_stability",
            )
            stability_records.append(
                {
                    "model_key": model_key,
                    "trial_number": repeated.trial_number,
                    "split_seed": seed,
                    "macro_f1": repeated.macro_f1,
                    "run_id": repeated.run_id,
                }
            )
            repeated.predictor.cleanup()
            del X_training, X_validation, y_training, y_validation
            gc.collect()
        winner.predictor.cleanup()
        gc.collect()

    if stability_records:
        records = pd.DataFrame(stability_records)
        summary = (
            records.groupby("model_key")["macro_f1"]
            .agg(["mean", "std", "min", "max"])
            .reset_index()
        )
        summary["range"] = summary["max"] - summary["min"]
        output = find_project_root() / "ml" / "reports" / "generated"
        output.mkdir(parents=True, exist_ok=True)
        records.to_csv(output / "tree_tuning_stability_runs.csv", index=False)
        summary.to_csv(output / "tree_tuning_stability_summary.csv", index=False)
        print("\nThree-split stability summary:")
        print(summary.to_string(index=False))
    return successful
