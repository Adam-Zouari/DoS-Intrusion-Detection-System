"""Compare the original and tuned XGBoost across matched development splits."""

from __future__ import annotations

import gc
from collections.abc import Sequence

import mlflow
import pandas as pd

from ..data import (
    RANDOM_STATE,
    ExperimentData,
    find_project_root,
    make_development_split,
)
from ..reporting import filter_to_contract, query_screening_runs
from ..screening import ValidationPartition, run_validation_experiment
from ..experiment_specs import ExperimentSpec, specs_for_round
from ..tracking import configure_tracking, setup_mlflow_experiment
from ..tree_models import build_adapter
from .training import (
    FEATURE_SET,
    STABILITY_SEEDS,
    VERIFICATION_EXPERIMENT,
    WEIGHTING_MODE,
)

ORIGINAL_CONFIGURATION = "original_screening"
TUNED_CONFIGURATION = "tuned_optuna"


def original_xgboost_spec() -> ExperimentSpec:
    """Return the single source of truth for the original screening configuration."""

    matches = [
        spec
        for spec in specs_for_round("tree")
        if spec.model_key == "xgboost"
        and spec.feature_set == FEATURE_SET
        and spec.weighting_mode == WEIGHTING_MODE
    ]
    if len(matches) != 1:
        raise AssertionError("The original XGBoost screening contract is ambiguous.")
    return matches[0]


def _latest_per_seed(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "start_time" not in frame:
        frame = frame.assign(start_time=pd.NaT)
    return (
        frame.sort_values("start_time", ascending=False)
        .drop_duplicates("split_seed", keep="first")
        .sort_values("split_seed")
        .reset_index(drop=True)
    )


def _screening_seed_42_record(data: ExperimentData) -> dict[str, object] | None:
    configuration_key = original_xgboost_spec().configuration_key
    runs = filter_to_contract(
        query_screening_runs(["tree"]), data.contract.comparison_fields()
    )
    selected = runs.loc[
        runs["status"].eq("FINISHED")
        & runs["configuration_key"].eq(configuration_key)
        & runs["macro_f1"].notna()
    ].sort_values("start_time", ascending=False)
    if selected.empty:
        return None
    row = selected.iloc[0]
    return {
        "configuration": ORIGINAL_CONFIGURATION,
        "split_seed": RANDOM_STATE,
        "macro_f1": float(row["macro_f1"]),
        "accuracy_reference": float(row["accuracy_reference"]),
        "binary_attack_recall": float(row["binary_attack_recall"]),
        "run_id": str(row["run_id"]),
        "run_source": "existing_tree_screening",
    }


def _verification_runs(data: ExperimentData) -> pd.DataFrame:
    configure_tracking()
    experiment = mlflow.get_experiment_by_name(VERIFICATION_EXPERIMENT)
    if experiment is None:
        return pd.DataFrame()
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id], output_format="pandas"
    )
    model_key = runs.get("tags.model_key", pd.Series(index=runs.index, dtype=object))
    dataset_version = runs.get(
        "tags.dataset_version", pd.Series(index=runs.index, dtype=object)
    )
    test_fingerprint = runs.get(
        "tags.test_split_fingerprint", pd.Series(index=runs.index, dtype=object)
    )
    return runs.loc[
        runs["status"].eq("FINISHED")
        & model_key.eq("xgboost")
        & dataset_version.eq(data.contract.dataset_version)
        & test_fingerprint.eq(data.contract.test_fingerprint)
    ].copy()


def _existing_original_records(data: ExperimentData) -> pd.DataFrame:
    runs = _verification_runs(data)
    if runs.empty:
        return pd.DataFrame()
    configuration = runs.get(
        "tags.stability_configuration", pd.Series(index=runs.index, dtype=object)
    )
    selected = runs.loc[configuration.eq(ORIGINAL_CONFIGURATION)].copy()
    if selected.empty:
        return pd.DataFrame()
    records = pd.DataFrame(
        {
            "configuration": ORIGINAL_CONFIGURATION,
            "split_seed": pd.to_numeric(selected["tags.split_seed"]),
            "macro_f1": pd.to_numeric(selected["metrics.macro_f1"]),
            "accuracy_reference": pd.to_numeric(
                selected["metrics.accuracy_reference"]
            ),
            "binary_attack_recall": pd.to_numeric(
                selected["metrics.binary_attack_recall"]
            ),
            "run_id": selected["run_id"],
            "run_source": "original_comparison_run",
            "start_time": selected["start_time"],
        }
    )
    return _latest_per_seed(records)


def _tuned_records(data: ExperimentData) -> pd.DataFrame:
    runs = _verification_runs(data)
    if runs.empty:
        return pd.DataFrame()
    selected_for_stability = runs.get(
        "tags.selected_for_stability", pd.Series(index=runs.index, dtype=object)
    )
    selected_seed_42 = runs.loc[selected_for_stability.eq("true")].sort_values(
        "start_time", ascending=False
    )
    if selected_seed_42.empty:
        return pd.DataFrame()
    trial_number = str(selected_seed_42.iloc[0]["tags.source_trial_number"])
    source_trial = runs.get(
        "tags.source_trial_number", pd.Series(index=runs.index, dtype=object)
    )
    split_seed = pd.to_numeric(
        runs.get("tags.split_seed", pd.Series(index=runs.index, dtype=object)),
        errors="coerce",
    )
    selected = runs.loc[
        source_trial.astype(str).eq(trial_number) & split_seed.isin(STABILITY_SEEDS)
    ].copy()
    if selected.empty:
        return pd.DataFrame()
    records = pd.DataFrame(
        {
            "configuration": TUNED_CONFIGURATION,
            "split_seed": pd.to_numeric(selected["tags.split_seed"]),
            "macro_f1": pd.to_numeric(selected["metrics.macro_f1"]),
            "accuracy_reference": pd.to_numeric(
                selected["metrics.accuracy_reference"]
            ),
            "binary_attack_recall": pd.to_numeric(
                selected["metrics.binary_attack_recall"]
            ),
            "run_id": selected["run_id"],
            "run_source": f"optuna_trial_{trial_number}",
            "start_time": selected["start_time"],
        }
    )
    return _latest_per_seed(records)


