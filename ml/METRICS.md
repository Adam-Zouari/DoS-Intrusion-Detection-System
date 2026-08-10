# Model-Evaluation Metrics

This document defines the metrics used to evaluate and compare the multiclass intrusion-detection models in this project. **Macro F1 is the only primary model-selection metric.** All other measurements provide class-level, diagnostic, operational, or reference information.

## Multiclass counting convention

For a class $c$, its metrics are calculated using a one-vs-rest view:

- **True positives ($TP_c$)**: samples whose true label and predicted label are both $c$.
- **False positives ($FP_c$)**: samples predicted as $c$ whose true label is another class.
- **False negatives ($FN_c$)**: samples whose true label is $c$ but that are predicted as another class.
- **Support ($N_c$)**: the number of test samples whose true label is $c$, so $N_c = TP_c + FN_c$.

These definitions apply independently to `BENIGN` and to every attack class.

## Primary model-selection metric

### Macro F1

For each class $c$, calculate its precision, recall, and F1 score:

$$
P_c = \frac{TP_c}{TP_c + FP_c}
$$

$$
R_c = \frac{TP_c}{TP_c + FN_c}
$$

$$
F1_c = \frac{2P_cR_c}{P_c + R_c}
     = \frac{2TP_c}{2TP_c + FP_c + FN_c}
$$

For $K$ classes, macro F1 is the unweighted mean of their individual F1 scores:

$$
\text{Macro F1} = \frac{1}{K}\sum_{c=1}^{K} F1_c
$$

Use the fixed set of dataset classes for $K$. If a precision, recall, or F1 denominator is zero, record that class's corresponding score as 0 so every run follows the same defined convention.

Every class contributes equally, regardless of how many samples it contains. This makes macro F1 suitable for the highly imbalanced CIC-IDS-2017 dataset: a model cannot obtain a strong primary score merely by performing well on `BENIGN` and frequent attack classes. It must balance precision and recall across all classes.

Macro F1 must be used to select and rank models. It should be calculated on the same fixed test set for every final model comparison.

A rare class can make macro F1 unstable because its class-level score is based on very few examples. Macro F1 must therefore be read together with per-class scores and support. A poor score for a tiny class is important, but the small support means that its exact value has greater uncertainty.

## Per-class metrics

### Precision

$$
P_c = \frac{TP_c}{TP_c + FP_c}
$$

Precision answers: *Of all flows predicted as class $c$, how many actually belong to that class?* Low precision means that the model raises many incorrect alerts for that class.

### Recall

$$
R_c = \frac{TP_c}{TP_c + FN_c}
$$

Recall answers: *Of all flows that truly belong to class $c$, how many did the model identify correctly?* Low recall for an attack class means that many occurrences of that attack are missed or assigned to another class.

### F1

$$
F1_c = \frac{2P_cR_c}{P_c + R_c}
$$

Per-class F1 summarizes the balance between false alerts and missed or misclassified instances for one class. It is useful for finding attack families on which a model is weak even when its overall macro F1 is competitive.

### Support

$$
N_c = TP_c + FN_c
$$

Support is not a performance score. It provides the sample count needed to interpret the reliability of each per-class result. Scores based on very small support can change substantially after only a few predictions.

Per-class precision, recall, F1, and support must be recorded for every class.

## Secondary operational metric

### Binary attack-detection recall

For this metric only, collapse every non-`BENIGN` true label into one `ATTACK` category and do the same for predictions:

$$
\text{Binary attack recall}
= \frac{TP_{attack}}{TP_{attack} + FN_{attack}}
$$

Here, $TP_{attack}$ is an attack flow predicted as any attack class, while $FN_{attack}$ is an attack flow predicted as `BENIGN`.

This measures whether the IDS detects malicious traffic at all. If the true class is `DoS Hulk` but the prediction is `DDoS`, binary attack-detection recall counts the flow as detected. The per-class recall for `DoS Hulk`, however, counts it as a miss because the exact attack family was incorrect. This metric is secondary because it does not measure the correctness of attack-family classification, and frequent attacks can dominate its value.

## Reference metric

### Accuracy

$$
\text{Accuracy} = \frac{\text{number of exactly correct predictions}}{\text{total number of predictions}}
$$

A prediction is correct only when it matches the exact multiclass label. Accuracy provides a familiar overall reference, but it must not be used to select models because the majority classes can dominate it and hide weak performance on rare attacks.

## Diagnostic artifacts

### Raw confusion matrix

The raw multiclass confusion matrix contains sample counts:

- Rows represent true classes.
- Columns represent predicted classes.
- Diagonal cells are correct predictions.
- Off-diagonal cell $(i, j)$ counts samples of true class $i$ predicted as class $j$.

