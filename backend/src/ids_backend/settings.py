"""Runtime settings for the local flow-level IDS application."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path



def find_project_root() -> Path:
    """Find the monorepo root without importing the model-development package."""
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "ml" / "final_model_spec.json").is_file()
        ):
            return candidate.resolve()
    raise FileNotFoundError("Could not locate the intrusion-detection project root.")


def _resolve_path(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _default_model_path(root: Path) -> Path:
    specification = root / "ml" / "final_model_spec.json"
    if specification.exists():
        recipe = json.loads(specification.read_text(encoding="utf-8"))
        source_run = str(recipe.get("selection", {}).get("source_mlflow_run_id", ""))
        if source_run:
            return root / "ml" / "models" / f"xgboost_final_{source_run[:12]}.joblib"
    return root / "ml" / "models" / "final_pipeline.joblib"


@dataclass(frozen=True)
class ServingSettings:
    project_root: Path
    model_path: Path
    database_path: Path
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    source_name: str = "CIC-IDS-2017 replay"
    max_request_bytes: int = 128 * 1024
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_environment(cls, project_root: Path | None = None) -> "ServingSettings":
        root = (project_root or find_project_root()).resolve()
        model_value = os.environ.get("IDS_MODEL_PATH")
        database_value = os.environ.get(
            "IDS_DATABASE_PATH", str(root / "runtime-data" / "ids.sqlite")
        )
        origins = tuple(
            origin.strip()
            for origin in os.environ.get(
                "IDS_ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        )
        if not origins:
            raise ValueError("IDS_ALLOWED_ORIGINS must contain at least one origin.")
        return cls(
            project_root=root,
            model_path=(
                _resolve_path(model_value, root)
                if model_value
                else _default_model_path(root).resolve()
            ),
            database_path=_resolve_path(database_value, root),
            allowed_origins=origins,
            source_name=os.environ.get("IDS_SOURCE_NAME", "CIC-IDS-2017 replay"),
            max_request_bytes=int(os.environ.get("IDS_MAX_REQUEST_BYTES", 128 * 1024)),
            host=os.environ.get("IDS_HOST", "127.0.0.1"),
            port=int(os.environ.get("IDS_PORT", "8000")),
        )
