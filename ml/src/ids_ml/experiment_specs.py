"""Single source of truth for screening rounds and model configurations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

FEATURE_SETS = ("all_71", "reduced_64")
WEIGHTING_MODES = ("unweighted", "balanced")


@dataclass(frozen=True)
class ModelDefinition:
    model_key: str
    model_family: str
    candidate_role: str | None = None
    protocol_mode: str = "one_hot"
    feature_sets: tuple[str, ...] = FEATURE_SETS
    weighting_modes: tuple[str, ...] = WEIGHTING_MODES


@dataclass(frozen=True)
class RoundDefinition:
    round_name: str
    experiment_name: str
    implementation_module: str
    models: tuple[ModelDefinition, ...]


@dataclass(frozen=True)
class ExperimentSpec:
    screening_round: str
    model_key: str
    model_family: str
    feature_set: str
    weighting_mode: str
    protocol_mode: str

    @property
    def configuration_key(self) -> str:
        return make_configuration_key(
            self.screening_round,
            self.model_key,
            self.feature_set,
            self.weighting_mode,
        )


ROUND_DEFINITIONS = {
    definition.round_name: definition
    for definition in (
        RoundDefinition(
            round_name="baseline",
            experiment_name="cicids2017-multiclass-baselines",
            implementation_module="ids_ml.baseline_models",
            models=(
                ModelDefinition(
                    "dummy",
                    "DummyClassifier",
                    feature_sets=("all_71",),
                    weighting_modes=("unweighted",),
                ),
                ModelDefinition("sgd", "SGDClassifier"),
                ModelDefinition("decision_tree", "DecisionTreeClassifier"),
                ModelDefinition(
                    "random_forest", "RandomForestClassifier", "bagging"
                ),
                ModelDefinition(
                    "hist_gradient_boosting",
                    "HistGradientBoostingClassifier",
                    "boosting",
                ),
                ModelDefinition("mlp", "MLPClassifier"),
            ),
        ),
        RoundDefinition(
            round_name="tree",
            experiment_name="cicids2017-tree-challengers",
            implementation_module="ids_ml.tree_models",
            models=(
                ModelDefinition("extra_trees", "ExtraTreesClassifier", "bagging"),
                ModelDefinition("xgboost", "XGBClassifier", "boosting"),
                ModelDefinition("lightgbm", "LGBMClassifier", "boosting"),
            ),
        ),
        RoundDefinition(
            round_name="neural",
            experiment_name="cicids2017-neural-challengers",
            implementation_module="ids_ml.neural.experiments",
            models=(
                ModelDefinition("mlp", "RTDL MLP", "neural"),
                ModelDefinition("resnet", "RTDL ResNet", "neural"),
                ModelDefinition(
                    "ft_transformer",
                    "FT-Transformer",
                    "neural",
                    protocol_mode="embedding",
                ),
                ModelDefinition(
                    "tabnet", "TabNet", "neural", protocol_mode="embedding"
                ),
            ),
        ),
    )
}

ROUND_EXPERIMENTS = {
    name: definition.experiment_name
    for name, definition in ROUND_DEFINITIONS.items()
}


def make_configuration_key(
    screening_round: str,
    model_key: str,
    feature_set: str,
    weighting_mode: str,
) -> str:
    return ":".join(
        [screening_round, model_key, feature_set, weighting_mode]
    )


def validate_round_filter(
    round_filter: Iterable[str] | str | None,
) -> tuple[str, ...]:
    if round_filter is None:
        return tuple(ROUND_DEFINITIONS)
    rounds = [round_filter] if isinstance(round_filter, str) else list(round_filter)
    if not rounds:
        raise ValueError("ROUND_FILTER cannot be empty; use None to select all rounds.")
    if len(rounds) != len(set(rounds)):
        raise ValueError("ROUND_FILTER contains duplicate round names.")
    unknown = sorted(set(rounds) - set(ROUND_DEFINITIONS))
    if unknown:
        raise ValueError(
            f"Unknown experiment rounds: {unknown}. "
            f"Expected values from {list(ROUND_DEFINITIONS)}."
        )
    return tuple(rounds)


def round_definition(round_name: str) -> RoundDefinition:
    try:
        return ROUND_DEFINITIONS[round_name]
    except KeyError as error:
        raise ValueError(f"Unknown experiment round: {round_name}") from error


def specs_for_round(round_name: str) -> list[ExperimentSpec]:
    definition = round_definition(round_name)
    return [
        ExperimentSpec(
            screening_round=round_name,
            model_key=model.model_key,
            model_family=model.model_family,
            feature_set=feature_set,
            weighting_mode=weighting_mode,
            protocol_mode=model.protocol_mode,
        )
        for model in definition.models
        for feature_set in model.feature_sets
        for weighting_mode in model.weighting_modes
    ]


def model_keys_for_round(round_name: str) -> tuple[str, ...]:
    return tuple(model.model_key for model in round_definition(round_name).models)


def models_for_candidate_role(role: str) -> set[tuple[str, str]]:
    return {
        (definition.round_name, model.model_key)
        for definition in ROUND_DEFINITIONS.values()
        for model in definition.models
        if model.candidate_role == role
    }


def expected_configuration_keys(round_name: str) -> set[str]:
    return {spec.configuration_key for spec in specs_for_round(round_name)}
