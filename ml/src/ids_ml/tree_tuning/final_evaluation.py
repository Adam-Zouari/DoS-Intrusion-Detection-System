"""One-time refit of the frozen XGBoost recipe and protected-test evaluation."""

from __future__ import annotations

import json
import platform
import tempfile
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
import sklearn
import xgboost

from ..data import (
    LABEL_ORDER,
    ExperimentData,
    find_project_root,
    index_fingerprint,
    load_dataset_contract,
    load_experiment_data,
)
from ..evaluation import (
    calculate_metrics_and_diagnostics,
    log_evaluation_artifacts,
    make_timing_inputs,
    measure_predictor_speed,
)
from ..tracking import configure_tracking, setup_mlflow_experiment
from ..tree_models import log_tree_importance
from .final_selection import (
    final_spec_path,
    read_frozen_recipe,
    validate_frozen_recipe_against_source,
    validate_frozen_recipe_structure,
)
from .verification import fit_fixed_predictor, importance_values

FINAL_EXPERIMENT = "cicids2017-final-test"


def combine_development_partition(
    data: ExperimentData,
) -> tuple[pd.DataFrame, pd.Series, str]:
    """Return all and only the original 64% fitting plus 16% validation rows."""

    if not data.X_fit.index.intersection(data.X_validation.index).empty:
        raise AssertionError("Fitting and validation rows overlap.")
    X_development = pd.concat([data.X_fit, data.X_validation]).sort_index()
    y_development = pd.concat([data.y_fit, data.y_validation]).sort_index()
    expected_indices = data.X_fit.index.union(data.X_validation.index).sort_values()
    if not X_development.index.equals(expected_indices):
        raise AssertionError("The development partition is not the exact 64% + 16% union.")
    if not X_development.index.equals(y_development.index):
        raise AssertionError("Development features and labels are misaligned.")
    if len(X_development) != len(data.X_fit) + len(data.X_validation):
        raise AssertionError("The development partition has an unexpected row count.")
    if not X_development.index.intersection(data.X_test.index).empty:
        raise AssertionError("Protected test rows leaked into development data.")
    return X_development, y_development, index_fingerprint(X_development.index)


def _validate_recipe_against_data(
    recipe: dict[str, object], data: ExperimentData
) -> None:
    validate_frozen_recipe_structure(recipe)
    frozen_contract = recipe["dataset_contract"]
    expected_contract = {
        "dataset_sha256": data.contract.dataset_sha256,
        "dataset_version": data.contract.dataset_version,
        "fit_split_fingerprint": data.contract.fit_fingerprint,
        "validation_split_fingerprint": data.contract.validation_fingerprint,
        "protected_test_fingerprint": data.contract.test_fingerprint,
        "timing_input_fingerprint": data.contract.timing_fingerprint,
    }
    if frozen_contract != expected_contract:
        raise ValueError("The frozen recipe does not match the current dataset/splits.")
    model = recipe["model_recipe"]
    if list(model["source_features"]) != data.feature_sets["all_71"]:
        raise ValueError("The frozen source-feature order has changed.")
    if list(model["label_order"]) != LABEL_ORDER:
        raise ValueError("The frozen target-label order has changed.")
    if model.get("xgboost_version") != xgboost.__version__:
        raise ValueError("The installed XGBoost version differs from the frozen recipe.")
    if model.get("scikit_learn_version") != sklearn.__version__:
        raise ValueError(
            "The installed scikit-learn version differs from the frozen recipe."
        )


def matching_successful_final_runs(
    recipe: dict[str, object], project_root: Path | None = None
) -> pd.DataFrame:
    """Find any completed final evaluation of this protected test partition."""

    configure_tracking(project_root)
    experiment = mlflow.get_experiment_by_name(FINAL_EXPERIMENT)
    if experiment is None:
        return pd.DataFrame()
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id], output_format="pandas"
    )
    if runs.empty:
        return runs
    test_fingerprint = runs.get(
        "tags.test_split_fingerprint", pd.Series(index=runs.index, dtype=object)
    )
    return runs.loc[
        runs["status"].eq("FINISHED")
        & test_fingerprint.eq(
            recipe["dataset_contract"]["protected_test_fingerprint"]
        )
    ].copy()


def final_evaluation_exists(
    recipe: dict[str, object], project_root: Path | None = None
) -> bool:
    return not matching_successful_final_runs(recipe, project_root).empty


def _log_frozen_recipe(recipe: dict[str, object], recipe_path: Path) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        selection_path = Path(temporary_directory) / "selected_source_run.json"
        selection_path.write_text(
            json.dumps(recipe["selection"], indent=2) + "\n", encoding="utf-8"
        )
        mlflow.log_artifact(selection_path, artifact_path="selection")
    mlflow.log_artifact(recipe_path, artifact_path="selection")


