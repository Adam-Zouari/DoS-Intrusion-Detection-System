"""Loading and prediction for the frozen complete XGBoost pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import joblib
import pandas as pd

from .contracts import ModelContract, ValidatedFlow

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PredictionResult:
    label: str
    inference_latency_ms: float


class FlowPredictor:
    """Loads one trusted local pipeline once and predicts completed flows."""

    def __init__(self, model_path: Path, contract: ModelContract) -> None:
        self.model_path = model_path
        self.contract = contract
        self.model: object | None = None
        self.load_error: str | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None and self.load_error is None

    def load(self) -> None:
        try:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model artifact not found: {self.model_path}")
            model = joblib.load(self.model_path)
            selected = tuple(getattr(model, "selected_features", ()))
            if selected != self.contract.source_features:
                raise ValueError("Serialized model features do not match the frozen recipe.")
            if getattr(model, "model_key", None) != self.contract.model_key:
                raise ValueError("Serialized model family does not match the frozen recipe.")
            if int(getattr(model, "iteration_count", -1)) != self.contract.boosting_iterations:
                raise ValueError("Serialized model iteration count does not match the frozen recipe.")
            if getattr(model, "booster", None) is None:
                raise ValueError("Serialized model does not contain its trained booster.")
            self.model = model
            self.load_error = None
        except FileNotFoundError:
            LOGGER.exception("The frozen model artifact could not be found.")
            self.model = None
            self.load_error = (
                "Final model artifact not found. Set IDS_MODEL_PATH or create the "
                "artifact with the documented final-evaluation workflow."
            )
        except Exception:
            LOGGER.exception("The frozen model artifact failed to load or validate.")
            self.model = None
            self.load_error = (
                "Final model artifact could not be loaded or did not match the frozen recipe."
            )

    def predict(self, flow: ValidatedFlow) -> PredictionResult:
        if not self.ready or self.model is None:
            raise RuntimeError(self.load_error or "The model is not ready.")
        frame = pd.DataFrame(
            [[flow.features[name] for name in self.contract.source_features]],
            columns=self.contract.source_features,
        )
        started = perf_counter()
        predictions = self.model.predict(frame)
        elapsed_ms = (perf_counter() - started) * 1_000
        if len(predictions) != 1:
            raise RuntimeError("The model returned an unexpected prediction count.")
        label = str(predictions[0])
        if label not in self.contract.label_order:
            raise RuntimeError(f"The model returned an unknown label: {label!r}.")
        return PredictionResult(label=label, inference_latency_ms=float(elapsed_ms))

    def information(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "error": self.load_error,
            "family": "XGBoost",
            "task": "15-class completed-flow classification",
            "source_feature_count": len(self.contract.source_features),
            "source_features": list(self.contract.source_features),
            "transformed_feature_count": self.contract.transformed_feature_count,
            "boosting_iterations": self.contract.boosting_iterations,
            "labels": list(self.contract.label_order),
            "inference_device": "cpu",
            "model_path": str(self.model_path),
        }
