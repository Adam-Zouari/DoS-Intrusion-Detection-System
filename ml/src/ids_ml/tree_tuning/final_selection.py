"""Select the best tuned XGBoost validation run and freeze its recipe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import sklearn
import xgboost

from ..data import (
    EXPECTED_PROTOCOL_VALUES,
    LABEL_ORDER,
    RANDOM_STATE,
    DatasetContract,
    find_project_root,
    load_dataset_contract,
    model_input_features_from_schema,
)
from ..tracking import configure_tracking
from .training import FEATURE_SET, VERIFICATION_EXPERIMENT, WEIGHTING_MODE
from .search_space import validate_resolved_parameters

FINAL_SPEC_SCHEMA_VERSION = 1
FINAL_SPEC_FILENAME = "final_model_spec.json"
OUTER_VALIDATION_STAGE = "outer_validation_top_trial"

XGBOOST_PARAMETER_TYPES = {
    "learning_rate": float,
    "subsample": float,
    "colsample_bytree": float,
    "reg_lambda": float,
    "reg_alpha": float,
    "max_depth": int,
    "min_child_weight": float,
    "gamma": float,
}


def final_spec_path(project_root: Path | None = None) -> Path:
    return (project_root or find_project_root()) / "ml" / FINAL_SPEC_FILENAME


def _value(mapping: dict[str, str], name: str, converter: type) -> object:
    try:
        return converter(mapping[name])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"The selected MLflow run has invalid {name!r}.") from error


def _run_trial_number(run: Any) -> int:
    value = run.data.tags.get(
        "source_trial_number", run.data.params.get("source_trial_number")
    )
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"MLflow run {run.info.run_id} has no valid Optuna trial number."
        ) from error


def _resolved_parameters(run: Any) -> dict[str, object]:
    parameters = {
        name: _value(run.data.params, name, converter)
        for name, converter in XGBOOST_PARAMETER_TYPES.items()
    }
    validate_resolved_parameters("xgboost", parameters)
    return parameters


def _selected_iterations(run: Any) -> int:
    iterations = int(
        _value(run.data.params, "selected_boosting_iterations", int)
    )
    if iterations < 1:
        raise ValueError("The selected boosting iteration count must be positive.")
    return iterations


def _validate_source_run(run: Any, contract: DatasetContract) -> None:
    tags = run.data.tags
    parameters = run.data.params
    if run.info.status != "FINISHED":
        raise ValueError("The selected MLflow source run did not finish successfully.")
    if tags.get("model_key", parameters.get("model_key")) != "xgboost":
        raise ValueError("The selected MLflow source run is not XGBoost.")
    if tags.get("evaluation_stage") != OUTER_VALIDATION_STAGE:
        raise ValueError("The selected run is not an outer-validation result.")
    if tags.get("feature_set", parameters.get("feature_set")) != FEATURE_SET:
        raise ValueError("The selected run does not use all_71.")
    if tags.get("weighting_mode", parameters.get("weighting_mode")) != WEIGHTING_MODE:
        raise ValueError("The selected run does not use balanced training.")
    expected_tags = {
        "dataset_version": contract.dataset_version,
        "fit_split_fingerprint": contract.fit_fingerprint,
        "evaluation_split_fingerprint": contract.validation_fingerprint,
        "test_split_fingerprint": contract.test_fingerprint,
        "split_seed": str(RANDOM_STATE),
    }
    mismatches = {
        name: (tags.get(name), expected)
        for name, expected in expected_tags.items()
        if tags.get(name) != expected
    }
    if mismatches:
        raise ValueError(
            f"The selected MLflow run has mismatched dataset/split tags: {mismatches}"
        )
    macro_f1 = run.data.metrics.get("macro_f1")
    if macro_f1 is None or not np.isfinite(float(macro_f1)):
        raise ValueError("The selected MLflow run has no finite macro F1.")
    _run_trial_number(run)
    _resolved_parameters(run)
    _selected_iterations(run)


def _verification_experiment() -> Any:
    experiment = mlflow.get_experiment_by_name(VERIFICATION_EXPERIMENT)
    if experiment is None:
        raise RuntimeError(
            f"MLflow experiment {VERIFICATION_EXPERIMENT!r} does not exist."
        )
    return experiment


def tuned_xgboost_outer_validation_runs(
    contract: DatasetContract,
    project_root: Path | None = None,
) -> list[Any]:
    """Return every compatible successful tuned XGBoost outer-validation run."""

    configure_tracking(project_root)
    experiment = _verification_experiment()
    raw = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id], output_format="pandas"
    )
    if raw.empty:
        return []
    model = raw.get("tags.model_key", pd.Series(index=raw.index, dtype=object))
    stage = raw.get(
        "tags.evaluation_stage", pd.Series(index=raw.index, dtype=object)
    )
    matching_ids = raw.loc[
        raw["status"].eq("FINISHED")
        & model.eq("xgboost")
        & stage.eq(OUTER_VALIDATION_STAGE),
        "run_id",
    ]
    client = mlflow.MlflowClient()
    runs = [client.get_run(str(run_id)) for run_id in matching_ids]
    compatible = []
    for run in runs:
        try:
            _validate_source_run(run, contract)
        except ValueError:
            continue
        compatible.append(run)
    return compatible


def select_best_tuned_xgboost_run(
    contract: DatasetContract,
    project_root: Path | None = None,
) -> tuple[Any, pd.DataFrame]:
    """Select the compatible run with the highest full-precision macro F1."""

    runs = tuned_xgboost_outer_validation_runs(contract, project_root)
    if not runs:
        raise RuntimeError(
            "No successful tuned XGBoost outer-validation runs match the current "
            "dataset and split fingerprints."
        )
    records = pd.DataFrame(
        [
            {
                "run_id": run.info.run_id,
                "trial_number": _run_trial_number(run),
                "macro_f1": float(run.data.metrics["macro_f1"]),
                "boosting_iterations": _selected_iterations(run),
                "start_time_ms": int(run.info.start_time or 0),
            }
            for run in runs
        ]
    )
    best_index = records["macro_f1"].idxmax()
    best_run_id = str(records.loc[best_index, "run_id"])
    selected = next(run for run in runs if run.info.run_id == best_run_id)
    leaderboard = records.sort_values(
        ["macro_f1", "start_time_ms"], ascending=[False, False]
    ).reset_index(drop=True)
    leaderboard.insert(0, "rank", np.arange(1, len(leaderboard) + 1, dtype=int))
    return selected, leaderboard


def build_frozen_recipe(
    source_run: Any,
    contract: DatasetContract,
    model_input_features: list[str],
) -> dict[str, object]:
    _validate_source_run(source_run, contract)
    if len(model_input_features) != 71 or "Protocol" not in model_input_features:
        raise ValueError("The frozen source-feature schema must contain 71 features.")
    return {
        "schema_version": FINAL_SPEC_SCHEMA_VERSION,
        "selection": {
            "source_mlflow_experiment": VERIFICATION_EXPERIMENT,
            "source_mlflow_run_id": str(source_run.info.run_id),
            "source_optuna_trial_number": _run_trial_number(source_run),
            "selection_metric": "macro_f1",
            "outer_validation_macro_f1": float(
                source_run.data.metrics["macro_f1"]
            ),
        },
        "dataset_contract": {
            "dataset_sha256": contract.dataset_sha256,
            "dataset_version": contract.dataset_version,
            "fit_split_fingerprint": contract.fit_fingerprint,
            "validation_split_fingerprint": contract.validation_fingerprint,
            "protected_test_fingerprint": contract.test_fingerprint,
            "timing_input_fingerprint": contract.timing_fingerprint,
        },
        "model_recipe": {
            "model_key": "xgboost",
            "feature_set": FEATURE_SET,
            "source_features": model_input_features,
            "source_feature_count": 71,
            "protocol_encoding": "one_hot",
            "protocol_categories": EXPECTED_PROTOCOL_VALUES,
            "transformed_feature_count": 73,
            "numeric_dtype": "float32",
            "weighting_mode": WEIGHTING_MODE,
            "weighting_mechanism": "balanced_sample_weight",
            "parameters": _resolved_parameters(source_run),
            "boosting_iterations": _selected_iterations(source_run),
            "model_random_state": RANDOM_STATE,
            "training_device": "cuda",
            "inference_device": "cpu",
            "xgboost_version": xgboost.__version__,
            "scikit_learn_version": sklearn.__version__,
            "label_order": LABEL_ORDER,
        },
    }


def validate_frozen_recipe_structure(recipe: dict[str, object]) -> None:
    if recipe.get("schema_version") != FINAL_SPEC_SCHEMA_VERSION:
        raise ValueError("Unsupported final-model recipe schema version.")
    selection = recipe.get("selection")
    contract = recipe.get("dataset_contract")
    model = recipe.get("model_recipe")
    if not all(isinstance(value, dict) for value in (selection, contract, model)):
        raise ValueError("The frozen recipe is missing required sections.")
    if selection.get("selection_metric") != "macro_f1":
        raise ValueError("The frozen recipe was not selected by macro F1.")
    if not selection.get("source_mlflow_run_id"):
        raise ValueError("The frozen recipe has no source MLflow run ID.")
    features = model.get("source_features")
    if (
        model.get("model_key") != "xgboost"
        or model.get("feature_set") != FEATURE_SET
        or model.get("weighting_mode") != WEIGHTING_MODE
        or not isinstance(features, list)
        or len(features) != 71
        or len(set(features)) != 71
        or "Protocol" not in features
    ):
        raise ValueError("The frozen XGBoost feature/weighting recipe is invalid.")
    if (
        model.get("protocol_encoding") != "one_hot"
        or model.get("protocol_categories") != EXPECTED_PROTOCOL_VALUES
        or model.get("transformed_feature_count") != 73
        or model.get("numeric_dtype") != "float32"
    ):
        raise ValueError("The frozen preprocessing recipe is invalid.")
    if model.get("label_order") != LABEL_ORDER:
        raise ValueError("The frozen label order is invalid.")
    validate_resolved_parameters("xgboost", dict(model["parameters"]))
    if int(model.get("boosting_iterations", 0)) < 1:
        raise ValueError("The frozen boosting iteration count is invalid.")


def _contract_from_recipe(recipe: dict[str, object]) -> DatasetContract:
    values = recipe["dataset_contract"]
    return DatasetContract(
        dataset_sha256=str(values["dataset_sha256"]),
        fit_fingerprint=str(values["fit_split_fingerprint"]),
        validation_fingerprint=str(values["validation_split_fingerprint"]),
        test_fingerprint=str(values["protected_test_fingerprint"]),
        timing_fingerprint=str(values["timing_input_fingerprint"]),
    )


def validate_frozen_recipe_against_source(
    recipe: dict[str, object], project_root: Path | None = None
) -> None:
    """Confirm the frozen values still equal their selected MLflow source run."""

    validate_frozen_recipe_structure(recipe)
    configure_tracking(project_root)
    experiment = _verification_experiment()
    run_id = str(recipe["selection"]["source_mlflow_run_id"])
    try:
        source_run = mlflow.MlflowClient().get_run(run_id)
    except Exception as error:
        raise ValueError(f"The source MLflow run {run_id!r} cannot be loaded.") from error
    if str(source_run.info.experiment_id) != str(experiment.experiment_id):
        raise ValueError("The frozen source run belongs to a different experiment.")
    contract = _contract_from_recipe(recipe)
    _validate_source_run(source_run, contract)
    expected = build_frozen_recipe(
        source_run,
        contract,
        list(recipe["model_recipe"]["source_features"]),
    )
    if recipe != expected:
        raise ValueError("The frozen JSON recipe no longer matches its MLflow source run.")


def read_frozen_recipe(project_root: Path | None = None) -> dict[str, object]:
    path = final_spec_path(project_root)
    if not path.exists():
        raise FileNotFoundError(
            f"No frozen final recipe exists at {path}. Run freeze-final first."
        )
    recipe = json.loads(path.read_text(encoding="utf-8"))
    validate_frozen_recipe_structure(recipe)
    return recipe


def freeze_final_model(project_root: Path | None = None) -> dict[str, object]:
    """Select the best tuned outer-validation run and freeze its exact recipe."""

    root = project_root or find_project_root()
    contract = load_dataset_contract(root)
    features = model_input_features_from_schema(root)
    source_run, leaderboard = select_best_tuned_xgboost_run(contract, root)
    recipe = build_frozen_recipe(source_run, contract, features)
    validate_frozen_recipe_against_source(recipe, root)

    path = final_spec_path(root)
    path.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    reports = root / "ml" / "reports" / "generated"
    reports.mkdir(parents=True, exist_ok=True)
    leaderboard.to_csv(reports / "xgboost_tuned_outer_validation.csv", index=False)

    print("\nTuned XGBoost outer-validation runs:")
    print(leaderboard.to_string(index=False))
    print(
        f"\nSelected trial {recipe['selection']['source_optuna_trial_number']} "
        f"with macro F1 {recipe['selection']['outer_validation_macro_f1']:.15f}."
    )
    print(f"Frozen recipe: {path}")
    return recipe
