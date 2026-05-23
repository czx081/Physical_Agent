"""HAL driver for XiaoZhi ESP32 robots exposing a local MCP WebSocket."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import socket
import ssl
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hal.base_driver import BaseDriver

_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
_OTTO_ACTION_ALIASES = {
    "wave": "hand_wave",
    "waving": "hand_wave",
    "handwave": "hand_wave",
    "reset": "home",
    "stand": "home",
}
_OTTO_ARG_RANGES = {
    "steps": (1, 100),
    "speed": (100, 3000),
    "direction": (-1, 1),
    "amount": (0, 170),
    "arm_swing": (0, 170),
}
_OTTO_ACTION_ARGS = {
    "walk": {"steps", "speed", "direction", "arm_swing"},
    "turn": {"steps", "speed", "direction", "arm_swing"},
    "jump": {"steps", "speed"},
    "swing": {"steps", "speed", "amount"},
    "moonwalk": {"steps", "speed", "direction", "amount"},
    "bend": {"steps", "speed", "direction"},
    "shake_leg": {"steps", "speed", "direction"},
    "updown": {"steps", "speed", "amount"},
    "whirlwind_leg": {"steps", "speed", "amount"},
    "hands_up": {"speed", "direction"},
    "hands_down": {"speed", "direction"},
    "hand_wave": {"direction"},
    "windmill": {"steps", "speed", "amount"},
    "takeoff": {"steps", "speed", "amount"},
    "fitness": {"steps", "speed", "amount"},
    "greeting": {"steps", "direction"},
    "shy": {"steps", "direction"},
}


def _parse_int(raw: str | None, default: int) -> int:
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_float(raw: str | None, default: float) -> float:
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw in (None, ""):
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


class XiaoZhiMcpWebSocketClient:
    """Small JSON-RPC client for XiaoZhi's local ``/ws`` MCP control socket."""

    def __init__(
        self,
        url: str,
        *,
        connect_timeout_s: float = 2.0,
        timeout_s: float = 2.0,
    ) -> None:
        self.url = url
        self.connect_timeout_s = connect_timeout_s
        self.timeout_s = timeout_s
        self._ws: Any | None = None
        self._next_id = 1

    @property
    def is_connected(self) -> bool:
        return self._ws is not None

    def connect(self) -> None:
        self.close()
        parsed = urlparse(self.url)
        if parsed.scheme not in {"ws", "wss"}:
            raise RuntimeError(f"unsupported WebSocket URL scheme: {parsed.scheme}")
        if not parsed.hostname:
            raise RuntimeError(f"invalid WebSocket URL: {self.url}")

        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        sock = socket.create_connection(
            (parsed.hostname, port),
            timeout=self.connect_timeout_s,
        )
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=parsed.hostname)
        sock.settimeout(self.connect_timeout_s)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host = parsed.hostname if parsed.port is None else f"{parsed.hostname}:{port}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = self._read_http_response(sock)
        self._validate_handshake(response, key)
        sock.settimeout(self.timeout_s)
        self._ws = sock

    def close(self) -> None:
        ws = self._ws
        self._ws = None
        if ws is None:
            return
        try:
            self._send_frame(b"", opcode=0x8, sock=ws)
        except Exception:
            pass
        try:
            ws.close()
        except Exception:
            pass

    def initialize(self) -> dict[str, Any]:
        response = self.request(
            "initialize",
            {
                "capabilities": {},
                "clientInfo": {"name": "PhysicalAgent", "version": "0.1"},
            },
        )
        return self._response_result(response)

    def list_tools(self, *, with_user_tools: bool = True) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor = ""
        while True:
            response = self.request(
                "tools/list",
                {"cursor": cursor, "withUserTools": with_user_tools},
            )
            result = self._response_result(response)
            page_tools = result.get("tools", [])
            if isinstance(page_tools, list):
                tools.extend(item for item in page_tools if isinstance(item, dict))
            cursor = str(result.get("nextCursor") or "")
            if not cursor:
                break
        return tools

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        response = self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            timeout_s=timeout_s,
        )
        return self._response_result(response)

    def send_tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> int:
        return self.send_request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )

    def send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        if not self.is_connected:
            raise RuntimeError("websocket is not connected")

        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        self._send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return request_id

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_connected:
            raise RuntimeError("websocket is not connected")

        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        sock = self._ws
        if sock is None:
            raise RuntimeError("websocket is not connected")
        old_timeout = sock.gettimeout()
        if timeout_s is not None:
            sock.settimeout(timeout_s)
        try:
            self._send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            deadline = time.monotonic() + (timeout_s or self.timeout_s)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"timed out waiting for MCP response to {method}")
                sock.settimeout(remaining)
                message = self._recv_text()
                response = self._decode_message(message)
                if response.get("id") == request_id:
                    return response
        finally:
            sock.settimeout(old_timeout)

    def _read_http_response(self, sock: socket.socket) -> bytes:
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("websocket handshake closed before response")
            response += chunk
            if len(response) > 65536:
                raise RuntimeError("websocket handshake response too large")
        return response

    def _validate_handshake(self, response: bytes, key: str) -> None:
        head = response.split(b"\r\n\r\n", 1)[0].decode("latin1", errors="replace")
        lines = head.split("\r\n")
        if not lines or " 101 " not in f" {lines[0]} ":
            raise RuntimeError(f"websocket handshake failed: {lines[0] if lines else head}")

        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

        accept = headers.get("sec-websocket-accept")
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if accept != expected:
            raise RuntimeError("websocket handshake failed: invalid Sec-WebSocket-Accept")

    def _send_text(self, message: str) -> None:
        self._send_frame(message.encode("utf-8"), opcode=0x1)

    def _send_frame(
        self,
        payload: bytes,
        *,
        opcode: int,
        sock: socket.socket | None = None,
    ) -> None:
        sock = sock or self._ws
        if sock is None:
            raise RuntimeError("websocket is not connected")
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        sock.sendall(header + masked)

    def _recv_text(self) -> str:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x1:
                return payload.decode("utf-8", errors="replace")
            if opcode == 0x2:
                return payload.decode("utf-8", errors="replace")
            if opcode == 0x8:
                self.close()
                raise RuntimeError("websocket closed by peer")
            if opcode == 0x9:
                self._send_frame(payload, opcode=0xA)

    def _recv_frame(self) -> tuple[int, bytes]:
        sock = self._ws
        if sock is None:
            raise RuntimeError("websocket is not connected")
        first = self._recv_exact(2)
        byte1, byte2 = first
        opcode = byte1 & 0x0F
        masked = bool(byte2 & 0x80)
        length = byte2 & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, size: int) -> bytes:
        sock = self._ws
        if sock is None:
            raise RuntimeError("websocket is not connected")
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise RuntimeError("websocket closed")
            data += chunk
        return data

    def _decode_message(self, message: str | bytes) -> dict[str, Any]:
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="replace")
        data = json.loads(message)
        if isinstance(data, dict) and data.get("type") == "mcp":
            payload = data.get("payload")
            if isinstance(payload, dict):
                return payload
        if isinstance(data, dict):
            return data
        raise RuntimeError(f"unexpected MCP response: {data!r}")

    def _response_result(self, response: dict[str, Any]) -> dict[str, Any]:
        if "error" in response:
            error = response["error"]
            if isinstance(error, dict):
                raise RuntimeError(str(error.get("message") or error))
            raise RuntimeError(str(error))
        result = response.get("result")
        if isinstance(result, dict):
            return result
        return {"content": [{"type": "text", "text": str(result)}], "isError": False}


