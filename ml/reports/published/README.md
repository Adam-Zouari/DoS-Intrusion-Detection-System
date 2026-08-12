# Published result artifacts

This directory contains the small, versioned subset of final MLflow artifacts needed to inspect the protected-test result without the local SQLite tracking database.

The artifacts were copied read-only from the already completed final evaluation. Publishing them did not refit a model or repeat test prediction.

## Final artifacts

- [`per_class_report.csv`](final/per_class_report.csv) contains exact class-level precision, recall, F1, and support.
- [`confusion_matrix_raw.csv`](final/confusion_matrix_raw.csv) and its [PNG](final/confusion_matrix_raw.png) contain absolute prediction counts.
- [`confusion_matrix_row_normalized.csv`](final/confusion_matrix_row_normalized.csv) and its [PNG](final/confusion_matrix_row_normalized.png) show the prediction distribution within each true class.
- [`tree_feature_importance.csv`](final/tree_feature_importance.csv) and its [top-30 PNG](final/tree_feature_importance_top30.png) contain the final XGBoost importance diagnostic.

The screening, tuning, stability, and final decision tables are presented directly in [ml/RESULTS.md](../../RESULTS.md) rather than duplicated here. Local MLflow and Optuna stores, model binaries, datasets, and temporary generated reports remain ignored by Git.
