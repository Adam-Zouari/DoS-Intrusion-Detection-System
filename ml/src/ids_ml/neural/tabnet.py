"""TabNet classifier and attention diagnostics."""

from __future__ import annotations

from time import perf_counter

import numpy as np
import pandas as pd
import torch
from pytorch_tabnet.metrics import Metric
from pytorch_tabnet.tab_model import TabNetClassifier
from sklearn.metrics import f1_score
from torch import nn

from ..data import (
    EXPECTED_PROTOCOL_VALUES,
    LABEL_ORDER,
    RANDOM_STATE,
    encode_labels,
    transformed_feature_count,
)
from ..experiment_specs import ExperimentSpec
from .preprocessing import (
    EARLY_STOPPING_PATIENCE,
    INFERENCE_BATCH_SIZE,
    MAX_EPOCHS,
    InnerSplit,
    NeuralFitResult,
    NeuralPreprocessor,
    NeuralResourceOwner,
    balanced_loss_weights,
    release_torch_memory,
    training_device,
)


class MacroF1Metric(Metric):
    def __init__(self) -> None:
        self._name = "macro_f1"
        self._maximize = True

    def __call__(self, y_true: np.ndarray, y_score: np.ndarray) -> float:
        return float(
            f1_score(
                y_true,
                np.argmax(y_score, axis=1),
                labels=np.arange(len(LABEL_ORDER)),
                average="macro",
                zero_division=0,
            )
        )


