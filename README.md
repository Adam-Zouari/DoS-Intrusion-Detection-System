# Intrusion Detection System

An end-to-end machine-learning research project for multiclass network-intrusion detection using the official CIC-IDS-2017 flow dataset. The repository documents the full path from raw-data inspection to a frozen XGBoost recipe and one protected-test evaluation.

The final model achieved:

- **0.9602 macro F1** across 15 classes;
- **99.991% binary attack recall**;
- **13.31 ms CPU p99 complete-pipeline latency**; and
- approximately **51,090 flows per second** in the recorded batch-throughput test.

See the [complete results and decision record](ml/RESULTS.md) for baseline comparisons, tuning evidence, class-level results, and limitations.

## Review the project

The project is intended to be read in this order:

1. [Dataset and feature reference](ml/DATASET.md) explains CIC-IDS-2017, CICFlowMeter flows, and every source column.
2. [Data exploration](ml/notebooks/01_data_exploration.ipynb) investigates and cleans the merged raw dataset.
3. [Feature engineering](ml/notebooks/02_feature_engineering.ipynb) defines eligible features, creates the protected split, and records feature-selection diagnostics.
4. [Model screening analysis](ml/notebooks/03_model_screening_analysis.ipynb) compares the completed baseline and tree rounds and the eight completed neural configurations.
5. [Results](ml/RESULTS.md) follows the evidence from screening through tuning, stability checks, model selection, and final testing.
6. [Frozen model specification](ml/final_model_spec.json) records the selected preprocessing and XGBoost recipe.
7. [ML implementation guide](ml/src/ids_ml/README.md) explains the reusable package structure.
8. [Test guide](tests/README.md) explains the data-free validation suite.

```text
Merged CIC-IDS-2017 CSV
    -> exploration and cleaning
    -> cleaned Parquet dataset
    -> feature preparation and protected split
    -> baseline, tree, and neural screening
    -> XGBoost and LightGBM tuning
    -> outer-validation selection
    -> frozen XGBoost recipe
    -> complete 80% development refit
    -> one protected 20% test evaluation
```

## Reproduce the work

The detailed [machine-learning workflow guide](ml/README.md) gives the environment setup and commands in execution order. The raw and processed datasets, local MLflow and Optuna stores, generated reports, and model binaries are intentionally excluded from Git.

The committed notebooks retain their outputs, and [published result artifacts](ml/reports/published/README.md) expose the final diagnostics without requiring the local tracking database.

## Repository layout

```text
.
|-- ml/
|   |-- DATASET.md                 # Dataset provenance and feature dictionary
|   |-- METRICS.md                 # Evaluation metric definitions
|   |-- RESULTS.md                 # Decision evidence and final results
|   |-- final_model_spec.json      # Frozen final XGBoost recipe
|   |-- data/                      # Ignored raw and processed datasets
|   |-- notebooks/
|   |   |-- 01_data_exploration.ipynb
|   |   |-- 02_feature_engineering.ipynb
|   |   `-- 03_model_screening_analysis.ipynb
|   |-- src/ids_ml/                # Installable experiment package
|   |-- reports/published/         # Versioned final diagnostic evidence
|   |-- models/                    # Ignored local model artifacts
|   `-- archive/                   # Historical notebooks and legacy experiments
|-- tests/                         # Synthetic and repository-contract tests
|-- inference/                     # Legacy binary inference prototype
|-- api/                           # Legacy dashboard API
|-- frontend/                      # Legacy React dashboard
|-- docs/LEGACY_APPLICATION.md     # Prototype status and data flow
|-- pyproject.toml
`-- LICENSE
```

## Legacy application prototype

The `inference/`, `api/`, and `frontend/` folders belong to an older binary `BENIGN`/`DoS` prototype. They are retained as application-design evidence but are **not connected to the final 15-class XGBoost pipeline**. See [Legacy application prototype](docs/LEGACY_APPLICATION.md) before running or presenting these components.

## Tests

Run the data-free test suite locally:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

GitHub Actions runs the same tests on a clean hosted environment after pushes and pull requests. CI does not download the dataset, train models, use a GPU, or access the protected test set.

## License and attribution

Copyright © 2026 Adam Zouari.

The source code is licensed under the [Apache License 2.0](LICENSE). CIC-IDS-2017 is not covered by this repository's license and should be cited separately; see [ml/DATASET.md](ml/DATASET.md).
