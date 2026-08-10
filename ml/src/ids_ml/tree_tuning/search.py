"""Optuna study management and MLflow logging for tree-tuning trials."""

from __future__ import annotations

import gc
import platform
from collections.abc import Callable, Sequence
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
from optuna.samplers import TPESampler
from optuna.trial import FrozenTrial, TrialState
from sklearn.metrics import log_loss

from ..data import LABEL_ORDER, RANDOM_STATE, ExperimentData, decode_labels, find_project_root
from ..evaluation import (
    calculate_metrics_and_diagnostics,
    log_evaluation_artifacts,
    log_line_figure,
    log_table_artifact,
)
from ..tracking import setup_mlflow_experiment
from .core import (
    EARLY_STOPPING_PATIENCE,
    FEATURE_SET,
    LOG_LOSS_MIN_DELTA,
    MACRO_F1_MIN_DELTA,
    MAX_BOOSTING_ROUNDS,
    TARGET_TRIALS,
    TOP_TRIALS,
    TUNING_EXPERIMENT,
    WEIGHTING_MODE,
    BoosterFit,
    PreparedMatrices,
    predict_probabilities,
    prepare_matrices,
    train_booster,
)
from .search_space import suggest_parameters, validate_resolved_parameters


def optuna_storage_uri(project_root: Path | None = None) -> str:
    root = project_root or find_project_root()
    return f"sqlite:///{(root / 'ml' / 'optuna.db').resolve().as_posix()}"


def study_name(model_key: str, dataset_sha256: str) -> str:
    if model_key not in {"xgboost", "lightgbm"}:
        raise ValueError(f"Unknown tuning model: {model_key}")
    return f"cicids2017-{model_key}-all71-balanced-{dataset_sha256[:12]}"


def complete_trial_count(study: optuna.Study) -> int:
    return sum(trial.state == TrialState.COMPLETE for trial in study.trials)


