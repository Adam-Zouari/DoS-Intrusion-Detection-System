"""Shared leakage-safe preprocessing and training utilities for neural models."""

from __future__ import annotations

import gc
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, TensorDataset

from ..data import (
    EXPECTED_PROTOCOL_VALUES,
    INNER_STOPPING_SIZE,
    LABEL_ORDER,
    RANDOM_STATE,
    index_fingerprint,
)

MAX_EPOCHS = 50
EARLY_STOPPING_PATIENCE = 5
INFERENCE_BATCH_SIZE = 8_192


@dataclass(frozen=True)
class InnerSplit:
    training_positions: np.ndarray
    stopping_positions: np.ndarray
    training_fingerprint: str
    stopping_fingerprint: str


@dataclass
class NeuralFitResult:
    selected_epochs: int
    epoch_selection_time_seconds: float
    final_refit_time_seconds: float
    selection_history: pd.DataFrame
    final_history: pd.DataFrame


def set_reproducible_seed(seed: int = RANDOM_STATE) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def make_inner_split(y_fit: pd.Series) -> InnerSplit:
    all_positions = np.arange(len(y_fit), dtype=np.int64)
    training_positions, stopping_positions = train_test_split(
        all_positions,
        test_size=INNER_STOPPING_SIZE,
        random_state=RANDOM_STATE,
        stratify=y_fit,
    )
    training_index = y_fit.index[training_positions]
    stopping_index = y_fit.index[stopping_positions]
    if not training_index.intersection(stopping_index).empty:
        raise AssertionError("Neural training and stopping rows overlap.")
    for name, target in {
        "inner training": y_fit.iloc[training_positions],
        "inner stopping": y_fit.iloc[stopping_positions],
    }.items():
        missing = set(LABEL_ORDER) - set(target.unique())
        if missing:
            raise AssertionError(f"{name} is missing labels: {sorted(missing)}")
    return InnerSplit(
        training_positions=training_positions,
        stopping_positions=stopping_positions,
        training_fingerprint=index_fingerprint(training_index),
        stopping_fingerprint=index_fingerprint(stopping_index),
    )


class NeuralPreprocessor:
    """Fit numeric scaling and the fixed Protocol mapping on fitting rows only."""

    def __init__(self, selected_features: list[str], protocol_mode: str):
        if protocol_mode not in {"one_hot", "embedding"}:
            raise ValueError(f"Unknown Protocol mode: {protocol_mode}")
        self.numeric_features = [
            feature for feature in selected_features if feature != "Protocol"
        ]
        self.protocol_mode = protocol_mode
        self.scaler = StandardScaler()
        self.protocol_to_index = {
            value: index for index, value in enumerate(EXPECTED_PROTOCOL_VALUES)
        }

    def fit(self, X: pd.DataFrame) -> "NeuralPreprocessor":
        self.scaler.fit(X[self.numeric_features])
        unexpected = sorted(set(X["Protocol"].unique()) - set(EXPECTED_PROTOCOL_VALUES))
        if unexpected:
            raise AssertionError(f"Unexpected fitting Protocol categories: {unexpected}")
        return self

    def _numeric(self, X: pd.DataFrame) -> np.ndarray:
        numeric = X[self.numeric_features].to_numpy(dtype=np.float32, copy=True)
        numeric -= self.scaler.mean_.astype(np.float32)
        numeric /= self.scaler.scale_.astype(np.float32)
        return numeric

    def _protocol_indices(self, X: pd.DataFrame) -> np.ndarray:
        mapped = X["Protocol"].map(self.protocol_to_index)
        if mapped.isna().any():
            unknown = sorted(X.loc[mapped.isna(), "Protocol"].unique().tolist())
            raise ValueError(f"Unknown Protocol values: {unknown}")
        return mapped.to_numpy(dtype=np.int64).reshape(-1, 1)

    def transform(
        self, X: pd.DataFrame
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        numeric = self._numeric(X)
        protocol = self._protocol_indices(X)
        if self.protocol_mode == "embedding":
            return numeric, protocol
        one_hot = np.eye(len(EXPECTED_PROTOCOL_VALUES), dtype=np.float32)[
            protocol.ravel()
        ]
        return np.concatenate([numeric, one_hot], axis=1, dtype=np.float32)

    def transform_for_tabnet(self, X: pd.DataFrame) -> np.ndarray:
        transformed = self.transform(X)
        if not isinstance(transformed, tuple):
            raise AssertionError("TabNet requires embedding-mode preprocessing.")
        numeric, protocol = transformed
        return np.column_stack(
            [numeric, protocol.astype(np.float32, copy=False)]
        ).astype(np.float32, copy=False)

    @property
    def transformed_feature_names(self) -> list[str]:
        if self.protocol_mode == "one_hot":
            return self.numeric_features + [
                f"Protocol_{value}" for value in EXPECTED_PROTOCOL_VALUES
            ]
        return self.numeric_features + ["Protocol"]


def balanced_loss_weights(
    y_encoded: np.ndarray, device: torch.device
) -> torch.Tensor:
    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.arange(len(LABEL_ORDER)),
        y=y_encoded,
    )
    return torch.as_tensor(weights, dtype=torch.float32, device=device)


def training_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def release_torch_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class NeuralResourceOwner:
    """Common cleanup contract for fitted neural classifiers."""

    def cleanup(self) -> None:
        self.model = None
        self.preprocessor = None
        self.fit_result = None
        release_torch_memory()


def make_loader(
    arrays: np.ndarray | tuple[np.ndarray, np.ndarray],
    targets: np.ndarray | None,
    batch_size: int,
    shuffle: bool,
) -> DataLoader:
    if isinstance(arrays, tuple):
        continuous, categorical = arrays
        tensors = [torch.from_numpy(continuous), torch.from_numpy(categorical)]
    else:
        tensors = [torch.from_numpy(arrays)]
    if targets is not None:
        tensors.append(torch.from_numpy(targets))
    generator = torch.Generator().manual_seed(RANDOM_STATE)
    return DataLoader(
        TensorDataset(*tensors),
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
        generator=generator if shuffle else None,
    )
