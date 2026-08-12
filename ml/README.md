# Machine-learning workflow

This guide reproduces the CIC-IDS-2017 research workflow in chronological order. Static dataset semantics live in [DATASET.md](DATASET.md), metric definitions in [METRICS.md](METRICS.md), and the completed decision record in [RESULTS.md](RESULTS.md).

The raw and processed datasets, MLflow and Optuna databases, generated reports, and model binaries are local artifacts and are not committed. The notebooks retain their executed outputs, and selected final diagnostics are published under `reports/published/`.

## 1. Create the environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The editable installation exposes the `ids_ml` package and its commands while keeping source edits immediately available.

### NVIDIA GPU setup

The standard dependency declaration installs the normal PyTorch package. On a CUDA-capable Windows machine, install the project-tested CUDA build afterward:

```powershell
python -m pip install --force-reinstall -r ml/requirements-gpu.txt
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Neural screening and tuned XGBoost training use CUDA when required by their workflow. All recorded inference latency and throughput measurements use CPU inference for a consistent deployment comparison.

## 2. Place the merged source dataset

Download the official CIC-IDS-2017 flow CSV exports and concatenate them without cleaning into:

```text
ml/data/raw/cicids2017_merged.csv
```

Do not commit or overwrite this file. See [DATASET.md](DATASET.md) for provenance and feature meanings.

## 3. Explore and clean the data

Open and run:

```powershell
jupyter lab ml/notebooks/01_data_exploration.ipynb
```

Notebook 1 investigates the raw shape, target, class imbalance, missing and infinite values, invalid measurements, constants, zero-duration flows, duplicate records, and protocol values. It writes the validated dataset to:

```text
ml/data/processed/cicids2017_cleaned.parquet
```

## 4. Prepare features and protect the test split

Open and run:

```powershell
jupyter lab ml/notebooks/02_feature_engineering.ipynb
```

Notebook 2 removes the four identifier or leakage-prone columns, defines the 71 eligible source features, creates the reproducible stratified partitions, calculates mutual-information and correlation diagnostics, and documents the optional seven-feature reduction. It does not fit a final model or use the protected test set for model selection.

## 5. Run the screening rounds

Run the complete baseline and tree matrices:

```powershell
ids-run-baselines
ids-run-trees
```

Run the neural families that produced the eight completed configurations used in the published investigation:

```powershell
ids-run-neural --models mlp resnet
```

The larger neural matrix was stopped midway. FT-Transformer and TabNet required substantial computation while their monitored validation behavior showed no meaningful improvement. This was a resource-allocation decision, not proof that those architectures can never perform well.

Every screening command trains models, records metrics and artifacts in MLflow, skips matching successful configurations by default, and prints a leaderboard. Use `--rerun` only to intentionally duplicate completed work.

## 6. Investigate screening results

Open the committed read-only investigation:

```powershell
jupyter lab ml/notebooks/03_model_screening_analysis.ipynb
```

It compares the completed screening evidence in decision order and contains no training or protected-test evaluation. Its conclusion hands off XGBoost and LightGBM to tuning.

For terminal-only inspection of local runs:

```powershell
ids-show-results
ids-show-results --round baseline tree
ids-show-results --round neural
```

These commands query existing MLflow records; they do not train or score models.

## 7. Tune XGBoost and LightGBM

First smoke-test the training paths without starting full studies:

```powershell
ids-tune-trees search --smoke-only
```

Run or resume 20 successful trials per model:

```powershell
ids-tune-trees search --target-trials 20
```

`--target-trials` is the total target, so interrupted studies resume without repeating successful trials. Optuna search uses an inner validation holdout and never evaluates the outer validation or protected test partitions.

XGBoost tuning uses CUDA. LightGBM tuning uses the deterministic CPU build installed for this project.

## 8. Verify the strongest trials

```powershell
ids-tune-trees verify
ids-tune-trees report
```

`verify` refits the three strongest trials from each study and evaluates them on the fixed outer validation partition. It then compares the selected XGBoost and LightGBM settings across development-split seeds `42`, `123`, and `2025`. The protected test partition is not scored.

The diagnostic original-versus-tuned XGBoost comparison is:

```powershell
ids-tune-trees compare-original-xgboost
```

This command trains only missing comparison configurations and does not participate directly in automatic final selection.

## 9. Freeze the selected model

```powershell
ids-tune-trees freeze-final
```

This read-only selection command chooses the verified tuned XGBoost run with the highest full-precision outer-validation macro F1 and writes `ml/final_model_spec.json`. It validates the dataset, split, feature, parameter, and iteration contracts without predicting on the test partition.

The committed specification records the completed project's frozen recipe. A fresh reproduction must recreate compatible source MLflow runs before it can regenerate or validate that recipe.

## 10. Perform the one-time final evaluation

```powershell
ids-tune-trees evaluate-final
ids-tune-trees final-report
```

`evaluate-final` is the only command allowed to predict on the protected 20% test partition. It refits the frozen recipe on the complete 80% development data, serializes and reload-verifies the pipeline, evaluates the test once, and blocks another successful evaluation for the same protected-test fingerprint.

The published project has already completed this step. Its result is final and must not be used to restart tuning. `final-report` is read-only.

## 11. Read the published evidence

[RESULTS.md](RESULTS.md) explains the actual decisions using the recorded baseline, tree, neural, tuning, stability, and protected-test results. The selected final diagnostic CSV and PNG artifacts are available in [reports/published](reports/published/README.md) without the local MLflow database.

For ad-hoc inspection when local tracking state is available:

```powershell
mlflow ui --backend-store-uri sqlite:///ml/mlflow.db
```

## Implementation and tests

The [source-package guide](src/ids_ml/README.md) documents module ownership. The deeper [tree-tuning guide](src/ids_ml/tree_tuning/README.md) documents tuning dependencies and final-test isolation. The [test guide](../tests/README.md) explains the data-free suite used locally and in GitHub Actions.

```powershell
python -m pytest -q
```

The tests do not require CIC-IDS-2017, a GPU, MLflow state, Optuna state, or model training.
