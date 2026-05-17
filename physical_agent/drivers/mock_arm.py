from __future__ import annotations

from copy import deepcopy
from typing import Any

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
    "name": "mock_arm",
    "version": "0.1.0",
    "description": "Built-in simulated arm for Physical Agent quickstarts.",
    "entrypoint": {"module": "mock_arm", "class": "MockArmDriver"},
    "robot": {"kind": "arm", "supports_simulation": True},
    "config_schema": {
        "type": "object",
        "properties": {
            "bounds": {
                "type": "object",
                "properties": {
                    "x": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                    "y": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                    "z": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                },
                "additionalProperties": False,
            },
            "objects": {"type": "object"},
            "start_pose": {"type": "object"},
        },
        "additionalProperties": True,
    },
    "dependencies": {"python": []},
    "capability_contract": {"source": "runtime"},
}


DEFAULT_BOUNDS = {
    "x": [-1.0, 1.0],
    "y": [-1.0, 1.0],
    "z": [0.0, 1.0],
}

DEFAULT_OBJECTS = {
    "red_block": {
        "type": "block",
        "color": "red",
        "location": "table",
        "pose": {"x": 0.3, "y": 0.1, "z": 0.0},
    },
    "tray": {
        "type": "tray",
        "location": "table",
        "pose": {"x": -0.2, "y": 0.2, "z": 0.0},
    },
}


class MockArmDriver(PhysicalDriver):
    def __init__(self, context: DriverContext):
        super().__init__(context)
        self.config = context.config
        self.connected = False
        self.bounds = deepcopy(self.config.get("bounds", DEFAULT_BOUNDS))
        self.pose = deepcopy(self.config.get("start_pose", {"x": 0.0, "y": 0.0, "z": 0.4}))
        self.holding: str | None = None
        self.objects: dict[str, Any] = deepcopy(self.config.get("objects", DEFAULT_OBJECTS))

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
        visible = [
            object_id
            for object_id, item in self.objects.items()
            if item.get("location") != "held"
        ]
        holding = f" holding {self.holding}" if self.holding else " idle"
        summary = f"The arm is{holding}. Visible objects: {', '.join(visible) or 'none'}."
        return Observation(
            summary=summary,
            robots={
                self.context.robot_id: {
                    "status": "idle" if self.connected else "offline",
                    "pose": deepcopy(self.pose),
                    "holding": self.holding,
                }
            },
            objects=deepcopy(self.objects),
            environment={"bounds": deepcopy(self.bounds)},
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="observe",
                description="Observe the current workspace.",
                params_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            Capability(
                name="move_to",
                description="Move end effector to a target position.",
                params_schema={
                    "type": "object",
                    "required": ["x", "y", "z"],
                    "properties": {
                        axis: {
                            "type": "number",
                            "minimum": bounds[0],
                            "maximum": bounds[1],
                        }
                        for axis, bounds in self.bounds.items()
                    },
                    "additionalProperties": False,
                },
                constraints={"bounds": deepcopy(self.bounds)},
            ),
            Capability(
                name="pick",
                description="Pick an object by object_id.",
                params_schema={
                    "type": "object",
                    "required": ["object_id"],
                    "properties": {"object_id": {"type": "string"}},
                    "additionalProperties": False,
                },
            ),
            Capability(
                name="place",
                description="Place the held object at a named target.",
                params_schema={
                    "type": "object",
                    "required": ["target"],
                    "properties": {"target": {"type": "string"}},
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
            self.pose = {
                "x": float(action.params["x"]),
                "y": float(action.params["y"]),
                "z": float(action.params["z"]),
            }
            return ActionResult(
                status="completed",
                message=f"Moved to ({self.pose['x']}, {self.pose['y']}, {self.pose['z']}).",
                result={"pose": deepcopy(self.pose)},
            )

        if action.capability == "pick":
            object_id = str(action.params["object_id"])
            if self.holding is not None:
                return ActionResult(
                    status="failed",
                    message=f"Cannot pick {object_id}; already holding {self.holding}.",
                )
            if object_id not in self.objects:
                return ActionResult(status="failed", message=f"Unknown object: {object_id}")
            self.holding = object_id
            self.objects[object_id]["location"] = "held"
            return ActionResult(
                status="completed",
                message=f"Picked {object_id} successfully.",
                result={"holding": object_id},
            )

        if action.capability == "place":
            target = str(action.params["target"])
            if self.holding is None:
                return ActionResult(
                    status="failed",
                    message="Cannot place because the arm is not holding anything.",
                )
            placed_object = self.holding
            self.holding = None
            self.objects[placed_object]["location"] = target
            if target in self.objects and "pose" in self.objects[target]:
                self.objects[placed_object]["pose"] = deepcopy(self.objects[target]["pose"])
            return ActionResult(
                status="completed",
                message=f"Placed {placed_object} at {target}.",
                result={"object_id": placed_object, "target": target},
            )

        return ActionResult(
            status="failed",
            message=f"Unsupported capability: {action.capability}",
        )

