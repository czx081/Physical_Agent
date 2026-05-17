from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from physical_agent.protocol.schemas import Action


class Planner(ABC):
    @abstractmethod
    def plan(
        self,
        *,
        task: str,
        capabilities: dict[str, Any],
        world: dict[str, Any],
    ) -> list[Action]:
        raise NotImplementedError

