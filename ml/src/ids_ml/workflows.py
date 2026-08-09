"""Command-line orchestration for reproducible screening experiments."""

from __future__ import annotations

import argparse
import gc
import importlib
import traceback
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .data import (
    class_preserving_sample,
    load_dataset_contract,
    load_experiment_data,
)
from .evaluation import make_timing_inputs
from .reporting import (
    build_screening_report,
    filter_to_contract,
    latest_successful_runs,
    query_screening_runs,
    save_leaderboard,
)
from .screening import run_validation_experiment, smoke_fit_adapter
from .specs import (
    FEATURE_SETS,
    ROUND_EXPERIMENTS,
    WEIGHTING_MODES,
    ExperimentSpec,
    model_keys_for_round,
    round_definition,
    specs_for_round,
)
from .tracking import setup_mlflow_experiment


def _parser(round_name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Run CIC-IDS-2017 {round_name} screening."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=model_keys_for_round(round_name),
        help="Run only the selected model families.",
    )
    parser.add_argument(
        "--feature-sets",
        nargs="+",
        choices=FEATURE_SETS,
        help="Run only the selected source feature schemas.",
    )
    parser.add_argument(
        "--weighting-modes",
        nargs="+",
        choices=WEIGHTING_MODES,
        help="Run only the selected weighting modes.",
    )
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Smoke-fit each selected model family and stop before MLflow runs.",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Run configurations even when matching successful MLflow runs exist.",
    )
    return parser


def _filter_specs(
    specs: Sequence[ExperimentSpec], args: argparse.Namespace
) -> list[ExperimentSpec]:
    selected = [
        spec
        for spec in specs
        if (args.models is None or spec.model_key in args.models)
        and (args.feature_sets is None or spec.feature_set in args.feature_sets)
        and (
            args.weighting_modes is None
            or spec.weighting_mode in args.weighting_modes
        )
    ]
    if not selected:
        raise ValueError("The supplied filters select no valid configurations.")
    return selected


def partition_specs_for_execution(
    specs: Sequence[ExperimentSpec],
    completed_keys: set[str],
    rerun: bool,
) -> tuple[dict[str, ExperimentSpec], list[tuple[str, ExperimentSpec]], list[str]]:
    requested_by_key = {spec.configuration_key: spec for spec in specs}
    if rerun:
        return requested_by_key, list(requested_by_key.items()), []
    pending = [
        item for item in requested_by_key.items() if item[0] not in completed_keys
    ]
    skipped = [key for key in requested_by_key if key in completed_keys]
    return requested_by_key, pending, skipped


def _preferred_smoke_specs(
    specs: Sequence[ExperimentSpec],
) -> list[ExperimentSpec]:
    selected = []
    for model_key in dict.fromkeys(spec.model_key for spec in specs):
        candidates = [spec for spec in specs if spec.model_key == model_key]
        candidates.sort(
            key=lambda spec: (
                spec.feature_set != "all_71",
                spec.weighting_mode != "balanced",
            )
        )
        selected.append(candidates[0])
    return selected


def _print_plan(specs: Sequence[ExperimentSpec]) -> None:
    print("\nRequested configurations:")
    print(pd.DataFrame([asdict(spec) for spec in specs]).to_string(index=False))


def _print_report(report: object, output_path: Path | None = None) -> None:
    print(f"\nSelected data/split contract: {report.contract}")
    if len(report.available_contracts) > 1:
        print(
            f"Compatible alternatives found: {len(report.available_contracts) - 1}. "
            "Use --dataset-version with ids-show-results to select one explicitly."
        )
    print("\nExperiment coverage:")
    coverage_columns = [
        column
        for column in report.coverage.columns
        if column != "missing_configuration_keys"
    ]
    print(report.coverage[coverage_columns].to_string(index=False))
    print("\nLatest successful configurations ranked by validation macro F1:")
    if report.leaderboard.empty:
        print("No matching successful runs were found.")
    else:
        columns = [
            "rank",
            "screening_round",
            "model_family",
            "weighting_mode",
            "feature_set",
            "macro_f1",
            "binary_attack_recall",
            "latency_p99_ms",
            "throughput_flows_per_second",
            "run_id",
        ]
        print(report.leaderboard[columns].to_string(index=False))
    if output_path is not None:
        print(f"\nSaved leaderboard: {output_path}")


