from physical_agent.drivers import (
    Action,
    ActionResult,
    Capability,
    DriverContext,
    HealthStatus,
    Observation,
    PhysicalDriver,
)


class MyHardwareDriver(PhysicalDriver):
    def __init__(self, context: DriverContext):
        super().__init__(context)
        self.config = context.config
        self.mode = str(self.config.get("mode", "mock"))
        self.state = dict(self.config.get("mock_state") or {})
        self.pose = dict(self.state.get("pose") or {"x": 0.0, "y": 0.0, "z": 0.0})
        self.holding = self.state.get("holding")
        self.objects = dict(self.state.get("objects") or {})
        self.messages: list[str] = []
        self.light = dict(self.state.get("light") or {"r": 0, "g": 0, "b": 0})
        self.connected = False

    async def connect(self) -> None:
        # Keep mock mode runnable; place real SDK connection setup here.
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
            summary=f"{self.context.robot_id} is {'connected' if self.connected else 'offline'} in {self.mode} mode.",
            robots={
                self.context.robot_id: {
                    "status": "idle" if self.connected else "offline",
                    "mode": self.mode,
                    "pose": self.pose,
                    "holding": self.holding,
                    "light": self.light,
                }
            },
            objects=self.objects,
            raw={"messages": list(self.messages)},
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name='observe',
                description='Observe the current device state.',
                params_schema={'type': 'object', 'properties': {}, 'additionalProperties': False},
                returns_schema=None,
                constraints={},
                requires_approval=False,
                timeout_s=None,
            )
        ]

    async def execute(self, action: Action) -> ActionResult:
        if action.capability == "observe":
            observation = await self.observe()
            return ActionResult(
                status="completed",
                message="Observation completed.",
                result={"observation": observation.model_dump(mode="json")},
            )
        return ActionResult(
            status="failed",
            message=f"Unsupported capability: {action.capability}",
        )
