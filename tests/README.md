# Tests

The ML tests are grouped by responsibility under `tests/ml/`:

- `test_screening.py` covers experiment matrices, reporting, metrics, notebook safety, and screening commands.
- `test_tree_tuning.py` covers the search space, early stopping, verification helpers, and original-versus-tuned comparison.
- `test_final_workflow.py` covers automatic finalist selection, frozen-recipe validation, the 80% refit boundary, serialization, and final-test reuse protection.

The finalization smoke test uses synthetic data and never accesses the protected CIC-IDS-2017 test partition.
