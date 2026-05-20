from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from physical_agent.drivers.base import PhysicalDriver
from physical_agent.env import load_dotenv
from physical_agent.protocol.schemas import Action, ActionResult, Capability, DriverContext, HealthStatus, Observation


MANIFEST = {
    "schema": "physical-agent/driver/v1",
    "name": "xiaozhi_mcp",
    "version": "0.1.0",
    "description": "Example driver that treats a Xiaozhi MCP tool endpoint as hardware.",
    "entrypoint": {"module": "xiaozhi_mcp", "class": "XiaozhiMcpDriver"},
    "robot": {"kind": "mcp_device", "supports_simulation": True},
    "config_schema": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["mock", "http"], "default": "mock"},
            "endpoint_env": {"type": "string", "default": "XIAOZHI_MCP_ENDPOINT"},
            "token_env": {"type": "string", "default": "XIAOZHI_MCP_TOKEN"},
            "timeout_s": {"type": "number", "minimum": 1, "default": 10},
            "device_name": {"type": "string", "default": "xiaozhi-device"},
            "tool_prefix": {"type": "string", "default": "self.device"},
            "tools": {
                "type": "object",
                "properties": {
                    "observe": {"type": "string"},
                    "say": {"type": "string"},
                    "set_light": {"type": "string"},
                },
                "additionalProperties": {"type": "string"},
            },
            "mock_state": {"type": "object"},
        },
        "additionalProperties": False,
    },
    "dependencies": {"python": []},
    "capability_contract": {"source": "runtime"},
}


DEFAULT_TOOLS = {
    "observe": "self.device.observe",
    "say": "self.audio.speaker.speak",
    "set_light": "self.light.set_rgb",
}


