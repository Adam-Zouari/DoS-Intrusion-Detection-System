"""Command-line, smoke-validation, and reporting orchestration for tree tuning."""

from __future__ import annotations

import argparse
import gc
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
from optuna.samplers import TPESampler

from ..data import (
    RANDOM_STATE,
    ExperimentData,
    class_preserving_sample,
    find_project_root,
    load_dataset_contract,
    load_experiment_data,
    make_inner_split,
)
from ..evaluation import TimingInputs
from ..tracking import configure_tracking
from .training import FEATURE_SET, TARGET_TRIALS, VERIFICATION_EXPERIMENT, prepare_matrices
from .final_evaluation import evaluate_frozen_final_model, show_final_report
from .final_selection import freeze_final_model
from .search_space import MODEL_KEYS
from .search import (
    complete_trial_count,
    optuna_storage_uri,
    run_search,
    run_search_trial,
)
from .original_xgboost_comparison import run_original_xgboost_comparison
from .verification import (
    log_speed_for_candidate,
    run_verification,
    run_verification_fit,
)


def _smoke_timing_inputs(X: pd.DataFrame) -> TimingInputs:
    row_count = min(20, len(X))
    single_rows = tuple(X.iloc[[position]].copy() for position in range(row_count))
    return TimingInputs(single_rows=single_rows, batch_rows=X.copy(), fingerprint="smoke")


def run_smoke(data: ExperimentData, model_keys: Sequence[str]) -> None:
    """Exercise search, tracking, artifacts, refit and CPU inference cheaply."""

    X_sample, y_sample = class_preserving_sample(
        data.X_fit, data.y_fit, maximum_rows_per_class=100
    )
    outer = make_inner_split(y_sample, test_size=0.20)
    X_smoke_fit = X_sample.iloc[outer.training_positions]
    y_smoke_fit = y_sample.iloc[outer.training_positions]
    X_smoke_validation = X_sample.iloc[outer.stopping_positions]
    y_smoke_validation = y_sample.iloc[outer.stopping_positions]
    matrices = prepare_matrices(
        X_smoke_fit,
        y_smoke_fit,
        data.feature_sets[FEATURE_SET],
        inner_test_size=0.20,
    )

    previous_uri = mlflow.get_tracking_uri()
    previous_file_store_setting = os.environ.get("MLFLOW_ALLOW_FILE_STORE")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
        mlflow.set_tracking_uri((directory / "tracking").resolve().as_uri())
        artifact_root = directory / "artifacts"
        search_id = mlflow.create_experiment(
            "tree-tuning-smoke", artifact_location=artifact_root.resolve().as_uri()
        )
        verify_id = mlflow.create_experiment(
            "tree-verification-smoke", artifact_location=artifact_root.resolve().as_uri()
        )
        client = mlflow.MlflowClient()
        try:
            for model_key in model_keys:
                mlflow.set_experiment(experiment_id=search_id)
                smoke_study = optuna.create_study(
                    direction="maximize", sampler=TPESampler(seed=RANDOM_STATE)
                )
                live_trial = smoke_study.ask()
                value = run_search_trial(
                    live_trial,
                    model_key,
                    matrices,
                    data,
                    f"smoke-{model_key}",
                    maximum_rounds=3,
                    patience=2,
                )
                smoke_study.tell(live_trial, value)
                trial = smoke_study.trials[0]
                search_run_id = str(trial.user_attrs["mlflow_run_id"])
                search_artifacts = {
                    artifact.path for artifact in client.list_artifacts(search_run_id)
                }
                if not {"evaluation", "tuning"}.issubset(search_artifacts):
                    raise AssertionError("Smoke tuning artifacts are incomplete.")

                mlflow.set_experiment(experiment_id=verify_id)
                candidate = run_verification_fit(
                    model_key,
                    trial,
                    data,
                    X_smoke_fit,
                    y_smoke_fit,
                    X_smoke_validation,
                    y_smoke_validation,
                    RANDOM_STATE,
                    "smoke_outer_validation",
                )
                speed = log_speed_for_candidate(
                    candidate, _smoke_timing_inputs(X_smoke_validation)
                )
                if not all(np.isfinite(list(speed.values()))):
                    raise AssertionError("Smoke inference timing produced a non-finite value.")
                verification_artifacts = {
                    artifact.path for artifact in client.list_artifacts(candidate.run_id)
                }
                if not {"diagnostics", "evaluation"}.issubset(
                    verification_artifacts
                ):
                    raise AssertionError("Smoke verification artifacts are incomplete.")
                candidate.predictor.cleanup()
                print(
                    f"Passed smoke workflow: {model_key} "
                    f"(macro F1 {candidate.macro_f1:.6f})"
                )
        finally:
            mlflow.end_run()
            mlflow.set_tracking_uri(previous_uri)
            if previous_file_store_setting is None:
                os.environ.pop("MLFLOW_ALLOW_FILE_STORE", None)
            else:
                os.environ["MLFLOW_ALLOW_FILE_STORE"] = previous_file_store_setting
    del matrices, X_sample, y_sample
    gc.collect()


