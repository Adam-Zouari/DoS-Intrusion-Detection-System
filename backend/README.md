# Backend

The `ids_backend` package owns the deployable flow-classification service. It is separate from `ids_ml`, which is reserved for dataset processing, model experiments, tuning, and finalization.

## Files

| File | Responsibility |
|---|---|
| `src/ids_backend/app.py` | FastAPI lifecycle, HTTP endpoints, request limits, CORS, and Server-Sent Events. |
| `src/ids_backend/contracts.py` | Loads the frozen model specification and validates the flat 75-column flow contract. |
| `src/ids_backend/predictor.py` | Loads, verifies, and runs the trusted final Joblib pipeline. |
| `src/ids_backend/settings.py` | Resolves the project root, model path, SQLite path, origins, host, and port. |
| `src/ids_backend/storage.py` | Persists flow results and implements summaries, filtering, sorting, and pagination. |

The package reads `ml/final_model_spec.json` as its immutable schema contract. Loading the current Joblib artifact still requires `ids_ml` to be installed because Python serialization records the original model-wrapper class path. The backend does not otherwise import training modules directly.

Run it from the repository root after installing the project:

```powershell
ids-serve
```

`GET /api/model` exposes the four metadata columns and complete expected input-column order so live producers can validate compatibility before sending flows.

See [the application guide](../docs/APPLICATION.md) for the complete workflow and API, or the [CICFlowMeter integration guide](../integrations/cicflowmeter/README.md) for live capture.