It shows the absolute number of errors and which attack families the model confuses. Large classes naturally produce larger counts, so the raw matrix must be considered together with the row-normalized matrix.

### Row-normalized confusion matrix

Each raw matrix cell is divided by the total of its true-class row:

$$
C^{normalized}_{i,j} = \frac{C_{i,j}}{\sum_j C_{i,j}}
$$

Each non-empty row therefore sums to 1. The diagonal value for a class is its recall, and each off-diagonal value is the fraction of that true class assigned to another class. Row normalization makes error patterns comparable across classes with very different support.

## Operational measurements

Operational measurements must be collected under documented, consistent conditions so model comparisons are meaningful. Record the hardware, software versions, test-set size, batch size, number of timed repetitions, and whether CPU or GPU execution was used.

### Training time

Training time is the elapsed wall-clock time, in seconds, required to fit the complete trainable pipeline on the training data. It includes fitted preprocessing and model fitting, but excludes dataset loading, exploratory analysis, and test-set evaluation.

### Single-flow prediction latency

Single-flow latency measures the complete path for one flow through **all fitted preprocessing transformations and model prediction**. After warm-up runs, collect enough repeated measurements to report:

- **p50 latency**: the median; half of predictions complete at or below this time.
- **p95 latency**: 95% of predictions complete at or below this time.
- **p99 latency**: 99% of predictions complete at or below this time and represents rarer slow responses.

Report all three in milliseconds. Use the same input preparation, execution environment, warm-up procedure, and repetition count for every model.

### Batch throughput

$$
\text{Throughput} = \frac{\text{number of flows predicted}}{\text{elapsed prediction time in seconds}}
$$

Batch throughput is reported in flows per second using a fixed batch size. The timed path must include the same fitted preprocessing and prediction stages used in deployment. Batch throughput complements single-flow latency; neither should be inferred from the other.

### Finalist pipeline size

Pipeline size is the size in MiB of the serialized, deployment-ready artifact containing the fitted preprocessing and model. Record it for finalist models so storage and loading costs are compared using the actual deployable pipelines rather than model estimators alone.

## MLflow logging convention

Log scalar values with these exact names:

| Measurement | MLflow metric name |
|---|---|
| Macro F1 | `macro_f1` |
| Accuracy | `accuracy_reference` |
| Binary attack-detection recall | `binary_attack_recall` |
| Training time in seconds | `training_time_seconds` |
| Single-flow p50 latency in milliseconds | `latency_p50_ms` |
| Single-flow p95 latency in milliseconds | `latency_p95_ms` |
| Single-flow p99 latency in milliseconds | `latency_p99_ms` |
| Batch throughput in flows per second | `throughput_flows_per_second` |
| Serialized finalist pipeline size in MiB | `model_size_mib` |

Log the complete per-class precision, recall, F1, and support report as an MLflow artifact. Log both the raw and row-normalized confusion matrices as MLflow artifacts for every evaluated model. The scalar `macro_f1` remains the only metric used for primary model selection.

## Boosting-tuning diagnostics

The XGBoost and LightGBM tuning studies also record the following diagnostics. They explain training behavior and early stopping; they do not replace macro F1 as the sole optimization and model-selection metric.

| Measurement | MLflow name or artifact column |
|---|---|
| Optuna objective at the retained iteration | `tuning_objective_macro_f1` |
| Inner-validation multiclass log loss at the retained iteration | `inner_validation_log_loss` |
| Lowest observed inner-validation multiclass log loss | `best_validation_log_loss` |
| Training-monitor multiclass log loss at the retained iteration | `training_monitor_log_loss` |
| Booster-only fitting time, excluding the shared preprocessing fit | `booster_training_time_seconds` |
| Iteration with the highest inner-validation macro F1 | `best_macro_iteration` |
| Iteration with the lowest inner-validation log loss | `best_loss_iteration` |
| Fixed iteration count used for a verification refit | `selected_boosting_iterations` |
| Per-iteration inner-validation macro F1 | `inner_validation_macro_f1` in `tuning/iteration_history.csv` |
| Per-iteration inner-validation log loss | `inner_validation_log_loss` in `tuning/iteration_history.csv` |
| Per-iteration training-monitor log loss | `training_monitor_log_loss` in `tuning/iteration_history.csv` |
| Per-iteration elapsed time | `iteration_time_seconds` in `tuning/iteration_history.csv` |

The training-monitor sample is selected reproducibly from inner-training rows. It is never used to select parameters. Early-stopping patience resets when either inner-validation macro F1 improves by at least `1e-4` or inner-validation log loss decreases by at least `1e-5`. The retained model iteration is always the iteration with the highest observed inner-validation macro F1; the best-loss iteration is saved only as a diagnostic comparison.
