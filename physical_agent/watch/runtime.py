from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from physical_agent.config import DEFAULT_CONFIG_NAME, PhysicalAgentConfig, load_config
from physical_agent.drivers.loader import LoadedDriver, load_driver
from physical_agent.protocol.schemas import Action, ActionResult, Observation, RobotRuntimeProfile
from physical_agent.protocol.workspace import Workspace
from physical_agent.watch.safety import SafetyGate


class WatchRuntime:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_NAME):
        self.config_path = Path(config_path).resolve()
        self.base_dir = self.config_path.parent
        self.config: PhysicalAgentConfig | None = None
        self.workspace: Workspace | None = None
        self.loaded_drivers: dict[str, LoadedDriver] = {}
        self.profiles: dict[str, RobotRuntimeProfile] = {}
        self.started = False

    async def setup(self) -> None:
        if self.started:
            return
        self.config = load_config(self.config_path)
        workspace_path = self.config.workspace_path(self.base_dir)
        self.workspace = Workspace(workspace_path)
        self.workspace.initialize()
        self.workspace.append_log("`physical-agent watch` started.", actor="watch")

        for robot_id, robot_config in self.config.robots.items():
            loaded = load_driver(
                robot_id=robot_id,
                driver_ref=robot_config.driver,
                config=robot_config.config,
                workspace_path=self.workspace.path,
                artifacts_path=self.workspace.artifacts_path,
                base_dir=self.base_dir,
            )
            await loaded.driver.connect()
            capabilities = loaded.driver.capabilities()
            self.loaded_drivers[robot_id] = loaded
            self.profiles[robot_id] = RobotRuntimeProfile(
                robot_id=robot_id,
                kind=loaded.manifest.robot.kind,
                driver=loaded.manifest.name,
                status="connected",
                capabilities=capabilities,
                requires_approval=(
                    self.config.watch.require_human_approval
                    or not loaded.manifest.robot.supports_simulation
                ),
            )
            self.workspace.append_log(f"`{robot_id}` connected via `{loaded.manifest.name}`.", actor="watch")

        self.workspace.write_capabilities(self._capabilities_document())
        await self.update_world()
        self.started = True

    async def shutdown(self) -> None:
        for loaded in self.loaded_drivers.values():
            await loaded.driver.disconnect()
        if self.workspace is not None:
            self.workspace.append_log("`physical-agent watch` stopped.", actor="watch")
        self.started = False

    async def run_forever(self) -> None:
        await self.setup()
        assert self.config is not None
        try:
            while True:
                await self.step(setup=False)
                await asyncio.sleep(self.config.watch.tick_ms / 1000)
        finally:
            await self.shutdown()

    async def step(self, *, setup: bool = True) -> int:
        if setup:
            await self.setup()
        workspace = self._workspace()
        actions_doc = workspace.read_actions()
        pending: list[Action] = actions_doc["pending"]
        completed: list[Action] = actions_doc["completed"]
        cancelled: list[Action] = actions_doc["cancelled"]

        completed_ids = {action.id for action in completed}
        executed_ids = {action.id for action in completed + cancelled}
        for item in workspace.read_feedback().get("history", []):
            action_id = item.get("action_id")
            if action_id:
                executed_ids.add(str(action_id))
        safety_rules = workspace.read_safety()["rules"]
        executed_count = 0

        index = 0
        while index < len(pending):
            action = pending[index]
            gate = SafetyGate(
                robots=self.profiles,
                safety_rules=safety_rules,
                completed_action_ids=completed_ids,
                executed_action_ids=executed_ids,
            )
            decision = gate.validate(action)
            if not decision.ok:
                result = ActionResult(status="failed", message=decision.message)
                cancelled.append(action)
                pending.pop(index)
                executed_ids.add(action.id)
                await self._record_action_result(action, result)
                workspace.write_actions(pending, completed, cancelled)
                continue

            loaded = self.loaded_drivers[action.robot]
            result = await loaded.driver.execute(action)
            if result.status == "completed":
                completed.append(action)
                completed_ids.add(action.id)
            else:
                cancelled.append(action)
            pending.pop(index)
            executed_ids.add(action.id)
            executed_count += 1
            await self._record_action_result(action, result)
            workspace.write_actions(pending, completed, cancelled)
            await self.update_world()

        if executed_count == 0:
            await self.update_world()
        return executed_count

    async def update_world(self) -> Observation:
        observations = [await loaded.driver.observe() for loaded in self.loaded_drivers.values()]
        merged = merge_observations(observations)
        self._workspace().write_world(merged)
        return merged

    def _capabilities_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for robot_id, profile in self.profiles.items():
            document[robot_id] = {
                "kind": profile.kind,
                "driver": profile.driver,
                "status": profile.status,
                "requires_approval": profile.requires_approval,
                "capabilities": [
                    capability.model_dump(mode="json", exclude_none=True)
                    for capability in profile.capabilities
                ],
            }
        return document

    async def _record_action_result(self, action: Action, result: ActionResult) -> None:
        workspace = self._workspace()
        feedback = workspace.read_feedback()
        latest = {
            "action_id": action.id,
            "status": result.status,
            "robot": action.robot,
            "capability": action.capability,
            "message": result.message,
            "result": result.result,
            "artifacts": result.artifacts,
        }
        history = list(feedback["history"])
        history.append(latest)
        workspace.write_feedback(latest, history)
        workspace.append_log(
            f"Action `{action.id}` {result.status}: {result.message}",
            actor="watch",
        )

    def _workspace(self) -> Workspace:
        if self.workspace is None:
            raise RuntimeError("WatchRuntime has not been set up.")
        return self.workspace


def merge_observations(observations: list[Observation]) -> Observation:
    if not observations:
        return Observation(summary="No robots are configured.")
    summary = " ".join(observation.summary for observation in observations if observation.summary)
    robots: dict[str, Any] = {}
    objects: dict[str, Any] = {}
    environment: dict[str, Any] = {}
    artifacts: list[str] = []
    raw: dict[str, Any] = {}
    for observation in observations:
        robots.update(observation.robots)
        objects.update(observation.objects)
        environment.update(observation.environment)
        artifacts.extend(observation.artifacts)
        raw.update(observation.raw)
    return Observation(
        summary=summary,
        robots=robots,
        objects=objects,
        environment=environment,
        artifacts=artifacts,
        raw=raw,
    )
