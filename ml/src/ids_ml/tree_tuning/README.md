# Tree-tuning package reference

This package implements the tuning and validation workflow for the selected XGBoost and LightGBM challengers. It tunes only the balanced `all_71` feature configuration, trains XGBoost with CUDA, trains LightGBM on CPU, and measures final validation inference on CPU.

The protected 20% test partition is loaded only to validate its fingerprint and document that it remains unused. Nothing in this package predicts or scores it.

## File responsibilities

### `__init__.py`

Defines the public package interface. It exposes `tuning_main` for backward-compatible imports while leaving the implementation in `cli.py`.

This file should remain minimal. Training logic, configuration, data loading, and reporting do not belong here.

### `core.py`

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

Change tuning ranges in this file. `core.py`, `search.py`, and `verification.py` consume the resolved configuration and must not redefine those ranges.

### `search.py`

Owns the Optuna search lifecycle and its MLflow records:

- Builds the local ignored Optuna SQLite URI and deterministic study names.
- Creates or resumes TPE studies with five startup-random trials.
- Counts successful trials and runs only enough new attempts to reach the requested total.
- Resolves and ranks completed trials.
- Executes one tuning trial using the shared training code from `core.py`.
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

### `cli.py`

Provides the user-facing command and lightweight orchestration:

- Defines the `search`, `verify`, and `report` subcommands.
- Parses model filters and the successful-trial target.
- Loads the dataset only for commands that require it.
- Runs the temporary `--smoke-only` workflow for both training devices, MLflow artifacts, refitting, and CPU inference.
- Queries Optuna and MLflow to create terminal and CSV reports.
- Dispatches work to `search.py` and `verification.py` without implementing their model logic.

Code belongs here when it concerns arguments, command dispatch, terminal output, or smoke orchestration. Model fitting and metric definitions should stay in their reusable modules.

### `README.md`

Documents the package structure and ownership rules. Update it whenever files are added, removed, or given materially different responsibilities.

## Dependency direction

The intended internal dependency flow is:

```text
cli.py
├── search.py
│   ├── search_space.py
│   └── core.py
│       └── search_space.py
└── verification.py
    ├── search.py
    ├── search_space.py
    └── core.py
        └── search_space.py
```

`search_space.py` must not import the training or orchestration modules. `core.py` may consume its validation contract but must not import the higher-level modules. `search.py` must not import `verification.py` or `cli.py`. This one-way structure prevents circular imports and keeps training behavior reusable outside the command-line interface.

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
    → core.py preprocesses fitting data without validation/test leakage
    → core.py trains each proposed configuration
    → search.py logs the trial and continues until 20 successful trials
```

### Verification

```text
ids-tune-trees verify
    → cli.py loads the unchanged data contract
    → verification.py retrieves the top three trials from search.py
    → core.py refits their exact configurations
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
