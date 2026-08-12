# Tree-tuning package reference

This package implements tuning, validation, automatic finalist selection, and the guarded final evaluation for the selected XGBoost and LightGBM challengers. It tunes only the balanced `all_71` feature configuration, trains XGBoost with CUDA, trains LightGBM on CPU, and measures deployment-oriented inference on CPU.

The protected 20% test partition is never scored during search, verification, stability comparison, selection, or reporting. `final_evaluation.py` is the only module allowed to predict it, and only after `final_selection.py` has frozen an automatically selected recipe.

## File responsibilities

### `__init__.py`

Defines the public package interface. It exposes `tuning_main` for backward-compatible imports while leaving the implementation in `cli.py`.

This file should remain minimal. Training logic, configuration, data loading, and reporting do not belong here.

### `training.py`

Contains the model-independent contracts and the model-specific fitting details required by both search and verification:

- Tuning constants such as the model names, trial target, maximum boosting iterations, early-stopping patience, and MLflow experiment names.
- The fixed 71-source-feature and 73-transformed-feature contract.
- Leakage-safe fitting of the one-hot `Protocol` preprocessor.
- Construction of inner-training, inner-validation, and fixed training-monitor matrices.
- Per-iteration macro F1, log-loss, duration, and combined early-stopping monitoring.
- GPU XGBoost and CPU LightGBM training.
- Probability prediction and the complete raw-data-to-CPU-prediction wrapper.

Code belongs here when it directly defines how a model is prepared, trained, stopped, or used for prediction. MLflow run orchestration, study resumption, reports, and command-line parsing do not belong here.

### `search_space.py`

Defines the versioned hyperparameter-search contract in one place:

- Named ranges and categorical choices shared by both models.
- XGBoost-specific depth, child-weight, and split-gain choices.
- LightGBM-specific depth, leaves, child-sample, and split-gain choices.
- Conditional L1 regularization, including the explicit zero option.
- Conditional LightGBM `num_leaves` choices derived from `max_depth`.
- Optuna suggestion construction for both model families.
- Validation of every resolved configuration before training or refitting.

Change tuning ranges in this file. `training.py`, `search.py`, and `verification.py` consume the resolved configuration and must not redefine those ranges.

### `search.py`

Owns the Optuna search lifecycle and its MLflow records:

- Builds the local ignored Optuna SQLite URI and deterministic study names.
- Creates or resumes TPE studies with five startup-random trials.
- Counts successful trials and runs only enough new attempts to reach the requested total.
- Resolves and ranks completed trials.
- Executes one tuning trial using the shared training code from `training.py`.
- Logs parameters, scalar metrics, per-class reports, confusion matrices, iteration histories, and diagnostic plots to MLflow.
- Runs the requested model studies sequentially while preserving completed work.

Code belongs here when it controls which hyperparameters Optuna evaluates or how a tuning trial is tracked. Outer-validation refits and operational timing do not belong here.

### `verification.py`

Owns evaluation after Optuna has produced candidate configurations:

- Selects the three highest-scoring completed trials per model family.
- Refits each candidate on the complete fitting partition using its selected boosting-iteration count.
- Evaluates candidates on the fixed outer validation partition.
- Selects the strongest validation configuration per family using macro F1.
- Repeats that configuration across development-split seeds 42, 123, and 2025.
- Logs per-class reports, confusion matrices, tree importances, and stability results.
- Measures complete-pipeline CPU latency and throughput for the selected seed-42 candidate.
- Releases models between runs to control memory usage.

Code belongs here when it evaluates an already chosen Optuna trial or compares its behavior across validation splits. Parameter suggestion and CLI behavior do not belong here.

### `original_xgboost_comparison.py`

Owns the optional diagnostic comparison between the original screening XGBoost and the tuned XGBoost incumbent:

- Retrieves the exact original balanced `all_71` specification from the shared screening registry.
- Reuses the existing seed-42 screening result and any completed stability runs by default.
- Fits missing original-configuration runs on development-split seeds 123 and 2025.
- Logs the normal metrics, per-class reports, confusion matrices, and feature importances to the verification MLflow experiment.
- Retrieves the selected tuned trial's existing three-seed results.
- Writes aggregate and paired original-minus-tuned reports under `ml/reports/generated/`.

Code belongs here when it compares these two fixed configurations across development splits. It must not suggest hyperparameters, influence final selection, or access the protected test partition for prediction.

### `final_selection.py`

Owns automatic selection and freezing without loading any dataset rows:

- Queries successful tuned XGBoost runs evaluated on the fixed outer-validation split.
- Rejects runs with mismatched dataset, fit, validation, test, feature-set, weighting, or seed contracts.
- Selects the run with the highest full-precision MLflow `macro_f1` using `idxmax()`.
- Copies its parameters, selected boosting iterations, feature/preprocessing schema, library versions, source run ID, validation score, and dataset/split fingerprints into `ml/final_model_spec.json`.
- Verifies the generated JSON directly against the selected MLflow source run.

Original screening runs, development-split stability repetitions, LightGBM runs, neural runs, and inner-validation Optuna scores do not participate in this final selection.

