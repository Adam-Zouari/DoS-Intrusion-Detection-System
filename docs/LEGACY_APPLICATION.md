# Legacy application prototype

The application folders preserve an earlier binary intrusion-detection prototype. They are useful as interface and dashboard work, but they are not deployment of the final multiclass model documented under `ml/`.

## Current data flow

```text
CICFlowMeter daily CSV
    -> inference/back.py
    -> runtime-data/analyzed CSV
    -> Node API
    -> React dashboard
```

`inference/back.py` watches CICFlowMeter CSV output, selects ten flow features, loads a configured Joblib model, and writes `BENIGN` or `DoS` labels. The Node API reads those analyzed CSV files and exposes summaries consumed by the React dashboard.

## Compatibility boundary

The legacy inference path and final research pipeline have incompatible contracts:

| Concern | Legacy prototype | Final model |
|---|---|---|
| Task | Binary `BENIGN`/`DoS` | Fifteen-class classification |
| Input | Ten manually selected features | Seventy-one source features |
| Label mapping | Two hard-coded labels | Fixed fifteen-label order |
| Preprocessing | Legacy manual filtering | Serialized preprocessing pipeline |
| Validation status | Prototype only | Protected-test evaluation recorded |

The API and dashboard can still demonstrate the earlier application design, but their predictions must not be presented as results from the final XGBoost model.

## Running the prototype

Copy the configuration template and replace its example paths:

```powershell
Copy-Item config\config.example.json config\config.local.json
python inference\back.py
```

Start the API and frontend in separate terminals:

```powershell
cd api
npm install
npm run dev
```

```powershell
cd frontend
npm install
npm run dev
```

## Future integration work

A production integration would need to load the complete serialized multiclass pipeline, validate all 71 input columns, preserve the fixed feature schema, emit the fifteen model labels, and update the API and dashboard contracts. That work is intentionally outside the completed model-evaluation workflow.
