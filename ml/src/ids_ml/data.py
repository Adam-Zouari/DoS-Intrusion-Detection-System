"""Dataset contracts, feature schemas, and reproducible partitions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as parquet
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight

from .specs import FEATURE_SETS

RANDOM_STATE = 42
TEST_SIZE = 0.20
VALIDATION_SIZE_WITHIN_TRAINING = 0.20
INNER_STOPPING_SIZE = 0.10

EXPECTED_ROWS = 2_824_752
EXPECTED_COLUMNS = 76
EXPECTED_PROTOCOL_VALUES = [0, 6, 17]
EXPECTED_BASELINE_FIT_FINGERPRINT = (
    "95748603225bb464de387eb900629353bbba8657b24af7dba91208231886e33a"
)
EXPECTED_BASELINE_VALIDATION_FINGERPRINT = (
    "f21bc202dcdfb13964ca7cf323d7327212f2a5231e3715a248aad1a6a51a0ce6"
)
EXPECTED_BASELINE_TEST_FINGERPRINT = (
    "b695227aac126f599fb19e726881f08a4c412dc861cc473c93a498c78c498fec"
)
EXPECTED_BASELINE_TIMING_FINGERPRINT = (
    "da802a73d33489107c9109db2a6b15637c8675ad59708829e7afa6b2f5a2a871"
)
COMPARISON_CONTRACT_FIELDS = (
    "dataset_version",
    "fit_split_fingerprint",
    "evaluation_split_fingerprint",
    "timing_input_fingerprint",
)

LABEL_ORDER = [
    "BENIGN",
    "Bot",
    "DDoS",
    "DoS GoldenEye",
    "DoS Hulk",
    "DoS Slowhttptest",
    "DoS slowloris",
    "FTP-Patator",
    "Heartbleed",
    "Infiltration",
    "PortScan",
    "SSH-Patator",
    "Web Attack - Brute Force",
    "Web Attack - Sql Injection",
    "Web Attack - XSS",
]
LABEL_TO_INDEX = {label: index for index, label in enumerate(LABEL_ORDER)}

IDENTIFIER_COLUMNS = ["Flow ID", "Src IP", "Dst IP", "Timestamp"]
REDUNDANT_FEATURES = [
    "Fwd Segment Size Avg",
    "Bwd Segment Size Avg",
    "Subflow Fwd Packets",
    "Subflow Bwd Packets",
    "Subflow Fwd Bytes",
    "Subflow Bwd Bytes",
    "Packet Length Variance",
]


@dataclass(frozen=True)
class DatasetContract:
    dataset_sha256: str
    fit_fingerprint: str = EXPECTED_BASELINE_FIT_FINGERPRINT
    validation_fingerprint: str = EXPECTED_BASELINE_VALIDATION_FINGERPRINT
    test_fingerprint: str = EXPECTED_BASELINE_TEST_FINGERPRINT
    timing_fingerprint: str = EXPECTED_BASELINE_TIMING_FINGERPRINT

    @property
    def dataset_version(self) -> str:
        return f"sha256:{self.dataset_sha256}"

    def comparison_fields(self) -> dict[str, str]:
        return dict(
            zip(
                COMPARISON_CONTRACT_FIELDS,
                (
                    self.dataset_version,
                    self.fit_fingerprint,
                    self.validation_fingerprint,
                    self.timing_fingerprint,
                ),
                strict=True,
            )
        )


@dataclass
class ExperimentData:
    X_fit: pd.DataFrame
    X_validation: pd.DataFrame
    X_test: pd.DataFrame
    y_fit: pd.Series
    y_validation: pd.Series
    y_test: pd.Series
    model_input_features: list[str]
    feature_sets: dict[str, list[str]]
    contract: DatasetContract


def find_project_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "ml").is_dir():
            return candidate.resolve()
    raise FileNotFoundError("Could not locate the project root.")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def processed_dataset_path(project_root: Path | None = None) -> Path:
    root = project_root or find_project_root()
    return root / "ml" / "data" / "processed" / "cicids2017_cleaned.parquet"


def load_dataset_contract(project_root: Path | None = None) -> DatasetContract:
    dataset_path = processed_dataset_path(project_root)
    if not dataset_path.exists():
        raise FileNotFoundError(
            "The cleaned parquet dataset is missing. Run 01_data_exploration.ipynb first."
        )
    metadata = parquet.ParquetFile(dataset_path)
    observed_shape = (metadata.metadata.num_rows, len(metadata.schema_arrow.names))
    if observed_shape != (EXPECTED_ROWS, EXPECTED_COLUMNS):
        raise AssertionError(
            f"Expected {(EXPECTED_ROWS, EXPECTED_COLUMNS)}, observed {observed_shape}."
        )
    if "Label" not in metadata.schema_arrow.names:
        raise AssertionError("The cleaned parquet schema does not contain Label.")
    return DatasetContract(dataset_sha256=sha256_file(dataset_path))


def index_fingerprint(index: pd.Index) -> str:
    values = np.asarray(index, dtype=np.int64)
    return hashlib.sha256(values.tobytes()).hexdigest()


def encode_labels(labels: pd.Series | np.ndarray) -> np.ndarray:
    encoded = pd.Series(labels).map(LABEL_TO_INDEX)
    if encoded.isna().any():
        unknown = sorted(set(pd.Series(labels)[encoded.isna()].astype(str)))
        raise ValueError(f"Unknown target labels: {unknown}")
    return encoded.to_numpy(dtype=np.int64)


def decode_labels(indices: np.ndarray) -> np.ndarray:
    values = np.asarray(indices, dtype=np.int64)
    if ((values < 0) | (values >= len(LABEL_ORDER))).any():
        raise ValueError("A prediction contains an unknown label index.")
    return np.asarray(LABEL_ORDER, dtype=object)[values]


def transformed_feature_count(source_feature_count: int, protocol_mode: str) -> int:
    if protocol_mode == "one_hot":
        return source_feature_count - 1 + len(EXPECTED_PROTOCOL_VALUES)
    if protocol_mode == "embedding":
        return source_feature_count
    raise ValueError(f"Unknown Protocol mode: {protocol_mode}")


def balanced_sample_weights(labels: pd.Series | np.ndarray) -> np.ndarray:
    weights = np.asarray(compute_sample_weight("balanced", labels), dtype=np.float64)
    if len(weights) != len(labels):
        raise AssertionError("Sample weights do not match the fitting labels.")
    return weights


def load_experiment_data(
    project_root: Path | None = None,
    contract: DatasetContract | None = None,
) -> ExperimentData:
    dataset_path = processed_dataset_path(project_root)
    contract = contract or load_dataset_contract(project_root)

    data = pd.read_parquet(dataset_path)
    if "Label" not in data or data["Label"].isna().any():
        raise AssertionError("The target is missing or contains missing labels.")
    if set(data["Label"].unique()) != set(LABEL_ORDER):
        raise AssertionError("The detailed label set differs from the expected classes.")
    if data.drop(columns="Label").isna().any().any():
        raise AssertionError("The cleaned feature data contains missing values.")

    required_columns = IDENTIFIER_COLUMNS + REDUNDANT_FEATURES + ["Protocol"]
    missing_columns = [column for column in required_columns if column not in data]
    if missing_columns:
        raise KeyError(f"Required columns are missing: {missing_columns}")

    y = data.pop("Label")
    X = data.drop(columns=IDENTIFIER_COLUMNS)
    del data

    model_input_features = X.columns.tolist()
    reduced_features = [
        feature for feature in model_input_features if feature not in REDUNDANT_FEATURES
    ]
    feature_sets = dict(
        zip(FEATURE_SETS, (model_input_features, reduced_features), strict=True)
    )
    expected_feature_counts = dict(zip(FEATURE_SETS, (71, 64), strict=True))
    if {
        name: len(features) for name, features in feature_sets.items()
    } != expected_feature_counts:
        raise AssertionError("The 71/64 source feature contracts have changed.")
    protocol_values = sorted(X["Protocol"].unique().tolist())
    if protocol_values != EXPECTED_PROTOCOL_VALUES:
        raise AssertionError(
            f"Expected Protocol values {EXPECTED_PROTOCOL_VALUES}, observed {protocol_values}."
        )

    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    X_fit, X_validation, y_fit, y_validation = train_test_split(
        X_train_full,
        y_train_full,
        test_size=VALIDATION_SIZE_WITHIN_TRAINING,
        random_state=RANDOM_STATE,
        stratify=y_train_full,
    )
    del X, y, X_train_full, y_train_full

    partitions = {
        "fit": X_fit.index,
        "validation": X_validation.index,
        "test": X_test.index,
    }
    for first_name, first_index in partitions.items():
        for second_name, second_index in partitions.items():
            if first_name < second_name and not first_index.intersection(second_index).empty:
                raise AssertionError(f"{first_name} and {second_name} rows overlap.")

    for partition_name, target in {
        "fit": y_fit,
        "validation": y_validation,
        "test": y_test,
    }.items():
        missing_labels = set(LABEL_ORDER) - set(target.unique())
        if missing_labels:
            raise AssertionError(
                f"{partition_name} is missing labels: {sorted(missing_labels)}"
            )

    fit_fingerprint = index_fingerprint(X_fit.index)
    validation_fingerprint = index_fingerprint(X_validation.index)
    test_fingerprint = index_fingerprint(X_test.index)
    if fit_fingerprint != contract.fit_fingerprint:
        raise AssertionError("The fitting rows do not match the baseline split.")
    if validation_fingerprint != contract.validation_fingerprint:
        raise AssertionError("The validation rows do not match the baseline split.")
    if test_fingerprint != contract.test_fingerprint:
        raise AssertionError("The protected test rows do not match the baseline split.")

    return ExperimentData(
        X_fit=X_fit,
        X_validation=X_validation,
        X_test=X_test,
        y_fit=y_fit,
        y_validation=y_validation,
        y_test=y_test,
        model_input_features=model_input_features,
        feature_sets=feature_sets,
        contract=contract,
    )


def class_preserving_sample(
    X: pd.DataFrame,
    y: pd.Series,
    maximum_rows_per_class: int,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.Series]:
    positions: list[int] = []
    generator = np.random.default_rng(random_state)
    y_values = y.to_numpy()
    for label in LABEL_ORDER:
        label_positions = np.flatnonzero(y_values == label)
        take = min(maximum_rows_per_class, len(label_positions))
        positions.extend(
            generator.choice(label_positions, size=take, replace=False).tolist()
        )
    positions_array = np.asarray(positions, dtype=np.int64)
    generator.shuffle(positions_array)
    return X.iloc[positions_array].copy(), y.iloc[positions_array].copy()
