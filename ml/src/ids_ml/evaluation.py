"""Shared metrics, timing procedure, and MLflow evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

import mlflow
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    recall_score,
)

from .data import (
    EXPECTED_BASELINE_TIMING_FINGERPRINT,
    LABEL_ORDER,
    RANDOM_STATE,
)
from .plotting import plt

LATENCY_WARMUP_RUNS = 50
LATENCY_MEASUREMENTS = 1_000
THROUGHPUT_BATCH_SIZE = 10_000
THROUGHPUT_REPETITIONS = 5


class Predictor(Protocol):
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class TimingInputs:
    single_rows: tuple[pd.DataFrame, ...]
    batch_rows: pd.DataFrame
    fingerprint: str


def calculate_metrics_and_diagnostics(
    y_true: pd.Series | np.ndarray, y_pred: np.ndarray
) -> tuple[dict[str, float], pd.DataFrame, np.ndarray, np.ndarray]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=LABEL_ORDER, zero_division=0
    )
    report = pd.DataFrame(
        {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support.astype(np.int64),
        },
        index=pd.Index(LABEL_ORDER, name="label"),
    )
    raw_matrix = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER)
    row_totals = raw_matrix.sum(axis=1, keepdims=True)
    normalized_matrix = np.divide(
        raw_matrix,
        row_totals,
        out=np.zeros_like(raw_matrix, dtype=float),
        where=row_totals != 0,
    )
    nonempty_rows = row_totals.ravel() > 0
    if not np.allclose(normalized_matrix[nonempty_rows].sum(axis=1), 1.0):
        raise AssertionError("A normalized confusion-matrix row does not sum to 1.")

    true_positive = np.diag(raw_matrix).astype(float)
    false_positive = raw_matrix.sum(axis=0) - true_positive
    false_negative = raw_matrix.sum(axis=1) - true_positive
    denominator = 2 * true_positive + false_positive + false_negative
    f1_from_matrix = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator != 0,
    )
    macro_f1 = f1_score(
        y_true, y_pred, labels=LABEL_ORDER, average="macro", zero_division=0
    )
    if not np.isclose(macro_f1, f1_from_matrix.mean()):
        raise AssertionError("Macro F1 does not match the confusion-matrix calculation.")

    y_true_attack = np.asarray(y_true) != "BENIGN"
    y_pred_attack = np.asarray(y_pred) != "BENIGN"
    metrics = {
        "macro_f1": float(macro_f1),
        "accuracy_reference": float(accuracy_score(y_true, y_pred)),
        "binary_attack_recall": float(
            recall_score(y_true_attack, y_pred_attack, zero_division=0)
        ),
    }
    return metrics, report, raw_matrix, normalized_matrix


def make_timing_inputs(X_source: pd.DataFrame) -> TimingInputs:
    generator = np.random.default_rng(RANDOM_STATE)
    latency_count = min(LATENCY_MEASUREMENTS, len(X_source))
    latency_positions = generator.choice(
        len(X_source), size=latency_count, replace=False
    )
    single_rows = tuple(
        X_source.iloc[[int(position)]].copy() for position in latency_positions
    )
    batch_count = min(THROUGHPUT_BATCH_SIZE, len(X_source))
    batch_positions = generator.choice(len(X_source), size=batch_count, replace=False)
    batch_rows = X_source.iloc[batch_positions].copy()

    latency_indices = np.asarray(
        [int(row.index[0]) for row in single_rows], dtype=np.int64
    )
    batch_indices = np.asarray(batch_rows.index, dtype=np.int64)
    digest = hashlib.sha256()
    digest.update(latency_indices.tobytes())
    digest.update(batch_indices.tobytes())
    fingerprint = digest.hexdigest()
    if fingerprint != EXPECTED_BASELINE_TIMING_FINGERPRINT:
        raise AssertionError("Timing rows do not match the baseline experiment.")
    return TimingInputs(single_rows, batch_rows, fingerprint)


def measure_predictor_speed(
    predictor: Predictor, timing_inputs: TimingInputs
) -> dict[str, float]:
    warmup_row = timing_inputs.single_rows[0]
    for _ in range(LATENCY_WARMUP_RUNS):
        predictor.predict(warmup_row)

    latency_ms = []
    for row in timing_inputs.single_rows:
        start = perf_counter()
        predictor.predict(row)
        latency_ms.append((perf_counter() - start) * 1_000)

    predictor.predict(timing_inputs.batch_rows)
    batch_start = perf_counter()
    for _ in range(THROUGHPUT_REPETITIONS):
        predictor.predict(timing_inputs.batch_rows)
    batch_seconds = perf_counter() - batch_start
    return {
        "latency_p50_ms": float(np.percentile(latency_ms, 50)),
        "latency_p95_ms": float(np.percentile(latency_ms, 95)),
        "latency_p99_ms": float(np.percentile(latency_ms, 99)),
        "throughput_flows_per_second": float(
            len(timing_inputs.batch_rows) * THROUGHPUT_REPETITIONS / batch_seconds
        ),
    }


def _save_confusion_figure(
    matrix: np.ndarray, output_path: Path, title: str, value_format: str
) -> None:
    figure, axis = plt.subplots(figsize=(15, 12))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=value_format,
        cmap="Blues",
        xticklabels=LABEL_ORDER,
        yticklabels=LABEL_ORDER,
        ax=axis,
    )
    axis.set_title(title)
    axis.set_xlabel("Predicted label")
    axis.set_ylabel("True label")
    axis.tick_params(axis="x", labelrotation=45)
    axis.tick_params(axis="y", labelrotation=0)
    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def log_evaluation_artifacts(
    report: pd.DataFrame,
    raw_matrix: np.ndarray,
    normalized_matrix: np.ndarray,
    run_context: dict[str, Any],
) -> None:
    raw_frame = pd.DataFrame(raw_matrix, index=LABEL_ORDER, columns=LABEL_ORDER)
    normalized_frame = pd.DataFrame(
        normalized_matrix, index=LABEL_ORDER, columns=LABEL_ORDER
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        report.to_csv(directory / "per_class_report.csv")
        raw_frame.to_csv(directory / "confusion_matrix_raw.csv")
        normalized_frame.to_csv(directory / "confusion_matrix_row_normalized.csv")
        _save_confusion_figure(
            raw_matrix,
            directory / "confusion_matrix_raw.png",
            "Raw multiclass confusion matrix",
            "d",
        )
        _save_confusion_figure(
            normalized_matrix,
            directory / "confusion_matrix_row_normalized.png",
            "Row-normalized multiclass confusion matrix",
            ".3f",
        )
        with (directory / "run_context.json").open("w", encoding="utf-8") as handle:
            json.dump(run_context, handle, indent=2)
        mlflow.log_artifacts(directory, artifact_path="evaluation")


def log_table_artifact(
    frame: pd.DataFrame, filename: str, artifact_path: str
) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / filename
        frame.to_csv(path, index=True)
        mlflow.log_artifact(path, artifact_path=artifact_path)


def log_line_figure(
    frame: pd.DataFrame,
    columns: list[str],
    filename: str,
    title: str,
    artifact_path: str,
) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / filename
        figure, axis = plt.subplots(figsize=(10, 6))
        for column in columns:
            if column in frame:
                axis.plot(frame.index, frame[column], label=column)
        axis.set_title(title)
        axis.set_xlabel(frame.index.name or "step")
        axis.legend()
        figure.tight_layout()
        figure.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(figure)
        mlflow.log_artifact(path, artifact_path=artifact_path)