class XiaoZhiMcpDriver(BaseDriver):
    """Control a XiaoZhi ESP32 robot through its local MCP WebSocket server."""

    def __init__(
        self,
        gui: bool = False,
        *,
        host: str | None = None,
        port: int | None = None,
        path: str | None = None,
        url: str | None = None,
        robot_id: str | None = None,
        connect_timeout_s: float | None = None,
        response_timeout_s: float | None = None,
        reconnect_interval_s: float | None = None,
        reconnect_policy: str = "auto",
        discover_on_connect: bool = True,
        wait_for_responses: bool | None = None,
        **_kwargs: Any,
    ) -> None:
        self._gui = gui
        self.host = (
            host or os.environ.get("XIAOZHI_MCP_HOST") or "192.168.66.237"
        ).strip()
        self.port = (
            port
            if port is not None
            else _parse_int(os.environ.get("XIAOZHI_MCP_PORT"), 8080)
        )
        self.path = (
            path or os.environ.get("XIAOZHI_MCP_PATH") or "/ws"
        ).strip() or "/ws"
        if not self.path.startswith("/"):
            self.path = "/" + self.path
        self.url = (url or os.environ.get("XIAOZHI_MCP_URL") or "").strip()
        if not self.url:
            self.url = f"ws://{self.host}:{self.port}{self.path}"

        self.robot_id = (
            robot_id
            if robot_id is not None
            else (os.environ.get("XIAOZHI_MCP_ROBOT_ID") or "xiaozhi_robot_001")
        ).strip()
        self.connect_timeout_s = max(
            connect_timeout_s
            if connect_timeout_s is not None
            else _parse_float(os.environ.get("XIAOZHI_MCP_CONNECT_TIMEOUT_S"), 2.0),
            0.1,
        )
        self.response_timeout_s = max(
            response_timeout_s
            if response_timeout_s is not None
            else _parse_float(os.environ.get("XIAOZHI_MCP_RESPONSE_TIMEOUT_S"), 2.0),
            0.1,
        )
        self.reconnect_interval_s = max(
            reconnect_interval_s
            if reconnect_interval_s is not None
            else _parse_float(os.environ.get("XIAOZHI_MCP_RECONNECT_INTERVAL_S"), 5.0),
            0.0,
        )
        self.reconnect_policy = reconnect_policy
        self.discover_on_connect = discover_on_connect
        self.wait_for_responses = (
            wait_for_responses
            if wait_for_responses is not None
            else _parse_bool(os.environ.get("XIAOZHI_MCP_WAIT_FOR_RESPONSES"), True)
        )

        self._objects: dict[str, dict] = {}
        self._client: Any | None = None
        self._tools: list[dict[str, Any]] = []
        self._last_connect_attempt = 0.0
        self._runtime_state = {"robots": {self.robot_id: self._make_robot_state()}}

    def get_profile_path(self) -> Path:
        return _PROFILES_DIR / "xiaozhi_mcp.md"

    def load_scene(self, scene: dict[str, dict]) -> None:
        self._objects = dict(scene)

    def execute_action(self, action_type: str, params: dict) -> str:
        try:
            self._validate_robot_id(params)
            if action_type == "connect_robot":
                return "XiaoZhi MCP connection established." if self.connect() else self._conn_error()
            if action_type == "check_connection":
                return "connected" if self.health_check() else "disconnected"
            if action_type == "disconnect_robot":
                self.disconnect()
                return "XiaoZhi MCP connection closed."
            if action_type == "list_tools":
                tools = self._list_tools(force=True)
                return self._format_tools(tools)
            if action_type == "call_tool":
                return self._execute_call_tool(params)
            if action_type == "get_device_status":
                return self._call_tool_summary("self.get_device_status", {})
            if action_type == "set_volume":
                volume = int(params.get("volume", 50))
                if volume < 0 or volume > 100:
                    raise ValueError("volume must be between 0 and 100")
                return self._call_tool_summary("self.audio_speaker.set_volume", {"volume": volume})
            if action_type in {"otto_action", "robot_action"}:
                return self._execute_otto_action(params)
            if action_type in {"otto_home", "home"}:
                return self._call_tool_summary("self.otto.action", {"action": "home"})
            if action_type in {"otto_stop", "stop"}:
                return self._execute_stop()
            return f"Unknown action: {action_type}"
        except ValueError as exc:
            return self._error_result(str(exc))
        except Exception as exc:
            self._set_connection_status("error", last_error=str(exc))
            return self._error_result(f"{action_type} failed: {exc}")

    def get_scene(self) -> dict[str, dict]:
        return dict(self._objects)

    def connect(self) -> bool:
        return self._connect(force=True)

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._set_connection_status("disconnected", last_error=None)

    def is_connected(self) -> bool:
        return bool(self._client) and bool(getattr(self._client, "is_connected", False))

    def health_check(self) -> bool:
        if self.is_connected():
            self._touch_heartbeat()
            self._set_connection_status("connected", last_error=None)
            return True
        if self.reconnect_policy == "auto":
            return self._connect(force=False)
        self._set_connection_status("disconnected", last_error="disconnected")
        return False

    def get_runtime_state(self) -> dict[str, Any]:
        return copy.deepcopy(self._runtime_state)

    def close(self) -> None:
        self.disconnect()

    def _build_client(self) -> XiaoZhiMcpWebSocketClient:
        return XiaoZhiMcpWebSocketClient(
            self.url,
            connect_timeout_s=self.connect_timeout_s,
            timeout_s=self.response_timeout_s,
        )

    def _connect(self, *, force: bool) -> bool:
        if self.is_connected():
            self._touch_heartbeat()
            self._set_connection_status("connected", last_error=None)
            return True

        now = time.monotonic()
        if not force and now - self._last_connect_attempt < self.reconnect_interval_s:
            return False
        self._last_connect_attempt = now

        if not self.url:
            self._set_connection_status("error", last_error="missing XiaoZhi MCP URL")
            return False

        self._set_connection_status("connecting", last_error=None)
        try:
            client = self._build_client()
            client.connect()
            if self.wait_for_responses:
                client.initialize()
            self._client = client
            if self.wait_for_responses and self.discover_on_connect:
                self._tools = client.list_tools(with_user_tools=True)
            self._touch_heartbeat()
            self._set_connection_status("connected", last_error=None)
            self._set_nav_state(status="idle", mode="mcp")
            return True
        except Exception as exc:
            self._client = None
            self._set_connection_status("error", last_error=str(exc))
            return False

    def _ensure_connected(self) -> None:
        if not self.is_connected() and not self.connect():
            raise RuntimeError(self._robot_state()["connection_state"].get("last_error") or "not connected")

    def _list_tools(self, *, force: bool = False) -> list[dict[str, Any]]:
        self._ensure_connected()
        if not self.wait_for_responses:
            raise RuntimeError(
                "device is configured for fire-and-forget control; tool discovery requires wait_for_responses=true"
            )
        if force or not self._tools:
            self._tools = self._client.list_tools(with_user_tools=True)
        self._set_tools(self._tools)
        return list(self._tools)

    def _execute_call_tool(self, params: dict[str, Any]) -> str:
        name = str(params.get("name") or params.get("tool") or "").strip()
        if not name:
            raise ValueError("call_tool requires name")
        arguments = params.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError("call_tool arguments must be an object")
        timeout_s = params.get("timeout_s")
        timeout = float(timeout_s) if timeout_s is not None else self.response_timeout_s
        return self._call_tool_summary(name, arguments, timeout_s=timeout)

    def _execute_otto_action(self, params: dict[str, Any]) -> str:
        action = str(params.get("action") or "home").strip().lower().replace("-", "_")
        action = _OTTO_ACTION_ALIASES.get(action, action)
        if not action:
            raise ValueError("otto_action requires action")
        arguments: dict[str, Any] = {"action": action}

        allowed_args = _OTTO_ACTION_ARGS.get(action, set(_OTTO_ARG_RANGES))
        for key in allowed_args:
            if key in params:
                value = int(params[key])
                minimum, maximum = _OTTO_ARG_RANGES[key]
                if key == "speed" and value < minimum:
                    # LLMs often use speed=1 to mean "normal/slow"; Otto expects
                    # milliseconds in [100, 3000], so omit bad semantic speeds
                    # and let firmware use its default.
                    continue
                arguments[key] = max(minimum, min(maximum, value))
        return self._call_tool_summary("self.otto.action", arguments)

    def _execute_stop(self) -> str:
        tool_names = self._tool_names()
        if "self.otto.stop" in tool_names or not tool_names:
            return self._call_tool_summary("self.otto.stop", {})
        for candidate in ("self.dog.basic_control", "self.otto.action"):
            if candidate in tool_names:
                if candidate == "self.otto.action":
                    return self._call_tool_summary(candidate, {"action": "home"})
                return self._call_tool_summary(candidate, {"action": "stop"})
        raise RuntimeError("no known stop tool is available")

    def _call_tool_summary(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout_s: float | None = None,
    ) -> str:
        self._ensure_connected()
        if not self.wait_for_responses:
            request_id = self._client.send_tool_call(name, arguments)
            self._touch_heartbeat()
            self._set_nav_state(status="sent", mode="mcp", last_action=name)
            return f"{name} -> sent (request_id={request_id}, no response expected)"

        result = self._client.call_tool(name, arguments, timeout_s=timeout_s or self.response_timeout_s)
        self._touch_heartbeat()
        self._set_nav_state(status="idle", mode="mcp", last_action=name)
        return f"{name} -> {self._format_tool_result(result)}"

    def _tool_names(self) -> set[str]:
        if not self._tools and self.is_connected():
            try:
                self._list_tools(force=True)
            except Exception:
                pass
        return {
            str(tool.get("name"))
            for tool in self._tools
            if isinstance(tool, dict) and tool.get("name")
        }

    def _validate_robot_id(self, params: dict[str, Any]) -> None:
        requested = str(params.get("robot_id", "")).strip()
        if requested and requested != self.robot_id:
            raise ValueError(
                f"robot_id mismatch: requested={requested}, configured={self.robot_id}"
            )

    def _format_tools(self, tools: list[dict[str, Any]]) -> str:
        names = [str(tool.get("name")) for tool in tools if tool.get("name")]
        self._set_tools(tools)
        if not names:
            return "No MCP tools reported by XiaoZhi device."
        preview = ", ".join(names[:20])
        suffix = "" if len(names) <= 20 else f", ... (+{len(names) - 20} more)"
        return f"Available MCP tools ({len(names)}): {preview}{suffix}"

    def _format_tool_result(self, result: dict[str, Any]) -> str:
        content = result.get("content")
        if isinstance(content, list):
            texts = [
                str(item.get("text"))
                for item in content
                if isinstance(item, dict) and item.get("type") == "text" and "text" in item
            ]
            if texts:
                return " | ".join(texts)
        return json.dumps(result, ensure_ascii=False, sort_keys=True)

    def _make_robot_state(self) -> dict[str, Any]:
        now = self._now()
        return {
            "connection_state": {
                "status": "disconnected",
                "endpoint": self.url,
                "last_heartbeat": None,
                "last_error": None,
                "updated_at": now,
            },
            "robot_pose": {
                "frame": "lan",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "yaw": 0.0,
                "updated_at": now,
            },
            "nav_state": {
                "mode": "mcp",
                "status": "idle",
                "last_action": None,
                "updated_at": now,
            },
            "mcp": {
                "tool_count": 0,
                "tools": [],
            },
        }

    def _robot_state(self) -> dict[str, Any]:
        return self._runtime_state["robots"][self.robot_id]

    def _set_connection_status(self, status: str, *, last_error: str | None) -> None:
        state = self._robot_state()["connection_state"]
        state["status"] = status
        state["endpoint"] = self.url
        state["last_error"] = last_error
        state["updated_at"] = self._now()

    def _touch_heartbeat(self) -> None:
        self._robot_state()["connection_state"]["last_heartbeat"] = self._now()

    def _set_nav_state(
        self,
        *,
        status: str,
        mode: str = "mcp",
        last_action: str | None = None,
    ) -> None:
        state = self._robot_state()["nav_state"]
        state["mode"] = mode
        state["status"] = status
        if last_action is not None:
            state["last_action"] = last_action
        state["updated_at"] = self._now()

    def _set_tools(self, tools: list[dict[str, Any]]) -> None:
        names = [
            str(tool.get("name"))
            for tool in tools
            if isinstance(tool, dict) and tool.get("name")
        ]
        self._robot_state()["mcp"] = {
            "tool_count": len(names),
            "tools": names,
        }

    def _conn_error(self) -> str:
        error = self._robot_state()["connection_state"].get("last_error")
        return f"Connection error: {error or 'not connected'}"

    def _error_result(self, message: str) -> str:
        self._set_nav_state(status="failed", last_action=None)
        return f"Error: {message}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
