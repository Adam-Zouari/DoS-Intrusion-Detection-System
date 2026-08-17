from __future__ import annotations

import asyncio
import time
from pathlib import Path

from starlette.testclient import TestClient

from ids_ml.data import LABEL_ORDER
from ids_backend.app import EventBroker, create_app
from ids_backend.contracts import load_model_contract
from ids_backend.predictor import PredictionResult
from ids_backend.settings import ServingSettings

from .test_contracts import project_root, valid_payload


class FakePredictor:
    ready = True

    def information(self) -> dict[str, object]:
        return {
            "ready": True,
            "error": None,
            "family": "Fake XGBoost",
            "task": "15-class completed-flow classification",
            "source_feature_count": 71,
            "source_features": ["feature"] * 71,
            "transformed_feature_count": 73,
            "boosting_iterations": 990,
            "labels": LABEL_ORDER,
            "inference_device": "cpu",
            "model_path": "ignored-in-responses",
        }

    def predict(self, flow) -> PredictionResult:
        destination_port = int(flow.features["Dst Port"])
        label = {80: "DoS Hulk", 22: "SSH-Patator"}.get(destination_port, "BENIGN")
        latency = float(flow.features["Flow Duration"]) / 1_000 + 1.75
        return PredictionResult(label=label, inference_latency_ms=latency)


def make_client(tmp_path: Path) -> TestClient:
    root = project_root()
    settings = ServingSettings(
        project_root=root,
        model_path=tmp_path / "unused.joblib",
        database_path=tmp_path / "ids.sqlite",
    )
    return TestClient(create_app(settings, predictor=FakePredictor()))


def test_flow_prediction_storage_summary_and_filters(tmp_path: Path) -> None:
    payload = valid_payload()
    with make_client(tmp_path) as client:
        benign = client.post("/api/flows", json=payload)
        assert benign.status_code == 201
        assert benign.json()["prediction"] == "BENIGN"

        payload["Flow ID"] = "attack-flow"
        payload["Dst Port"] = 80
        attack = client.post("/api/flows", json=payload)
        assert attack.status_code == 201
        assert attack.json()["prediction"] == "DoS Hulk"
        assert attack.json()["source_ip"] == "192.0.2.10"
        assert attack.json()["total_packets"] == 10

        summary = client.get("/api/summary?window_minutes=60").json()
        assert summary["flow_count"] == 2
        assert summary["attack_count"] == 1
        assert summary["attack_percentage"] == 50
        assert summary["total_bytes"] == 1_400
        assert summary["total_packets"] == 20

        detections = client.get("/api/flows?traffic_scope=attacks").json()
        assert detections["total"] == 1
        assert detections["items"][0]["prediction"] == "DoS Hulk"
        assert detections["items"][0]["duration_us"] == 2_500
        assert detections["items"][0]["duration_ms"] == 2.5

        tcp = client.get("/api/flows?protocol=6&source_ip=192.0.2").json()
        assert tcp["total"] == 2
        assert tcp["items"][0]["total_bytes"] == 700
        assert tcp["items"][0]["total_packets"] == 10

        filtered = client.get(
            "/api/flows",
            params={
                "traffic_scope": "attacks",
                "label": "DoS Hulk",
                "source_ip": "192.0.2",
                "source_port": 50_000,
                "destination_ip": "198.51.100",
                "destination_port": 80,
                "protocol": 6,
                "received_from": attack.json()["received_at"],
                "received_to": attack.json()["received_at"],
                "min_packets": 10,
                "max_packets": 10,
                "min_bytes": 700,
                "max_bytes": 700,
                "min_duration_ms": 2.5,
                "max_duration_ms": 2.5,
                "min_latency_ms": 4.25,
                "max_latency_ms": 4.25,
                "sort_by": "latency",
                "sort_direction": "asc",
                "page_size": 25,
            },
        ).json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["id"] == attack.json()["id"]

        benign_only = client.get("/api/flows?traffic_scope=benign").json()
        assert benign_only["total"] == 1
        assert benign_only["items"][0]["prediction"] == "BENIGN"
        assert client.get("/api/detections").status_code == 404


