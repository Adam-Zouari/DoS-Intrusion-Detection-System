from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pandas as pd
import pytest

from ids_ml.data import LABEL_ORDER

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_FINAL = PROJECT_ROOT / "ml" / "reports" / "published" / "final"

FINAL_MACRO_F1 = 0.9601570258859387
FINAL_ACCURACY = 0.9994937614058564


def test_documented_local_links_resolve() -> None:
    documents = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "LEGACY_APPLICATION.md",
        PROJECT_ROOT / "ml" / "README.md",
        PROJECT_ROOT / "ml" / "DATASET.md",
        PROJECT_ROOT / "ml" / "RESULTS.md",
        PROJECT_ROOT / "ml" / "src" / "ids_ml" / "README.md",
        PROJECT_ROOT / "ml" / "src" / "ids_ml" / "tree_tuning" / "README.md",
        PROJECT_ROOT / "ml" / "reports" / "published" / "README.md",
        PROJECT_ROOT / "tests" / "README.md",
    ]
    markdown_link = re.compile(r"!?(?:\[[^]]*\])\(([^)]+)\)")
    missing: list[str] = []

    for document in documents:
        assert document.is_file(), f"Missing documentation file: {document}"
        for raw_target in markdown_link.findall(
            document.read_text(encoding="utf-8")
        ):
            target = raw_target.strip().split("#", maxsplit=1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (document.parent / unquote(target)).resolve()
            if not resolved.exists():
                missing.append(f"{document.relative_to(PROJECT_ROOT)} -> {target}")

    assert not missing, "Broken local documentation links:\n" + "\n".join(missing)


def test_feature_dictionary_has_one_authoritative_location() -> None:
    notebook_path = (
        PROJECT_ROOT / "ml" / "notebooks" / "01_data_exploration.ipynb"
    )
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    markdown = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )
    dataset_reference = (
        PROJECT_ROOT / "ml" / "DATASET.md"
    ).read_text(encoding="utf-8")

    assert "## Dataset feature dictionary" not in markdown
    assert "../DATASET.md" in markdown
    assert "## Feature dictionary" in dataset_reference
    assert "## What determines a flow?" in dataset_reference


def test_published_confusion_matrix_reproduces_final_metrics() -> None:
    matrix_frame = pd.read_csv(
        PUBLISHED_FINAL / "confusion_matrix_raw.csv", index_col=0
    )
    assert matrix_frame.index.tolist() == LABEL_ORDER
    assert matrix_frame.columns.tolist() == LABEL_ORDER

    matrix = matrix_frame.to_numpy(dtype=np.int64)
    true_support = matrix.sum(axis=1)
    predicted_support = matrix.sum(axis=0)
    true_positive = np.diag(matrix).astype(float)
    precision = np.divide(
        true_positive,
        predicted_support,
        out=np.zeros_like(true_positive),
        where=predicted_support != 0,
    )
    recall = np.divide(
        true_positive,
        true_support,
        out=np.zeros_like(true_positive),
        where=true_support != 0,
    )
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros_like(true_positive),
        where=(precision + recall) != 0,
    )

    assert float(f1.mean()) == pytest.approx(FINAL_MACRO_F1, abs=1e-12)
    assert float(true_positive.sum() / matrix.sum()) == pytest.approx(
        FINAL_ACCURACY, abs=1e-12
    )


def test_published_normalized_matrix_and_class_report_are_consistent() -> None:
    normalized = pd.read_csv(
        PUBLISHED_FINAL / "confusion_matrix_row_normalized.csv", index_col=0
    )
    report = pd.read_csv(PUBLISHED_FINAL / "per_class_report.csv")

    assert normalized.index.tolist() == LABEL_ORDER
    assert normalized.columns.tolist() == LABEL_ORDER
    assert np.allclose(normalized.sum(axis=1).to_numpy(), 1.0)
    assert report["label"].tolist() == LABEL_ORDER
    assert report["f1"].mean() == pytest.approx(FINAL_MACRO_F1, abs=1e-12)


def test_frozen_recipe_matches_the_published_model_contract() -> None:
    specification = json.loads(
        (PROJECT_ROOT / "ml" / "final_model_spec.json").read_text(
            encoding="utf-8"
        )
    )
    selection = specification["selection"]
    recipe = specification["model_recipe"]

    assert selection["source_optuna_trial_number"] == 14
    assert selection["outer_validation_macro_f1"] == pytest.approx(
        0.9720280653720391, abs=1e-15
    )
    assert recipe["source_feature_count"] == 71
    assert recipe["transformed_feature_count"] == 73
    assert recipe["boosting_iterations"] == 990
    assert recipe["weighting_mode"] == "balanced"
    assert recipe["training_device"] == "cuda"
    assert recipe["inference_device"] == "cpu"


def test_published_text_artifacts_contain_no_local_absolute_paths() -> None:
    text_files = [
        *PUBLISHED_FINAL.glob("*.csv"),
        PROJECT_ROOT / "ml" / "reports" / "published" / "README.md",
        PROJECT_ROOT / "ml" / "RESULTS.md",
    ]
    for path in text_files:
        text = path.read_text(encoding="utf-8")
        assert "C:\\Users\\" not in text


def test_generated_and_private_ml_artifacts_remain_ignored() -> None:
    ignored_candidates = [
        "ml/data/raw/example.csv",
        "ml/data/processed/example.parquet",
        "ml/models/example.joblib",
        "ml/reports/generated/example.csv",
        "ml/mlflow.db",
        "ml/optuna.db",
        "ml/mlruns/example/artifact.csv",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"],
        cwd=PROJECT_ROOT,
        input="\0".join(ignored_candidates) + "\0",
        text=True,
        capture_output=True,
        check=True,
    )
    ignored_output = {path for path in result.stdout.split("\0") if path}
    assert ignored_output == set(ignored_candidates)
    assert not subprocess.run(
        ["git", "check-ignore", "ml/reports/published/final/per_class_report.csv"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
