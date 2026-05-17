from __future__ import annotations

from abc import ABC, abstractmethod

from physical_agent.protocol.schemas import (
    Action,
    ActionResult,
    Capability,
    DriverContext,
    HealthStatus,
    Observation,
)


class PhysicalDriver(ABC):
    """Base class for physical adapters owned by the watch process."""

    def __init__(self, context: DriverContext):
        self.context = context

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> HealthStatus:
        raise NotImplementedError

    @abstractmethod
    async def observe(self) -> Observation:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> list[Capability]:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, action: Action) -> ActionResult:
        raise NotImplementedError

