"""Shared lifecycle for every tracked validation experiment."""

from __future__ import annotations

import gc
import platform
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, Protocol

import mlflow
import numpy as np
import pandas as pd

from .data import LABEL_ORDER, RANDOM_STATE, ExperimentData, index_fingerprint
from .evaluation import (
    TimingInputs,
    calculate_metrics_and_diagnostics,
    log_evaluation_artifacts,
    measure_predictor_speed,
)
from .experiment_specs import ExperimentSpec


@dataclass(frozen=True)
class AdapterMetadata:
    model_library: str
    model_library_version: str
    weighting_mechanism: str
    target_encoding: str
    protocol_encoding: str
    numeric_preprocessing: str
    numeric_dtype: str
    training_device: str = "cpu"
    inference_device: str = "cpu"


@dataclass
class FitDetails:
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationPartition:
    """One development-data fit/evaluation split for a tracked experiment."""

    X_training: pd.DataFrame
    y_training: pd.Series
    X_evaluation: pd.DataFrame
    y_evaluation: pd.Series
    split_seed: int
    evaluation_stage: str


class ScreeningAdapter(Protocol):
    spec: ExperimentSpec
    metadata: AdapterMetadata
    transformed_feature_count: int

    def parameters(self) -> dict[str, object]: ...

    def fit(self, X: pd.DataFrame, y: pd.Series) -> FitDetails: ...

    def predict(self, X: pd.DataFrame) -> np.ndarray: ...

    def fitted_context(self) -> dict[str, object]: ...

    def log_diagnostics(self, X: pd.DataFrame, y: pd.Series) -> None: ...

    def cleanup(self) -> None: ...


def smoke_fit_adapter(
    adapter_factory: Callable[[], ScreeningAdapter],
    X_smoke: pd.DataFrame,
    y_smoke: pd.Series,
) -> None:
    adapter: ScreeningAdapter | None = None
    try:
        adapter = adapter_factory()
        adapter.fit(X_smoke, y_smoke)
        predictions = adapter.predict(X_smoke.iloc[: min(32, len(X_smoke))])
        if len(predictions) == 0:
            raise AssertionError(
                f"{adapter.spec.model_family} smoke fit produced no predictions."
            )
    finally:
        if adapter is not None:
            adapter.cleanup()
        gc.collect()


