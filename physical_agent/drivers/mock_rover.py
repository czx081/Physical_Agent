from __future__ import annotations

from copy import deepcopy

from physical_agent.drivers.base import PhysicalDriver
from physical_agent.protocol.schemas import (
    Action,
    ActionResult,
    Capability,
    DriverContext,
    HealthStatus,
    Observation,
)


MANIFEST = {
    "schema": "physical-agent/driver/v1",
    "name": "mock_rover",
    "version": "0.1.0",
    "description": "Built-in simulated rover for Physical Agent.",
    "entrypoint": {"module": "mock_rover", "class": "MockRoverDriver"},
    "robot": {"kind": "rover", "supports_simulation": True},
    "config_schema": {
        "type": "object",
        "properties": {
            "start_pose": {"type": "object"},
            "battery": {"type": "number", "minimum": 0, "maximum": 100},
        },
        "additionalProperties": True,
    },
    "dependencies": {"python": []},
    "capability_contract": {"source": "runtime"},
}


class MockRoverDriver(PhysicalDriver):
    def __init__(self, context: DriverContext):
        super().__init__(context)
        self.config = context.config
        self.connected = False
        self.pose = deepcopy(self.config.get("start_pose", {"x": 0.0, "y": 0.0}))
        self.battery = float(self.config.get("battery", 100.0))

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def health(self) -> HealthStatus:
        return HealthStatus(ok=self.connected, message="connected" if self.connected else "not connected")

    async def observe(self) -> Observation:
        return Observation(
            summary=f"Rover is at ({self.pose['x']}, {self.pose['y']}) with {self.battery:.0f}% battery.",
            robots={
                self.context.robot_id: {
                    "status": "idle" if self.connected else "offline",
                    "pose": deepcopy(self.pose),
                    "battery": self.battery,
                }
            },
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="observe",
                description="Observe the current rover state.",
                params_schema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Capability(
                name="move_to",
                description="Move the rover to a planar target.",
                params_schema={
                    "type": "object",
                    "required": ["x", "y"],
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "additionalProperties": False,
                },
            ),
        ]

    async def execute(self, action: Action) -> ActionResult:
        if action.capability == "observe":
            observation = await self.observe()
            return ActionResult(
                status="completed",
                message="Observation completed.",
                result={"observation": observation.model_dump(mode="json")},
            )
        if action.capability == "move_to":
            self.pose = {"x": float(action.params["x"]), "y": float(action.params["y"])}
            self.battery = max(0.0, self.battery - 1.0)
            return ActionResult(
                status="completed",
                message=f"Rover moved to ({self.pose['x']}, {self.pose['y']}).",
                result={"pose": deepcopy(self.pose), "battery": self.battery},
            )
        return ActionResult(status="failed", message=f"Unsupported capability: {action.capability}")

