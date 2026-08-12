# Intrusion Detection System

An end-to-end multiclass network-intrusion detection project using the official CIC-IDS-2017 flow dataset. It includes the complete research path from raw-data inspection to one protected-test evaluation, plus a local application that serves the frozen XGBoost pipeline and classifies completed flows immediately.

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
8. [Application guide](docs/APPLICATION.md) explains the inference API, replay generator, persistence, and dashboard.
9. [Test guide](tests/README.md) explains the data-free validation suite.

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

The [application guide](docs/APPLICATION.md) is the entry point for running the frozen model through the local FastAPI and React application.

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
|   |-- src/ids_ml/                # Model-development package
|   |-- reports/published/         # Versioned final diagnostic evidence
|   |-- models/                    # Ignored local model artifacts
|   `-- archive/                   # Historical notebooks and legacy experiments
|-- backend/                       # FastAPI, model inference, and SQLite runtime
|   `-- src/ids_backend/
|-- tools/                         # Synthetic completed-flow replay utility
|   `-- src/ids_tools/
|-- tests/                         # Synthetic and repository-contract tests
|-- frontend/                      # React flow dashboard
|-- docs/APPLICATION.md            # Application architecture and commands
|-- pyproject.toml
`-- LICENSE
```

## Flow-level application

The former CSV watcher and Node API have been replaced by one Python serving path using the final 15-class pipeline. A synthetic producer replays cleaned dataset rows one flow at a time, while FastAPI validates and predicts, SQLite stores results, Server-Sent Events publish updates, and React displays backend-calculated statistics.

```text
Cleaned flow row -> FastAPI -> final XGBoost pipeline -> SQLite -> live dashboard
```

See the [application guide](docs/APPLICATION.md) for setup and commands. The replay source is clearly identified in the interface and can later be replaced by CICFlowMeter sending the same flat flow contract.

## Tests

Run the data-free test suite locally:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

GitHub Actions runs the Python tests and compilation checks plus the dashboard lint and production build on a clean hosted environment after pushes and pull requests. CI does not download the dataset, train models, use a GPU, or access the protected test set.

## License and attribution

Copyright © 2026 Adam Zouari.

The source code is licensed under the [Apache License 2.0](LICENSE). CIC-IDS-2017 is not covered by this repository's license and should be cited separately; see [ml/DATASET.md](ml/DATASET.md).
