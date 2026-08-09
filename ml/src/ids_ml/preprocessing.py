"""Shared tabular preprocessing for pipelines that one-hot encode Protocol."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .data import EXPECTED_PROTOCOL_VALUES


def make_one_hot_protocol_preprocessor(
    selected_features: list[str],
    numeric_transformer: Any,
    dtype: type[np.floating],
) -> ColumnTransformer:
    numeric_features = [feature for feature in selected_features if feature != "Protocol"]
    return ColumnTransformer(
        [
            ("numeric", numeric_transformer, numeric_features),
            (
                "protocol",
                OneHotEncoder(
                    categories=[EXPECTED_PROTOCOL_VALUES],
                    handle_unknown="ignore",
                    sparse_output=False,
                    dtype=dtype,
                ),
                ["Protocol"],
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=False,
    )


def make_one_hot_pipeline(
    selected_features: list[str],
    numeric_transformer: Any,
    dtype: type[np.floating],
    classifier: Any,
) -> Pipeline:
    return Pipeline(
        [
            (
                "preprocessor",
                make_one_hot_protocol_preprocessor(
                    selected_features, numeric_transformer, dtype
                ),
            ),
            ("classifier", classifier),
        ]
    )


def inspect_fitted_one_hot_preprocessor(
    preprocessor: ColumnTransformer, expected_feature_count: int
) -> tuple[np.ndarray, list[int]]:
    transformed_names = preprocessor.get_feature_names_out()
    if len(transformed_names) != expected_feature_count:
        raise AssertionError(
            f"Expected {expected_feature_count} transformed features, "
            f"observed {len(transformed_names)}."
        )
    protocols = preprocessor.named_transformers_["protocol"].categories_[0].tolist()
    if protocols != EXPECTED_PROTOCOL_VALUES:
        raise AssertionError(f"Unexpected Protocol categories: {protocols}")
    return transformed_names, protocols


class OneHotPipelineAdapterBase:
    """Common fitted-schema and parameter behavior for sklearn pipelines."""

    def __init__(self, pipeline: Pipeline, expected_feature_count: int) -> None:
        self.pipeline = pipeline
        self.expected_transformed_count = expected_feature_count
        self.transformed_feature_count = expected_feature_count
        self.transformed_names = np.array([], dtype=object)
        self.learned_protocols: list[int] = []

    def parameters(self) -> dict[str, object]:
        parameters: dict[str, object] = {
            "expected_transformed_feature_count": self.expected_transformed_count
        }
        for name, value in self.pipeline.named_steps["classifier"].get_params().items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                parameters[f"classifier__{name}"] = value
        return parameters

    def inspect_fitted_preprocessor(self) -> None:
        self.transformed_names, self.learned_protocols = (
            inspect_fitted_one_hot_preprocessor(
                self.pipeline.named_steps["preprocessor"],
                self.expected_transformed_count,
            )
        )
        self.transformed_feature_count = len(self.transformed_names)

    def fitted_context(self) -> dict[str, object]:
        return {
            "one_hot_protocol_values": self.learned_protocols,
            "expected_transformed_feature_count": self.expected_transformed_count,
        }

    def cleanup(self) -> None:
        self.pipeline = None  # type: ignore[assignment]
