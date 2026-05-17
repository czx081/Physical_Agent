from __future__ import annotations

import re
from pathlib import Path


def class_name_from_driver_name(name: str) -> str:
    parts = re.split(r"[^0-9A-Za-z]+", name)
    return "".join(part[:1].upper() + part[1:] for part in parts if part) + "Driver"


def manifest_template(name: str, class_name: str | None = None) -> str:
    class_name = class_name or class_name_from_driver_name(name)
    return f"""schema: physical-agent/driver/v1

name: {name}
version: 0.1.0
description: Local Physical Agent driver.

entrypoint:
  module: driver
  class: {class_name}

robot:
  kind: generic
  supports_simulation: true

config_schema:
  type: object
  properties: {{}}
  additionalProperties: true

dependencies:
  python: []

capability_contract:
  source: runtime
"""


def driver_template(name: str, class_name: str | None = None) -> str:
    class_name = class_name or class_name_from_driver_name(name)
    return f'''from physical_agent.drivers import (
    Action,
    ActionResult,
    Capability,
    DriverContext,
    HealthStatus,
    Observation,
    PhysicalDriver,
)


class {class_name}(PhysicalDriver):
    def __init__(self, context: DriverContext):
        super().__init__(context)
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def health(self) -> HealthStatus:
        return HealthStatus(
            ok=self.connected,
            message="connected" if self.connected else "not connected",
        )

    async def observe(self) -> Observation:
        return Observation(
            summary=f"{{self.context.robot_id}} is connected.",
            robots={{
                self.context.robot_id: {{
                    "status": "idle" if self.connected else "offline",
                }}
            }},
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="observe",
                description="Observe the current device state.",
                params_schema={{
                    "type": "object",
                    "properties": {{}},
                    "additionalProperties": False,
                }},
            )
        ]

    async def execute(self, action: Action) -> ActionResult:
        if action.capability == "observe":
            observation = await self.observe()
            return ActionResult(
                status="completed",
                message="Observation completed.",
                result={{"observation": observation.model_dump(mode="json")}},
            )
        return ActionResult(
            status="failed",
            message=f"Unsupported capability: {{action.capability}}",
        )
'''


def readme_template(name: str) -> str:
    return f"""# {name}

This is a local Physical Agent driver.

The watch process loads this directory, validates `physical_driver.yaml`,
imports `driver.py`, and passes structured `Action` objects into the driver.
The driver does not parse Markdown and does not call the agent runtime.
"""


def create_driver_template(target_dir: str | Path, *, name: str | None = None) -> Path:
    path = Path(target_dir).resolve()
    driver_name = name or path.name
    class_name = class_name_from_driver_name(driver_name)
    path.mkdir(parents=True, exist_ok=True)
    (path / "physical_driver.yaml").write_text(
        manifest_template(driver_name, class_name),
        encoding="utf-8",
    )
    (path / "driver.py").write_text(driver_template(driver_name, class_name), encoding="utf-8")
    (path / "README.md").write_text(readme_template(driver_name), encoding="utf-8")
    return path