def test_every_flow_filter_independently_excludes_nonmatching_rows(
    tmp_path: Path,
) -> None:
    first = valid_payload()
    second = valid_payload()
    second.update(
        {
            "Flow ID": "second",
            "Src IP": "203.0.113.7",
            "Dst IP": "192.0.2.44",
            "Src Port": 12_345,
            "Dst Port": 80,
            "Protocol": 17,
            "Flow Duration": 5_000,
            "Total Fwd Packet": 20,
            "Total Bwd packets": 10,
            "Total Length of Fwd Packet": 2_000,
            "Total Length of Bwd Packet": 1_000,
        }
    )
    third = valid_payload()
    third.update(
        {
            "Flow ID": "third",
            "Src IP": "10.0.0.1",
            "Dst IP": "10.0.0.2",
            "Src Port": 2_222,
            "Dst Port": 22,
            "Protocol": 0,
            "Flow Duration": 10_000,
            "Total Fwd Packet": 3,
            "Total Bwd packets": 2,
            "Total Length of Fwd Packet": 75,
            "Total Length of Bwd Packet": 25,
        }
    )

    with make_client(tmp_path) as client:
        responses = []
        for payload in (first, second, third):
            response = client.post("/api/flows", json=payload)
            assert response.status_code == 201
            responses.append(response.json())
            time.sleep(0.01)

        cases = [
            ({"traffic_scope": "attacks"}, {"second", "third"}),
            ({"traffic_scope": "benign"}, {first["Flow ID"]}),
            ({"label": "SSH-Patator"}, {"third"}),
            ({"source_ip": "203.0.113"}, {"second"}),
            ({"source_port": 2_222}, {"third"}),
            ({"destination_ip": "192.0.2.44"}, {"second"}),
            ({"destination_port": 22}, {"third"}),
            ({"protocol": 0}, {"third"}),
            ({"min_packets": 20}, {"second"}),
            ({"max_packets": 5}, {"third"}),
            ({"min_bytes": 1_000}, {"second"}),
            ({"max_bytes": 100}, {"third"}),
            ({"min_duration_ms": 8}, {"third"}),
            ({"max_duration_ms": 3}, {first["Flow ID"]}),
            ({"min_latency_ms": 8}, {"third"}),
            ({"max_latency_ms": 5}, {first["Flow ID"]}),
        ]
        for parameters, expected_flow_ids in cases:
            result = client.get("/api/flows", params=parameters).json()
            assert {row["flow_id"] for row in result["items"]} == expected_flow_ids
            assert result["total"] == len(expected_flow_ids)

        through_first = client.get(
            "/api/flows", params={"received_to": responses[0]["received_at"]}
        ).json()
        assert {row["flow_id"] for row in through_first["items"]} == {
            first["Flow ID"]
        }
        from_second = client.get(
            "/api/flows", params={"received_from": responses[1]["received_at"]}
        ).json()
        assert {row["flow_id"] for row in from_second["items"]} == {
            "second",
            "third",
        }

        ascending = client.get(
            "/api/flows", params={"sort_by": "bytes", "sort_direction": "asc"}
        ).json()
        assert [row["flow_id"] for row in ascending["items"]] == [
            "third",
            first["Flow ID"],
            "second",
        ]
        descending = client.get(
            "/api/flows", params={"sort_by": "bytes", "sort_direction": "desc"}
        ).json()
        assert [row["flow_id"] for row in descending["items"]] == [
            "second",
            first["Flow ID"],
            "third",
        ]
        paged = client.get("/api/flows?page=2&page_size=1").json()
        assert paged["total"] == 3
        assert len(paged["items"]) == 1
        assert paged["page"] == 2
        assert paged["page_size"] == 1


def test_invalid_requests_do_not_reach_prediction(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["Label"] = "BENIGN"
    with make_client(tmp_path) as client:
        response = client.post("/api/flows", json=payload)
        assert response.status_code == 422
        assert client.get("/api/health").json()["stored_flows"] == 0
        assert client.get("/api/flows?label=not-a-label").status_code == 422
        assert client.get("/api/flows?min_bytes=10&max_bytes=1").status_code == 422
        assert client.get("/api/flows?sort_by=unknown").status_code == 422
        assert client.get(
            "/api/flows?traffic_scope=benign&label=DoS%20Hulk"
        ).status_code == 422


def test_oversized_request_is_rejected_before_validation(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/flows",
            content=b"{}",
            headers={"content-type": "application/json", "content-length": "999999"},
        )
        assert response.status_code == 413
        assert response.json() == {"detail": "Request body is too large."}
        assert client.get("/api/health").json()["stored_flows"] == 0


def test_model_path_is_not_exposed(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        model = client.get("/api/model").json()
        assert "model_path" not in model
        assert model["labels"] == LABEL_ORDER
        assert len(model["source_features"]) == 71
        assert model["metadata_columns"] == [
            "Flow ID",
            "Src IP",
            "Dst IP",
            "Timestamp",
        ]
        assert model["expected_input_columns"] == [
            *model["metadata_columns"],
            *load_model_contract(project_root()).source_features,
        ]
        assert len(model["expected_input_columns"]) == 75


def test_missing_model_produces_degraded_health_and_no_prediction(tmp_path: Path) -> None:
    settings = ServingSettings(
        project_root=project_root(),
        model_path=tmp_path / "missing.joblib",
        database_path=tmp_path / "ids.sqlite",
    )
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health").json()
        assert health["status"] == "degraded"
        assert health["model_ready"] is False
        assert str(tmp_path) not in health["model_error"]
        assert client.post("/api/flows", json=valid_payload()).status_code == 503


def test_event_broker_delivers_one_live_event() -> None:
    async def scenario() -> None:
        broker = EventBroker()
        stream = broker.stream()
        waiting = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        await broker.publish({"id": 7, "prediction": "BENIGN"})
        message = await asyncio.wait_for(waiting, timeout=1)
        assert message.startswith('data: {"id":7')
        await stream.aclose()

    asyncio.run(scenario())