### `final_evaluation.py`

Owns the deliberately narrow final-test boundary:

- Validates the frozen JSON structure, dataset/split contracts, and equality with the selected MLflow source run.
- Combines all and only the original 64% fitting and 16% validation rows.
- Refits preprocessing and balanced weights on that complete 80% development partition.
- Trains the frozen XGBoost recipe on CUDA with no early stopping or parameter changes.
- Saves the complete CPU inference pipeline and native booster, reloads it, and verifies prediction equality on development rows.
- Predicts the protected 20% test set once, logs final metrics and artifacts, and blocks another successful final evaluation for that test fingerprint by default.
- Provides the read-only final report.

No other module should add a protected-test prediction path.

### `cli.py`

Provides the user-facing command and lightweight orchestration:

- Defines the `search`, `verify`, `compare-original-xgboost`, `report`, `freeze-final`, `evaluate-final`, and `final-report` subcommands.
- Parses model filters and the successful-trial target.
- Loads the dataset only for commands that require it.
- Runs the temporary `--smoke-only` workflow for both training devices, MLflow artifacts, refitting, and CPU inference.
- Queries Optuna and MLflow to create terminal and CSV reports.
- Dispatches work to the focused implementation modules without implementing their model logic.

Code belongs here when it concerns arguments, command dispatch, terminal output, or smoke orchestration. Model fitting and metric definitions should stay in their reusable modules.

### `README.md`

Documents the package structure and ownership rules. Update it whenever files are added, removed, or given materially different responsibilities.

## Dependency direction

The intended internal dependency flow is:

```text
cli.py
|-- search.py -> training.py -> search_space.py
|-- verification.py -> search.py, training.py, search_space.py
|-- original_xgboost_comparison.py -> shared screening/data/evaluation modules
|-- final_selection.py -> MLflow metadata and Parquet schema only
`-- final_evaluation.py -> frozen spec and shared fit/evaluation modules
```

`search_space.py` must not import the training or orchestration modules. `training.py` may consume its validation contract but must not import the higher-level modules. `search.py` must not import `verification.py` or `cli.py`. This one-way structure prevents circular imports and keeps training behavior reusable outside the command-line interface.

The package also reuses shared project modules rather than redefining them:

- `ids_ml.data` for dataset, labels, split fingerprints, encoding, and class weights.
- `ids_ml.preprocessing` for the fixed one-hot `Protocol` transformer.
- `ids_ml.evaluation` for metrics, confusion matrices, artifacts, latency, and throughput.
- `ids_ml.tracking` for the local MLflow backend.
- `ids_ml.tree_models` for the common tree-importance artifact format.

## Execution flow

### Search

```text
ids-tune-trees search --target-trials 20
    → cli.py validates arguments and loads the data contract
    → search.py creates or resumes each Optuna study
    → training.py preprocesses fitting data without validation/test leakage
    → training.py trains each proposed configuration
    → search.py logs the trial and continues until 20 successful trials
```

### Verification

```text
ids-tune-trees verify
    → cli.py loads the unchanged data contract
    → verification.py retrieves the top three trials from search.py
    → training.py refits their exact configurations
    → verification.py evaluates outer validation and three split seeds
    → verification.py logs CPU inference and stability results
```

### Reporting

```text
ids-tune-trees report
    → cli.py queries existing Optuna and MLflow records
    → prints progress and verification tables
    → saves ignored CSV reports under ml/reports/generated/
```

Reporting does not load the dataset or train a model.

### Original-versus-tuned XGBoost comparison

```text
ids-tune-trees compare-original-xgboost
    -> cli.py loads the unchanged data contract
    -> original_xgboost_comparison.py reuses the seed-42 screening run
    -> it fits only missing original runs for seeds 123 and 2025
    -> it pairs them with the selected tuned XGBoost results
    -> aggregate and seed-paired CSV reports are saved locally
```

Use `ids-tune-trees compare-original-xgboost --rerun` only when all three original fits should be intentionally repeated. This diagnostic does not affect final selection, and the protected test set remains untouched.

### Automatic freeze and final evaluation

```text
ids-tune-trees freeze-final
    -> final_selection.py reads MLflow records and Parquet schema metadata
    -> compatible tuned XGBoost outer-validation runs are validated
    -> the highest full-precision macro F1 is selected
    -> ml/final_model_spec.json is written and checked against its source run

ids-tune-trees evaluate-final
    -> final_evaluation.py rechecks the JSON against the source MLflow run
    -> the model is refitted on the complete 80% development partition
    -> the serialized CPU pipeline is reloaded and checked
    -> the protected 20% test set is evaluated once

ids-tune-trees final-report
    -> final_evaluation.py reads the frozen recipe and final MLflow run
    -> final metrics, per-class results, and artifact locations are printed
```

`freeze-final` fails when no compatible tuned XGBoost outer-validation run exists. `evaluate-final` fails when the JSON differs from its source run, when dataset/split contracts have changed, or when any successful final run already exists for the protected-test fingerprint.
