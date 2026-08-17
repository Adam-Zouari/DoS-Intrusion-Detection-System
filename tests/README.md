# Tests

The test suite uses synthetic data and committed repository evidence. It does not require CIC-IDS-2017, local MLflow or Optuna state, a GPU, or trained model artifacts.

The ML tests are grouped by responsibility under `tests/ml/`:

- `test_screening.py` covers experiment matrices, reporting, metrics, notebook safety, and screening commands.
- `test_tree_tuning.py` covers the search space, early stopping, verification helpers, and original-versus-tuned comparison.
- `test_final_workflow.py` covers automatic finalist selection, frozen-recipe validation, the 80% refit boundary, serialization, and final-test reuse protection.
- `test_repository_evidence.py` checks documentation links, published final metrics, confusion matrices, the frozen recipe, and ignore boundaries.

The backend tests under `tests/backend/` are data-free and use a fake predictor:

- `test_contracts.py` validates the frozen 75-column request contract and prevents target leakage.
- `test_api.py` covers prediction requests, SQLite totals, every query filter, sorting, unit conversion, and live event delivery.

`tests/tools/test_replay_flows.py` confirms the synthetic replay utility keeps ground truth private.

`tests/test_cicflowmeter_bundle.py` verifies that the committed Windows archive is the exact tested build, contains its launcher, native libraries, license and updated logging runtime, and remains aligned with the integration documentation.

Run all tests from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

GitHub Actions runs the same suite on a clean hosted Python environment, then lints and builds the React dashboard. The finalization smoke test uses synthetic data and never accesses the protected CIC-IDS-2017 test partition.
