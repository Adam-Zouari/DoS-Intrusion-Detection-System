"""Replay cleaned CIC-IDS-2017 rows as individual completed-flow requests."""

from __future__ import annotations

import argparse
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import httpx
import pyarrow.dataset as arrow_dataset

from ids_backend.contracts import load_model_contract, validate_flow_payload
from ids_backend.settings import find_project_root


def processed_dataset_path(project_root: Path) -> Path:
    return project_root / "ml" / "data" / "processed" / "cicids2017_cleaned.parquet"


def _json_value(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def iter_replay_rows(
    dataset_path: Path,
    *,
    labels: set[str] | None = None,
    shuffle: bool = False,
    seed: int = 42,
    batch_size: int = 8_192,
) -> Iterator[tuple[dict[str, Any], str]]:
    source = arrow_dataset.dataset(dataset_path, format="parquet")
    label_filter = (
        arrow_dataset.field("Label").isin(sorted(labels)) if labels else None
    )
    randomizer = random.Random(seed)
    for batch in source.to_batches(filter=label_filter, batch_size=batch_size):
        records = batch.to_pylist()
        if shuffle:
            randomizer.shuffle(records)
        for row in records:
            expected_label = str(row.pop("Label"))
            row.pop("ClassLabel", None)
            if labels and expected_label not in labels:
                continue
            yield ({key: _json_value(value) for key, value in row.items()}, expected_label)


def replay_flows(
    *,
    dataset_path: Path,
    endpoint: str,
    count: int,
    interval_ms: float,
    labels: set[str] | None,
    shuffle: bool,
    seed: int,
    project_root: Path,
) -> dict[str, Any]:
    contract = load_model_contract(project_root)
    correct = 0
    sent = 0
    predicted_counts: Counter[str] = Counter()
    expected_counts: Counter[str] = Counter()
    started = time.perf_counter()
    with httpx.Client(timeout=30.0) as client:
        for payload, expected in iter_replay_rows(
            dataset_path, labels=labels, shuffle=shuffle, seed=seed
        ):
            validate_flow_payload(payload, contract)
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            prediction = str(response.json()["prediction"])
            sent += 1
            correct += int(prediction == expected)
            predicted_counts[prediction] += 1
            expected_counts[expected] += 1
            print(
                f"[{sent}/{count}] expected={expected!r} predicted={prediction!r} "
                f"latency={response.json()['inference_latency_ms']:.3f} ms"
            )
            if sent >= count:
                break
            if interval_ms > 0:
                time.sleep(interval_ms / 1_000)
    if sent < count:
        raise RuntimeError(
            f"Only {sent} matching rows were available; {count} were requested."
        )
    elapsed = time.perf_counter() - started
    return {
        "sent": sent,
        "correct": correct,
        "replay_accuracy": correct / sent if sent else 0.0,
        "elapsed_seconds": elapsed,
        "expected_labels": dict(expected_counts),
        "predicted_labels": dict(predicted_counts),
    }


def generator_main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay cleaned CIC-IDS-2017 rows one flow at a time."
    )
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--interval-ms", type=float, default=500.0)
    parser.add_argument(
        "--endpoint", default="http://127.0.0.1:8000/api/flows"
    )
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--labels", nargs="+")
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle rows within each streamed Parquet batch.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-delay", action="store_true", help="Send the next flow immediately."
    )
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1.")
    if args.interval_ms < 0:
        parser.error("--interval-ms cannot be negative.")
    root = find_project_root()
    contract = load_model_contract(root)
    unknown = sorted(set(args.labels or []) - set(contract.label_order))
    if unknown:
        parser.error(f"Unknown labels: {unknown}")
    dataset = (args.dataset or processed_dataset_path(root)).resolve()
    if not dataset.exists():
        parser.error(f"Dataset not found: {dataset}")
    summary = replay_flows(
        dataset_path=dataset,
        endpoint=args.endpoint,
        count=args.count,
        interval_ms=0.0 if args.no_delay else args.interval_ms,
        labels=set(args.labels) if args.labels else None,
        shuffle=args.shuffle,
        seed=args.seed,
        project_root=root,
    )
    print("\nReplay summary")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    generator_main()