def _round_main(round_name: str, argv: Sequence[str] | None = None) -> int:
    args = _parser(round_name).parse_args(argv)
    specs = _filter_specs(specs_for_round(round_name), args)
    _print_plan(specs)

    definition = round_definition(round_name)
    setup_mlflow_experiment(definition.experiment_name)
    contract = load_dataset_contract()
    comparison_contract = contract.comparison_fields()
    existing = filter_to_contract(
        query_screening_runs([round_name]), comparison_contract
    )
    latest_existing, _ = latest_successful_runs(existing)
    completed_keys = set(latest_existing["configuration_key"].dropna())
    requested_by_key, pending, skipped = partition_specs_for_execution(
        specs, completed_keys, args.rerun
    )

    print(f"\nAlready completed and skipped: {len(skipped)}")
    for key in skipped:
        print(f"  {key}")
    print(f"Configurations to execute: {len(pending)}")

    if not args.smoke_only and not pending:
        report = build_screening_report([round_name], contract=comparison_contract)
        output_path = save_leaderboard(report)
        _print_report(report, output_path)
        return 0

    implementation = importlib.import_module(definition.implementation_module)
    build_adapter = implementation.build_adapter
    data = load_experiment_data(contract=contract)
    smoke_targets = specs if args.smoke_only else [spec for _, spec in pending]
    X_smoke, y_smoke = class_preserving_sample(
        data.X_fit, data.y_fit, maximum_rows_per_class=100
    )
    print("\nSmoke fitting model families that are about to run:")
    try:
        for spec in _preferred_smoke_specs(smoke_targets):
            smoke_fit_adapter(
                lambda spec=spec: build_adapter(
                    spec, data.feature_sets, smoke=True
                ),
                X_smoke,
                y_smoke,
            )
            print(f"Passed: {spec.model_family}")
    finally:
        del X_smoke, y_smoke
        gc.collect()
    if args.smoke_only:
        print("Smoke-only validation completed; no MLflow runs were created.")
        return 0

    timing_inputs = make_timing_inputs(data.X_validation)
    run_group_id = uuid.uuid4().hex
    failures: list[tuple[str, str]] = []
    for run_number, (key, spec) in enumerate(pending, start=1):
        print(f"\n[{run_number}/{len(pending)}] {key}")
        try:
            result = run_validation_experiment(
                spec,
                data,
                timing_inputs,
                lambda spec=spec: build_adapter(spec, data.feature_sets),
                extra_tags={
                    "configuration_key": key,
                    "run_group_id": run_group_id,
                },
            )
            print(f"Validation macro F1: {result['macro_f1']:.6f}")
        except Exception as error:  # independent configurations must keep running
            message = f"{type(error).__name__}: {error}"
            failures.append((key, message))
            print(f"FAILED: {message}")
            traceback.print_exc()

    report = build_screening_report([round_name], contract=comparison_contract)
    output_path = save_leaderboard(report)
    _print_report(report, output_path)
    completed_after = set(report.leaderboard["configuration_key"].dropna())
    missing_requested = sorted(set(requested_by_key) - completed_after)
    if failures:
        print("\nFailures in this invocation:")
        for key, message in failures:
            print(f"  {key}: {message}")
    if missing_requested:
        print("\nRequested configurations still missing:")
        for key in missing_requested:
            print(f"  {key}")
    return 1 if failures or missing_requested else 0


def baseline_main(argv: Sequence[str] | None = None) -> int:
    return _round_main("baseline", argv)


def tree_main(argv: Sequence[str] | None = None) -> int:
    return _round_main("tree", argv)


def neural_main(argv: Sequence[str] | None = None) -> int:
    return _round_main("neural", argv)


def show_results_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show the latest CIC-IDS-2017 screening results from MLflow."
    )
    parser.add_argument(
        "--round",
        nargs="+",
        choices=list(ROUND_EXPERIMENTS),
        dest="rounds",
        help="One or more experiment rounds; omit to include all rounds.",
    )
    parser.add_argument(
        "--dataset-version",
        help="Restrict automatic contract selection to one dataset version.",
    )
    args = parser.parse_args(argv)
    report = build_screening_report(
        args.rounds, dataset_version=args.dataset_version
    )
    output_path = save_leaderboard(report)
    _print_report(report, output_path)
    return 0
