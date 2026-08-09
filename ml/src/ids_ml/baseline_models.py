"""Scikit-learn baseline model adapters."""

from __future__ import annotations

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .data import (
    RANDOM_STATE,
    balanced_sample_weights,
    decode_labels,
    encode_labels,
    transformed_feature_count,
)
from .preprocessing import (
    OneHotPipelineAdapterBase,
    make_one_hot_pipeline,
)
from .screening import AdapterMetadata, FitDetails
from .specs import ExperimentSpec


def build_baseline_pipeline(
    spec: ExperimentSpec,
    feature_sets: dict[str, list[str]],
    smoke: bool = False,
) -> Pipeline:
    weighted = spec.weighting_mode == "balanced"
    scale_numeric = spec.model_key in {"sgd", "mlp"}
    if spec.model_key == "dummy":
        classifier = DummyClassifier(strategy="most_frequent")
    elif spec.model_key == "sgd":
        classifier = SGDClassifier(
            loss="log_loss",
            class_weight="balanced" if weighted else None,
            max_iter=3 if smoke else 1_000,
            tol=None if smoke else 1e-3,
            n_jobs=1 if smoke else -1,
            random_state=RANDOM_STATE,
        )
    elif spec.model_key == "decision_tree":
        classifier = DecisionTreeClassifier(
            max_depth=4 if smoke else 20,
            min_samples_leaf=5,
            class_weight="balanced" if weighted else None,
            random_state=RANDOM_STATE,
        )
    elif spec.model_key == "random_forest":
        classifier = RandomForestClassifier(
            n_estimators=3 if smoke else 100,
            max_depth=4 if smoke else 20,
            min_samples_leaf=2,
            max_features="sqrt",
            class_weight="balanced_subsample" if weighted else None,
            n_jobs=1 if smoke else -1,
            random_state=RANDOM_STATE,
        )
    elif spec.model_key == "hist_gradient_boosting":
        classifier = HistGradientBoostingClassifier(
            learning_rate=0.1,
            max_iter=3 if smoke else 100,
            max_leaf_nodes=7 if smoke else 31,
            l2_regularization=1.0,
            class_weight="balanced" if weighted else None,
            early_stopping=not smoke,
            random_state=RANDOM_STATE,
        )
    elif spec.model_key == "mlp":
        classifier = MLPClassifier(
            hidden_layer_sizes=(16,) if smoke else (128, 64),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            batch_size=128 if smoke else 2_048,
            learning_rate_init=1e-3,
            max_iter=1 if smoke else 50,
            early_stopping=not smoke,
            validation_fraction=0.10,
            n_iter_no_change=5,
            random_state=RANDOM_STATE,
        )
    else:
        raise ValueError(f"Unknown baseline model: {spec.model_key}")

    return make_one_hot_pipeline(
        feature_sets[spec.feature_set],
        StandardScaler() if scale_numeric else "passthrough",
        np.float64,
        classifier,
    )


def _weighting_mechanism(spec: ExperimentSpec) -> str:
    if spec.model_key == "mlp" and spec.weighting_mode == "balanced":
        return "balanced_sample_weight"
    if spec.weighting_mode == "balanced":
        return "classifier_class_weight"
    return "none"


class BaselineAdapter(OneHotPipelineAdapterBase):
    """Expose one scikit-learn configuration through the shared runner contract."""

    def __init__(
        self,
        spec: ExperimentSpec,
        feature_sets: dict[str, list[str]],
        smoke: bool = False,
    ) -> None:
        if spec.protocol_mode != "one_hot":
            raise ValueError("Scikit-learn baselines require one-hot Protocol input.")
        self.spec = spec
        expected_transformed_count = transformed_feature_count(
            len(feature_sets[spec.feature_set]), spec.protocol_mode
        )
        super().__init__(
            build_baseline_pipeline(spec, feature_sets, smoke=smoke),
            expected_transformed_count,
        )
        target_encoding = (
            "fixed_label_index" if spec.model_key == "mlp" else "original_string_labels"
        )
        self.metadata = AdapterMetadata(
            model_library="scikit-learn",
            model_library_version=sklearn.__version__,
            weighting_mechanism=_weighting_mechanism(spec),
            target_encoding=target_encoding,
            protocol_encoding=spec.protocol_mode,
            numeric_preprocessing=(
                "standard_scaler" if spec.model_key in {"sgd", "mlp"} else "passthrough"
            ),
            numeric_dtype="float64",
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> FitDetails:
        fit_parameters: dict[str, np.ndarray] = {}
        if self.spec.model_key == "mlp" and self.spec.weighting_mode == "balanced":
            fit_parameters["classifier__sample_weight"] = balanced_sample_weights(y)
        fitting_target = encode_labels(y) if self.spec.model_key == "mlp" else y
        self.pipeline.fit(X, fitting_target, **fit_parameters)

        self.inspect_fitted_preprocessor()
        return FitDetails()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        predictions = np.asarray(self.pipeline.predict(X))
        if self.spec.model_key == "mlp":
            return decode_labels(predictions.astype(np.int64))
        return predictions

    def log_diagnostics(self, X: pd.DataFrame, y: pd.Series) -> None:
        return None


def build_adapter(
    spec: ExperimentSpec,
    feature_sets: dict[str, list[str]],
    smoke: bool = False,
) -> BaselineAdapter:
    return BaselineAdapter(spec, feature_sets, smoke=smoke)
