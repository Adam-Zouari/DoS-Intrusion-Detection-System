# Application tools

The `ids_tools` package contains local utilities that exercise the application but are neither model-training code nor backend runtime code.

| File | Responsibility |
|---|---|
| `src/ids_tools/replay_flows.py` | Streams cleaned CIC-IDS-2017 rows individually to the backend while keeping ground-truth labels private. |

Run the replay producer after starting the backend:

```powershell
ids-generate-flows --count 100 --interval-ms 500
```

This producer remains the reproducible, data-driven demonstration path. The [bundled CICFlowMeter integration](../integrations/cicflowmeter/README.md) provides the corresponding live-capture path; both send one completed flow at a time through the same backend contract.