class XiaozhiMcpDriver(PhysicalDriver):
    """Physical Agent driver for a Xiaozhi-style MCP device adapter.

    The driver deliberately lives on the watch side. The agent only sees the
    capabilities rendered into CAPABILITIES.md and never calls the MCP endpoint
    directly.
    """

    def __init__(self, context: DriverContext):
        super().__init__(context)
        load_dotenv(context.workspace_path.parent / ".env")
        self.config = dict(context.config)
        self.mode = self.config.get("mode", "mock")
        self.timeout_s = float(self.config.get("timeout_s", 10))
        self.device_name = self.config.get("device_name", "xiaozhi-device")
        self.tool_prefix = self.config.get("tool_prefix", "self.device")
        self.tools = dict(DEFAULT_TOOLS)
        self.tools.update(self.config.get("tools", {}))
        self.session_id: str | None = None
        self.remote_tools: dict[str, dict[str, Any]] = {}
        self.connected = False
        self.last_message: str | None = None
        self.state = _default_mock_state(self.config.get("mock_state", {}))

    async def connect(self) -> None:
        if self.mode == "http":
            self._endpoint()
            await self._initialize_remote_session()
            await self._refresh_remote_tools()
        elif self.mode != "mock":
            raise ValueError(f"Unsupported xiaozhi_mcp mode: {self.mode}")
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def health(self) -> HealthStatus:
        if self.mode == "http":
            ok = self.connected and bool(self._endpoint(required=False))
            message = "connected to MCP endpoint" if ok else "missing MCP endpoint"
            return HealthStatus(
                ok=ok,
                message=message,
                details={
                    "mode": self.mode,
                    "session_id": self.session_id,
                    "remote_tools": sorted(self.remote_tools),
                },
            )
        return HealthStatus(ok=self.connected, message="mock device connected", details={"mode": self.mode})

    async def observe(self) -> Observation:
        if self.mode == "http" and self.connected:
            response = await self._call_tool(self.tools["observe"], {})
            summary = str(response.get("summary") or "Xiaozhi MCP device responded to observe.")
            raw_state = response.get("state") if isinstance(response.get("state"), dict) else response
            return Observation(
                summary=summary,
                robots={
                    self.context.robot_id: {
                        "status": "idle",
                        "device": self.device_name,
                        "mode": self.mode,
                        "session_id": self.session_id,
                    }
                },
                environment={"xiaozhi_mcp": raw_state},
                raw={"mcp_observe": response},
            )

        summary = (
            f"{self.device_name} is online in mock mode. "
            f"Light is {self.state['light']['power']} and color is {self.state['light']['color']}."
        )
        return Observation(
            summary=summary,
            robots={
                self.context.robot_id: {
                    "status": "idle" if self.connected else "offline",
                    "device": self.device_name,
                    "mode": self.mode,
                    "last_message": self.last_message,
                }
            },
            environment={"xiaozhi_mcp": deepcopy(self.state)},
        )

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="observe",
                description="Observe the Xiaozhi MCP device state.",
                params_schema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Capability(
                name="say",
                description="Ask the Xiaozhi MCP device to speak a short sentence.",
                params_schema={
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string", "minLength": 1, "maxLength": 120},
                    },
                    "additionalProperties": False,
                },
                constraints={"text_max_length": 120},
            ),
            Capability(
                name="set_light",
                description="Set an RGB light through the Xiaozhi MCP device.",
                params_schema={
                    "type": "object",
                    "required": ["r", "g", "b"],
                    "properties": {
                        "r": {"type": "integer", "minimum": 0, "maximum": 255},
                        "g": {"type": "integer", "minimum": 0, "maximum": 255},
                        "b": {"type": "integer", "minimum": 0, "maximum": 255},
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
                message="Xiaozhi MCP observation completed.",
                result={"observation": observation.model_dump(mode="json")},
            )
        if action.capability == "say":
            text = str(action.params["text"])
            if self.mode == "http":
                response = await self._call_tool(self.tools["say"], {"text": text})
            else:
                response = {"spoken": text, "mode": "mock"}
            self.last_message = text
            self.state["speaker"]["last_text"] = text
            return ActionResult(
                status="completed",
                message=f"Xiaozhi MCP device said: {text}",
                result={"text": text, "mcp_result": response},
            )
        if action.capability == "set_light":
            params = {key: int(action.params[key]) for key in ("r", "g", "b")}
            if self.mode == "http":
                response = await self._call_tool(self.tools["set_light"], params)
            else:
                response = {"color": params, "mode": "mock"}
            self.state["light"] = {
                "power": "on",
                "color": params,
            }
            return ActionResult(
                status="completed",
                message=f"Xiaozhi MCP light set to rgb({params['r']}, {params['g']}, {params['b']}).",
                result={"color": params, "mcp_result": response},
            )
        return ActionResult(status="failed", message=f"Unsupported capability: {action.capability}")

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(tool_name),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        return await asyncio.to_thread(self._post_jsonrpc, payload)

    async def _initialize_remote_session(self) -> None:
        response = await asyncio.to_thread(
            self._post_jsonrpc,
            {
                "jsonrpc": "2.0",
                "id": self._next_request_id("initialize"),
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "physical-agent-watch",
                        "version": "0.1.0",
                    },
                    "capabilities": {},
                },
            },
        )
        session_id = response.get("session_id") or response.get("sessionId")
        if session_id is not None:
            self.session_id = str(session_id)

    async def _refresh_remote_tools(self) -> None:
        response = await asyncio.to_thread(
            self._post_jsonrpc,
            {
                "jsonrpc": "2.0",
                "id": self._next_request_id("tools/list"),
                "method": "tools/list",
                "params": {},
            },
        )
        tools = response.get("tools", [])
        if isinstance(tools, list):
            self.remote_tools = {
                str(tool.get("name")): tool
                for tool in tools
                if isinstance(tool, dict) and tool.get("name")
            }
            for key, tool_name in list(self.tools.items()):
                if tool_name not in self.remote_tools and self.mode == "http":
                    # Keep the configured tool mapping even when the endpoint does not echo it.
                    self.remote_tools[tool_name] = {"name": tool_name, "mapped_from": key}

    def _post_jsonrpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint(),
            data=body,
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            data = json.loads(response.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(f"MCP tool call failed: {data['error']}")
        result = data.get("result", {})
        return result if isinstance(result, dict) else {"value": result}

    def _next_request_id(self, method: str) -> str:
        suffix = f"{self.context.robot_id}:{method}"
        if self.session_id:
            return f"{self.session_id}:{suffix}"
        return f"pa:{suffix}"

    def _endpoint(self, *, required: bool = True) -> str:
        endpoint_env = self.config.get("endpoint_env", "XIAOZHI_MCP_ENDPOINT")
        endpoint = os.getenv(endpoint_env) or self.config.get("endpoint")
        if required and not endpoint:
            raise ValueError(
                f"Missing Xiaozhi MCP endpoint. Set {endpoint_env} in .env or use mode: mock."
            )
        return str(endpoint or "")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token_env = self.config.get("token_env", "XIAOZHI_MCP_TOKEN")
        token = os.getenv(token_env) or self.config.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


def _default_mock_state(overrides: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "light": {"power": "off", "color": {"r": 0, "g": 0, "b": 0}},
        "speaker": {"last_text": None},
        "sensors": {"online": True},
    }
    _deep_update(state, deepcopy(overrides))
    return state


def _deep_update(target: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
