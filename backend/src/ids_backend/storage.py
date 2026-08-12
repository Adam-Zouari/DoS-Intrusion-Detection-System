"""Small SQLite persistence and server-side flow analytics."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .contracts import ValidatedFlow
from .predictor import PredictionResult

SORT_EXPRESSIONS = {
    "received_at": "received_at",
    "prediction": "prediction",
    "source_ip": "source_ip",
    "source_port": "source_port",
    "destination_ip": "destination_ip",
    "destination_port": "destination_port",
    "protocol": "protocol",
    "packets": "forward_packets + backward_packets",
    "bytes": "forward_bytes + backward_bytes",
    "duration": "duration_us",
    "latency": "inference_latency_ms",
}


def _contains_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def protocol_name(value: int) -> str:
    return {0: "HOPOPT", 1: "ICMP", 6: "TCP", 17: "UDP"}.get(
        value, f"Protocol {value}"
    )


class FlowStorage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id TEXT NOT NULL,
                    source_ip TEXT NOT NULL,
                    source_port INTEGER NOT NULL,
                    destination_ip TEXT NOT NULL,
                    destination_port INTEGER NOT NULL,
                    protocol INTEGER NOT NULL,
                    flow_timestamp TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    predicted_at TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    inference_latency_ms REAL NOT NULL,
                    duration_us REAL NOT NULL,
                    forward_packets REAL NOT NULL,
                    backward_packets REAL NOT NULL,
                    forward_bytes REAL NOT NULL,
                    backward_bytes REAL NOT NULL,
                    features_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_flows_received_at ON flows(received_at);
                CREATE INDEX IF NOT EXISTS idx_flows_prediction ON flows(prediction);
                CREATE INDEX IF NOT EXISTS idx_flows_source_ip ON flows(source_ip);
                CREATE INDEX IF NOT EXISTS idx_flows_destination_ip ON flows(destination_ip);
                """
            )

    def insert(
        self,
        flow: ValidatedFlow,
        result: PredictionResult,
        received_at: datetime,
        predicted_at: datetime,
    ) -> int:
        features = flow.features
        values = (
            flow.metadata["Flow ID"],
            flow.metadata["Src IP"],
            int(features["Src Port"]),
            flow.metadata["Dst IP"],
            int(features["Dst Port"]),
            int(features["Protocol"]),
            flow.metadata["Timestamp"],
            iso_utc(received_at),
            iso_utc(predicted_at),
            result.label,
            result.inference_latency_ms,
            float(features["Flow Duration"]),
            float(features["Total Fwd Packet"]),
            float(features["Total Bwd packets"]),
            float(features["Total Length of Fwd Packet"]),
            float(features["Total Length of Bwd Packet"]),
            json.dumps(features, separators=(",", ":"), sort_keys=False),
        )
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO flows (
                    flow_id, source_ip, source_port, destination_ip,
                    destination_port, protocol, flow_timestamp, received_at,
                    predicted_at, prediction, inference_latency_ms, duration_us,
                    forward_packets, backward_packets, forward_bytes,
                    backward_bytes, features_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return int(cursor.lastrowid)

    @staticmethod
    def _public_row(row: sqlite3.Row) -> dict[str, Any]:
        total_packets = float(row["forward_packets"] + row["backward_packets"])
        total_bytes = float(row["forward_bytes"] + row["backward_bytes"])
        return {
            "id": int(row["id"]),
            "flow_id": row["flow_id"],
            "source_ip": row["source_ip"],
            "source_port": int(row["source_port"]),
            "destination_ip": row["destination_ip"],
            "destination_port": int(row["destination_port"]),
            "protocol": int(row["protocol"]),
            "protocol_name": protocol_name(int(row["protocol"])),
            "flow_timestamp": row["flow_timestamp"],
            "received_at": row["received_at"],
            "predicted_at": row["predicted_at"],
            "prediction": row["prediction"],
            "inference_latency_ms": float(row["inference_latency_ms"]),
            "duration_us": float(row["duration_us"]),
            "duration_ms": float(row["duration_us"]) / 1_000.0,
            "total_packets": total_packets,
            "total_bytes": total_bytes,
        }

    def list_flows(
        self,
        *,
        page: int,
        page_size: int,
        traffic_scope: str = "all",
        label: str | None = None,
        source_ip: str | None = None,
        source_port: int | None = None,
        destination_ip: str | None = None,
        destination_port: int | None = None,
        protocol: int | None = None,
        received_from: str | None = None,
        received_to: str | None = None,
        min_packets: float | None = None,
        max_packets: float | None = None,
        min_bytes: float | None = None,
        max_bytes: float | None = None,
        min_duration_ms: float | None = None,
        max_duration_ms: float | None = None,
        min_latency_ms: float | None = None,
        max_latency_ms: float | None = None,
        sort_by: str = "received_at",
        sort_direction: str = "desc",
    ) -> dict[str, Any]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if traffic_scope == "attacks":
            clauses.append("prediction <> 'BENIGN'")
        elif traffic_scope == "benign":
            clauses.append("prediction = 'BENIGN'")
        if label:
            clauses.append("prediction = ?")
            parameters.append(label)
        if source_ip:
            clauses.append("source_ip LIKE ? ESCAPE '\\'")
            parameters.append(_contains_pattern(source_ip))
        if source_port is not None:
            clauses.append("source_port = ?")
            parameters.append(source_port)
        if destination_ip:
            clauses.append("destination_ip LIKE ? ESCAPE '\\'")
            parameters.append(_contains_pattern(destination_ip))
        if destination_port is not None:
            clauses.append("destination_port = ?")
            parameters.append(destination_port)
        if protocol is not None:
            clauses.append("protocol = ?")
            parameters.append(protocol)
        range_filters = (
            ("received_at >= ?", received_from),
            ("received_at <= ?", received_to),
            ("forward_packets + backward_packets >= ?", min_packets),
            ("forward_packets + backward_packets <= ?", max_packets),
            ("forward_bytes + backward_bytes >= ?", min_bytes),
            ("forward_bytes + backward_bytes <= ?", max_bytes),
            ("duration_us >= ?", None if min_duration_ms is None else min_duration_ms * 1_000),
            ("duration_us <= ?", None if max_duration_ms is None else max_duration_ms * 1_000),
            ("inference_latency_ms >= ?", min_latency_ms),
            ("inference_latency_ms <= ?", max_latency_ms),
        )
        for clause, value in range_filters:
            if value is not None:
                clauses.append(clause)
                parameters.append(value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        sort_expression = SORT_EXPRESSIONS[sort_by]
        direction = sort_direction.upper()
        with self.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM flows {where}", parameters
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM flows {where}
                ORDER BY {sort_expression} {direction}, id {direction}
                LIMIT ? OFFSET ?
                """,
                [*parameters, page_size, offset],
            ).fetchall()
        return {
            "items": [self._public_row(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_flow(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM flows WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise LookupError(f"Stored flow {record_id} was not found.")
        return self._public_row(row)

    def summary(self, window_minutes: int) -> dict[str, Any]:
        cutoff = iso_utc(utc_now() - timedelta(minutes=window_minutes))
        with self.connect() as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS flow_count,
                       SUM(CASE WHEN prediction <> 'BENIGN' THEN 1 ELSE 0 END) AS attack_count,
                       COALESCE(SUM(forward_bytes + backward_bytes), 0) AS total_bytes,
                       COALESCE(SUM(forward_packets + backward_packets), 0) AS total_packets,
                       COALESCE(AVG(inference_latency_ms), 0) AS average_latency_ms,
                       MAX(received_at) AS last_flow_at
                FROM flows WHERE received_at >= ?
                """,
                (cutoff,),
            ).fetchone()
            labels = connection.execute(
                """
                SELECT prediction AS label, COUNT(*) AS count
                FROM flows WHERE received_at >= ?
                GROUP BY prediction ORDER BY count DESC, label
                """,
                (cutoff,),
            ).fetchall()
            protocols = connection.execute(
                """
                SELECT protocol, COUNT(*) AS count
                FROM flows WHERE received_at >= ?
                GROUP BY protocol ORDER BY count DESC, protocol
                """,
                (cutoff,),
            ).fetchall()
            timeline = connection.execute(
                """
                SELECT substr(received_at, 1, 16) || ':00Z' AS bucket,
                       COUNT(*) AS flows,
                       SUM(CASE WHEN prediction <> 'BENIGN' THEN 1 ELSE 0 END) AS attacks,
                       SUM(forward_bytes + backward_bytes) AS bytes,
                       SUM(forward_packets + backward_packets) AS packets
                FROM flows WHERE received_at >= ?
                GROUP BY bucket ORDER BY bucket
                """,
                (cutoff,),
            ).fetchall()
        flow_count = int(totals["flow_count"] or 0)
        attack_count = int(totals["attack_count"] or 0)
        return {
            "window_minutes": window_minutes,
            "flow_count": flow_count,
            "attack_count": attack_count,
            "attack_percentage": (attack_count / flow_count * 100) if flow_count else 0.0,
            "total_bytes": float(totals["total_bytes"] or 0),
            "total_packets": float(totals["total_packets"] or 0),
            "average_inference_latency_ms": float(totals["average_latency_ms"] or 0),
            "last_flow_at": totals["last_flow_at"],
            "labels": [dict(row) for row in labels],
            "protocols": [
                {
                    "protocol": int(row["protocol"]),
                    "name": protocol_name(int(row["protocol"])),
                    "count": int(row["count"]),
                }
                for row in protocols
            ],
            "timeline": [dict(row) for row in timeline],
        }

    def count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM flows").fetchone()[0])
