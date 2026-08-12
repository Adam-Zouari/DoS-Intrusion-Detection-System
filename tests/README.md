# Tests

The test suite uses synthetic data and committed repository evidence. It does not require CIC-IDS-2017, local MLflow or Optuna state, a GPU, or trained model artifacts.

The ML tests are grouped by responsibility under `tests/ml/`:

- `test_screening.py` covers experiment matrices, reporting, metrics, notebook safety, and screening commands.
- `test_tree_tuning.py` covers the search space, early stopping, verification helpers, and original-versus-tuned comparison.
- `test_final_workflow.py` covers automatic finalist selection, frozen-recipe validation, the 80% refit boundary, serialization, and final-test reuse protection.
- `test_repository_evidence.py` checks documentation links, published final metrics, confusion matrices, the frozen recipe, and ignore boundaries.

Run all tests from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

GitHub Actions runs the same suite on a clean hosted Python environment. The finalization smoke test uses synthetic data and never accesses the protected CIC-IDS-2017 test partition.
