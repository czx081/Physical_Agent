from __future__ import annotations

import re
from typing import Any

from physical_agent.agent.planner import Planner
from physical_agent.protocol.schemas import Action


class RuleBasedPlanner(Planner):
    """Small offline planner for the v1 Markdown loop."""

    def plan(
        self,
        *,
        task: str,
        capabilities: dict[str, Any],
        world: dict[str, Any],
    ) -> list[Action]:
        text = task.lower()
        robots = capabilities.get("robots", {})
        actions: list[Action] = []

        wants_observe = any(word in text for word in ("observe", "look", "scan"))
        wants_pick = any(word in text for word in ("pick", "grasp"))
        wants_place = any(word in text for word in ("place", "drop"))
        wants_move = bool(re.search(r"\b(move|go)\b", text))

        if wants_observe:
            robot_id = self._choose_robot(robots, ["observe"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="observe",
                        params={},
                        reason="The task asks for an observation.",
                    )
                )

        if wants_move:
            robot_id = self._choose_robot(robots, ["move_to"])
            if robot_id:
                params = self._move_params(text, robots[robot_id])
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="move_to",
                        params=params,
                        reason="The task asks for movement.",
                    )
                )

        if wants_pick:
            robot_id = self._choose_robot(robots, ["pick"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="pick",
                        params={"object_id": self._object_id(text, world)},
                        reason="The task asks to pick an object.",
                    )
                )

        if wants_place:
            robot_id = self._choose_robot(robots, ["place"])
            if robot_id:
                dependencies = [actions[-1].id] if actions and actions[-1].capability == "pick" else []
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="place",
                        params={"target": self._target_id(text, world)},
                        reason="The task asks to place or drop an object.",
                        depends_on=dependencies,
                    )
                )

        return actions

    def _choose_robot(self, robots: dict[str, Any], required: list[str]) -> str | None:
        for robot_id, robot in robots.items():
            names = {capability.get("name") for capability in robot.get("capabilities", [])}
            if all(name in names for name in required):
                return robot_id
        return None

    def _action_id(self, number: int) -> str:
        return f"act_{number:03d}"

    def _object_id(self, text: str, world: dict[str, Any]) -> str:
        objects = world.get("state", {}).get("objects", {})
        if "red block" in text:
            for object_id, item in objects.items():
                if item.get("color") == "red" and item.get("type") == "block":
                    return object_id
            return "red_block"
        match = re.search(r"(?:pick|grasp)\s+(?:the\s+)?([a-z0-9_ -]+?)(?:\s+and|\s+then|$)", text)
        if match:
            candidate = match.group(1).strip().replace(" ", "_").replace("-", "_")
            if candidate:
                return candidate
        return "red_block"

    def _target_id(self, text: str, world: dict[str, Any]) -> str:
        objects = world.get("state", {}).get("objects", {})
        for object_id in objects:
            if object_id.lower() in text:
                return object_id
        if "tray" in text:
            return "tray"
        match = re.search(r"(?:on|in|at|to)\s+(?:the\s+)?([a-z0-9_ -]+?)(?:\.|$)", text)
        if match:
            candidate = match.group(1).strip().replace(" ", "_").replace("-", "_")
            if candidate:
                return candidate
        return "tray"

    def _move_params(self, text: str, robot: dict[str, Any]) -> dict[str, Any]:
        numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", text)]
        capabilities = robot.get("capabilities", [])
        move_schema = {}
        for capability in capabilities:
            if capability.get("name") == "move_to":
                move_schema = capability.get("params_schema", {})
        required = move_schema.get("required", ["x", "y", "z"])
        params: dict[str, Any] = {}
        for index, name in enumerate(required):
            params[name] = numbers[index] if index < len(numbers) else 0.0
        return params

