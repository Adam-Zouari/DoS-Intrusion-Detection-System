from __future__ import annotations

import json
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import pytest

from ids_ml.data import LABEL_ORDER, DatasetContract, ExperimentData
from ids_ml.tree_tuning.cli import tuning_main
from ids_ml.tree_tuning.final_evaluation import (
    combine_development_partition,
    evaluate_frozen_final_model,
)
from ids_ml.tree_tuning.final_selection import (
    OUTER_VALIDATION_STAGE,
    build_frozen_recipe,
    select_best_tuned_xgboost_run,
    validate_frozen_recipe_against_source,
)
from ids_ml.tracking import setup_mlflow_experiment

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "subcommand", ["freeze-final", "evaluate-final", "final-report"]
)
def test_final_workflow_command_help_does_not_load_the_dataset(subcommand) -> None:
    with pytest.raises(SystemExit) as exit_info:
        tuning_main([subcommand, "--help"])
    assert exit_info.value.code == 0


def test_tuning_source_never_scores_or_predicts_on_protected_test() -> None:
    tuning_directory = (
        PROJECT_ROOT / "ml" / "src" / "ids_ml" / "tree_tuning"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(tuning_directory.glob("*.py"))
        if path.name != "final_evaluation.py"
    )
    assert "predict(data.X_test" not in source
    assert "predictor.predict(data.X_test" not in source
    assert "PCA" not in source

    selection_source = (tuning_directory / "final_selection.py").read_text(
        encoding="utf-8"
    )
    assert "load_experiment_data" not in selection_source
    assert ".X_test" not in selection_source

    final_source = (tuning_directory / "final_evaluation.py").read_text(
        encoding="utf-8"
    )
    assert final_source.count(".predict(data.X_test)") == 1
    assert "PCA" not in final_source


TUNED_XGBOOST_PARAMETERS = {
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.75,
    "reg_lambda": 1.0,
    "reg_alpha": 0.0,
    "max_depth": 6,
    "min_child_weight": 2.0,
    "gamma": 0.1,
}


def _log_synthetic_tuned_run(
    root: Path,
    contract: DatasetContract,
    trial_number: int,
    macro_f1: float,
    *,
    iterations: int = 500,
    dataset_version: str | None = None,
):
    from ids_ml.tree_tuning.training import VERIFICATION_EXPERIMENT

    setup_mlflow_experiment(VERIFICATION_EXPERIMENT, root)
    tags = {
        "model_key": "xgboost",
        "evaluation_stage": OUTER_VALIDATION_STAGE,
        "feature_set": "all_71",
        "weighting_mode": "balanced",
        "dataset_version": dataset_version or contract.dataset_version,
        "fit_split_fingerprint": contract.fit_fingerprint,
        "evaluation_split_fingerprint": contract.validation_fingerprint,
        "test_split_fingerprint": contract.test_fingerprint,
        "split_seed": "42",
        "source_trial_number": str(trial_number),
    }
    with mlflow.start_run(tags=tags) as active_run:
        mlflow.log_params(
            {
                "model_key": "xgboost",
                "source_trial_number": trial_number,
                "feature_set": "all_71",
                "weighting_mode": "balanced",
                "selected_boosting_iterations": iterations,
                **TUNED_XGBOOST_PARAMETERS,
            }
        )
        mlflow.log_metric("macro_f1", macro_f1)
        run_id = active_run.info.run_id
    return mlflow.MlflowClient().get_run(run_id)


def test_final_selection_uses_highest_full_precision_outer_macro_f1(
    tmp_path: Path,
) -> None:
    root = tmp_path
    (root / "ml").mkdir()
    contract = DatasetContract(dataset_sha256="synthetic")
    previous_uri = mlflow.get_tracking_uri()
    try:
        _log_synthetic_tuned_run(root, contract, 14, 0.972028000000001)
        expected = _log_synthetic_tuned_run(root, contract, 15, 0.972028000000002)
        _log_synthetic_tuned_run(root, contract, 16, 0.970000000000000)
        _log_synthetic_tuned_run(
            root,
            contract,
            99,
            0.999,
            dataset_version="sha256:different",
        )

        selected, leaderboard = select_best_tuned_xgboost_run(contract, root)
        assert selected.info.run_id == expected.info.run_id
        assert leaderboard["trial_number"].tolist() == [15, 14, 16]
        assert leaderboard.iloc[0]["macro_f1"] == 0.972028000000002
    finally:
        mlflow.end_run()
        mlflow.set_tracking_uri(previous_uri)


def test_frozen_recipe_must_match_its_mlflow_source(
    tmp_path: Path,
) -> None:
    root = tmp_path
    (root / "ml").mkdir()
    contract = DatasetContract(dataset_sha256="synthetic")
    features = ["Protocol", *[f"feature_{index}" for index in range(70)]]
    previous_uri = mlflow.get_tracking_uri()
    try:
        source = _log_synthetic_tuned_run(root, contract, 14, 0.972028)
        recipe = build_frozen_recipe(source, contract, features)
        validate_frozen_recipe_against_source(recipe, root)

        changed = json.loads(json.dumps(recipe))
        changed["model_recipe"]["parameters"]["max_depth"] = 10
        with pytest.raises(ValueError, match="no longer matches"):
            validate_frozen_recipe_against_source(changed, root)
    finally:
        mlflow.end_run()
        mlflow.set_tracking_uri(previous_uri)


