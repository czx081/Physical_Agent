from __future__ import annotations

import asyncio
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from physical_agent.agent.runtime import AgentRuntime
from physical_agent.config import DEFAULT_CONFIG_NAME, load_config, write_default_config
from physical_agent.doctor import doctor_ok, run_doctor
from physical_agent.protocol.schemas import Action
from physical_agent.protocol.workspace import Workspace
from physical_agent.quickstart import setup_project
from physical_agent.watch.runtime import WatchRuntime


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
        return {
            "ready": True,
            "watch_started": self._watch_started,
            "message": "Ready.",
            "config_path": str(self.config_path),
            "workspace_path": str(workspace.path),
            "task": workspace.read_task(),
            "capabilities": workspace.read_capabilities(),
            "world": workspace.read_world(),
            "actions": {
                "pending": _dump_actions(actions["pending"]),
                "completed": _dump_actions(actions["completed"]),
                "cancelled": _dump_actions(actions["cancelled"]),
            },
            "feedback": feedback,
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
                self._send_html(INDEX_HTML)
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

        def _send_html(self, html: str) -> None:
            payload = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Physical Agent Console</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d8dde6;
      --text: #1d2430;
      --muted: #5c6675;
      --blue: #2563eb;
      --green: #15803d;
      --red: #b42318;
      --amber: #a16207;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { margin: 0; font-size: 20px; line-height: 1.2; }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .stack { display: grid; gap: 12px; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .wide { grid-column: 1 / -1; }
    h2 { margin: 0 0 12px; font-size: 15px; }
    h3 { margin: 0 0 8px; font-size: 13px; color: var(--muted); }
    p { margin: 0; color: var(--muted); line-height: 1.5; }
    button {
      min-height: 36px;
      border: 1px solid #b8c1d1;
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font-weight: 600;
      cursor: pointer;
    }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
    button.success { background: var(--green); border-color: var(--green); color: #fff; }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    textarea {
      width: 100%;
      min-height: 92px;
      resize: vertical;
      border: 1px solid #b8c1d1;
      border-radius: 6px;
      padding: 10px;
      font: inherit;
      line-height: 1.4;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 4px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      font-size: 12px;
      color: var(--muted);
      background: #fff;
    }
    .badge.ok { border-color: #86efac; color: var(--green); background: #f0fdf4; }
    .badge.warn { border-color: #fcd34d; color: var(--amber); background: #fffbeb; }
    .badge.fail { border-color: #fca5a5; color: var(--red); background: #fef2f2; }
    .list { display: grid; gap: 8px; }
    .item {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
      min-width: 0;
    }
    .item strong { display: block; margin-bottom: 3px; }
    code, pre {
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }
    pre {
      overflow: auto;
      max-height: 300px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfe;
      color: #243044;
    }
    .path { overflow-wrap: anywhere; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Physical Agent Console</h1>
      <p>Markdown workspace control surface for watch, run, safety, and feedback.</p>
    </div>
    <div id="status" class="badge warn">Loading</div>
  </header>

  <main>
    <aside class="stack">
      <section class="stack">
        <h2>Controls</h2>
        <button id="setup" class="primary">Setup Project</button>
        <button id="reset">Reset Workspace</button>
        <button id="start-watch">Start Watch</button>
        <button id="step-watch">Run Watch Step</button>
        <button id="demo" class="success">Run Pick and Place Demo</button>
        <button id="refresh">Refresh</button>
      </section>

      <section class="stack">
        <h2>Submit Task</h2>
        <textarea id="task">pick the red block and place it on the tray</textarea>
        <button id="submit-task" class="primary">Submit Task</button>
        <p id="last-message"></p>
      </section>

      <section>
        <h2>Doctor</h2>
        <div id="doctor" class="list"></div>
      </section>
    </aside>

    <div class="stack">
      <section>
        <h2>Project</h2>
        <div id="project" class="list"></div>
      </section>

      <section class="grid">
        <div>
          <h2>World</h2>
          <p id="world-summary">No world state yet.</p>
          <pre id="world-state">{}</pre>
        </div>
        <div>
          <h2>Feedback</h2>
          <pre id="feedback">{}</pre>
        </div>
      </section>

      <section class="grid">
        <div>
          <h2>Robots</h2>
          <div id="robots" class="list"></div>
        </div>
        <div>
          <h2>Action Board</h2>
          <div id="actions" class="list"></div>
        </div>
      </section>
    </div>
  </main>

  <script>
    const els = {
      status: document.querySelector("#status"),
      setup: document.querySelector("#setup"),
      reset: document.querySelector("#reset"),
      startWatch: document.querySelector("#start-watch"),
      stepWatch: document.querySelector("#step-watch"),
      demo: document.querySelector("#demo"),
      refresh: document.querySelector("#refresh"),
      submitTask: document.querySelector("#submit-task"),
      task: document.querySelector("#task"),
      lastMessage: document.querySelector("#last-message"),
      project: document.querySelector("#project"),
      doctor: document.querySelector("#doctor"),
      worldSummary: document.querySelector("#world-summary"),
      worldState: document.querySelector("#world-state"),
      feedback: document.querySelector("#feedback"),
      robots: document.querySelector("#robots"),
      actions: document.querySelector("#actions")
    };

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "Request failed");
      return data;
    }

    async function post(path, payload = {}) {
      return api(path, {method: "POST", body: JSON.stringify(payload)});
    }

    function pretty(value) {
      return JSON.stringify(value || {}, null, 2);
    }

    function item(title, body, tone = "") {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(body || "")}</span>`;
      if (tone) div.classList.add(tone);
      return div;
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[char]));
    }

    function render(state) {
      const ready = Boolean(state.ready);
      els.status.className = ready ? "badge ok" : "badge warn";
      els.status.textContent = ready
        ? (state.watch_started ? "Ready, watch connected" : "Ready, watch stopped")
        : "Setup needed";

      els.project.innerHTML = "";
      els.project.appendChild(item("Config", state.config_path || "Not created"));
      els.project.appendChild(item("Workspace", state.workspace_path || "Not created"));
      els.project.appendChild(item("Message", state.message || ""));

      els.doctor.innerHTML = "";
      for (const check of state.doctor || []) {
        els.doctor.appendChild(item(check.ok ? "OK " + check.name : "FAIL " + check.name, check.message));
      }

      const world = state.world || {};
      els.worldSummary.textContent = world.summary || "No world state yet.";
      els.worldState.textContent = pretty(world.state);
      els.feedback.textContent = pretty((state.feedback || {}).latest);

      els.robots.innerHTML = "";
      const robots = ((state.capabilities || {}).robots) || {};
      if (Object.keys(robots).length === 0) {
        els.robots.appendChild(item("No robots published", "Click Start Watch to publish capabilities."));
      } else {
        for (const [id, robot] of Object.entries(robots)) {
          const caps = (robot.capabilities || []).map(cap => cap.name).join(", ");
          els.robots.appendChild(item(id, `${robot.kind} via ${robot.driver}; ${caps}`));
        }
      }

      els.actions.innerHTML = "";
      const board = state.actions || {pending: [], completed: [], cancelled: []};
      for (const name of ["pending", "completed", "cancelled"]) {
        const rows = board[name] || [];
        els.actions.appendChild(item(name.toUpperCase(), rows.length ? rows.map(row => `${row.id}: ${row.robot}.${row.capability}`).join("\n") : "none"));
      }
    }

    async function refresh() {
      try {
        render(await api("/api/state"));
      } catch (error) {
        els.lastMessage.textContent = error.message;
      }
    }

    async function run(label, fn) {
      els.lastMessage.textContent = `${label}...`;
      try {
        const result = await fn();
        els.lastMessage.textContent = result.message || "Done.";
        render(result.state || await api("/api/state"));
      } catch (error) {
        els.lastMessage.textContent = error.message;
      }
    }

    els.setup.addEventListener("click", () => run("Setting up project", () => post("/api/setup")));
    els.reset.addEventListener("click", () => run("Resetting workspace", () => post("/api/setup", {force: true})));
    els.startWatch.addEventListener("click", () => run("Starting watch", () => post("/api/watch/start")));
    els.stepWatch.addEventListener("click", () => run("Running watch step", () => post("/api/watch/step")));
    els.demo.addEventListener("click", () => run("Running demo", () => post("/api/demo")));
    els.refresh.addEventListener("click", refresh);
    els.submitTask.addEventListener("click", () => run("Submitting task", () => post("/api/task", {task: els.task.value})));

    refresh();
  </script>
</body>
</html>
"""
