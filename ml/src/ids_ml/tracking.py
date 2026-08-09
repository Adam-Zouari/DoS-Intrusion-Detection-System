"""Local MLflow tracking configuration."""

from __future__ import annotations

from pathlib import Path

import mlflow

from .data import find_project_root


def tracking_uri(project_root: Path | None = None) -> str:
    root = project_root or find_project_root()
    return f"sqlite:///{(root / 'ml' / 'mlflow.db').resolve().as_posix()}"


def configure_tracking(project_root: Path | None = None) -> str:
    uri = tracking_uri(project_root)
    mlflow.set_tracking_uri(uri)
    return uri


def setup_mlflow_experiment(
    experiment_name: str, project_root: Path | None = None
) -> None:
    root = project_root or find_project_root()
    configure_tracking(root)
    artifact_root = root / "ml" / "mlruns"
    artifact_root.mkdir(parents=True, exist_ok=True)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        mlflow.create_experiment(
            experiment_name, artifact_location=artifact_root.resolve().as_uri()
        )
    mlflow.set_experiment(experiment_name)
