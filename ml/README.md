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
| `src/ids_ml/experiment_specs.py` | The single source of truth for experiment names, screening rounds, model families, feature sets, weighting modes, Protocol handling, candidate roles, and configuration keys. |
| `src/ids_ml/data.py` | Locates and validates the cleaned parquet dataset; defines labels, feature exclusions, hashes, dataset and split contracts; reads the input schema without loading rows; recreates the fixed fit, validation, and protected-test partitions; and provides label encoding, deterministic inner splits, class-preserving sampling, and weight helpers. |
| `src/ids_ml/preprocessing.py` | Shared preprocessing for scikit-learn and tree pipelines: numeric transformation, fixed one-hot encoding of `Protocol`, transformed-schema validation, parameter extraction, and common fitted-pipeline cleanup. |
| `src/ids_ml/evaluation.py` | Calculates the metrics defined in `ml/METRICS.md`, constructs per-class reports and confusion matrices, creates fixed timing inputs, measures complete-pipeline latency and throughput, and logs shared evaluation artifacts. |
| `src/ids_ml/screening.py` | Implements the single MLflow validation lifecycle used by every model and reusable development partition: create the run, log common metadata, fit, evaluate, optionally time inference, log artifacts and diagnostics, handle cleanup, and return the result record. It also provides the common smoke-fit procedure. |
| `src/ids_ml/baseline_models.py` | Defines the Dummy, SGD, Decision Tree, Random Forest, Histogram Gradient Boosting, and scikit-learn MLP baseline configurations and adapts them to the shared screening lifecycle. |
| `src/ids_ml/tree_models.py` | Defines ExtraTrees, XGBoost, and LightGBM screening configurations, their weighting behavior, target encoding, and tree feature-importance artifacts. |
| `src/ids_ml/tree_tuning/__init__.py` | Marks the tree-tuning directory as a package and preserves the public `tuning_main` import. |
| `src/ids_ml/tree_tuning/search_space.py` | Defines the named XGBoost and LightGBM hyperparameter ranges, conditional Optuna suggestions, and validation of every resolved configuration. |
| `src/ids_ml/tree_tuning/training.py` | Defines the 71-feature tuning contract, shared preprocessing, boosting callbacks, combined early stopping, XGBoost/LightGBM fitting, and complete CPU prediction wrapper. |
| `src/ids_ml/tree_tuning/search.py` | Owns Optuna study storage and resumption, successful-trial counting, TPE study creation, tuning-run MLflow metadata, iteration artifacts, and the 20-trial search lifecycle. |
| `src/ids_ml/tree_tuning/verification.py` | Refits top trials, evaluates the outer validation split, logs confusion matrices and importances, measures CPU inference, and performs the three-development-split stability check. |
| `src/ids_ml/tree_tuning/original_xgboost_comparison.py` | Compares the exact original balanced 71-feature XGBoost with the tuned XGBoost across matched development splits, reuses completed runs, and creates paired comparison reports. |
| `src/ids_ml/tree_tuning/final_selection.py` | Finds compatible successful tuned XGBoost outer-validation runs, selects the highest full-precision macro F1, and freezes the selected run's exact parameters, iteration count, feature schema, and dataset/split contracts in JSON. |
| `src/ids_ml/tree_tuning/final_evaluation.py` | Verifies the frozen JSON against its source MLflow run, owns the only protected-test prediction path, refits on the complete 80% development partition, serializes and reloads the CPU pipeline, logs the one-time test result, and prevents accidental test reuse. |
| `src/ids_ml/tree_tuning/cli.py` | Implements temporary smoke validation, generated tuning reports, argument parsing, and all installed `ids-tune-trees` subcommands. |
| `src/ids_ml/tree_tuning/README.md` | Explains the detailed ownership, dependency direction, and execution flow of every tree-tuning package file. |
| `src/ids_ml/tracking.py` | Configures the local SQLite MLflow tracking URI and creates or selects experiments with the local artifact directory. |
| `src/ids_ml/reporting.py` | Queries MLflow, normalizes current and legacy run records, selects compatible dataset/split contracts, removes duplicate configurations, builds coverage and leaderboard tables, compares feature and weighting choices, creates candidate shortlists, and downloads result artifacts. |
| `src/ids_ml/screening_workflows.py` | Implements the four screening and result-inspection commands. It parses filters, skips completed configurations, loads full data only when work remains, runs smoke checks, continues after isolated failures, invokes the shared screening lifecycle, and prints or saves leaderboards. |
| `src/ids_ml/neural/__init__.py` | Marks the neural implementation directory as a subpackage without triggering PyTorch or model-library imports. |
| `src/ids_ml/neural/preprocessing.py` | Owns neural-only shared behavior: reproducible seeds, numeric scaling, Protocol conversion, mini-batch loaders, balanced loss weights, training-device selection, fit-result records, and memory cleanup. It consumes the shared leakage-safe inner-split contract from `data.py`. |
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

