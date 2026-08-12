from __future__ import annotations

import json
from argparse import Namespace
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from ids_ml.data import LABEL_ORDER, transformed_feature_count
from ids_ml.evaluation import calculate_metrics_and_diagnostics
from ids_ml.experiment_specs import (
    expected_configuration_keys,
    specs_for_round,
    validate_round_filter,
)
from ids_ml.reporting import (
    filter_to_contract,
    latest_successful_runs,
    normalize_runs,
    screening_candidates,
    summarize_contracts,
)
from ids_ml.screening_workflows import (
    _filter_specs,
    baseline_main,
    neural_main,
    partition_specs_for_execution,
    show_results_main,
    tree_main,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def test_experiment_matrices_are_complete_and_unique() -> None:
    matrices = {
        round_name: specs_for_round(round_name)
        for round_name in ["baseline", "tree", "neural"]
    }
    expected_counts = {"baseline": 21, "tree": 12, "neural": 16}
    for round_name, specs in matrices.items():
        keys = {spec.configuration_key for spec in specs}
        assert len(specs) == expected_counts[round_name]
        assert len(keys) == len(specs)
        assert keys == expected_configuration_keys(round_name)


def test_protocol_contract_produces_expected_transformed_counts() -> None:
    assert transformed_feature_count(71, "one_hot") == 73
    assert transformed_feature_count(64, "one_hot") == 66
    assert transformed_feature_count(71, "embedding") == 71
    assert transformed_feature_count(64, "embedding") == 64

    neural_modes = {
        spec.model_key: spec.protocol_mode
        for spec in specs_for_round("neural")
    }
    assert neural_modes == {
        "mlp": "one_hot",
        "resnet": "one_hot",
        "ft_transformer": "embedding",
        "tabnet": "embedding",
    }


def test_round_filter_supports_every_nonempty_combination() -> None:
    rounds = ["baseline", "tree", "neural"]
    for size in range(1, len(rounds) + 1):
        for selected in combinations(rounds, size):
            assert validate_round_filter(list(selected)) == selected
    assert validate_round_filter(None) == tuple(rounds)
    assert validate_round_filter("tree") == ("tree",)


@pytest.mark.parametrize(
    "invalid_filter, message",
    [
        ([], "cannot be empty"),
        (["tree", "tree"], "duplicate"),
        (["unknown"], "Unknown experiment rounds"),
    ],
)
def test_round_filter_rejects_invalid_values(invalid_filter, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_round_filter(invalid_filter)


def test_model_feature_and_weighting_filters() -> None:
    args = Namespace(
        models=["xgboost"],
        feature_sets=["reduced_64"],
        weighting_modes=["balanced"],
    )
    selected = _filter_specs(specs_for_round("tree"), args)
    assert len(selected) == 1
    assert selected[0].model_key == "xgboost"
    assert selected[0].feature_set == "reduced_64"
    assert selected[0].weighting_mode == "balanced"


def test_completed_configurations_are_skipped_unless_rerun() -> None:
    specs = specs_for_round("tree")[:2]
    completed_key = specs[0].configuration_key
    requested, pending, skipped = partition_specs_for_execution(
        specs, {completed_key}, rerun=False
    )
    assert len(requested) == 2
    assert [key for key, _ in pending] == [specs[1].configuration_key]
    assert skipped == [completed_key]

    _, rerun_pending, rerun_skipped = partition_specs_for_execution(
        specs, {completed_key}, rerun=True
    )
    assert len(rerun_pending) == 2
    assert rerun_skipped == []


def test_legacy_run_normalization_and_latest_deduplication() -> None:
    raw = pd.DataFrame(
        {
            "run_id": ["old", "new", "failed"],
            "experiment_id": ["1", "1", "1"],
            "experiment_name": [
                "cicids2017-multiclass-baselines",
                "cicids2017-multiclass-baselines",
                "cicids2017-multiclass-baselines",
            ],
            "status": ["FINISHED", "FINISHED", "FAILED"],
            "start_time": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03"], utc=True
            ),
            "tags.model_family": ["SGDClassifier"] * 3,
            "tags.weighting_mode": ["balanced"] * 3,
            "tags.feature_set": ["all_71"] * 3,
            "params.model_key": ["sgd"] * 3,
            "tags.dataset_version": ["sha256:test"] * 3,
            "tags.fit_split_fingerprint": ["fit"] * 3,
            "tags.evaluation_split_fingerprint": ["validation"] * 3,
            "tags.timing_input_fingerprint": ["timing"] * 3,
            "metrics.macro_f1": [0.7, 0.8, np.nan],
        }
    )
    normalized = normalize_runs(raw)
    assert set(normalized["screening_round"]) == {"baseline"}
    assert set(normalized["model_key"]) == {"sgd"}
    assert set(normalized["configuration_key"]) == {
        "baseline:sgd:all_71:balanced"
    }

    contract = {
        "dataset_version": "sha256:test",
        "fit_split_fingerprint": "fit",
        "evaluation_split_fingerprint": "validation",
        "timing_input_fingerprint": "timing",
    }
    matching = filter_to_contract(normalized, contract)
    latest, duplicates = latest_successful_runs(matching)
    assert latest.iloc[0]["run_id"] == "new"
    assert duplicates.iloc[0]["successful_run_count"] == 2


def test_contracts_are_ranked_by_coverage_before_recency() -> None:
    runs = pd.DataFrame(
        {
            "run_id": ["old-1", "old-2", "new-1"],
            "status": ["FINISHED"] * 3,
            "macro_f1": [0.8, 0.9, 0.95],
            "configuration_key": ["tree:a", "tree:b", "tree:a"],
            "dataset_version": ["sha256:complete"] * 2 + ["sha256:new"],
            "fit_split_fingerprint": ["fit"] * 3,
            "evaluation_split_fingerprint": ["validation"] * 3,
            "timing_input_fingerprint": ["timing"] * 3,
            "start_time": pd.to_datetime(
                ["2026-01-01", "2026-01-01", "2026-02-01"], utc=True
            ),
        }
    )
    summary = summarize_contracts(runs)
    assert summary.iloc[0]["dataset_version"] == "sha256:complete"
    assert summary.iloc[0]["successful_configurations"] == 2


def test_candidate_roles_do_not_confuse_baseline_and_neural_mlp() -> None:
    leaderboard = pd.DataFrame(
        [
            {
                "screening_round": "baseline",
                "model_key": "hist_gradient_boosting",
                "macro_f1": 0.95,
                "latency_p99_ms": 4.0,
            },
            {
                "screening_round": "baseline",
                "model_key": "random_forest",
                "macro_f1": 0.94,
                "latency_p99_ms": 5.0,
            },
            {
                "screening_round": "baseline",
                "model_key": "mlp",
                "macro_f1": 0.99,
                "latency_p99_ms": 2.0,
            },
            {
                "screening_round": "neural",
                "model_key": "resnet",
                "macro_f1": 0.90,
                "latency_p99_ms": 6.0,
            },
        ]
    )
    candidates = screening_candidates(leaderboard)
    neural = candidates.loc[candidates["candidate_category"].eq("Best neural model")]
    assert neural.iloc[0]["model_key"] == "resnet"


def test_multiclass_metric_calculation_is_exact_for_perfect_predictions() -> None:
    y_true = np.asarray(LABEL_ORDER, dtype=object)
    metrics, report, raw_matrix, normalized_matrix = (
        calculate_metrics_and_diagnostics(y_true, y_true.copy())
    )
    assert metrics == {
        "macro_f1": 1.0,
        "accuracy_reference": 1.0,
        "binary_attack_recall": 1.0,
    }
    assert (report[["precision", "recall", "f1"]] == 1.0).all().all()
    assert np.array_equal(raw_matrix, np.eye(len(LABEL_ORDER), dtype=int))
    assert np.allclose(normalized_matrix.sum(axis=1), 1.0)


def test_comparison_notebook_is_read_only_and_compiles() -> None:
    notebook_path = (
        PROJECT_ROOT
        / "ml"
        / "notebooks"
        / "03_model_screening_analysis.ipynb"
    )
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    cell_ids = [cell["id"] for cell in notebook["cells"]]
    assert len(cell_ids) == len(set(cell_ids))
    code = "\n".join(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )
    compile(code, str(notebook_path), "exec")
    assert ".fit(" not in code
    assert ".predict(" not in code
    assert "run_tree_experiment" not in code
    assert "run_neural_experiment" not in code
    assert "run_baseline_experiment" not in code
    assert "X_test" not in code


def test_pyproject_exposes_the_expected_commands() -> None:
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert configuration["project"]["scripts"] == {
        "ids-run-baselines": "ids_ml.screening_workflows:baseline_main",
        "ids-run-trees": "ids_ml.screening_workflows:tree_main",
        "ids-run-neural": "ids_ml.screening_workflows:neural_main",
        "ids-show-results": "ids_ml.screening_workflows:show_results_main",
        "ids-tune-trees": "ids_ml.tree_tuning.cli:tuning_main",
        "ids-serve": "ids_backend.app:serve_main",
        "ids-generate-flows": "ids_tools.replay_flows:generator_main",
    }


@pytest.mark.parametrize(
    "command_main",
    [baseline_main, tree_main, neural_main, show_results_main],
)
def test_command_help_does_not_load_the_dataset(command_main) -> None:
    with pytest.raises(SystemExit) as exit_info:
        command_main(["--help"])
    assert exit_info.value.code == 0