class TabNetFlowClassifier(NeuralResourceOwner):
    def __init__(
        self,
        spec: ExperimentSpec,
        selected_features: list[str],
        smoke: bool = False,
    ) -> None:
        if spec.protocol_mode != "embedding":
            raise ValueError("TabNet requires embedding-mode Protocol input.")
        self.spec = spec
        self.selected_features = list(selected_features)
        self.max_epochs = 1 if smoke else MAX_EPOCHS
        self.patience = 1 if smoke else EARLY_STOPPING_PATIENCE
        self.batch_size = 128 if smoke else 8_192
        self.virtual_batch_size = 32 if smoke else 1_024
        self.training_device = training_device()
        self.preprocessor: NeuralPreprocessor | None = None
        self.model: TabNetClassifier | None = None
        self.fit_result: NeuralFitResult | None = None

    @property
    def transformed_feature_count(self) -> int:
        return transformed_feature_count(
            len(self.selected_features), self.spec.protocol_mode
        )

    def _build_model(self, device_name: str) -> TabNetClassifier:
        return TabNetClassifier(
            n_d=32,
            n_a=32,
            n_steps=5,
            gamma=1.5,
            lambda_sparse=1e-4,
            cat_idxs=[len(self.selected_features) - 1],
            cat_dims=[len(EXPECTED_PROTOCOL_VALUES)],
            cat_emb_dim=2,
            optimizer_fn=torch.optim.Adam,
            optimizer_params={"lr": 2e-2},
            seed=RANDOM_STATE,
            verbose=0,
            device_name=device_name,
        )

    def _loss(self, targets: np.ndarray, device: torch.device) -> nn.Module:
        weights = (
            balanced_loss_weights(targets, device)
            if self.spec.weighting_mode == "balanced"
            else None
        )
        return nn.CrossEntropyLoss(weight=weights)

    @staticmethod
    def _history_frame(model: TabNetClassifier) -> pd.DataFrame:
        history = pd.DataFrame(model.history.history)
        if "loss" in history and "training_loss" not in history:
            history = history.rename(columns={"loss": "training_loss"})
        history.index = pd.RangeIndex(1, len(history) + 1, name="epoch")
        return history

    @staticmethod
    def _move_model_to_device(
        model: TabNetClassifier, device: torch.device
    ) -> None:
        """Move parameters and TabNet's unregistered attention tensors."""
        model.network.to(device)
        for module in model.network.modules():
            for name, value in vars(module).items():
                if isinstance(value, torch.Tensor):
                    setattr(module, name, value.to(device))
        if isinstance(getattr(model, "group_matrix", None), torch.Tensor):
            model.group_matrix = model.group_matrix.to(device)
        model.device = device

    def fit_with_inner_selection(
        self, X: pd.DataFrame, y: pd.Series, inner_split: InnerSplit
    ) -> NeuralFitResult:
        y_encoded = encode_labels(y)
        device_name = self.training_device.type
        selection_start = perf_counter()
        inner_preprocessor = NeuralPreprocessor(
            self.selected_features, self.spec.protocol_mode
        ).fit(X.iloc[inner_split.training_positions])
        X_training = inner_preprocessor.transform_for_tabnet(
            X.iloc[inner_split.training_positions]
        )
        X_stopping = inner_preprocessor.transform_for_tabnet(
            X.iloc[inner_split.stopping_positions]
        )
        y_training = y_encoded[inner_split.training_positions]
        y_stopping = y_encoded[inner_split.stopping_positions]
        provisional = self._build_model(device_name)
        provisional.fit(
            X_training,
            y_training,
            eval_set=[(X_stopping, y_stopping)],
            eval_name=["stopping"],
            eval_metric=[MacroF1Metric],
            loss_fn=self._loss(y_training, self.training_device),
            max_epochs=self.max_epochs,
            patience=self.patience,
            batch_size=self.batch_size,
            virtual_batch_size=self.virtual_batch_size,
            num_workers=0,
            drop_last=False,
        )
        selection_time = perf_counter() - selection_start
        selected_epochs = max(1, int(provisional.best_epoch) + 1)
        selection_history = self._history_frame(provisional)

        del provisional, X_training, X_stopping, y_training, y_stopping
        del inner_preprocessor
        release_torch_memory()

        final_training_start = perf_counter()
        self.preprocessor = NeuralPreprocessor(
            self.selected_features, self.spec.protocol_mode
        ).fit(X)
        X_final = self.preprocessor.transform_for_tabnet(X)
        self.model = self._build_model(device_name)
        self.model.fit(
            X_final,
            y_encoded,
            loss_fn=self._loss(y_encoded, self.training_device),
            max_epochs=selected_epochs,
            patience=0,
            batch_size=self.batch_size,
            virtual_batch_size=self.virtual_batch_size,
            num_workers=0,
            drop_last=False,
        )
        final_refit_time = perf_counter() - final_training_start
        final_history = self._history_frame(self.model)
        self._move_model_to_device(self.model, torch.device("cpu"))
        self.training_device = torch.device("cpu")
        del X_final, y_encoded
        release_torch_memory()

        self.fit_result = NeuralFitResult(
            selected_epochs=selected_epochs,
            epoch_selection_time_seconds=float(selection_time),
            final_refit_time_seconds=float(final_refit_time),
            selection_history=selection_history,
            final_history=final_history,
        )
        return self.fit_result

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None or self.preprocessor is None:
            raise RuntimeError("TabNet is not fitted.")
        predictions = []
        for start in range(0, len(X), INFERENCE_BATCH_SIZE):
            values = self.preprocessor.transform_for_tabnet(
                X.iloc[start : start + INFERENCE_BATCH_SIZE]
            )
            predictions.append(np.asarray(self.model.predict(values), dtype=np.int64))
        return np.concatenate(predictions)

    def attention_summary(
        self, X: pd.DataFrame, y: pd.Series
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self.model is None or self.preprocessor is None:
            raise RuntimeError("TabNet is not fitted.")
        values = self.preprocessor.transform_for_tabnet(X)
        explanations, _ = self.model.explain(values)
        feature_names = self.preprocessor.transformed_feature_names
        explanations = np.asarray(explanations)
        global_frame = pd.DataFrame(
            {
                "feature": feature_names,
                "mean_attention": explanations.mean(axis=0),
            }
        ).sort_values("mean_attention", ascending=False)
        class_rows = []
        y_values = y.to_numpy()
        for label in LABEL_ORDER:
            mask = y_values == label
            if mask.any():
                class_mean = explanations[mask].mean(axis=0)
                class_rows.extend(
                    {
                        "label": label,
                        "feature": feature,
                        "mean_attention": float(value),
                        "support": int(mask.sum()),
                    }
                    for feature, value in zip(feature_names, class_mean)
                )
        return global_frame, pd.DataFrame(class_rows)
