from __future__ import annotations

from pathlib import Path
from typing import Any

from physical_agent.agent.runtime import AgentRuntime
from physical_agent.config import DEFAULT_CONFIG_NAME, load_config
from physical_agent.protocol.schemas import Action
from physical_agent.protocol.workspace import Workspace


class PhysicalAgentMCP:
    """Lightweight MCP-shaped facade over the Markdown workspace.

    The v1 package keeps this dependency-free so MCP support does not become
    part of the critical watch/agent loop. A future adapter can expose these
    methods through a concrete MCP server library.
    """

    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_NAME):
        self.config_path = Path(config_path).resolve()

    async def submit_task(self, task: str) -> dict[str, Any]:
        runtime = AgentRuntime(self.config_path)
        return await runtime.run_task(task, wait_for_feedback=False)

    def get_state(self) -> dict[str, Any]:
        workspace = self._workspace()
        return {
            "capabilities": workspace.read_capabilities(),
            "world": workspace.read_world(),
            "actions": workspace.read_actions(),
            "feedback": workspace.read_feedback(),
        }

    def list_robots(self) -> dict[str, Any]:
        return self._workspace().read_capabilities().get("robots", {})

    def run_action(self, action: dict[str, Any]) -> dict[str, Any]:
        workspace = self._workspace()
        actions = workspace.read_actions()
        pending = actions["pending"]
        pending.append(Action.model_validate(action))
        workspace.write_actions(pending, actions["completed"], actions["cancelled"])
        workspace.append_log(
            f"MCP submitted action `{action.get('id', '<unknown>')}`.",
            actor="mcp",
        )
        return {"ok": True, "message": "Action submitted to Markdown workspace."}

    def _workspace(self) -> Workspace:
        cfg = load_config(self.config_path)
        return Workspace(cfg.workspace_path(self.config_path.parent))

