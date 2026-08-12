from __future__ import annotations

import os
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
import pytest

from ids_ml.data import (
    LABEL_ORDER,
    DatasetContract,
    ExperimentData,
    make_inner_split,
)
from ids_ml.tree_models import build_tree_pipeline
from ids_ml.tree_tuning.cli import tuning_main
from ids_ml.tree_tuning.original_xgboost_comparison import (
    _paired_comparison,
    _run_original_fit,
    original_xgboost_spec,
)
from ids_ml.tree_tuning.search import optimize_to_target, top_complete_trials
from ids_ml.tree_tuning.search_space import (
    suggest_parameters,
    validate_resolved_parameters,
)
from ids_ml.tree_tuning.training import IterationMonitor, base_parameters

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("arguments", [["--help"], ["compare-original-xgboost", "--help"]])
def test_tree_tuning_command_help_does_not_load_the_dataset(arguments) -> None:
    with pytest.raises(SystemExit) as exit_info:
        tuning_main(arguments)
    assert exit_info.value.code == 0


def test_original_xgboost_comparison_uses_exact_screening_configuration() -> None:
    spec = original_xgboost_spec()
    assert spec.configuration_key == "tree:xgboost:all_71:balanced"
    feature_sets = {
        "all_71": ["Protocol", *[f"feature_{index}" for index in range(70)]],
        "reduced_64": [],
    }
    classifier = build_tree_pipeline(spec, feature_sets).named_steps["classifier"]
    assert classifier.n_estimators == 200
    assert classifier.max_depth == 8
    assert classifier.learning_rate == 0.1
    assert classifier.subsample == 0.8
    assert classifier.colsample_bytree == 0.8
    assert classifier.reg_lambda == 1.0
    assert classifier.tree_method == "hist"
    assert classifier.random_state == 42


def test_original_and_tuned_comparison_is_paired_by_split_seed() -> None:
    original = pd.DataFrame(
        {
            "split_seed": [42, 123, 2025],
            "macro_f1": [0.97, 0.96, 0.95],
            "run_id": ["o42", "o123", "o2025"],
        }
    )
    tuned = pd.DataFrame(
        {
            "split_seed": [2025, 42, 123],
            "macro_f1": [0.94, 0.965, 0.955],
            "run_id": ["t2025", "t42", "t123"],
        }
    )
    paired = _paired_comparison(original, tuned)
    assert paired["split_seed"].tolist() == [42, 123, 2025]
    assert np.allclose(
        paired["macro_f1_difference_original_minus_tuned"],
        [0.005, 0.005, 0.01],
    )


def test_original_xgboost_comparison_smoke_fit_logs_shared_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature_names = ["Protocol", *[f"feature_{index}" for index in range(70)]]
    generator = np.random.default_rng(42)

    def features(rows: int, index_start: int) -> pd.DataFrame:
        frame = pd.DataFrame(
            generator.normal(size=(rows, len(feature_names))),
            columns=feature_names,
            index=np.arange(index_start, index_start + rows),
        )
        frame["Protocol"] = np.resize(np.asarray([0, 6, 17]), rows)
        return frame

    X_training = features(45, 0)
    y_training = pd.Series(np.repeat(LABEL_ORDER, 3), index=X_training.index)
    X_validation = features(15, 100)
    y_validation = pd.Series(LABEL_ORDER, index=X_validation.index)
    X_test = features(15, 200)
    y_test = pd.Series(LABEL_ORDER, index=X_test.index)
    data = ExperimentData(
        X_fit=X_training,
        X_validation=X_validation,
        X_test=X_test,
        y_fit=y_training,
        y_validation=y_validation,
        y_test=y_test,
        model_input_features=feature_names,
        feature_sets={"all_71": feature_names, "reduced_64": feature_names[:64]},
        contract=DatasetContract(dataset_sha256="synthetic"),
    )

    previous_uri = mlflow.get_tracking_uri()
    previous_file_store_setting = os.environ.get("MLFLOW_ALLOW_FILE_STORE")
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
    tracking_directory = tmp_path / "tracking"
    mlflow.set_tracking_uri(tracking_directory.resolve().as_uri())
    mlflow.set_experiment("original-xgboost-comparison-smoke")
    try:
        result = _run_original_fit(
            data,
            42,
            X_training,
            y_training,
            X_validation,
            y_validation,
            smoke=True,
        )
        artifacts = {
            artifact.path
            for artifact in mlflow.MlflowClient().list_artifacts(str(result["run_id"]))
        }
        assert {"diagnostics", "evaluation"}.issubset(artifacts)
        assert np.isfinite(float(result["macro_f1"]))
    finally:
        mlflow.end_run()
        mlflow.set_tracking_uri(previous_uri)
        if previous_file_store_setting is None:
            monkeypatch.delenv("MLFLOW_ALLOW_FILE_STORE", raising=False)
        else:
            monkeypatch.setenv(
                "MLFLOW_ALLOW_FILE_STORE", previous_file_store_setting
            )


