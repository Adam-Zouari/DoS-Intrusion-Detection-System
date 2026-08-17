# Flow-level IDS application

The application serves the frozen 15-class XGBoost pipeline and classifies one completed CICFlowMeter-compatible flow per request. It supports both reproducible CIC-IDS-2017 replay and direct completed-flow publishing from the bundled Windows CICFlowMeter integration.

## Architecture

```text
Synthetic CIC-IDS-2017 replay ---+
                                 +-> POST /api/flows
Live CICFlowMeter capture --------+       -> validation and XGBoost inference
                                         -> SQLite persistence and summaries
                                         -> Server-Sent Events
                                         -> React dashboard
```

Both producers send one completed flow at a time through the same strict backend contract. No CSV file exists between live capture and inference.

## Code ownership

| Location | Responsibility |
|---|---|
| [`backend/src/ids_backend`](../backend/README.md) | API, inference, validation, persistence, querying, and live events |
| [`tools/src/ids_tools`](../tools/README.md) | Synthetic completed-flow replay producer |
| [`integrations/cicflowmeter`](../integrations/cicflowmeter/README.md) | Tested Windows live-capture distribution and launcher |
| [`frontend`](../frontend/) | React dashboard and API client |
| [`ml/src/ids_ml`](../ml/src/ids_ml/README.md) | Dataset processing, model experiments, tuning, and finalization only |

## Flow contract

Each request contains the original flat CICFlowMeter row without `Label`:

- `Flow ID`, `Src IP`, `Dst IP`, and `Timestamp` are retained as log metadata.
- The frozen 71 source features are passed to the complete serialized pipeline.
- `Label`, `ClassLabel`, unknown columns, missing columns, NaN, infinity, and invalid ranges are rejected.

The backend creates its own database ID and reception timestamp. The sender does not need to create schema, event, or database identifiers.

## Start the application

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e . --no-build-isolation
ids-serve
```

The API binds to `127.0.0.1:8000` by default. In another terminal, start the dashboard:

```powershell
cd frontend
npm install
npm run dev
```

Choose one of the two supported flow producers.

### Synthetic replay

Replay completed flows from the cleaned dataset:

```powershell
ids-generate-flows --count 100 --interval-ms 500
```

Useful replay examples:

```powershell
ids-generate-flows --labels BENIGN "DoS Hulk" PortScan --count 100
ids-generate-flows --shuffle --count 1000 --interval-ms 50
ids-generate-flows --no-delay --count 10000
```

The generator keeps the dataset `Label` private, sends each flow once, and prints the expected and predicted labels only in its own terminal. The backend and dashboard never receive ground truth.

### Live CICFlowMeter

Set the source name before starting the backend:

```powershell
$env:IDS_SOURCE_NAME = "Live CICFlowMeter"
ids-serve
```

Then launch the committed Windows distribution:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\integrations\cicflowmeter\Start-CICFlowMeter-IDS.ps1
```

The launcher verifies `/api/model`, extracts the tested distribution under ignored `runtime-data/`, and starts CICFlowMeter with the configured backend endpoint. Select an active interface and begin capture. See the [live integration guide](../integrations/cicflowmeter/README.md) for Java, Npcap, permission, source-tag, and troubleshooting details.

## Runtime configuration

| Variable | Default | Purpose |
|---|---|---|
| `IDS_MODEL_PATH` | Frozen final artifact under `ml/models/` | Trusted local Joblib pipeline |
| `IDS_DATABASE_PATH` | `runtime-data/ids.sqlite` | SQLite flow and prediction store |
| `IDS_ALLOWED_ORIGINS` | Localhost and `127.0.0.1` on port 5173 | Comma-separated browser origins |
| `IDS_SOURCE_NAME` | `CIC-IDS-2017 replay` | Source description shown by the dashboard; use `Live CICFlowMeter` for capture |
| `IDS_HOST` | `127.0.0.1` | API bind address |
| `IDS_PORT` | `8000` | API port |

Model binaries, the SQLite database, and runtime logs remain local and ignored by Git. The API starts in a degraded state if the model is missing and explains the problem through `/api/health`.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/flows` | Validate, classify, and persist one completed flow |
| `GET /api/health` | Model, database, source, and stored-flow status |
| `GET /api/model` | Deployed model plus its exact feature and label contract |
| `GET /api/summary` | Correct time-windowed counts, byte/packet totals, and distributions |
| `GET /api/flows` | Unified, paginated Flow Explorer query |
| `GET /api/events` | Complete live flow records using Server-Sent Events |

All summaries are calculated in the backend. `Flow Duration` is stored in microseconds and converted explicitly to milliseconds for display. Transferred-byte and packet totals use directional totals rather than summing rate fields.

The Flow Explorer supports all/attack/benign scope, exact prediction label, source and destination IP fragments, exact endpoint ports, protocol, reception-time bounds, packet and byte ranges, duration and inference-latency ranges, sorting, direction, and page size. Filter edits are applied explicitly rather than sending a request for every keystroke. A matching SSE record is inserted into the visible first page in place, so live traffic does not trigger a table reload or loading flash.

## Scope

This is near-real-time completed-flow classification. Live detection occurs after a bidirectional flow terminates or reaches an inactivity or maximum-duration timeout. The application does not classify unfinished flows, block traffic, or prove a network is secure.
