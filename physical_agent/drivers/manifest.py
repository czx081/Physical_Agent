from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from physical_agent.protocol.schemas import DriverManifest


MANIFEST_FILENAME = "physical_driver.yaml"


def load_driver_manifest(path: str | Path) -> DriverManifest:
    manifest_path = Path(path)
    if manifest_path.is_dir():
        manifest_path = manifest_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Driver manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    manifest = DriverManifest.model_validate(data)
    if manifest.schema != "physical-agent/driver/v1":
        raise ValueError(f"Unsupported driver manifest schema: {manifest.schema}")
    return manifest


def validate_driver_config(manifest: DriverManifest, config: dict[str, Any]) -> None:
    schema = manifest.config_schema or {"type": "object"}
    try:
        Draft202012Validator(schema).validate(config)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        prefix = f" at {path}" if path else ""
        raise ValueError(f"Invalid config for driver {manifest.name}{prefix}: {exc.message}") from exc

