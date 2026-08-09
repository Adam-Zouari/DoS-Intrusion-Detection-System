"""Neural screening adapters and MLflow diagnostics."""

from __future__ import annotations

import importlib.metadata
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd

from ..data import RANDOM_STATE, class_preserving_sample, decode_labels
from ..evaluation import log_line_figure, log_table_artifact
from ..screening import AdapterMetadata, FitDetails
from ..specs import ExperimentSpec
from .preprocessing import NeuralFitResult, make_inner_split
from .rtdl import RTDLFlowClassifier
from .tabnet import TabNetFlowClassifier

NeuralClassifier = RTDLFlowClassifier | TabNetFlowClassifier


def _library(spec: ExperimentSpec) -> tuple[str, str]:
    package = (
        "pytorch-tabnet"
        if spec.model_key == "tabnet"
        else "rtdl-revisiting-models"
    )
    return package, importlib.metadata.version(package)


def _log_neural_history(fit_result: NeuralFitResult) -> None:
    log_table_artifact(
        fit_result.selection_history,
        "epoch_selection_history.csv",
        "training",
    )
    log_line_figure(
        fit_result.selection_history,
        ["training_loss", "stopping_macro_f1"],
        "epoch_selection_curves.png",
        "Inner stopping-set epoch selection",
        "training",
    )
    log_table_artifact(
        fit_result.final_history,
        "final_refit_history.csv",
        "training",
    )


def _log_tabnet_attention(
    classifier: TabNetFlowClassifier,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
) -> None:
    X_sample, y_sample = class_preserving_sample(
        X_validation,
        y_validation,
        maximum_rows_per_class=2_000,
        random_state=RANDOM_STATE,
    )
    global_frame, class_frame = classifier.attention_summary(X_sample, y_sample)
    log_table_artifact(
        global_frame.set_index("feature"),
        "tabnet_global_attention.csv",
        "diagnostics",
    )
    log_table_artifact(
        class_frame.set_index(["label", "feature"]),
        "tabnet_class_attention.csv",
        "diagnostics",
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "tabnet_global_attention_top30.png"
        top = global_frame.head(30).sort_values("mean_attention")
        figure, axis = plt.subplots(figsize=(11, 9))
        axis.barh(top["feature"], top["mean_attention"])
        axis.set_title("TabNet global attention: top 30 features")
        axis.set_xlabel("Mean attention on the diagnostic sample")
        figure.tight_layout()
        figure.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(figure)
        mlflow.log_artifact(path, artifact_path="diagnostics")


class NeuralAdapter:
    """Expose one neural configuration through the shared runner contract."""

    def __init__(
        self,
        spec: ExperimentSpec,
        feature_sets: dict[str, list[str]],
        smoke: bool = False,
    ) -> None:
        self.spec = spec
        selected_features = feature_sets[spec.feature_set]
        if spec.model_key == "tabnet":
            self.classifier: NeuralClassifier = TabNetFlowClassifier(
                spec, selected_features, smoke=smoke
            )
        else:
            self.classifier = RTDLFlowClassifier(
                spec, selected_features, smoke=smoke
            )
        self.transformed_feature_count = self.classifier.transformed_feature_count
        self.fit_result: NeuralFitResult | None = None
        self.inner_training_rows = 0
        self.inner_stopping_rows = 0
        self.inner_training_fingerprint = ""
        self.inner_stopping_fingerprint = ""
        library, version = _library(spec)
        protocol_encoding = (
            "learned_embedding" if spec.protocol_mode == "embedding" else "one_hot"
        )
        self.metadata = AdapterMetadata(
            model_library=library,
            model_library_version=version,
            weighting_mechanism=(
                "balanced_cross_entropy"
                if spec.weighting_mode == "balanced"
                else "none"
            ),
            target_encoding="fixed_label_index",
            protocol_encoding=protocol_encoding,
            numeric_preprocessing="standard_scaler",
            numeric_dtype="float32",
            training_device=self.classifier.training_device.type,
            inference_device="cpu",
        )

    def parameters(self) -> dict[str, object]:
        parameters: dict[str, object] = {
            "transformed_feature_count": self.transformed_feature_count,
            "max_epochs": self.classifier.max_epochs,
            "early_stopping_metric": "inner_macro_f1",
            "early_stopping_patience": self.classifier.patience,
            "batch_size": self.classifier.batch_size,
        }
        virtual_batch_size = getattr(self.classifier, "virtual_batch_size", None)
        if virtual_batch_size is not None:
            parameters["virtual_batch_size"] = virtual_batch_size
        return parameters

    def fit(self, X: pd.DataFrame, y: pd.Series) -> FitDetails:
        inner_split = make_inner_split(y)
        self.inner_training_rows = len(inner_split.training_positions)
        self.inner_stopping_rows = len(inner_split.stopping_positions)
        self.inner_training_fingerprint = inner_split.training_fingerprint
        self.inner_stopping_fingerprint = inner_split.stopping_fingerprint
        self.fit_result = self.classifier.fit_with_inner_selection(X, y, inner_split)
        return FitDetails(
            metrics={
                "epoch_selection_time_seconds": (
                    self.fit_result.epoch_selection_time_seconds
                ),
                "final_refit_time_seconds": self.fit_result.final_refit_time_seconds,
                "selected_epochs": float(self.fit_result.selected_epochs),
            }
        )

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return decode_labels(self.classifier.predict(X))

    def fitted_context(self) -> dict[str, object]:
        return {
            "selected_epochs": (
                self.fit_result.selected_epochs if self.fit_result else None
            ),
            "inner_training_rows": self.inner_training_rows,
            "inner_stopping_rows": self.inner_stopping_rows,
            "inner_training_fingerprint": self.inner_training_fingerprint,
            "inner_stopping_fingerprint": self.inner_stopping_fingerprint,
        }

    def log_diagnostics(self, X: pd.DataFrame, y: pd.Series) -> None:
        if self.fit_result is None:
            raise RuntimeError("Cannot log diagnostics before fitting.")
        _log_neural_history(self.fit_result)
        if isinstance(self.classifier, TabNetFlowClassifier):
            _log_tabnet_attention(self.classifier, X, y)

    def cleanup(self) -> None:
        self.classifier.cleanup()
        self.fit_result = None


def build_adapter(
    spec: ExperimentSpec,
    feature_sets: dict[str, list[str]],
    smoke: bool = False,
) -> NeuralAdapter:
    return NeuralAdapter(spec, feature_sets, smoke=smoke)
