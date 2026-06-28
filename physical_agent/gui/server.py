from __future__ import annotations

import asyncio
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from physical_agent.agent.chat_runtime import ChatRuntime
from physical_agent.agent.driver_coder import DriverCodingAgent
from physical_agent.agent.onboarding import HardwareIntegrationAssistant
from physical_agent.agent.runtime import AgentRuntime
from physical_agent.config import DEFAULT_CONFIG_NAME, load_config, write_default_config
from physical_agent.doctor import doctor_ok, run_doctor
from physical_agent.protocol.schemas import Action
from physical_agent.protocol.workspace import Workspace
from physical_agent.quickstart import setup_project
from physical_agent.watch.runtime import WatchRuntime


STATIC_DIR = Path(__file__).with_name("static")
STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


class GuiController:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_NAME):
        self.config_path = Path(config_path).resolve()
        self.lock = threading.Lock()
        self.watch_runtime: WatchRuntime | None = None

    def state(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {
                "ready": False,
                "watch_started": False,
                "message": "Project is not initialized. Click Setup Project.",
                "doctor": [check.as_dict() for check in run_doctor(self.config_path)],
            }

        config = load_config(self.config_path)
        workspace = Workspace(config.workspace_path(self.config_path.parent))
        if not workspace.exists():
            return {
                "ready": False,
                "watch_started": self._watch_started,
                "message": "Workspace is missing. Click Setup Project.",
                "doctor": [check.as_dict() for check in run_doctor(self.config_path)],
            }

        actions = workspace.read_actions()
        feedback = workspace.read_feedback()
        code_result = _latest_code_result(workspace.read_chat())
        return {
            "ready": True,
            "watch_started": self._watch_started,
            "message": "Ready.",
            "config_path": str(self.config_path),
            "workspace_path": str(workspace.path),
            "task": workspace.read_task(),
            "capabilities": workspace.read_capabilities(),
            "world": workspace.read_world(),
            "code_result": code_result,
            "actions": {
                "pending": _dump_actions(actions["pending"]),
                "completed": _dump_actions(actions["completed"]),
                "cancelled": _dump_actions(actions["cancelled"]),
            },
            "feedback": feedback,
            "chat": workspace.read_chat(),
            "plan": workspace.read_plan(),
            "memory": workspace.read_memory(),
            "doctor": [check.as_dict() for check in run_doctor(self.config_path)],
        }

    def setup(self, *, force: bool = False) -> dict[str, Any]:
        with self.lock:
            if self.watch_runtime is not None and self.watch_runtime.started:
                asyncio.run(self.watch_runtime.shutdown())
            self.watch_runtime = None
            result = setup_project(self.config_path, force=force, publish=True, smoke_test=False)
            self.watch_runtime = WatchRuntime(self.config_path)
            asyncio.run(self.watch_runtime.setup())
            return {"ok": True, "result": result, "state": self.state()}

    def start_watch(self) -> dict[str, Any]:
        with self.lock:
            self._ensure_watch_started()
            return {"ok": True, "message": "Watch runtime is connected.", "state": self.state()}

    def stop_watch(self) -> dict[str, Any]:
        with self.lock:
            if self.watch_runtime is not None and self.watch_runtime.started:
                asyncio.run(self.watch_runtime.shutdown())
            self.watch_runtime = None
            return {"ok": True, "message": "Watch runtime stopped.", "state": self.state()}

    def step_watch(self) -> dict[str, Any]:
        with self.lock:
            self._ensure_watch_started()
            assert self.watch_runtime is not None
            executed = asyncio.run(self.watch_runtime.step(setup=False))
            return {
                "ok": True,
                "message": f"Executed {executed} action(s).",
                "executed": executed,
                "state": self.state(),
            }

    def submit_task(self, task: str) -> dict[str, Any]:
        with self.lock:
            self._ensure_watch_started()
            result = asyncio.run(AgentRuntime(self.config_path).run_task(task, wait_for_feedback=False))
            return {"ok": bool(result["ok"]), "result": _json_safe(result), "state": self.state()}

    def chat_message(self, message: str, *, planner: str = "auto", auto_step: bool = False) -> dict[str, Any]:
        with self.lock:
            self._ensure_watch_started()
            result = ChatRuntime(self.config_path, planner_name=planner).respond(
                message,
                auto_step=False,
            )
            executed = 0
            if auto_step and result["actions"]:
                assert self.watch_runtime is not None
                executed = asyncio.run(self.watch_runtime.step(setup=False))
                result["executed"] = executed
            state = self.state()
            if result.get("code_result") is not None:
                state = {**state, "code_result": result["code_result"]}
            return {
                "ok": True,
                "message": result["reply"],
                "result": _json_safe(result),
                "code_result": _json_safe(result.get("code_result")),
                "executed": executed,
                "state": state,
            }

    def integrate_hardware(
        self,
        source: str,
        *,
        output: str | None = None,
        name: str | None = None,
        llm: bool = False,
        model: str | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            if not self.config_path.exists():
                write_default_config(self.config_path)
            config = load_config(self.config_path)
            Workspace(config.workspace_path(self.config_path.parent)).initialize()
            if llm:
                result = DriverCodingAgent(
                    source,
                    output_dir=output or None,
                    name=name or None,
                    base_dir=self.config_path.parent,
                    model=model or None,
                ).generate()
                message = (
                    f"Generated LLM driver draft at {result.output_path}."
                    if result.llm_used
                    else f"Generated safe scaffold at {result.output_path}; LLM coding did not validate."
                )
                return {
                    "ok": True,
                    "message": message,
                    "result": _json_safe(result.model_dump(mode="json")),
                    "state": self.state(),
                }
            assistant = HardwareIntegrationAssistant(
                source,
                output_dir=output or None,
                name=name or None,
                base_dir=self.config_path.parent,
            )
            result = assistant.generate()
            return {
                "ok": True,
                "message": f"Generated driver scaffold at {result.output_path}.",
                "result": _json_safe(result.model_dump(mode="json")),
                "state": self.state(),
            }

    def run_demo(self) -> dict[str, Any]:
        with self.lock:
            self._ensure_watch_started()
            task = "pick the red block and place it on the tray"
            result = asyncio.run(AgentRuntime(self.config_path).run_task(task, wait_for_feedback=False))
            assert self.watch_runtime is not None
            executed = asyncio.run(self.watch_runtime.step(setup=False))
            return {
                "ok": bool(result["ok"] and executed == 2),
                "message": "Demo completed.",
                "executed": executed,
                "result": _json_safe(result),
                "state": self.state(),
            }

    def doctor(self) -> dict[str, Any]:
        checks = run_doctor(self.config_path)
        return {"ok": doctor_ok(checks), "checks": [check.as_dict() for check in checks]}

    @property
    def _watch_started(self) -> bool:
        return bool(self.watch_runtime is not None and self.watch_runtime.started)

    def _ensure_watch_started(self) -> None:
        if not self.config_path.exists():
            write_default_config(self.config_path)
        config = load_config(self.config_path)
        Workspace(config.workspace_path(self.config_path.parent)).initialize()
        if self.watch_runtime is None or not self.watch_runtime.started:
            self.watch_runtime = WatchRuntime(self.config_path)
            asyncio.run(self.watch_runtime.setup())


def make_server(
    config_path: str | Path = DEFAULT_CONFIG_NAME,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    controller = GuiController(config_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "PhysicalAgentGUI/0.1"

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route == "/":
                self._send_static("index.html")
                return
            if route.startswith("/static/"):
                self._send_static(unquote(route.removeprefix("/static/")))
                return
            if route == "/api/state":
                self._send_json(controller.state())
                return
            if route == "/api/doctor":
                self._send_json(controller.doctor())
                return
            self._send_json({"ok": False, "message": "Not found."}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            try:
                if route == "/api/setup":
                    payload = self._read_json()
                    self._send_json(controller.setup(force=bool(payload.get("force", False))))
                    return
                if route == "/api/watch/start":
                    self._send_json(controller.start_watch())
                    return
                if route == "/api/watch/stop":
                    self._send_json(controller.stop_watch())
                    return
                if route == "/api/watch/step":
                    self._send_json(controller.step_watch())
                    return
                if route == "/api/task":
                    payload = self._read_json()
                    task = str(payload.get("task", "")).strip()
                    if not task:
                        self._send_json(
                            {"ok": False, "message": "Task cannot be empty."},
                            HTTPStatus.BAD_REQUEST,
                        )
                        return
                    self._send_json(controller.submit_task(task))
                    return
                if route == "/api/chat":
                    payload = self._read_json()
                    message = str(payload.get("message", "")).strip()
                    if not message:
                        self._send_json(
                            {"ok": False, "message": "Chat message cannot be empty."},
                            HTTPStatus.BAD_REQUEST,
                        )
                        return
                    planner = str(payload.get("planner", "auto"))
                    auto_step = bool(payload.get("auto_step", False))
                    self._send_json(
                        controller.chat_message(message, planner=planner, auto_step=auto_step)
                    )
                    return
                if route == "/api/integrate":
                    payload = self._read_json()
                    source = str(payload.get("source", "")).strip()
                    if not source:
                        self._send_json(
                            {"ok": False, "message": "Source cannot be empty."},
                            HTTPStatus.BAD_REQUEST,
                        )
                        return
                    output = str(payload.get("output", "")).strip() or None
                    name = str(payload.get("name", "")).strip() or None
                    llm = bool(payload.get("llm", False))
                    model = str(payload.get("model", "")).strip() or None
                    self._send_json(
                        controller.integrate_hardware(
                            source,
                            output=output,
                            name=name,
                            llm=llm,
                            model=model,
                        )
                    )
                    return
                if route == "/api/demo":
                    self._send_json(controller.run_demo())
                    return
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"ok": False, "message": "Not found."}, HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def _send_static(self, relative_path: str) -> None:
            try:
                target = (STATIC_DIR / relative_path).resolve()
                target.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self._send_json({"ok": False, "message": "Not found."}, HTTPStatus.NOT_FOUND)
                return
            if not target.is_file():
                self._send_json({"ok": False, "message": "Not found."}, HTTPStatus.NOT_FOUND)
                return

            payload = target.read_bytes()
            content_type = STATIC_CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            payload = json.dumps(_json_safe(data), indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer((host, port), Handler)
    server.controller = controller  # type: ignore[attr-defined]
    return server


def run_gui(
    config_path: str | Path = DEFAULT_CONFIG_NAME,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    server = make_server(config_path, host=host, port=port)
    url = f"http://{host}:{server.server_address[1]}"
    if open_browser:
        webbrowser.open(url)
    print(f"Physical Agent GUI running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller: GuiController = server.controller  # type: ignore[attr-defined]
        controller.stop_watch()
        server.server_close()


def _dump_actions(actions: list[Action]) -> list[dict[str, Any]]:
    return [action.model_dump(mode="json") for action in actions]


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _latest_code_result(chat: dict[str, Any]) -> dict[str, Any] | None:
    messages = chat.get("messages", [])
    for message in reversed(messages):
        metadata = None
        if hasattr(message, "metadata"):
            metadata = getattr(message, "metadata")
        elif isinstance(message, dict):
            metadata = message.get("metadata")
        if isinstance(metadata, dict) and metadata.get("code_result") is not None:
            return _json_safe(metadata["code_result"])
    return None
