"""Versioned Optuna search spaces and resolved-parameter validation."""

from __future__ import annotations

import optuna

MODEL_KEYS = ("xgboost", "lightgbm")

LEARNING_RATE_RANGE = (0.02, 0.15)
SUBSAMPLE_RANGE = (0.70, 1.0)
COLSAMPLE_BYTREE_RANGE = (0.60, 1.0)
REG_LAMBDA_RANGE = (0.1, 10.0)
REG_ALPHA_NONZERO_RANGE = (1e-4, 1.0)

XGBOOST_MAX_DEPTHS = (4, 6, 8, 10)
XGBOOST_MIN_CHILD_WEIGHT_RANGE = (1.0, 20.0)
XGBOOST_GAMMA_RANGE = (0.0, 1.0)

LIGHTGBM_MAX_DEPTHS = (-1, 6, 8, 10, 12)
LIGHTGBM_NUM_LEAVES = (15, 31, 63, 127)
LIGHTGBM_MIN_CHILD_SAMPLES = (10, 20, 50, 100, 200)
LIGHTGBM_MIN_SPLIT_GAIN_RANGE = (0.0, 1.0)


def _suggest_common_parameters(trial: optuna.Trial) -> dict[str, object]:
    parameters: dict[str, object] = {
        "learning_rate": trial.suggest_float(
            "learning_rate", *LEARNING_RATE_RANGE, log=True
        ),
        "subsample": trial.suggest_float("subsample", *SUBSAMPLE_RANGE),
        "colsample_bytree": trial.suggest_float(
            "colsample_bytree", *COLSAMPLE_BYTREE_RANGE
        ),
        "reg_lambda": trial.suggest_float(
            "reg_lambda", *REG_LAMBDA_RANGE, log=True
        ),
    }
    alpha_mode = trial.suggest_categorical("reg_alpha_mode", ["zero", "nonzero"])
    parameters["reg_alpha"] = (
        0.0
        if alpha_mode == "zero"
        else trial.suggest_float(
            "reg_alpha_nonzero", *REG_ALPHA_NONZERO_RANGE, log=True
        )
    )
    return parameters


def suggest_parameters(trial: optuna.Trial, model_key: str) -> dict[str, object]:
    """Resolve one valid conditional parameter configuration."""

    common = _suggest_common_parameters(trial)
    if model_key == "xgboost":
        return {
            **common,
            "max_depth": trial.suggest_categorical(
                "max_depth", XGBOOST_MAX_DEPTHS
            ),
            "min_child_weight": trial.suggest_float(
                "min_child_weight", *XGBOOST_MIN_CHILD_WEIGHT_RANGE, log=True
            ),
            "gamma": trial.suggest_float("gamma", *XGBOOST_GAMMA_RANGE),
        }
    if model_key == "lightgbm":
        max_depth = trial.suggest_categorical("max_depth", LIGHTGBM_MAX_DEPTHS)
        leaf_choices = (
            tuple(leaves for leaves in LIGHTGBM_NUM_LEAVES if leaves <= 2**max_depth)
            if max_depth > 0
            else LIGHTGBM_NUM_LEAVES
        )
        leaf_parameter = (
            "num_leaves_unlimited"
            if max_depth == -1
            else f"num_leaves_depth_{max_depth}"
        )
        return {
            **common,
            "max_depth": max_depth,
            "num_leaves": trial.suggest_categorical(leaf_parameter, leaf_choices),
            "min_child_samples": trial.suggest_categorical(
                "min_child_samples", LIGHTGBM_MIN_CHILD_SAMPLES
            ),
            "min_split_gain": trial.suggest_float(
                "min_split_gain", *LIGHTGBM_MIN_SPLIT_GAIN_RANGE
            ),
            "subsample_freq": 1,
        }
    raise ValueError(f"Unknown tuning model: {model_key}")


def _assert_in_range(name: str, value: float, bounds: tuple[float, float]) -> None:
    if not bounds[0] <= value <= bounds[1]:
        raise AssertionError(f"{name} is outside the tuning contract.")


def validate_resolved_parameters(model_key: str, params: dict[str, object]) -> None:
    """Reject any resolved configuration that violates the versioned space."""

    if model_key not in MODEL_KEYS:
        raise ValueError(f"Unknown tuning model: {model_key}")
    _assert_in_range(
        "learning_rate", float(params["learning_rate"]), LEARNING_RATE_RANGE
    )
    _assert_in_range("subsample", float(params["subsample"]), SUBSAMPLE_RANGE)
    _assert_in_range(
        "colsample_bytree",
        float(params["colsample_bytree"]),
        COLSAMPLE_BYTREE_RANGE,
    )
    _assert_in_range("reg_lambda", float(params["reg_lambda"]), REG_LAMBDA_RANGE)
    reg_alpha = float(params["reg_alpha"])
    if reg_alpha != 0.0:
        _assert_in_range("reg_alpha", reg_alpha, REG_ALPHA_NONZERO_RANGE)

    max_depth = int(params["max_depth"])
    if model_key == "xgboost":
        if max_depth not in XGBOOST_MAX_DEPTHS:
            raise AssertionError("max_depth is outside the XGBoost tuning contract.")
        _assert_in_range(
            "min_child_weight",
            float(params["min_child_weight"]),
            XGBOOST_MIN_CHILD_WEIGHT_RANGE,
        )
        _assert_in_range("gamma", float(params["gamma"]), XGBOOST_GAMMA_RANGE)
        return

    if max_depth not in LIGHTGBM_MAX_DEPTHS:
        raise AssertionError("max_depth is outside the LightGBM tuning contract.")
    num_leaves = int(params["num_leaves"])
    if num_leaves not in LIGHTGBM_NUM_LEAVES:
        raise AssertionError("num_leaves is outside the LightGBM tuning contract.")
    if max_depth > 0 and num_leaves > 2**max_depth:
        raise AssertionError("LightGBM leaves exceed the depth constraint.")
    if int(params["min_child_samples"]) not in LIGHTGBM_MIN_CHILD_SAMPLES:
        raise AssertionError(
            "min_child_samples is outside the LightGBM tuning contract."
        )
    _assert_in_range(
        "min_split_gain",
        float(params["min_split_gain"]),
        LIGHTGBM_MIN_SPLIT_GAIN_RANGE,
    )
    if int(params["subsample_freq"]) != 1:
        raise AssertionError("LightGBM subsample_freq must remain 1.")