def _final_tags(
    recipe: dict[str, object], development_fingerprint: str
) -> dict[str, str]:
    selection = recipe["selection"]
    contract = recipe["dataset_contract"]
    model = recipe["model_recipe"]
    return {
        "model_key": "xgboost",
        "model_family": "XGBoost",
        "feature_set": str(model["feature_set"]),
        "weighting_mode": str(model["weighting_mode"]),
        "evaluation_stage": "protected_final_test",
        "source_tuned_run_id": str(selection["source_mlflow_run_id"]),
        "source_optuna_trial_number": str(
            selection["source_optuna_trial_number"]
        ),
        "dataset_version": str(contract["dataset_version"]),
        "development_split_fingerprint": development_fingerprint,
        "test_split_fingerprint": str(contract["protected_test_fingerprint"]),
        "timing_input_fingerprint": str(contract["timing_input_fingerprint"]),
        "training_device": "cuda",
        "inference_device": "cpu",
        "python_version": platform.python_version(),
        "xgboost_version": xgboost.__version__,
    }


def evaluate_frozen_final_model(
    project_root: Path | None = None,
    *,
    recipe: dict[str, object] | None = None,
    data: ExperimentData | None = None,
) -> dict[str, object]:
    """Refit on 80% and evaluate the protected 20% once."""

    root = project_root or find_project_root()
    recipe = recipe or read_frozen_recipe(root)
    validate_frozen_recipe_against_source(recipe, root)
    if final_evaluation_exists(recipe, root):
        raise RuntimeError(
            "A successful final evaluation already exists for this protected-test "
            "fingerprint. Repeating it is prohibited by default."
        )

    contract = load_dataset_contract(root) if data is None else data.contract
    data = data or load_experiment_data(root, contract=contract)
    _validate_recipe_against_data(recipe, data)
    X_development, y_development, development_fingerprint = (
        combine_development_partition(data)
    )
    model = recipe["model_recipe"]
    parameters = dict(model["parameters"])
    iteration_count = int(model["boosting_iterations"])
    selected_features = list(model["source_features"])

    model_directory = root / "ml" / "models"
    model_directory.mkdir(parents=True, exist_ok=True)
    source_run_id = str(recipe["selection"]["source_mlflow_run_id"])
    artifact_stem = f"xgboost_final_{source_run_id[:12]}"
    pipeline_path = model_directory / f"{artifact_stem}.joblib"
    booster_path = model_directory / f"{artifact_stem}.ubj"

    setup_mlflow_experiment(FINAL_EXPERIMENT, root)
    tags = _final_tags(recipe, development_fingerprint)
    predictor = None
    reloaded = None
    with mlflow.start_run(run_name=artifact_stem, tags=tags) as active_run:
        try:
            predictor, training_seconds, transformed_names = fit_fixed_predictor(
                "xgboost",
                parameters,
                iteration_count,
                X_development,
                y_development,
                selected_features,
            )
            if len(transformed_names) != int(model["transformed_feature_count"]):
                raise AssertionError(
                    "The fitted transformed schema differs from the frozen recipe."
                )
            if predictor.booster is None:
                raise RuntimeError("The fitted XGBoost booster is unavailable.")
            predictor.booster.save_model(booster_path)
            joblib.dump(predictor, pipeline_path, compress=3)
            reloaded = joblib.load(pipeline_path)

            verification_rows = data.X_validation.iloc[: min(1_024, len(data.X_validation))]
            if not np.array_equal(
                predictor.predict(verification_rows),
                reloaded.predict(verification_rows),
            ):
                raise AssertionError(
                    "Serialized pipeline predictions differ after reload."
                )
            predictor.cleanup()
            predictor = None

            predictions = reloaded.predict(data.X_test)
            metrics, report, raw_matrix, normalized_matrix = (
                calculate_metrics_and_diagnostics(data.y_test, predictions)
            )
            diagonal = np.diag(raw_matrix).astype(float)
            denominator = (
                2.0 * diagonal
                + raw_matrix.sum(axis=0)
                - diagonal
                + raw_matrix.sum(axis=1)
                - diagonal
            )
            macro_f1_from_matrix = float(
                np.divide(
                    2.0 * diagonal,
                    denominator,
                    out=np.zeros_like(diagonal),
                    where=denominator != 0,
                ).mean()
            )
            if not np.isclose(macro_f1_from_matrix, metrics["macro_f1"]):
                raise AssertionError("Final macro F1 does not match the confusion matrix.")

            speed = measure_predictor_speed(
                reloaded, make_timing_inputs(data.X_validation)
            )
            model_size_mib = pipeline_path.stat().st_size / (1024**2)
            logged_metrics = {
                **metrics,
                **speed,
                "training_time_seconds": float(training_seconds),
                "model_size_mib": float(model_size_mib),
                "selected_boosting_iterations": float(iteration_count),
            }
            mlflow.log_params(
                {
                    "model_key": "xgboost",
                    "source_tuned_run_id": source_run_id,
                    "source_optuna_trial_number": recipe["selection"][
                        "source_optuna_trial_number"
                    ],
                    "outer_validation_macro_f1": recipe["selection"][
                        "outer_validation_macro_f1"
                    ],
                    "feature_set": model["feature_set"],
                    "weighting_mode": model["weighting_mode"],
                    "boosting_iterations": iteration_count,
                    **parameters,
                }
            )
            mlflow.log_metrics(logged_metrics)
            log_evaluation_artifacts(
                report,
                raw_matrix,
                normalized_matrix,
                {
                    "dataset_sha256": data.contract.dataset_sha256,
                    "label_order": LABEL_ORDER,
                    "selected_source_features": selected_features,
                    "source_feature_count": len(selected_features),
                    "transformed_feature_count": len(transformed_names),
                    "evaluation_stage": "protected_final_test",
                    "source_tuned_run_id": source_run_id,
                    "development_rows": len(X_development),
                    "protected_test_rows": len(data.X_test),
                    "development_split_fingerprint": development_fingerprint,
                    "protected_test_fingerprint": data.contract.test_fingerprint,
                    "training_device": "cuda",
                    "inference_device": "cpu",
                    "serialization_reload_predictions_equal": True,
                },
            )
            log_tree_importance(
                transformed_names,
                importance_values(reloaded, transformed_names),
                "XGBoost final model",
            )
            _log_frozen_recipe(recipe, final_spec_path(root))
            mlflow.log_artifact(pipeline_path, artifact_path="model")
            mlflow.log_artifact(booster_path, artifact_path="model")

            result = {
                "run_id": active_run.info.run_id,
                "source_tuned_run_id": source_run_id,
                "source_optuna_trial_number": recipe["selection"][
                    "source_optuna_trial_number"
                ],
                "pipeline_path": str(pipeline_path),
                "booster_path": str(booster_path),
                **logged_metrics,
            }
            reports = root / "ml" / "reports" / "generated"
            reports.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([result]).to_csv(
                reports / "xgboost_final_test_summary.csv", index=False
            )
            print("\nProtected final-test result:")
            print(pd.DataFrame([result]).to_string(index=False))
            return result
        finally:
            if predictor is not None:
                predictor.cleanup()
            if reloaded is not None:
                reloaded.cleanup()


