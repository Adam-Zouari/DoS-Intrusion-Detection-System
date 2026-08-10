# Machine-learning workspace

This directory contains the CIC-IDS-2017 research and validation workflow. Model screening is executed through installed command-line entry points, results are stored in MLflow, and notebooks are used for exploration and comparison.

## Layout

- `data/raw/` contains the immutable merged source dataset locally.
- `data/processed/` contains the cleaned parquet dataset produced by Notebook 1.
- `src/ids_ml/` contains the installable experiment package described below.
- `notebooks/01_data_exploration.ipynb` explores and cleans the source dataset.
- `notebooks/02_feature_engineering.ipynb` documents the feature preparation decisions.
- `notebooks/03_model_comparison.ipynb` reads and compares MLflow results without training.
- `archive/experiments/` preserves completed historical training notebooks.
- `models/` and `reports/generated/` contain ignored local outputs.

## Source package reference

All reusable experiment code lives under `src/ids_ml/`. Training commands and notebooks import these modules instead of redefining their logic.

| File | Role |
|---|---|
| `src/ids_ml/__init__.py` | Marks `ids_ml` as a Python package. It intentionally performs no imports or initialization, keeping package imports lightweight. |
| `src/ids_ml/specs.py` | The single source of truth for experiment names, screening rounds, model families, feature sets, weighting modes, Protocol handling, candidate roles, and configuration keys. |
| `src/ids_ml/data.py` | Locates and validates the cleaned parquet dataset; defines labels, feature exclusions, hashes, dataset and split contracts; recreates the fixed fit, validation, and protected-test partitions; and provides label encoding, class-preserving sampling, and weight helpers. |
| `src/ids_ml/preprocessing.py` | Shared preprocessing for scikit-learn and tree pipelines: numeric transformation, fixed one-hot encoding of `Protocol`, transformed-schema validation, parameter extraction, and common fitted-pipeline cleanup. |
| `src/ids_ml/evaluation.py` | Calculates the metrics defined in `ml/METRICS.md`, constructs per-class reports and confusion matrices, creates fixed timing inputs, measures complete-pipeline latency and throughput, and logs shared evaluation artifacts. |
| `src/ids_ml/screening.py` | Implements the single MLflow validation lifecycle used by every model: create the run, log common metadata, fit, evaluate, time inference, log artifacts and diagnostics, handle cleanup, and return the result record. It also provides the common smoke-fit procedure. |
| `src/ids_ml/baseline_models.py` | Defines the Dummy, SGD, Decision Tree, Random Forest, Histogram Gradient Boosting, and scikit-learn MLP baseline configurations and adapts them to the shared screening lifecycle. |
| `src/ids_ml/tree_models.py` | Defines ExtraTrees, XGBoost, and LightGBM screening configurations, their weighting behavior, target encoding, and tree feature-importance artifacts. |
| `src/ids_ml/tracking.py` | Configures the local SQLite MLflow tracking URI and creates or selects experiments with the local artifact directory. |
| `src/ids_ml/reporting.py` | Queries MLflow, normalizes current and legacy run records, selects compatible dataset/split contracts, removes duplicate configurations, builds coverage and leaderboard tables, compares feature and weighting choices, creates candidate shortlists, and downloads result artifacts. |
| `src/ids_ml/workflows.py` | Implements the four installed commands. It parses filters, skips completed configurations, loads full data only when work remains, runs smoke checks, continues after isolated failures, invokes the shared screening lifecycle, and prints or saves leaderboards. |
| `src/ids_ml/neural/__init__.py` | Marks the neural implementation directory as a subpackage without triggering PyTorch or model-library imports. |
| `src/ids_ml/neural/preprocessing.py` | Owns neural-only shared behavior: reproducible seeds, the leakage-safe inner stopping split, numeric scaling, Protocol conversion, mini-batch loaders, balanced loss weights, training-device selection, fit-result records, and memory cleanup. |
| `src/ids_ml/neural/rtdl.py` | Implements the RTDL MLP, ResNet, and FT-Transformer training, macro-F1 epoch selection, full-fit refitting, CPU inference, and prediction batching. |
| `src/ids_ml/neural/tabnet.py` | Implements TabNet training and refitting, its macro-F1 stopping metric, CPU prediction, and global and class-level attention summaries. |
| `src/ids_ml/neural/experiments.py` | Connects the neural classifiers to the shared screening interface and logs selected epochs, training histories, timing details, and TabNet attention diagnostics. |

## Environment setup

From the repository root, activate the project virtual environment and install the project in editable mode:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Editable installation makes the `ids_ml` package available to scripts and notebook kernels while keeping source edits immediately visible.

### NVIDIA GPU setup

On a CUDA-capable Windows machine, install the official CUDA build of PyTorch after the editable project installation:

```powershell
python -m pip install --force-reinstall -r ml/requirements-gpu.txt
```

The separate requirements file is necessary because standard project dependencies cannot declare pip's PyTorch CUDA package index. Verify the environment before neural screening:

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Neural training automatically uses CUDA when available. Inference latency and throughput are still measured on CPU for a consistent deployment comparison.

## Run experiments

Each experiment command smoke-fits model families that are about to run. Successful configurations already stored for the same dataset and split fingerprints are skipped unless `--rerun` is supplied.

```powershell
ids-run-baselines
ids-run-trees
ids-run-neural
```

Restrict a run to particular configurations when required:

```powershell
ids-run-trees --models xgboost lightgbm
ids-run-trees --feature-sets all_71 --weighting-modes balanced
ids-run-neural --models resnet --smoke-only
ids-run-trees --rerun
```

Every full invocation prints the resulting leaderboard and writes an ignored CSV under `ml/reports/generated/`. A script returns a nonzero exit code when one of its requested configurations fails or remains incomplete.

## Inspect results

Show the latest successful configuration for each requested model setup directly in the terminal:

```powershell
ids-show-results --round tree
ids-show-results --round baseline tree
ids-show-results --round tree neural
ids-show-results
ids-show-results --dataset-version sha256:<dataset-hash>
```

For plots, per-class reports, confusion matrices, feature importances, training curves, and candidate selection, open the comparison notebook:

```powershell
jupyter lab ml/notebooks/03_model_comparison.ipynb
```

Select the project's `.venv` kernel. Set `ROUND_FILTER` to any non-empty combination of `baseline`, `tree`, and `neural`, or use `None` for all rounds. `DATASET_VERSION` can select an older compatible dataset explicitly. Otherwise, reporting chooses the contract with the most completed configurations, using recency only as a tie-breaker. Restart the kernel and run all cells after changing either value.

For ad-hoc inspection of individual runs, start the local MLflow UI from the repository root:

```powershell
mlflow ui --backend-store-uri sqlite:///ml/mlflow.db
```

The SQLite database and artifacts remain local and ignored by Git. Per-class reports, confusion matrices, tree importances, and neural training histories are stored with their MLflow runs.

## Test-set protection

All current training commands are validation-only. They recreate and validate the protected test partition for fingerprint and support checks, but never predict or score it. Final model serialization and the one-time final-test evaluation remain later stages.
