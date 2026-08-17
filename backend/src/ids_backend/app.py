"""FastAPI application for immediate completed-flow inference."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .contracts import (
    METADATA_COLUMNS,
    FlowContractError,
    load_model_contract,
    validate_flow_payload,
)
from .predictor import FlowPredictor
from .settings import ServingSettings
from .storage import FlowStorage, SORT_EXPRESSIONS, iso_utc, utc_now

TrafficScope = Literal["all", "attacks", "benign"]
SortDirection = Literal["asc", "desc"]


class EventBroker:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    async def publish(self, event: dict[str, Any]) -> None:
        for queue in tuple(self.subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def stream(self) -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self.subscribers.add(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            self.subscribers.discard(queue)


def create_app(
    settings: ServingSettings | None = None,
    *,
    predictor: Any | None = None,
    storage: FlowStorage | None = None,
) -> FastAPI:
    resolved_settings = settings or ServingSettings.from_environment()
    contract = load_model_contract(resolved_settings.project_root)
    resolved_predictor = predictor or FlowPredictor(resolved_settings.model_path, contract)
    resolved_storage = storage or FlowStorage(resolved_settings.database_path)
    broker = EventBroker()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        resolved_storage.initialize()
        if predictor is None:
            resolved_predictor.load()
        application.state.settings = resolved_settings
        application.state.contract = contract
        application.state.predictor = resolved_predictor
        application.state.storage = resolved_storage
        application.state.broker = broker
        yield

    application = FastAPI(
        title="Intrusion Detection System API",
        version="1.0.0",
        description="Immediate classification of completed CICFlowMeter-compatible flows.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.middleware("http")
    async def request_size_limit(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Content-Length must be an integer."},
                )
            if declared_size > resolved_settings.max_request_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body is too large."},
                )
        return await call_next(request)

    @application.get("/api/health")
    async def health() -> dict[str, Any]:
        information = resolved_predictor.information()
        return {
            "status": "ready" if information["ready"] else "degraded",
            "model_ready": information["ready"],
            "database_ready": True,
            "stored_flows": resolved_storage.count(),
            "source": resolved_settings.source_name,
            "model_error": information["error"],
        }

    @application.get("/api/model")
    async def model_information() -> dict[str, Any]:
        information = resolved_predictor.information()
        information.pop("model_path", None)
        information["source"] = resolved_settings.source_name
        information["metadata_columns"] = list(METADATA_COLUMNS)
        information["expected_input_columns"] = list(contract.expected_columns)
        return information

    @application.post("/api/flows", status_code=201)
    async def classify_flow(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        if not resolved_predictor.ready:
            raise HTTPException(
                status_code=503,
                detail=resolved_predictor.information()["error"] or "Model unavailable.",
            )
        try:
            flow = validate_flow_payload(payload, contract)
        except FlowContractError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        received_at = utc_now()
        try:
            result = await run_in_threadpool(resolved_predictor.predict, flow)
        except Exception as error:
            raise HTTPException(status_code=500, detail="Prediction failed.") from error
        predicted_at = utc_now()
        record_id = await run_in_threadpool(
            resolved_storage.insert, flow, result, received_at, predicted_at
        )
        response = await run_in_threadpool(resolved_storage.get_flow, record_id)
        await broker.publish(response)
        return response

    @application.get("/api/summary")
    async def summary(
        window_minutes: int = Query(60, ge=1, le=10_080),
    ) -> dict[str, Any]:
        return await run_in_threadpool(resolved_storage.summary, window_minutes)

    @application.get("/api/flows")
    async def flows(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
        traffic_scope: TrafficScope = "all",
        label: str | None = None,
        source_ip: str | None = None,
        source_port: int | None = Query(None, ge=0, le=65_535),
        destination_ip: str | None = None,
        destination_port: int | None = Query(None, ge=0, le=65_535),
        protocol: int | None = Query(None, ge=0, le=255),
        received_from: datetime | None = None,
        received_to: datetime | None = None,
        min_packets: float | None = Query(None, ge=0),
        max_packets: float | None = Query(None, ge=0),
        min_bytes: float | None = Query(None, ge=0),
        max_bytes: float | None = Query(None, ge=0),
        min_duration_ms: float | None = Query(None, ge=0),
        max_duration_ms: float | None = Query(None, ge=0),
        min_latency_ms: float | None = Query(None, ge=0),
        max_latency_ms: float | None = Query(None, ge=0),
        sort_by: str = "received_at",
        sort_direction: SortDirection = "desc",
    ) -> dict[str, Any]:
        if label is not None and label not in contract.label_order:
            raise HTTPException(status_code=422, detail=f"Unknown label: {label!r}.")
        if traffic_scope == "benign" and label not in (None, "BENIGN"):
            raise HTTPException(
                status_code=422,
                detail="A specific attack label cannot be combined with benign-only traffic.",
            )
        if sort_by not in SORT_EXPRESSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"sort_by must be one of {sorted(SORT_EXPRESSIONS)}.",
            )
        ranges = (
            ("received time", received_from, received_to),
            ("packet count", min_packets, max_packets),
            ("byte count", min_bytes, max_bytes),
            ("duration", min_duration_ms, max_duration_ms),
            ("latency", min_latency_ms, max_latency_ms),
        )
        for name, minimum, maximum in ranges:
            if minimum is not None and maximum is not None and minimum > maximum:
                raise HTTPException(
                    status_code=422, detail=f"Minimum {name} cannot exceed maximum."
                )
        received_from_text = iso_utc(received_from) if received_from else None
        received_to_text = iso_utc(received_to) if received_to else None
        return await run_in_threadpool(
            resolved_storage.list_flows,
            page=page,
            page_size=page_size,
            traffic_scope=traffic_scope,
            label=label,
            source_ip=source_ip,
            source_port=source_port,
            destination_ip=destination_ip,
            destination_port=destination_port,
            protocol=protocol,
            received_from=received_from_text,
            received_to=received_to_text,
            min_packets=min_packets,
            max_packets=max_packets,
            min_bytes=min_bytes,
            max_bytes=max_bytes,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )

    @application.get("/api/events")
    async def events() -> StreamingResponse:
        return StreamingResponse(
            broker.stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return application


app = create_app()


def serve_main() -> None:
    parser = argparse.ArgumentParser(description="Run the local flow IDS API.")
    parser.add_argument("--host", help="Bind host; defaults to IDS_HOST or 127.0.0.1.")
    parser.add_argument("--port", type=int, help="Bind port; defaults to IDS_PORT or 8000.")
    args = parser.parse_args()
    settings = ServingSettings.from_environment()
    uvicorn.run(
        app,
        host=args.host or settings.host,
        port=args.port or settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    serve_main()
