from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Type

from physical_agent.drivers.base import PhysicalDriver
from physical_agent.drivers.manifest import load_driver_manifest, validate_driver_config
from physical_agent.drivers.registry import (
    get_builtin_driver_class,
    get_builtin_manifest,
    is_builtin_driver,
)
from physical_agent.protocol.schemas import DriverContext, DriverManifest


@dataclass(frozen=True)
class LoadedDriver:
    robot_id: str
    driver: PhysicalDriver
    manifest: DriverManifest
    source: str


def _load_local_module(module_path: Path, unique_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load driver module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    driver_dir = str(module_path.parent)
    added_path = False
    if driver_dir not in sys.path:
        sys.path.insert(0, driver_dir)
        added_path = True
    try:
        spec.loader.exec_module(module)
    finally:
        if added_path:
            sys.path.remove(driver_dir)
    return module


def _load_local_driver_class(driver_dir: Path, manifest: DriverManifest, robot_id: str) -> Type[PhysicalDriver]:
    module_file = driver_dir / f"{manifest.entrypoint.module}.py"
    if not module_file.exists():
        raise FileNotFoundError(f"Driver entrypoint module not found: {module_file}")
    module_name = f"physical_agent_local_driver_{robot_id}_{abs(hash(driver_dir))}"
    module = _load_local_module(module_file, module_name)
    driver_class = getattr(module, manifest.entrypoint.class_name)
    if not issubclass(driver_class, PhysicalDriver):
        raise TypeError(
            f"{manifest.entrypoint.class_name} must subclass physical_agent.drivers.PhysicalDriver"
        )
    return driver_class


def load_driver(
    *,
    robot_id: str,
    driver_ref: str,
    config: dict,
    workspace_path: Path,
    artifacts_path: Path,
    base_dir: Path | None = None,
) -> LoadedDriver:
    if is_builtin_driver(driver_ref):
        manifest = get_builtin_manifest(driver_ref)
        driver_class = get_builtin_driver_class(driver_ref)
        source = driver_ref
    else:
        driver_dir = Path(driver_ref)
        if not driver_dir.is_absolute():
            driver_dir = (base_dir or Path.cwd()) / driver_dir
        driver_dir = driver_dir.resolve()
        manifest = load_driver_manifest(driver_dir)
        driver_class = _load_local_driver_class(driver_dir, manifest, robot_id)
        source = str(driver_dir)

    validate_driver_config(manifest, config)
    context = DriverContext(
        robot_id=robot_id,
        robot_name=robot_id,
        config=config,
        workspace_path=workspace_path,
        artifacts_path=artifacts_path,
    )
    driver = driver_class(context)
    return LoadedDriver(robot_id=robot_id, driver=driver, manifest=manifest, source=source)