def _study_progress(
    model_keys: Sequence[str], project_root: Path | None = None
) -> pd.DataFrame:
    storage = optuna_storage_uri(project_root)
    try:
        summaries = optuna.study.get_all_study_summaries(storage=storage)
    except Exception:
        return pd.DataFrame(
            columns=[
                "model_key",
                "study_name",
                "successful_trials",
                "total_trials",
                "best_macro_f1",
            ]
        )
    records = []
    for summary in summaries:
        matching = [key for key in model_keys if f"-{key}-" in summary.study_name]
        if not matching:
            continue
        study = optuna.load_study(study_name=summary.study_name, storage=storage)
        completed = complete_trial_count(study)
        records.append(
            {
                "model_key": matching[0],
                "study_name": summary.study_name,
                "successful_trials": completed,
                "total_trials": len(study.trials),
                "best_macro_f1": study.best_value if completed else np.nan,
            }
        )
    return pd.DataFrame(records)


def _verification_report(
    model_keys: Sequence[str], project_root: Path | None = None
) -> pd.DataFrame:
    configure_tracking(project_root)
    experiment = mlflow.get_experiment_by_name(VERIFICATION_EXPERIMENT)
    if experiment is None:
        return pd.DataFrame()
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id], output_format="pandas"
    )
    model_column = runs.get("tags.model_key", pd.Series(index=runs.index, dtype=object))
    selected = runs.loc[
        runs["status"].eq("FINISHED") & model_column.isin(model_keys)
    ].copy()
    if selected.empty:
        return selected
    columns = {
        "run_id": "run_id",
        "tags.model_key": "model_key",
        "tags.evaluation_stage": "evaluation_stage",
        "tags.source_trial_number": "trial_number",
        "tags.split_seed": "split_seed",
        "metrics.macro_f1": "macro_f1",
        "metrics.accuracy_reference": "accuracy_reference",
        "metrics.binary_attack_recall": "binary_attack_recall",
        "metrics.latency_p99_ms": "latency_p99_ms",
        "metrics.throughput_flows_per_second": "throughput_flows_per_second",
    }
    available = [column for column in columns if column in selected]
    return selected[available].rename(columns=columns).sort_values(
        ["model_key", "macro_f1"], ascending=[True, False]
    )


def show_tuning_report(model_keys: Sequence[str]) -> None:
    progress = _study_progress(model_keys)
    verification = _verification_report(model_keys)
    output = find_project_root() / "ml" / "reports" / "generated"
    output.mkdir(parents=True, exist_ok=True)
    print("\nOptuna study progress:")
    print("No matching studies." if progress.empty else progress.to_string(index=False))
    print("\nVerification runs:")
    print(
        "No matching verification runs."
        if verification.empty
        else verification.to_string(index=False)
    )
    progress.to_csv(output / "tree_tuning_study_progress.csv", index=False)
    verification.to_csv(output / "tree_tuning_verification_runs.csv", index=False)
    print(f"\nSaved generated reports under {output}")


def _add_model_filter(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--models",
        nargs="+",
        choices=MODEL_KEYS,
        default=list(MODEL_KEYS),
        help="Restrict the command to one or both selected boosting families.",
    )


def _tuning_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tune and verify CIC-IDS-2017 XGBoost and LightGBM challengers."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search", help="Resume Optuna studies to a successful-trial target."
    )
    _add_model_filter(search)
    search.add_argument(
        "--target-trials",
        type=int,
        default=TARGET_TRIALS,
        help="Target successful trials per model; existing trials count toward it.",
    )
    search.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run shortened temporary search and verification fits only.",
    )

    verify = subparsers.add_parser(
        "verify", help="Verify top trials and run three-split stability checks."
    )
    _add_model_filter(verify)

    comparison = subparsers.add_parser(
        "compare-original-xgboost",
        help="Compare the original and tuned XGBoost across three splits.",
    )
    comparison.add_argument(
        "--rerun",
        action="store_true",
        help="Repeat original-configuration fits even when completed runs exist.",
    )

    report = subparsers.add_parser(
        "report", help="Show saved Optuna progress and MLflow verification results."
    )
    _add_model_filter(report)

    subparsers.add_parser(
        "freeze-final",
        help="Freeze the tuned XGBoost run with the best outer-validation macro F1.",
    )
    subparsers.add_parser(
        "evaluate-final",
        help="Refit the frozen XGBoost on 80%% and evaluate the protected test once.",
    )
    subparsers.add_parser(
        "final-report",
        help="Show the frozen recipe and final-test result without fitting.",
    )
    return parser


def tuning_main(argv: Sequence[str] | None = None) -> int:
    args = _tuning_parser().parse_args(argv)
    model_keys = tuple(dict.fromkeys(getattr(args, "models", ())))
    if args.command == "report":
        show_tuning_report(model_keys)
        return 0
    if args.command == "freeze-final":
        try:
            freeze_final_model()
            return 0
        except (RuntimeError, ValueError) as error:
            print(error)
            return 1
    if args.command == "final-report":
        try:
            show_final_report()
            return 0
        except (FileNotFoundError, ValueError) as error:
            print(error)
            return 1
    if args.command == "evaluate-final":
        try:
            evaluate_frozen_final_model()
            return 0
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            print(error)
            return 1

    contract = load_dataset_contract()
    data = load_experiment_data(contract=contract)
    if args.command == "search" and args.smoke_only:
        run_smoke(data, model_keys)
        return 0
    if args.command == "search":
        if args.target_trials < 1:
            raise ValueError("--target-trials must be positive.")
        return 0 if run_search(data, model_keys, args.target_trials) else 1
    if args.command == "verify":
        return 0 if run_verification(data, model_keys) else 1
    if args.command == "compare-original-xgboost":
        return 0 if run_original_xgboost_comparison(data, rerun=args.rerun) else 1
    raise AssertionError(f"Unhandled command: {args.command}")