def test_development_refit_partition_is_exact_80_percent_union() -> None:
    X_fit = pd.DataFrame({"Protocol": [0, 6]}, index=[3, 1])
    X_validation = pd.DataFrame({"Protocol": [17]}, index=[2])
    X_test = pd.DataFrame({"Protocol": [0]}, index=[9])
    data = ExperimentData(
        X_fit=X_fit,
        X_validation=X_validation,
        X_test=X_test,
        y_fit=pd.Series(["BENIGN", "Bot"], index=X_fit.index),
        y_validation=pd.Series(["DDoS"], index=X_validation.index),
        y_test=pd.Series(["BENIGN"], index=X_test.index),
        model_input_features=["Protocol"],
        feature_sets={"all_71": ["Protocol"], "reduced_64": ["Protocol"]},
        contract=DatasetContract(dataset_sha256="synthetic"),
    )
    X_development, y_development, fingerprint = combine_development_partition(data)
    assert X_development.index.tolist() == [1, 2, 3]
    assert y_development.index.tolist() == [1, 2, 3]
    assert len(fingerprint) == 64


class _SyntheticPreprocessor:
    def get_feature_names_out(self):
        return np.asarray([f"transformed_{index}" for index in range(73)])


class _SyntheticBooster:
    def save_model(self, path):
        Path(path).write_text("synthetic booster", encoding="utf-8")


class _SyntheticFinalPredictor:
    def __init__(self):
        self.preprocessor = _SyntheticPreprocessor()
        self.booster = _SyntheticBooster()

    def predict(self, X):
        indices = X["feature_0"].to_numpy(dtype=int)
        return np.asarray(LABEL_ORDER, dtype=object)[indices]

    def cleanup(self):
        self.booster = None


def test_final_evaluation_smoke_uses_development_only_and_cannot_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ids_ml.evaluation import TimingInputs
    from ids_ml.tree_tuning import final_evaluation as final_module

    root = tmp_path
    (root / "ml").mkdir()
    contract = DatasetContract(dataset_sha256="synthetic")
    features = ["Protocol", *[f"feature_{index}" for index in range(70)]]
    previous_uri = mlflow.get_tracking_uri()
    source = _log_synthetic_tuned_run(root, contract, 14, 0.972028)
    alternate_source = _log_synthetic_tuned_run(root, contract, 15, 0.970435)

    def frame(labels, start):
        rows = len(labels)
        values = np.zeros((rows, len(features)), dtype=float)
        result = pd.DataFrame(
            values,
            columns=features,
            index=np.arange(start, start + rows),
        )
        result["Protocol"] = np.resize([0, 6, 17], rows)
        result["feature_0"] = [LABEL_ORDER.index(label) for label in labels]
        return result

    fit_labels = [label for label in LABEL_ORDER for _ in range(2)]
    validation_labels = list(LABEL_ORDER)
    test_labels = list(LABEL_ORDER)
    X_fit = frame(fit_labels, 0)
    X_validation = frame(validation_labels, 100)
    X_test = frame(test_labels, 200)
    data = ExperimentData(
        X_fit=X_fit,
        X_validation=X_validation,
        X_test=X_test,
        y_fit=pd.Series(fit_labels, index=X_fit.index),
        y_validation=pd.Series(validation_labels, index=X_validation.index),
        y_test=pd.Series(test_labels, index=X_test.index),
        model_input_features=features,
        feature_sets={"all_71": features, "reduced_64": features[:64]},
        contract=contract,
    )
    recipe = build_frozen_recipe(source, contract, features)
    alternate_recipe = build_frozen_recipe(alternate_source, contract, features)
    spec_path = root / "ml" / "final_model_spec.json"
    spec_path.write_text(json.dumps(recipe, indent=2), encoding="utf-8")

    observed_training_indices = []

    def fake_fit(model_key, parameters, iterations, X_training, y_training, selected):
        observed_training_indices.extend(X_training.index.tolist())
        assert X_training.index.equals(y_training.index)
        assert set(X_training.index) == set(X_fit.index).union(X_validation.index)
        assert not set(X_training.index).intersection(X_test.index)
        return (
            _SyntheticFinalPredictor(),
            0.01,
            np.asarray([f"transformed_{index}" for index in range(73)]),
        )

    timing = TimingInputs(
        single_rows=(X_validation.iloc[[0]].copy(),),
        batch_rows=X_validation.copy(),
        fingerprint=contract.timing_fingerprint,
    )
    monkeypatch.setattr(final_module, "fit_fixed_predictor", fake_fit)
    monkeypatch.setattr(final_module, "make_timing_inputs", lambda X: timing)
    monkeypatch.setattr(
        final_module,
        "measure_predictor_speed",
        lambda predictor, inputs: {
            "latency_p50_ms": 1.0,
            "latency_p95_ms": 2.0,
            "latency_p99_ms": 3.0,
            "throughput_flows_per_second": 1000.0,
        },
    )
    monkeypatch.setattr(
        final_module,
        "importance_values",
        lambda predictor, names: np.zeros(len(names)),
    )

    try:
        result = evaluate_frozen_final_model(
            root, recipe=recipe, data=data
        )
        assert result["macro_f1"] == 1.0
        assert len(observed_training_indices) == len(X_fit) + len(X_validation)
        artifacts = {
            artifact.path
            for artifact in mlflow.MlflowClient().list_artifacts(result["run_id"])
        }
        assert {"selection", "evaluation", "diagnostics", "model"}.issubset(
            artifacts
        )
        with pytest.raises(RuntimeError, match="Repeating it is prohibited"):
            evaluate_frozen_final_model(root, recipe=alternate_recipe, data=data)
    finally:
        mlflow.end_run()
        mlflow.set_tracking_uri(previous_uri)


