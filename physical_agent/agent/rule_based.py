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
        wants_open_gripper = any(
            word in text
            for word in (
                "open gripper",
                "open the gripper",
                "gripper open",
                "打开夹爪",
                "张开夹爪",
                "打开抓手",
                "张开抓手",
            )
        )
        wants_close_gripper = any(
            word in text
            for word in (
                "close gripper",
                "close the gripper",
                "gripper close",
                "关闭夹爪",
                "合上夹爪",
                "闭合夹爪",
                "关闭抓手",
                "合上抓手",
            )
        )
        wants_say = any(word in text for word in ("say", "speak", "tts", "播报", "说"))
        wants_light = any(word in text for word in ("light", "rgb", "led", "灯"))
        wants_stop = any(word in text for word in ("stop", "halt", "刹车", "停止"))
        wants_home = any(word in text for word in ("home", "reset", "stand", "归位", "复位", "站好"))
        wants_wave = any(word in text for word in ("wave", "hand wave", "挥手"))
        wants_walk = any(word in text for word in ("walk", "forward", "backward", "前进", "后退"))
        wants_turn = any(word in text for word in ("turn", "左转", "右转"))
        wants_jump = any(word in text for word in ("jump", "跳"))
        wants_volume = any(word in text for word in ("volume", "louder", "quieter", "音量", "声音"))

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

        joint_move = self._joint_move_request(text, robots)
        if joint_move is not None:
            robot_id, params = joint_move
            actions.append(
                Action(
                    id=self._action_id(len(actions) + 1),
                    robot=robot_id,
                    capability="move_joint",
                    params=params,
                    reason="The task asks for a joint-level movement.",
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

        if wants_open_gripper:
            robot_id = self._choose_robot(robots, ["open_gripper"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="open_gripper",
                        params={},
                        reason="The task asks to open the gripper.",
                    )
                )

        if wants_close_gripper:
            robot_id = self._choose_robot(robots, ["close_gripper"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="close_gripper",
                        params={},
                        reason="The task asks to close the gripper.",
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

        if wants_volume:
            robot_id = self._choose_robot(robots, ["set_volume"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="set_volume",
                        params={"volume": self._volume_param(text)},
                        reason="The task asks to change speaker volume.",
                    )
                )

        if wants_wave:
            robot_id = self._choose_robot(robots, ["otto_action"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="otto_action",
                        params={"action": "hand_wave", "direction": self._direction_param(text)},
                        reason="The task asks the robot to wave.",
                    )
                )

        if wants_walk:
            robot_id = self._choose_robot(robots, ["otto_action"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="otto_action",
                        params=self._otto_motion_params("walk", text),
                        reason="The task asks the robot to walk.",
                    )
                )

        if wants_turn:
            robot_id = self._choose_robot(robots, ["otto_action"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="otto_action",
                        params=self._otto_motion_params("turn", text),
                        reason="The task asks the robot to turn.",
                    )
                )

        if wants_jump:
            robot_id = self._choose_robot(robots, ["otto_action"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="otto_action",
                        params={"action": "jump", "steps": 1, "speed": 800},
                        reason="The task asks the robot to jump.",
                    )
                )

        if wants_home:
            robot_id = self._choose_robot(robots, ["home"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="home",
                        params={},
                        reason="The task asks the robot to return home.",
                    )
                )

        if wants_stop:
            robot_id = self._choose_robot(robots, ["stop"])
            if robot_id:
                actions.append(
                    Action(
                        id=self._action_id(len(actions) + 1),
                        robot=robot_id,
                        capability="stop",
                        params={},
                        reason="The task asks the robot to stop.",
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

    def _joint_move_request(self, text: str, robots: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        robot_id = self._choose_robot(robots, ["move_joint"])
        if robot_id is None:
            return None

        move_joint_schema: dict[str, Any] = {}
        for capability in robots[robot_id].get("capabilities", []):
            if capability.get("name") == "move_joint":
                move_joint_schema = capability.get("params_schema", {})
                break

        joint_name_schema = (
            move_joint_schema.get("properties", {}).get("joint_name", {})
            if isinstance(move_joint_schema, dict)
            else {}
        )
        available_joint_names = joint_name_schema.get("enum") or []
        if not isinstance(available_joint_names, list):
            available_joint_names = []

        candidate_joint_name = self._match_joint_name(text, [str(name) for name in available_joint_names])
        if candidate_joint_name is None:
            return None

        number_match = re.search(r"-?\d+(?:\.\d+)?", text)
        if number_match is None:
            return None
        value = float(number_match.group(0))

        if any(token in text for token in (" to ", "到", "target", "set ", "设为", "设置为")):
            return robot_id, {"joint_name": candidate_joint_name, "target_deg": value}
        return robot_id, {"joint_name": candidate_joint_name, "delta_deg": value}

    def _match_joint_name(self, text: str, joint_names: list[str]) -> str | None:
        alias_map = {
            "wrist_roll": ["wrist_roll", "wrist roll", "roll wrist", "腕旋转", "手腕旋转", "腕滚转"],
            "shoulder_pan": ["shoulder_pan", "shoulder pan", "base joint", "底座"],
            "shoulder_lift": ["shoulder_lift", "shoulder lift", "大臂"],
            "elbow_flex": ["elbow_flex", "elbow flex", "elbow", "小臂"],
            "wrist_flex": ["wrist_flex", "wrist flex", "wrist", "手腕"],
        }
        for joint_name in joint_names:
            candidates = alias_map.get(joint_name, [joint_name, joint_name.replace("_", " ")])
            if any(candidate in text for candidate in candidates):
                return joint_name
        return None

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

    def _volume_param(self, text: str) -> int:
        numbers = [int(value) for value in re.findall(r"\b\d{1,3}\b", text)]
        if numbers:
            return max(0, min(100, numbers[0]))
        if any(word in text for word in ("louder", "higher", "大")):
            return 80
        if any(word in text for word in ("quieter", "lower", "小")):
            return 20
        return 50

    def _direction_param(self, text: str) -> int:
        if any(word in text for word in ("left", "左")):
            return -1
        if any(word in text for word in ("right", "右")):
            return 1
        return 1

    def _otto_motion_params(self, action: str, text: str) -> dict[str, int | str]:
        params: dict[str, int | str] = {
            "action": action,
            "steps": 2,
            "speed": 800,
        }
        if action in {"walk", "turn"}:
            params["direction"] = self._direction_param(text)
        numbers = [int(value) for value in re.findall(r"\b\d{1,4}\b", text)]
        if numbers:
            params["steps"] = max(1, min(100, numbers[0]))
        if len(numbers) >= 2:
            params["speed"] = max(100, min(3000, numbers[1]))
        if "backward" in text or "后退" in text:
            params["direction"] = -1
        if "forward" in text or "前进" in text:
            params["direction"] = 1
        return params