def _run_original_fit(
    data: ExperimentData,
    split_seed: int,
    X_training: pd.DataFrame,
    y_training: pd.Series,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
    *,
    smoke: bool = False,
) -> dict[str, object]:
    spec = original_xgboost_spec()
    run_name = f"compare__xgboost__original__seed_{split_seed}"
    tags = {
        "stability_configuration": ORIGINAL_CONFIGURATION,
        "configuration_key": f"comparison:xgboost:{ORIGINAL_CONFIGURATION}:seed_{split_seed}",
        "model_random_state": str(RANDOM_STATE),
    }
    result = run_validation_experiment(
        spec,
        data,
        None,
        lambda: build_adapter(spec, data.feature_sets, smoke=smoke),
        extra_tags=tags,
        partition=ValidationPartition(
            X_training=X_training,
            y_training=y_training,
            X_evaluation=X_validation,
            y_evaluation=y_validation,
            split_seed=split_seed,
            evaluation_stage="development_split_stability",
        ),
        run_name=run_name,
    )
    return {
        "configuration": ORIGINAL_CONFIGURATION,
        "split_seed": split_seed,
        "macro_f1": float(result["macro_f1"]),
        "accuracy_reference": float(result["accuracy_reference"]),
        "binary_attack_recall": float(result["binary_attack_recall"]),
        "run_id": str(result["run_id"]),
        "run_source": "original_comparison_run",
    }


def _summaries(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()
    summary = (
        records.groupby("configuration")["macro_f1"]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
    )
    summary["range"] = summary["max"] - summary["min"]
    return summary


def _paired_comparison(
    original: pd.DataFrame, tuned: pd.DataFrame
) -> pd.DataFrame:
    if original.empty or tuned.empty:
        return pd.DataFrame()
    original_columns = original[
        ["split_seed", "macro_f1", "run_id"]
    ].rename(
        columns={
            "macro_f1": "original_macro_f1",
            "run_id": "original_run_id",
        }
    )
    tuned_columns = tuned[["split_seed", "macro_f1", "run_id"]].rename(
        columns={"macro_f1": "tuned_macro_f1", "run_id": "tuned_run_id"}
    )
    paired = original_columns.merge(tuned_columns, on="split_seed", how="inner")
    paired["macro_f1_difference_original_minus_tuned"] = (
        paired["original_macro_f1"] - paired["tuned_macro_f1"]
    )
    return paired.sort_values("split_seed").reset_index(drop=True)


def run_original_xgboost_comparison(
    data: ExperimentData, *, rerun: bool = False, seeds: Sequence[int] = STABILITY_SEEDS
) -> bool:
    """Compare original and tuned XGBoost on the same development splits."""

    requested_seeds = tuple(dict.fromkeys(int(seed) for seed in seeds))
    if requested_seeds != STABILITY_SEEDS:
        raise ValueError(f"Stability seeds must remain fixed at {STABILITY_SEEDS}.")

    setup_mlflow_experiment(VERIFICATION_EXPERIMENT)
    existing = _existing_original_records(data)
    records: list[dict[str, object]] = []
    if not rerun:
        screening_record = _screening_seed_42_record(data)
        if screening_record is not None:
            records.append(screening_record)
        records.extend(existing.to_dict("records"))
    existing_seeds = {int(record["split_seed"]) for record in records}

    for seed in requested_seeds:
        if seed in existing_seeds:
            print(f"Original XGBoost seed {seed}: reused completed run.")
            continue
        X_training, X_validation, y_training, y_validation = make_development_split(
            data, seed
        )
        result = _run_original_fit(
            data,
            seed,
            X_training,
            y_training,
            X_validation,
            y_validation,
        )
        records.append(result)
        print(f"Original XGBoost seed {seed}: macro F1 {result['macro_f1']:.6f}")
        if seed != RANDOM_STATE:
            del X_training, X_validation, y_training, y_validation
            gc.collect()

    original = _latest_per_seed(pd.DataFrame(records))
    missing = sorted(set(requested_seeds) - set(original["split_seed"].astype(int)))
    tuned = _tuned_records(data)
    combined = pd.concat([original, tuned], ignore_index=True)
    summary = _summaries(combined)
    paired = _paired_comparison(original, tuned)

    output = find_project_root() / "ml" / "reports" / "generated"
    output.mkdir(parents=True, exist_ok=True)
    original.to_csv(output / "xgboost_original_comparison_runs.csv", index=False)
    summary.to_csv(
        output / "xgboost_original_vs_tuned_comparison_summary.csv", index=False
    )
    paired.to_csv(output / "xgboost_original_vs_tuned_by_split.csv", index=False)

    print("\nOriginal-versus-tuned XGBoost comparison summary:")
    print(summary.to_string(index=False))
    if paired.empty:
        print("\nNo complete matched tuned comparison was found in MLflow.")
    else:
        print("\nPaired original-versus-tuned comparison:")
        print(paired.to_string(index=False))
    print(f"\nSaved generated reports under {output}")
    return not missing