def run_validation_experiment(
    spec: ExperimentSpec,
    data: ExperimentData,
    timing_inputs: TimingInputs | None,
    adapter_factory: Callable[[], ScreeningAdapter],
    extra_tags: dict[str, str] | None = None,
    *,
    partition: ValidationPartition | None = None,
    run_name: str | None = None,
) -> dict[str, object]:
    selected_features = data.feature_sets[spec.feature_set]
    default_partition = partition is None
    partition = partition or ValidationPartition(
        X_training=data.X_fit,
        y_training=data.y_fit,
        X_evaluation=data.X_validation,
        y_evaluation=data.y_validation,
        split_seed=RANDOM_STATE,
        evaluation_stage=f"{spec.screening_round}_screening_validation",
    )
    if (
        default_partition
        and timing_inputs is not None
        and timing_inputs.fingerprint != data.contract.timing_fingerprint
    ):
        raise AssertionError("Timing inputs do not match the dataset contract.")
    comparison_contract = {
        "dataset_version": data.contract.dataset_version,
        "fit_split_fingerprint": index_fingerprint(partition.X_training.index),
        "evaluation_split_fingerprint": index_fingerprint(
            partition.X_evaluation.index
        ),
        "timing_input_fingerprint": (
            timing_inputs.fingerprint if timing_inputs is not None else "not_measured"
        ),
    }
    if default_partition and comparison_contract != data.contract.comparison_fields():
        raise AssertionError("The default validation partition changed unexpectedly.")
    selected_run_name = run_name or (
        f"{spec.screening_round}_screening__{spec.model_key}__"
        f"{spec.weighting_mode}__{spec.feature_set}"
    )
    base_tags = {
        "screening_round": spec.screening_round,
        "model_family": spec.model_family,
        "model_key": spec.model_key,
        "weighting_mode": spec.weighting_mode,
        "split_seed": str(partition.split_seed),
        "feature_set": spec.feature_set,
        "source_feature_count": str(len(selected_features)),
        "evaluation_stage": partition.evaluation_stage,
        "test_split_fingerprint": data.contract.test_fingerprint,
        "python_version": platform.python_version(),
        "operating_system": platform.platform(),
        "machine": platform.machine(),
        **comparison_contract,
    }
    base_tags.update(extra_tags or {})

    adapter: ScreeningAdapter | None = None
    try:
        with mlflow.start_run(run_name=selected_run_name, tags=base_tags) as active_run:
            adapter = adapter_factory()
            metadata = adapter.metadata
            mlflow.set_tags(
                {
                    "model_library": metadata.model_library,
                    "model_library_version": metadata.model_library_version,
                    "training_device": metadata.training_device,
                    "inference_device": metadata.inference_device,
                    "weighting_mechanism": metadata.weighting_mechanism,
                    "target_encoding": metadata.target_encoding,
                    "protocol_encoding": metadata.protocol_encoding,
                }
            )
            parameters = {
                "model_key": spec.model_key,
                "weighting_mode": spec.weighting_mode,
                "weighting_mechanism": metadata.weighting_mechanism,
                "target_encoding": metadata.target_encoding,
                "feature_set": spec.feature_set,
                "source_feature_count": len(selected_features),
                "protocol_encoding": metadata.protocol_encoding,
                "numeric_preprocessing": metadata.numeric_preprocessing,
                "numeric_dtype": metadata.numeric_dtype,
                "random_state": RANDOM_STATE,
                "data_split_seed": partition.split_seed,
                **adapter.parameters(),
            }
            mlflow.log_params(parameters)

            training_start = perf_counter()
            fit_details = adapter.fit(partition.X_training, partition.y_training)
            training_time_seconds = perf_counter() - training_start

            predictions = adapter.predict(partition.X_evaluation)
            metrics, report, raw_matrix, normalized_matrix = (
                calculate_metrics_and_diagnostics(partition.y_evaluation, predictions)
            )
            metrics["training_time_seconds"] = float(training_time_seconds)
            metrics.update(fit_details.metrics)
            if timing_inputs is not None:
                metrics.update(measure_predictor_speed(adapter, timing_inputs))
            mlflow.log_metrics(metrics)
            mlflow.set_tag(
                "transformed_feature_count", str(adapter.transformed_feature_count)
            )

            run_context = {
                "dataset_sha256": data.contract.dataset_sha256,
                "label_order": LABEL_ORDER,
                "pipeline_input_features": data.model_input_features,
                "selected_source_features": selected_features,
                "source_feature_count": len(selected_features),
                "transformed_feature_count": adapter.transformed_feature_count,
                "protocol_encoding": metadata.protocol_encoding,
                "target_encoding": metadata.target_encoding,
                "evaluation_stage": partition.evaluation_stage,
                "data_split_seed": partition.split_seed,
                "model_random_state": RANDOM_STATE,
                "fit_rows": len(partition.X_training),
                "evaluation_rows": len(partition.X_evaluation),
                "test_rows_not_evaluated": len(data.X_test),
                "training_device": metadata.training_device,
                "inference_device": metadata.inference_device,
                "comparison_contract": comparison_contract,
                **adapter.fitted_context(),
            }
            log_evaluation_artifacts(
                report, raw_matrix, normalized_matrix, run_context
            )
            adapter.log_diagnostics(
                partition.X_evaluation, partition.y_evaluation
            )

            return {
                "run_id": active_run.info.run_id,
                "model_key": spec.model_key,
                "model_family": spec.model_family,
                "library_version": metadata.model_library_version,
                "weighting_mode": spec.weighting_mode,
                "weighting_mechanism": metadata.weighting_mechanism,
                "feature_set": spec.feature_set,
                "source_feature_count": len(selected_features),
                "transformed_feature_count": adapter.transformed_feature_count,
                "protocol_encoding": metadata.protocol_encoding,
                "training_device": metadata.training_device,
                "inference_device": metadata.inference_device,
                **comparison_contract,
                **metrics,
            }
    finally:
        if adapter is not None:
            adapter.cleanup()
        gc.collect()