def show_final_report(project_root: Path | None = None) -> pd.DataFrame:
    """Print the frozen recipe and final result without loading the dataset."""

    root = project_root or find_project_root()
    recipe = read_frozen_recipe(root)
    validate_frozen_recipe_against_source(recipe, root)
    selection = recipe["selection"]
    model = recipe["model_recipe"]
    print("\nFrozen final model:")
    print(f"Source MLflow run: {selection['source_mlflow_run_id']}")
    print(f"Optuna trial: {selection['source_optuna_trial_number']}")
    print(f"Outer-validation macro F1: {selection['outer_validation_macro_f1']:.15f}")
    print(f"Boosting iterations: {model['boosting_iterations']}")
    print("Parameters:")
    print(json.dumps(model["parameters"], indent=2, sort_keys=True))

    runs = matching_successful_final_runs(recipe, root)
    if runs.empty:
        print("\nNo successful protected final-test run exists.")
        return runs
    latest = runs.sort_values("start_time", ascending=False).iloc[0]
    metric_columns = [
        "metrics.macro_f1",
        "metrics.accuracy_reference",
        "metrics.binary_attack_recall",
        "metrics.training_time_seconds",
        "metrics.latency_p50_ms",
        "metrics.latency_p95_ms",
        "metrics.latency_p99_ms",
        "metrics.throughput_flows_per_second",
        "metrics.model_size_mib",
    ]
    summary = pd.DataFrame(
        [
            {
                "run_id": latest["run_id"],
                **{
                    column.removeprefix("metrics."): latest.get(column, np.nan)
                    for column in metric_columns
                },
                "artifact_uri": latest["artifact_uri"],
            }
        ]
    )
    print("\nFinal metrics:")
    print(summary.to_string(index=False))
    client = mlflow.MlflowClient()
    try:
        report_path = client.download_artifacts(
            str(latest["run_id"]), "evaluation/per_class_report.csv"
        )
        print("\nPer-class metrics:")
        print(pd.read_csv(report_path).to_string(index=False))
    except Exception as error:
        print(f"\nPer-class artifact could not be read: {error}")
    print(f"\nArtifacts: {latest['artifact_uri']}")
    return summary
