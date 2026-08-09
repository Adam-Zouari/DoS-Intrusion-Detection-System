"""Tree-challenger model adapters and diagnostics."""

from __future__ import annotations

import tempfile
from pathlib import Path

import lightgbm
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import sklearn
import xgboost
from lightgbm import LGBMClassifier
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from xgboost import XGBClassifier

from .data import (
    LABEL_ORDER,
    RANDOM_STATE,
    balanced_sample_weights,
    decode_labels,
    encode_labels,
    transformed_feature_count,
)
from .preprocessing import (
    OneHotPipelineAdapterBase,
    make_one_hot_pipeline,
)
from .screening import AdapterMetadata, FitDetails
from .specs import ExperimentSpec


def _as_float32(values: pd.DataFrame | np.ndarray) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def build_tree_pipeline(
    spec: ExperimentSpec,
    feature_sets: dict[str, list[str]],
    smoke: bool = False,
) -> Pipeline:
    weighted = spec.weighting_mode == "balanced"
    if spec.model_key == "extra_trees":
        classifier = ExtraTreesClassifier(
            n_estimators=3 if smoke else 300,
            max_depth=4 if smoke else 20,
            min_samples_leaf=2,
            max_features="sqrt",
            class_weight="balanced" if weighted else None,
            n_jobs=1 if smoke else -1,
            random_state=RANDOM_STATE,
        )
    elif spec.model_key == "xgboost":
        classifier = XGBClassifier(
            objective="multi:softprob",
            num_class=len(LABEL_ORDER),
            n_estimators=3 if smoke else 200,
            max_depth=3 if smoke else 8,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            tree_method="hist",
            eval_metric="mlogloss",
            n_jobs=1 if smoke else -1,
            random_state=RANDOM_STATE,
        )
    elif spec.model_key == "lightgbm":
        classifier = LGBMClassifier(
            objective="multiclass",
            num_class=len(LABEL_ORDER),
            n_estimators=3 if smoke else 200,
            num_leaves=7 if smoke else 31,
            learning_rate=0.1,
            min_child_samples=20,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            deterministic=True,
            force_col_wise=True,
            verbosity=-1,
            n_jobs=1 if smoke else -1,
            random_state=RANDOM_STATE,
        )
    else:
        raise ValueError(f"Unknown tree model: {spec.model_key}")

    return make_one_hot_pipeline(
        feature_sets[spec.feature_set],
        FunctionTransformer(_as_float32, feature_names_out="one-to-one"),
        np.float32,
        classifier,
    )


def _library(spec: ExperimentSpec) -> tuple[str, str]:
    if spec.model_key == "xgboost":
        return "xgboost", xgboost.__version__
    if spec.model_key == "lightgbm":
        return "lightgbm", lightgbm.__version__
    return "scikit-learn", sklearn.__version__


def _weighting_mechanism(spec: ExperimentSpec) -> str:
    if spec.weighting_mode == "unweighted":
        return "none"
    if spec.model_key == "extra_trees":
        return "classifier_class_weight"
    return "balanced_sample_weight"


def _log_tree_importance(
    feature_names: np.ndarray,
    importances: np.ndarray,
    model_family: str,
) -> None:
    frame = (
        pd.DataFrame({"feature": feature_names, "importance": importances})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        frame.to_csv(directory / "tree_feature_importance.csv", index=False)
        figure, axis = plt.subplots(figsize=(11, 9))
        top = frame.head(30).sort_values("importance")
        axis.barh(top["feature"], top["importance"])
        axis.set_title(f"{model_family}: top 30 impurity/gain importances")
        axis.set_xlabel("Model-reported importance")
        figure.tight_layout()
        figure.savefig(
            directory / "tree_feature_importance_top30.png",
            dpi=160,
            bbox_inches="tight",
        )
        plt.close(figure)
        mlflow.log_artifacts(directory, artifact_path="diagnostics")


class TreeAdapter(OneHotPipelineAdapterBase):
    """Expose one tree challenger through the shared runner contract."""

    def __init__(
        self,
        spec: ExperimentSpec,
        feature_sets: dict[str, list[str]],
        smoke: bool = False,
    ) -> None:
        if spec.protocol_mode != "one_hot":
            raise ValueError("Tree challengers require one-hot Protocol input.")
        self.spec = spec
        expected_transformed_count = transformed_feature_count(
            len(feature_sets[spec.feature_set]), spec.protocol_mode
        )
        super().__init__(
            build_tree_pipeline(spec, feature_sets, smoke=smoke),
            expected_transformed_count,
        )
        library, version = _library(spec)
        self.metadata = AdapterMetadata(
            model_library=library,
            model_library_version=version,
            weighting_mechanism=_weighting_mechanism(spec),
            target_encoding="fixed_label_index",
            protocol_encoding=spec.protocol_mode,
            numeric_preprocessing="passthrough_float32",
            numeric_dtype="float32",
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> FitDetails:
        fit_parameters: dict[str, np.ndarray] = {}
        if self.spec.weighting_mode == "balanced" and self.spec.model_key != "extra_trees":
            fit_parameters["classifier__sample_weight"] = balanced_sample_weights(y)
        self.pipeline.fit(X, encode_labels(y), **fit_parameters)

        self.inspect_fitted_preprocessor()
        return FitDetails()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return decode_labels(np.asarray(self.pipeline.predict(X), dtype=np.int64))

    def log_diagnostics(self, X: pd.DataFrame, y: pd.Series) -> None:
        _log_tree_importance(
            self.transformed_names,
            self.pipeline.named_steps["classifier"].feature_importances_,
            self.spec.model_family,
        )

def build_adapter(
    spec: ExperimentSpec,
    feature_sets: dict[str, list[str]],
    smoke: bool = False,
) -> TreeAdapter:
    return TreeAdapter(spec, feature_sets, smoke=smoke)