def test_tuning_inner_split_is_deterministic_and_class_preserving() -> None:
    labels = pd.Series(
        np.repeat(LABEL_ORDER, 20), index=np.arange(10_000, 10_300)
    )
    first = make_inner_split(labels)
    second = make_inner_split(labels)
    assert np.array_equal(first.training_positions, second.training_positions)
    assert np.array_equal(first.stopping_positions, second.stopping_positions)
    assert first.training_fingerprint == second.training_fingerprint
    assert first.stopping_fingerprint == second.stopping_fingerprint
    assert set(labels.iloc[first.training_positions]) == set(LABEL_ORDER)
    assert set(labels.iloc[first.stopping_positions]) == set(LABEL_ORDER)


def test_tuning_search_spaces_resolve_valid_conditional_parameters() -> None:
    common = {
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.75,
        "reg_lambda": 1.0,
        "reg_alpha_mode": "zero",
    }
    xgboost_params = suggest_parameters(
        optuna.trial.FixedTrial(
            {
                **common,
                "max_depth": 8,
                "min_child_weight": 3.0,
                "gamma": 0.2,
            }
        ),
        "xgboost",
    )
    lightgbm_params = suggest_parameters(
        optuna.trial.FixedTrial(
            {
                **common,
                "max_depth": 6,
                "num_leaves_depth_6": 63,
                "min_child_samples": 50,
                "min_split_gain": 0.1,
            }
        ),
        "lightgbm",
    )
    validate_resolved_parameters("xgboost", xgboost_params)
    validate_resolved_parameters("lightgbm", lightgbm_params)
    assert lightgbm_params["num_leaves"] <= 2 ** lightgbm_params["max_depth"]
    assert base_parameters("xgboost")["device"] == "cuda"
    assert base_parameters("lightgbm")["device_type"] == "cpu"


def test_tuning_target_counts_only_successful_trials_and_resumes() -> None:
    study = optuna.create_study(direction="maximize")

    def objective(trial):
        return float(trial.number)

    attempts, completed = optimize_to_target(study, objective, 2)
    assert (attempts, completed) == (2, 2)
    attempts, completed = optimize_to_target(study, objective, 2)
    assert (attempts, completed) == (0, 2)
    attempts, completed = optimize_to_target(study, objective, 3)
    assert (attempts, completed) == (1, 3)
    assert [trial.number for trial in top_complete_trials(study, 2)] == [2, 1]


def test_combined_early_stopping_keeps_absolute_best_iterations() -> None:
    monitor = IterationMonitor(patience=2, macro_min_delta=0.01, loss_min_delta=0.01)
    assert not monitor.record(0, 1.0, 1.0, 0.50)
    assert not monitor.record(1, 0.9, 0.995, 0.505)
    assert monitor.record(2, 0.8, 0.994, 0.506)
    assert monitor.best_macro_iteration == 3
    assert monitor.best_loss_iteration == 3
    assert list(monitor.history().columns) == [
        "training_monitor_log_loss",
        "inner_validation_log_loss",
        "inner_validation_macro_f1",
        "iteration_time_seconds",
    ]