## Tune the selected boosting challengers

The tuning workflow uses the balanced 71-feature configurations selected during screening. XGBoost trains with CUDA; the installed LightGBM build trains deterministically on CPU. Optuna state is stored in ignored `ml/optuna.db` files, so interrupted studies can resume without repeating successful trials.

First validate both model paths without starting the full studies:

```powershell
ids-tune-trees search --smoke-only
```

Run or resume up to 20 successful TPE trials per model:

```powershell
ids-tune-trees search --target-trials 20
ids-tune-trees search --models xgboost --target-trials 20
ids-tune-trees search --models lightgbm --target-trials 20
```

`--target-trials` is a total, not an additional count. Repeating the first command after 12 successful trials runs only the trials still needed to reach 20. Failed trials do not count toward that target.

After both studies contain at least three successful trials, verify their top configurations on the outer validation split and run the selected configuration across development-split seeds 42, 123, and 2025:

```powershell
ids-tune-trees verify
ids-tune-trees report
```

Optionally compare the exact original 200-tree XGBoost screening configuration with the selected tuned XGBoost across the same split seeds. Existing compatible runs are reused by default, so normally only missing original runs are trained:

```powershell
ids-tune-trees compare-original-xgboost
ids-tune-trees compare-original-xgboost --rerun
```

The command writes the original runs, aggregate summaries, and seed-paired differences under `ml/reports/generated/`. `--rerun` intentionally repeats all three original-configuration fits. This comparison is diagnostic and does not participate in final selection.

The search objective is inner-validation macro F1. Per-iteration training-monitor log loss, inner-validation log loss, macro F1, and iteration duration are stored as MLflow artifacts. The protected test partition is never scored by these commands.

## Freeze and evaluate the final XGBoost

Freeze the tuned XGBoost configuration with the highest macro F1 on the fixed outer-validation split:

```powershell
ids-tune-trees freeze-final
```

The command considers only successful XGBoost runs tagged as `outer_validation_top_trial` from the tuning-verification experiment. It rejects runs from another dataset or split, selects the maximum full-precision `macro_f1`, and writes `ml/final_model_spec.json` without loading dataset rows. The JSON records the source MLflow run, validation score, parameters, boosting iterations, feature/preprocessing schema, library versions, and dataset/split fingerprints. It is immediately checked against the source run.

Review the frozen specification before crossing the final-test boundary. Then run the one-time final evaluation:

```powershell
ids-tune-trees evaluate-final
ids-tune-trees final-report
```

`evaluate-final` checks that the JSON still matches its selected MLflow run, then refits it on the complete 80% development partition using CUDA for training and CPU for inference. It reloads and verifies the serialized pipeline before predicting the protected 20% test partition once. Metrics, diagnostics, the pipeline, and the native booster are logged under `cicids2017-final-test`. If any successful final run already uses that protected-test fingerprint, another evaluation is refused by default. `final-report` is read-only.

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

The tuning and verification runs appear in the separate MLflow experiments `cicids2017-tree-tuning` and `cicids2017-tree-tuning-verification`. Optuna decides which parameters to try; MLflow remains the authoritative record of metrics and artifacts for each completed fit.

## Test-set protection

Screening, tuning, verification, original-versus-tuned comparison, reporting, and `freeze-final` never predict or score the protected test partition. Only `evaluate-final` may do so after the best tuned outer-validation run has been frozen. Any successful final run for the protected-test fingerprint blocks another evaluation by default, and the observed result must not be used to restart tuning.
