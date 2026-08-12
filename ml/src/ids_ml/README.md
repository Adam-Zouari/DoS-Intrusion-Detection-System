# `ids_ml` source package

The installable `ids_ml` package owns reusable data contracts, preprocessing, model definitions, experiment execution, reporting, tuning, and guarded finalization. Notebooks use the package rather than redefining training logic.

## Shared modules

| Module | Responsibility |
|---|---|
| `__init__.py` | Keeps the package import lightweight. |
| `experiment_specs.py` | Defines experiment names, rounds, model families, feature sets, weighting modes, and configuration keys. |
| `data.py` | Validates the cleaned dataset, defines labels and feature exclusions, recreates fixed partitions, calculates fingerprints, encodes labels, samples classes, and derives fitting-only weights. |
| `preprocessing.py` | Builds shared feature selection and fixed one-hot `Protocol` preprocessing for scikit-learn and tree pipelines. |
| `evaluation.py` | Calculates documented metrics, creates class reports and confusion matrices, measures complete-pipeline CPU inference, and logs evaluation artifacts. |
| `tracking.py` | Configures the local SQLite MLflow backend and artifact root. |
| `screening.py` | Runs the shared MLflow fit/evaluate lifecycle and smoke-fit procedure. |
| `reporting.py` | Queries compatible MLflow runs and builds coverage, leaderboard, comparison, shortlist, and artifact views. |
| `screening_workflows.py` | Implements the baseline, tree, neural, and result-inspection command-line workflows. |

## Model definitions

| Module | Responsibility |
|---|---|
| `baseline_models.py` | Dummy, SGD, Decision Tree, Random Forest, Histogram Gradient Boosting, and scikit-learn MLP screening definitions. |
| `tree_models.py` | ExtraTrees, XGBoost, and LightGBM screening definitions, weighting behavior, target encoding, and importance diagnostics. |
| `neural/preprocessing.py` | Neural scaling, category conversion, batching, loss weights, device selection, reproducibility, and cleanup. |
| `neural/rtdl.py` | RTDL MLP, ResNet, and FT-Transformer training, epoch selection, refitting, and CPU prediction. |
| `neural/tabnet.py` | TabNet training, refitting, CPU prediction, and attention summaries. |
| `neural/experiments.py` | Connects neural classifiers to the shared screening and MLflow lifecycle. |

## Tree tuning and finalization

The `tree_tuning/` package separates search configuration, fitting, verification, diagnostics, selection, and the protected-test boundary.

| Module | Responsibility |
|---|---|
| `search_space.py` | Versioned XGBoost and LightGBM parameter ranges and constraints. |
| `training.py` | Shared tuning preprocessing, callbacks, early stopping, GPU XGBoost and CPU LightGBM fitting, and CPU prediction wrappers. |
| `search.py` | Resumable Optuna studies and tuning-trial MLflow records. |
| `verification.py` | Top-three outer-validation refits, operational timing, and three-split stability comparison. |
| `original_xgboost_comparison.py` | Diagnostic original-versus-tuned XGBoost comparison across matched development splits. |
| `final_selection.py` | Automatic outer-validation selection and frozen JSON generation without test prediction. |
| `final_evaluation.py` | The only protected-test prediction path; complete development refit, serialization verification, metrics, and reuse protection. |
| `cli.py` | `ids-tune-trees` argument parsing, command dispatch, smoke validation, and read-only reports. |

See the [tree-tuning package reference](tree_tuning/README.md) for dependency direction and command-level execution flow.

## Installed commands

| Command | Purpose |
|---|---|
| `ids-run-baselines` | Run or resume baseline screening. |
| `ids-run-trees` | Run or resume tree-challenger screening. |
| `ids-run-neural` | Run or resume selected neural screening configurations. |
| `ids-show-results` | Query and compare existing screening results. |
| `ids-tune-trees` | Search, verify, compare, freeze, evaluate, and report tuned tree models. |

### `ids-tune-trees` subcommands

The tuning entry point exposes the following subcommands:

| Command | Purpose |
|---|---|
| `ids-tune-trees search` | Run or resume the Optuna studies until the requested successful-trial target is reached. |
| `ids-tune-trees verify` | Refit the top trials on the fitting partition, evaluate outer validation, and perform the three-split stability comparison. |
| `ids-tune-trees compare-original-xgboost` | Compare the original screening XGBoost and tuned XGBoost configurations across matched development splits. |
| `ids-tune-trees report` | Display saved Optuna progress and MLflow verification results without fitting models. |
| `ids-tune-trees freeze-final` | Select the tuned XGBoost run with the highest outer-validation macro F1 and write the frozen JSON recipe. |
| `ids-tune-trees evaluate-final` | Refit the frozen recipe on the complete 80% development partition and perform the guarded one-time protected-test evaluation. |
| `ids-tune-trees final-report` | Display the frozen recipe and completed final-test result without fitting or predicting. |

Use `ids-tune-trees <subcommand> --help` to inspect the options for an individual operation.

The chronological user guide is [ml/README.md](../../README.md). Metric contracts are defined in [ml/METRICS.md](../../METRICS.md).
