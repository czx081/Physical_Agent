from __future__ import annotations

from importlib import import_module
from typing import Type

from physical_agent.drivers.base import PhysicalDriver
from physical_agent.protocol.schemas import DriverManifest


BUILTIN_DRIVERS = {
    "mock_arm": ("physical_agent.drivers.mock_arm", "MockArmDriver"),
    "mock_rover": ("physical_agent.drivers.mock_rover", "MockRoverDriver"),
}


def list_builtin_drivers() -> list[str]:
    return sorted(BUILTIN_DRIVERS)


def is_builtin_driver(name: str) -> bool:
    return name in BUILTIN_DRIVERS


def get_builtin_driver_class(name: str) -> Type[PhysicalDriver]:
    if name not in BUILTIN_DRIVERS:
        raise KeyError(f"Unknown built-in driver: {name}")
    module_name, class_name = BUILTIN_DRIVERS[name]
    module = import_module(module_name)
    driver_class = getattr(module, class_name)
    if not issubclass(driver_class, PhysicalDriver):
        raise TypeError(f"Built-in driver {name} does not subclass PhysicalDriver.")
    return driver_class


def get_builtin_manifest(name: str) -> DriverManifest:
    if name not in BUILTIN_DRIVERS:
        raise KeyError(f"Unknown built-in driver: {name}")
    module_name, _ = BUILTIN_DRIVERS[name]
    module = import_module(module_name)
    return DriverManifest.model_validate(module.MANIFEST)

