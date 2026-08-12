"""Canonical incoming-flow and frozen-model contracts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

METADATA_COLUMNS = ("Flow ID", "Src IP", "Dst IP", "Timestamp")
FORBIDDEN_INPUT_COLUMNS = frozenset({"Label", "ClassLabel"})
WINDOW_COLUMNS = frozenset({"FWD Init Win Bytes", "Bwd Init Win Bytes"})
PORT_COLUMNS = frozenset({"Src Port", "Dst Port"})


class FlowContractError(ValueError):
    """Raised when a flow does not match the deployed model contract."""


@dataclass(frozen=True)
class ModelContract:
    source_features: tuple[str, ...]
    label_order: tuple[str, ...]
    transformed_feature_count: int
    boosting_iterations: int
    model_key: str
    specification_path: Path

    @property
    def expected_columns(self) -> tuple[str, ...]:
        return (*METADATA_COLUMNS, *self.source_features)


@dataclass(frozen=True)
class ValidatedFlow:
    metadata: dict[str, str]
    features: dict[str, int | float]

    @property
    def flow_id(self) -> str:
        return self.metadata["Flow ID"]


def load_model_contract(project_root: Path) -> ModelContract:
    specification_path = project_root / "ml" / "final_model_spec.json"
    if not specification_path.exists():
        raise FileNotFoundError(f"Frozen model specification not found: {specification_path}")
    recipe = json.loads(specification_path.read_text(encoding="utf-8"))
    model = recipe.get("model_recipe", {})
    features = tuple(model.get("source_features", []))
    labels = tuple(model.get("label_order", []))
    if len(features) != 71 or len(set(features)) != 71:
        raise FlowContractError("The frozen specification must contain 71 unique features.")
    if features[:3] != ("Src Port", "Dst Port", "Protocol"):
        raise FlowContractError("The frozen feature order is not the expected all_71 schema.")
    if len(labels) != 15 or len(set(labels)) != 15 or labels[0] != "BENIGN":
        raise FlowContractError("The frozen specification must contain 15 unique labels with BENIGN first.")
    if model.get("feature_set") != "all_71":
        raise FlowContractError("The deployed model must use the frozen all_71 feature set.")
    return ModelContract(
        source_features=features,
        label_order=labels,
        transformed_feature_count=int(model["transformed_feature_count"]),
        boosting_iterations=int(model["boosting_iterations"]),
        model_key=str(model["model_key"]),
        specification_path=specification_path,
    )


def _finite_number(column: str, value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise FlowContractError(f"{column!r} must be a numeric value.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise FlowContractError(f"{column!r} must be finite.")

    if column in PORT_COLUMNS:
        if not numeric.is_integer() or not 0 <= numeric <= 65_535:
            raise FlowContractError(f"{column!r} must be an integer from 0 to 65535.")
        return int(numeric)
    if column == "Protocol":
        if not numeric.is_integer() or not 0 <= numeric <= 255:
            raise FlowContractError("'Protocol' must be an integer from 0 to 255.")
        return int(numeric)
    if column in WINDOW_COLUMNS:
        if numeric < -1 or numeric > 65_535:
            raise FlowContractError(f"{column!r} must be between -1 and 65535.")
    elif column == "Flow Duration":
        if numeric <= 0:
            raise FlowContractError("'Flow Duration' must be greater than zero.")
    elif numeric < 0:
        raise FlowContractError(f"{column!r} cannot be negative.")
    return int(numeric) if numeric.is_integer() else numeric


def validate_flow_payload(
    payload: Mapping[str, Any], contract: ModelContract
) -> ValidatedFlow:
    if not isinstance(payload, Mapping):
        raise FlowContractError("The request body must be one flat JSON object.")
    forbidden = sorted(FORBIDDEN_INPUT_COLUMNS.intersection(payload))
    if forbidden:
        raise FlowContractError(
            f"Ground-truth columns must not be sent to inference: {forbidden}."
        )
    expected = set(contract.expected_columns)
    observed = set(payload)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    problems: list[str] = []
    if missing:
        problems.append(f"missing columns: {missing}")
    if unexpected:
        problems.append(f"unexpected columns: {unexpected}")
    if problems:
        raise FlowContractError("; ".join(problems))

    metadata: dict[str, str] = {}
    for column in METADATA_COLUMNS:
        value = payload[column]
        if not isinstance(value, str) or not value.strip():
            raise FlowContractError(f"{column!r} must be a non-empty string.")
        metadata[column] = value.strip()
    features = {
        column: _finite_number(column, payload[column])
        for column in contract.source_features
    }
    return ValidatedFlow(metadata=metadata, features=features)
