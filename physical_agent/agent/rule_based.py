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
        wants_say = any(word in text for word in ("say", "speak", "tts", "播报", "说"))
        wants_light = any(word in text for word in ("light", "rgb", "led", "灯"))

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

        if wants_say:
            robot_id = self._choose_robot(robots, ["say"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="say",
                        params={"text": self._speech_text(task)},
                        reason="The task asks the device to speak.",
                    )
                )

        if wants_light:
            robot_id = self._choose_robot(robots, ["set_light"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="set_light",
                        params=self._light_params(text),
                        reason="The task asks to change a light.",
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

    def _speech_text(self, task: str) -> str:
        match = re.search(r'["“](.+?)["”]', task)
        if match:
            return match.group(1).strip()
        match = re.search(r"(?:say|speak|播报|说)\s+(.+)$", task, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()[:120]
        return task.strip()[:120]

    def _light_params(self, text: str) -> dict[str, int]:
        numbers = [int(value) for value in re.findall(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)\b", text)]
        if len(numbers) >= 3:
            return {"r": numbers[0], "g": numbers[1], "b": numbers[2]}
        colors = {
            "red": {"r": 255, "g": 0, "b": 0},
            "green": {"r": 0, "g": 180, "b": 0},
            "blue": {"r": 0, "g": 90, "b": 255},
            "white": {"r": 255, "g": 255, "b": 255},
            "yellow": {"r": 255, "g": 210, "b": 0},
            "红": {"r": 255, "g": 0, "b": 0},
            "绿": {"r": 0, "g": 180, "b": 0},
            "蓝": {"r": 0, "g": 90, "b": 255},
            "白": {"r": 255, "g": 255, "b": 255},
            "黄": {"r": 255, "g": 210, "b": 0},
        }
        for name, params in colors.items():
            if name in text:
                return params
        return {"r": 255, "g": 255, "b": 255}
