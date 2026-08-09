"""Programmatic MLflow queries and comparison tables for screening runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import mlflow
import numpy as np
import pandas as pd

from .data import COMPARISON_CONTRACT_FIELDS, find_project_root
from .specs import (
    FEATURE_SETS,
    ROUND_EXPERIMENTS,
    WEIGHTING_MODES,
    expected_configuration_keys,
    make_configuration_key,
    models_for_candidate_role,
    validate_round_filter,
)
from .tracking import configure_tracking
CONTRACT_COLUMNS = list(COMPARISON_CONTRACT_FIELDS)
LEADERBOARD_COLUMNS = [
    "screening_round",
    "experiment_name",
    "run_id",
    "run_name",
    "model_key",
    "model_family",
    "weighting_mode",
    "feature_set",
    "source_feature_count",
    "transformed_feature_count",
    "macro_f1",
    "accuracy_reference",
    "binary_attack_recall",
    "training_time_seconds",
    "latency_p50_ms",
    "latency_p95_ms",
    "latency_p99_ms",
    "throughput_flows_per_second",
    "selected_epochs",
    "training_device",
    "start_time",
    "configuration_key",
]


@dataclass
class ScreeningReport:
    selected_rounds: tuple[str, ...]
    contract: dict[str, str]
    available_contracts: pd.DataFrame
    matching_runs: pd.DataFrame
    leaderboard: pd.DataFrame
    coverage: pd.DataFrame
    failed_runs: pd.DataFrame
    duplicate_runs: pd.DataFrame


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame:
        return frame[name]
    return pd.Series(index=frame.index, dtype=object)


def _coalesce(frame: pd.DataFrame, *names: str) -> pd.Series:
    result = pd.Series(index=frame.index, dtype=object)
    for name in names:
        candidate = _column(frame, name)
        missing = result.isna()
        result.loc[missing] = candidate.loc[missing]
    return result


def normalize_runs(raw_runs: pd.DataFrame) -> pd.DataFrame:
    if raw_runs.empty:
        return pd.DataFrame(columns=LEADERBOARD_COLUMNS + CONTRACT_COLUMNS + ["status"])

    normalized = pd.DataFrame(index=raw_runs.index)
    passthrough = [
        "run_id",
        "experiment_id",
        "status",
        "start_time",
        "end_time",
        "artifact_uri",
    ]
    for name in passthrough:
        normalized[name] = _column(raw_runs, name)
    normalized["experiment_name"] = _column(raw_runs, "experiment_name")
    round_by_experiment = {
        experiment_name: round_name
        for round_name, experiment_name in ROUND_EXPERIMENTS.items()
    }
    normalized["screening_round"] = _coalesce(
        raw_runs, "tags.screening_round"
    ).fillna(normalized["experiment_name"].map(round_by_experiment))
    normalized["run_name"] = _coalesce(raw_runs, "tags.mlflow.runName")
    normalized["model_key"] = _coalesce(
        raw_runs, "tags.model_key", "params.model_key"
    )
    normalized["model_family"] = _coalesce(raw_runs, "tags.model_family")
    normalized["weighting_mode"] = _coalesce(
        raw_runs, "tags.weighting_mode", "params.weighting_mode"
    )
    normalized["feature_set"] = _coalesce(
        raw_runs, "tags.feature_set", "params.feature_set"
    )
    normalized["source_feature_count"] = pd.to_numeric(
        _coalesce(raw_runs, "tags.source_feature_count", "params.source_feature_count"),
        errors="coerce",
    )
    normalized["transformed_feature_count"] = pd.to_numeric(
        _coalesce(
            raw_runs,
            "tags.transformed_feature_count",
            "tags.expected_transformed_feature_count",
            "params.transformed_feature_count",
            "params.expected_transformed_feature_count",
        ),
        errors="coerce",
    )
    normalized["training_device"] = _coalesce(raw_runs, "tags.training_device")
    normalized["evaluation_stage"] = _coalesce(raw_runs, "tags.evaluation_stage")
    normalized["run_group_id"] = _coalesce(raw_runs, "tags.run_group_id")

    for name in CONTRACT_COLUMNS:
        normalized[name] = _coalesce(raw_runs, f"tags.{name}")
    for name in [
        "macro_f1",
        "accuracy_reference",
        "binary_attack_recall",
        "training_time_seconds",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "throughput_flows_per_second",
        "selected_epochs",
    ]:
        normalized[name] = pd.to_numeric(_column(raw_runs, f"metrics.{name}"), errors="coerce")

    tagged_key = _coalesce(raw_runs, "tags.configuration_key")
    computed_key = pd.Series(index=normalized.index, dtype=object)
    required = ["screening_round", "model_key", "feature_set", "weighting_mode"]
    complete = normalized[required].notna().all(axis=1)
    computed_key.loc[complete] = normalized.loc[complete, required].apply(
        lambda row: make_configuration_key(
            str(row["screening_round"]),
            str(row["model_key"]),
            str(row["feature_set"]),
            str(row["weighting_mode"]),
        ),
        axis=1,
    )
    normalized["configuration_key"] = tagged_key.fillna(computed_key)
    return normalized.reset_index(drop=True)


def query_screening_runs(
    round_filter: Iterable[str] | str | None = None,
    project_root: Path | None = None,
) -> pd.DataFrame:
    rounds = validate_round_filter(round_filter)
    configure_tracking(project_root)
    experiments = []
    for round_name in rounds:
        experiment = mlflow.get_experiment_by_name(ROUND_EXPERIMENTS[round_name])
        if experiment is not None:
            experiments.append(experiment)
    if not experiments:
        return normalize_runs(pd.DataFrame())
    raw_runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id for experiment in experiments],
        output_format="pandas",
    )
    experiment_name_by_id = {
        str(experiment.experiment_id): experiment.name for experiment in experiments
    }
    raw_runs["experiment_name"] = raw_runs["experiment_id"].astype(str).map(
        experiment_name_by_id
    )
    return normalize_runs(raw_runs)


def filter_to_contract(
    runs: pd.DataFrame, contract: dict[str, str]
) -> pd.DataFrame:
    matching = runs.copy()
    for column, value in contract.items():
        matching = matching.loc[matching[column] == value]
    return matching.copy()


def summarize_contracts(runs: pd.DataFrame) -> pd.DataFrame:
    """Rank compatible run contracts by coverage, then recency."""
    successful = runs.loc[
        runs["status"].eq("FINISHED")
        & runs["macro_f1"].notna()
        & runs["configuration_key"].notna()
        & runs[CONTRACT_COLUMNS].notna().all(axis=1)
    ]
    if successful.empty:
        return pd.DataFrame(
            columns=CONTRACT_COLUMNS
            + ["successful_configurations", "successful_runs", "latest_run"]
        )
    summary = (
        successful.groupby(CONTRACT_COLUMNS, dropna=False)
        .agg(
            successful_configurations=("configuration_key", "nunique"),
            successful_runs=("run_id", "size"),
            latest_run=("start_time", "max"),
        )
        .reset_index()
        .sort_values(
            ["successful_configurations", "latest_run"],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )
    return summary


def _select_contract(
    runs: pd.DataFrame, dataset_version: str | None = None
) -> tuple[dict[str, str], pd.DataFrame]:
    candidates = runs
    if dataset_version is not None:
        candidates = candidates.loc[candidates["dataset_version"].eq(dataset_version)]
    available = summarize_contracts(candidates)
    if available.empty:
        return {}, available
    reference = available.iloc[0]
    return {column: str(reference[column]) for column in CONTRACT_COLUMNS}, available


def latest_successful_runs(runs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    successful = runs.loc[
        runs["status"].eq("FINISHED")
        & runs["macro_f1"].notna()
        & runs["configuration_key"].notna()
    ].sort_values("start_time", ascending=False)
    counts = successful.groupby("configuration_key").size()
    duplicates = (
        counts.loc[counts > 1]
        .rename("successful_run_count")
        .reset_index()
    )
    latest = successful.drop_duplicates("configuration_key", keep="first")
    return latest, duplicates


def build_screening_report(
    round_filter: Iterable[str] | str | None = None,
    project_root: Path | None = None,
    contract: dict[str, str] | None = None,
    dataset_version: str | None = None,
) -> ScreeningReport:
    if contract is not None and dataset_version is not None:
        raise ValueError("Supply either contract or dataset_version, not both.")
    selected_rounds = validate_round_filter(round_filter)
    runs = query_screening_runs(selected_rounds, project_root)
    inferred_contract, available_contracts = _select_contract(runs, dataset_version)
    selected_contract = contract if contract is not None else inferred_contract
    if contract is not None:
        available_contracts = summarize_contracts(runs)
    matching = filter_to_contract(runs, selected_contract) if selected_contract else runs
    latest, duplicates = latest_successful_runs(matching)
    leaderboard = latest.sort_values("macro_f1", ascending=False).reset_index(drop=True)
    available_columns = [column for column in LEADERBOARD_COLUMNS if column in leaderboard]
    leaderboard = leaderboard[available_columns]
    leaderboard.insert(0, "rank", np.arange(1, len(leaderboard) + 1))

    failed_runs = matching.loc[~matching["status"].eq("FINISHED")].copy()
    coverage_records = []
    for round_name in selected_rounds:
        expected = expected_configuration_keys(round_name)
        completed = set(
            leaderboard.loc[
                leaderboard["screening_round"].eq(round_name), "configuration_key"
            ].dropna()
        )
        failed_count = int(failed_runs["screening_round"].eq(round_name).sum())
        duplicate_count = int(
            duplicates["configuration_key"].str.startswith(f"{round_name}:").sum()
        ) if not duplicates.empty else 0
        missing = sorted(expected - completed)
        coverage_records.append(
            {
                "screening_round": round_name,
                "expected_configurations": len(expected),
                "completed_configurations": len(completed & expected),
                "missing_configurations": len(missing),
                "failed_runs": failed_count,
                "duplicated_configurations": duplicate_count,
                "missing_configuration_keys": "; ".join(missing),
            }
        )
    coverage = pd.DataFrame(coverage_records)
    return ScreeningReport(
        selected_rounds=selected_rounds,
        contract=selected_contract,
        available_contracts=available_contracts,
        matching_runs=matching,
        leaderboard=leaderboard,
        coverage=coverage,
        failed_runs=failed_runs,
        duplicate_runs=duplicates,
    )


def feature_set_comparison(leaderboard: pd.DataFrame) -> pd.DataFrame:
    real_models = leaderboard.loc[leaderboard["model_key"].ne("dummy")]
    if real_models.empty:
        return pd.DataFrame()
    comparison = real_models.pivot_table(
        index=["screening_round", "model_family", "weighting_mode"],
        columns="feature_set",
        values=["macro_f1", "latency_p99_ms", "throughput_flows_per_second"],
        aggfunc="first",
    )
    if {("macro_f1", name) for name in FEATURE_SETS}.issubset(comparison.columns):
        comparison[("macro_f1_difference", "reduced_64_minus_all_71")] = (
            comparison[("macro_f1", "reduced_64")]
            - comparison[("macro_f1", "all_71")]
        )
    return comparison


def weighting_comparison(leaderboard: pd.DataFrame) -> pd.DataFrame:
    real_models = leaderboard.loc[leaderboard["model_key"].ne("dummy")]
    if real_models.empty:
        return pd.DataFrame()
    comparison = real_models.pivot_table(
        index=["screening_round", "model_family", "feature_set"],
        columns="weighting_mode",
        values=["macro_f1", "binary_attack_recall"],
        aggfunc="first",
    )
    if {("macro_f1", name) for name in WEIGHTING_MODES}.issubset(comparison.columns):
        comparison[("macro_f1_difference", "balanced_minus_unweighted")] = (
            comparison[("macro_f1", "balanced")]
            - comparison[("macro_f1", "unweighted")]
        )
    return comparison


def best_per_family(leaderboard: pd.DataFrame) -> pd.DataFrame:
    if leaderboard.empty:
        return leaderboard.copy()
    ranked = leaderboard.sort_values("macro_f1", ascending=False)
    return ranked.drop_duplicates(
        ["screening_round", "model_family"], keep="first"
    ).reset_index(drop=True)


def screening_candidates(leaderboard: pd.DataFrame) -> pd.DataFrame:
    if leaderboard.empty:
        return pd.DataFrame()
    categories = [
        (
            "Best boosting model",
            "boosting",
        ),
        (
            "Best bagging/randomized-tree model",
            "bagging",
        ),
        (
            "Best neural model",
            "neural",
        ),
    ]
    records = []
    ranked = leaderboard.sort_values("macro_f1", ascending=False)
    for category, candidate_role in categories:
        eligible_models = models_for_candidate_role(candidate_role)
        eligible = pd.Series(
            list(
                zip(
                    ranked["screening_round"],
                    ranked["model_key"],
                )
            ),
            index=ranked.index,
        ).isin(eligible_models)
        rows = ranked.loc[
            eligible
        ]
        if rows.empty:
            return pd.DataFrame()
        record = rows.iloc[0].copy()
        record["candidate_category"] = category
        records.append(record)
    best_macro_f1 = leaderboard["macro_f1"].max()
    near_best = leaderboard.loc[leaderboard["macro_f1"] >= best_macro_f1 - 0.03]
    if near_best["latency_p99_ms"].notna().any():
        low_latency = near_best.sort_values("latency_p99_ms").iloc[0].copy()
        low_latency["candidate_category"] = (
            "Lowest latency within 0.03 macro F1 of the screening leader"
        )
        records.append(low_latency)
    return pd.DataFrame(records).reset_index(drop=True)


def download_csv_artifact(run_id: str, artifact_path: str) -> pd.DataFrame:
    local_path = mlflow.artifacts.download_artifacts(
        run_id=run_id, artifact_path=artifact_path
    )
    return pd.read_csv(local_path)


def save_leaderboard(
    report: ScreeningReport,
    filename: str | None = None,
    project_root: Path | None = None,
) -> Path:
    root = project_root or find_project_root()
    output_directory = root / "ml" / "reports" / "generated"
    output_directory.mkdir(parents=True, exist_ok=True)
    if filename is None:
        filename = f"{'_'.join(report.selected_rounds)}_leaderboard.csv"
    output_path = output_directory / filename
    report.leaderboard.to_csv(output_path, index=False)
    return output_path
