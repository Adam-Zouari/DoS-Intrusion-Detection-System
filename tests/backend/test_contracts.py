from __future__ import annotations

import json
from pathlib import Path

import pytest

from ids_backend.contracts import (
    FlowContractError,
    load_model_contract,
    validate_flow_payload,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def valid_payload() -> dict[str, object]:
    contract = load_model_contract(project_root())
    payload: dict[str, object] = {
        "Flow ID": "192.0.2.10-198.51.100.20-50000-443-6",
        "Src IP": "192.0.2.10",
        "Dst IP": "198.51.100.20",
        "Timestamp": "08/12/2026 10:00:00 AM",
    }
    payload.update({feature: 0 for feature in contract.source_features})
    payload["Src Port"] = 50_000
    payload["Dst Port"] = 443
    payload["Protocol"] = 6
    payload["Flow Duration"] = 2_500
    payload["Total Fwd Packet"] = 6
    payload["Total Bwd packets"] = 4
    payload["Total Length of Fwd Packet"] = 500
    payload["Total Length of Bwd Packet"] = 200
    payload["FWD Init Win Bytes"] = -1
    payload["Bwd Init Win Bytes"] = -1
    return payload


def test_frozen_contract_is_the_expected_75_column_request() -> None:
    contract = load_model_contract(project_root())
    assert len(contract.source_features) == 71
    assert len(contract.expected_columns) == 75
    assert contract.transformed_feature_count == 73
    assert contract.boosting_iterations == 990


@pytest.mark.parametrize("forbidden", ["Label", "ClassLabel"])
def test_ground_truth_is_rejected(forbidden: str) -> None:
    contract = load_model_contract(project_root())
    payload = valid_payload()
    payload[forbidden] = "BENIGN"
    with pytest.raises(FlowContractError, match="must not be sent"):
        validate_flow_payload(payload, contract)


def test_missing_and_unexpected_columns_are_rejected() -> None:
    contract = load_model_contract(project_root())
    payload = valid_payload()
    payload.pop("Flow IAT Mean")
    payload["mystery"] = 1
    with pytest.raises(FlowContractError, match="missing columns.*unexpected columns"):
        validate_flow_payload(payload, contract)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("Flow Duration", 0, "greater than zero"),
        ("Flow IAT Mean", -1, "cannot be negative"),
        ("Flow Bytes/s", float("inf"), "must be finite"),
        ("Src Port", 70_000, "0 to 65535"),
        ("Protocol", 6.5, "integer from 0 to 255"),
        ("FWD Init Win Bytes", -2, "between -1 and 65535"),
    ],
)
def test_invalid_numeric_values_are_rejected(
    column: str, value: object, message: str
) -> None:
    contract = load_model_contract(project_root())
    payload = valid_payload()
    payload[column] = value
    with pytest.raises(FlowContractError, match=message):
        validate_flow_payload(payload, contract)


def test_frozen_spec_contains_no_machine_specific_model_path() -> None:
    recipe = json.loads(
        (project_root() / "ml" / "final_model_spec.json").read_text(encoding="utf-8")
    )
    assert "model_path" not in recipe["model_recipe"]