def optimize_to_target(
    study: optuna.Study,
    objective: Callable[[optuna.Trial], float],
    target_trials: int,
    *,
    failure_allowance: int | None = None,
) -> tuple[int, int]:
    """Run only enough attempts to reach the requested successful total."""

    if target_trials < 1:
        raise ValueError("target_trials must be positive.")
    completed_before = complete_trial_count(study)
    if completed_before >= target_trials:
        return 0, completed_before
    allowance = (
        failure_allowance
        if failure_allowance is not None
        else max(5, target_trials // 2)
    )
    maximum_attempts = target_trials - completed_before + allowance
    attempts = 0
    while complete_trial_count(study) < target_trials and attempts < maximum_attempts:
        study.optimize(objective, n_trials=1, catch=(Exception,))
        attempts += 1
    return attempts, complete_trial_count(study)


def resolved_trial_parameters(trial: FrozenTrial) -> dict[str, object]:
    parameters = trial.user_attrs.get("resolved_parameters")
    if not isinstance(parameters, dict):
        raise ValueError(f"Trial {trial.number} has no resolved parameter record.")
    return parameters


def top_complete_trials(
    study: optuna.Study, count: int = TOP_TRIALS
) -> list[FrozenTrial]:
    complete = [trial for trial in study.trials if trial.state == TrialState.COMPLETE]
    return sorted(
        complete,
        key=lambda trial: (-float(trial.value), trial.number),
    )[:count]


def create_or_load_study(
    model_key: str,
    dataset_sha256: str,
    project_root: Path | None = None,
) -> optuna.Study:
    return optuna.create_study(
        study_name=study_name(model_key, dataset_sha256),
        storage=optuna_storage_uri(project_root),
        direction="maximize",
        sampler=TPESampler(seed=RANDOM_STATE, n_startup_trials=5),
        load_if_exists=True,
    )


def _trial_tags(
    model_key: str,
    data: ExperimentData,
    matrices: PreparedMatrices,
    trial_number: int,
    selected_study_name: str,
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
        "inference_device": "cuda" if model_key == "xgboost" else "cpu",
        "evaluation_stage": "inner_tuning_validation",
        "study_name": selected_study_name,
        "trial_number": str(trial_number),
        "dataset_version": data.contract.dataset_version,
        "inner_training_split_fingerprint": matrices.split.training_fingerprint,
        "inner_validation_split_fingerprint": matrices.split.stopping_fingerprint,
        "outer_fit_split_fingerprint": data.contract.fit_fingerprint,
        "outer_validation_split_fingerprint": data.contract.validation_fingerprint,
        "test_split_fingerprint": data.contract.test_fingerprint,
        "split_seed": str(RANDOM_STATE),
        "python_version": platform.python_version(),
    }


def _log_iteration_artifacts(history: pd.DataFrame) -> None:
    log_table_artifact(history, "iteration_history.csv", "tuning")
    log_line_figure(
        history,
        ["inner_validation_macro_f1"],
        "inner_validation_macro_f1.png",
        "Inner-validation macro F1 by boosting iteration",
        "tuning",
    )
    log_line_figure(
        history,
        ["training_monitor_log_loss", "inner_validation_log_loss"],
        "log_loss_history.png",
        "Training-monitor and inner-validation log loss",
        "tuning",
    )
    log_line_figure(
        history,
        ["iteration_time_seconds"],
        "iteration_duration.png",
        "Boosting iteration duration",
        "tuning",
    )


def run_search_trial(
    trial: optuna.Trial,
    model_key: str,
    matrices: PreparedMatrices,
    data: ExperimentData,
    selected_study_name: str,
    *,
    maximum_rounds: int = MAX_BOOSTING_ROUNDS,
    patience: int = EARLY_STOPPING_PATIENCE,
) -> float:
    resolved_params = suggest_parameters(trial, model_key)
    validate_resolved_parameters(model_key, resolved_params)
    run_name = f"tune__{model_key}__trial_{trial.number:04d}"
    tags = _trial_tags(model_key, data, matrices, trial.number, selected_study_name)
    fit: BoosterFit | None = None
    with mlflow.start_run(run_name=run_name, tags=tags) as active_run:
        mlflow.log_params(
            {
                "model_key": model_key,
                "feature_set": FEATURE_SET,
                "weighting_mode": WEIGHTING_MODE,
                "random_state": RANDOM_STATE,
                "maximum_boosting_rounds": maximum_rounds,
                "early_stopping_patience": patience,
                "macro_f1_min_delta": MACRO_F1_MIN_DELTA,
                "log_loss_min_delta": LOG_LOSS_MIN_DELTA,
                **resolved_params,
            }
        )
        try:
            fit = train_booster(
                model_key,
                resolved_params,
                matrices,
                maximum_rounds=maximum_rounds,
                patience=patience,
            )
            probabilities = predict_probabilities(
                model_key,
                fit.booster,
                matrices.X_stopping,
                fit.best_macro_iteration,
            )
            predictions = decode_labels(probabilities.argmax(axis=1))
            true_labels = decode_labels(matrices.y_stopping)
            metrics, report, raw_matrix, normalized_matrix = (
                calculate_metrics_and_diagnostics(true_labels, predictions)
            )
            if not np.isclose(metrics["macro_f1"], fit.best_macro_f1, atol=1e-8):
                raise AssertionError("Logged macro F1 differs from callback macro F1.")
            best_macro_row = fit.history.loc[fit.best_macro_iteration]
            metrics.update(
                {
                    "tuning_objective_macro_f1": fit.best_macro_f1,
                    "inner_validation_log_loss": float(
                        log_loss(
                            matrices.y_stopping,
                            probabilities,
                            labels=np.arange(len(LABEL_ORDER)),
                        )
                    ),
                    "training_monitor_log_loss": float(
                        best_macro_row["training_monitor_log_loss"]
                    ),
                    "best_validation_log_loss": fit.best_validation_log_loss,
                    "best_macro_iteration": float(fit.best_macro_iteration),
                    "best_loss_iteration": float(fit.best_loss_iteration),
                    "booster_training_time_seconds": fit.training_time_seconds,
                    "training_time_seconds": (
                        matrices.preprocessing_time_seconds
                        + fit.training_time_seconds
                    ),
                }
            )
            mlflow.log_metrics(metrics)
            _log_iteration_artifacts(fit.history)
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
                    "evaluation_stage": "inner_tuning_validation",
                    "inner_training_rows": len(matrices.X_training),
                    "inner_validation_rows": len(matrices.X_stopping),
                    "outer_validation_rows_not_evaluated": len(data.X_validation),
                    "test_rows_not_evaluated": len(data.X_test),
                    "best_macro_iteration": fit.best_macro_iteration,
                    "best_loss_iteration": fit.best_loss_iteration,
                    "training_device": tags["training_device"],
                },
            )
            trial.set_user_attr("resolved_parameters", resolved_params)
            trial.set_user_attr("best_macro_iteration", fit.best_macro_iteration)
            trial.set_user_attr("best_loss_iteration", fit.best_loss_iteration)
            trial.set_user_attr("best_validation_log_loss", fit.best_validation_log_loss)
            trial.set_user_attr("mlflow_run_id", active_run.info.run_id)
            return float(fit.best_macro_f1)
        finally:
            if fit is not None:
                del fit.booster
            gc.collect()


def run_search(
    data: ExperimentData,
    model_keys: Sequence[str],
    target_trials: int = TARGET_TRIALS,
) -> bool:
    matrices = prepare_matrices(
        data.X_fit, data.y_fit, data.feature_sets[FEATURE_SET]
    )
    setup_mlflow_experiment(TUNING_EXPERIMENT)
    complete = True
    for model_key in model_keys:
        study = create_or_load_study(model_key, data.contract.dataset_sha256)
        before = complete_trial_count(study)
        print(f"\n{model_key}: {before}/{target_trials} successful trials already stored.")
        attempts, completed = optimize_to_target(
            study,
            lambda trial, key=model_key: run_search_trial(
                trial, key, matrices, data, study.study_name
            ),
            target_trials,
        )
        print(
            f"{model_key}: attempted {attempts} new trial(s); "
            f"{completed}/{target_trials} successful."
        )
        if completed < target_trials:
            complete = False
    del matrices
    gc.collect()
    return complete
