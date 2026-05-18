from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from physical_agent.protocol.markdown import parse_front_matter, render_front_matter
from physical_agent.protocol.parsers import (
    parse_actions,
    parse_capabilities,
    parse_chat,
    parse_feedback,
    parse_memory,
    parse_plan,
    parse_safety,
    parse_task,
    parse_world,
)
from physical_agent.protocol.renderers import (
    render_actions,
    render_capabilities,
    render_chat,
    render_feedback,
    render_log,
    render_memory,
    render_plan,
    render_safety,
    render_task,
    render_world,
)
from physical_agent.protocol.schemas import Action, ChatMessage, ChatPlan, Observation


class Workspace:
    filenames = {
        "task": "TASK.md",
        "capabilities": "CAPABILITIES.md",
        "world": "WORLD.md",
        "actions": "ACTIONS.md",
        "feedback": "FEEDBACK.md",
        "safety": "SAFETY.md",
        "log": "LOG.md",
        "chat": "CHAT.md",
        "plan": "PLAN.md",
        "memory": "MEMORY.md",
    }

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.artifacts_path = self.path / "artifacts"

    def file(self, name: str) -> Path:
        return self.path / self.filenames[name]

    def initialize(self, *, overwrite: bool = False) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        defaults = {
            "task": render_task("No active task."),
            "capabilities": render_capabilities({}),
            "world": render_world(Observation(summary="No observation has been recorded yet.")),
            "actions": render_actions(),
            "feedback": render_feedback(),
            "safety": render_safety(),
            "log": render_log(),
            "chat": render_chat(),
            "plan": render_plan(),
            "memory": render_memory(),
        }
        for name, content in defaults.items():
            target = self.file(name)
            if overwrite or not target.exists():
                target.write_text(content, encoding="utf-8")

    def exists(self) -> bool:
        return self.path.exists() and all(self.file(name).exists() for name in self.filenames)

    def _next_revision(self, target: Path) -> int:
        if not target.exists():
            return 1
        try:
            return parse_front_matter(target.read_text(encoding="utf-8")).revision + 1
        except Exception:
            return 1

    def write_task(
        self,
        task: str,
        constraints: list[str] | None = None,
        *,
        owner: str = "human",
        status: str = "active",
    ) -> None:
        target = self.file("task")
        target.write_text(
            render_task(
                task,
                constraints,
                owner=owner,
                status=status,
                revision=self._next_revision(target),
            ),
            encoding="utf-8",
        )

    def read_task(self) -> dict[str, Any]:
        return parse_task(self.file("task").read_text(encoding="utf-8"))

    def write_capabilities(self, robots: dict[str, Any]) -> None:
        target = self.file("capabilities")
        target.write_text(
            render_capabilities(robots, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_capabilities(self) -> dict[str, Any]:
        return parse_capabilities(self.file("capabilities").read_text(encoding="utf-8"))

    def write_world(self, observation: Observation | dict[str, Any]) -> None:
        target = self.file("world")
        target.write_text(
            render_world(observation, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_world(self) -> dict[str, Any]:
        return parse_world(self.file("world").read_text(encoding="utf-8"))

    def write_actions(
        self,
        pending: list[Action | dict[str, Any]] | None = None,
        completed: list[Action | dict[str, Any]] | None = None,
        cancelled: list[Action | dict[str, Any]] | None = None,
    ) -> None:
        target = self.file("actions")
        target.write_text(
            render_actions(
                pending,
                completed,
                cancelled,
                revision=self._next_revision(target),
            ),
            encoding="utf-8",
        )

    def read_actions(self) -> dict[str, Any]:
        return parse_actions(self.file("actions").read_text(encoding="utf-8"))

    def write_feedback(
        self,
        latest: dict[str, Any] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        target = self.file("feedback")
        target.write_text(
            render_feedback(latest, history, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_feedback(self) -> dict[str, Any]:
        return parse_feedback(self.file("feedback").read_text(encoding="utf-8"))

    def write_safety(self, rules: dict[str, Any] | None = None) -> None:
        target = self.file("safety")
        target.write_text(
            render_safety(rules, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_safety(self) -> dict[str, Any]:
        return parse_safety(self.file("safety").read_text(encoding="utf-8"))

    def write_chat(self, messages: list[ChatMessage | dict[str, Any]]) -> None:
        target = self.file("chat")
        target.write_text(
            render_chat(messages, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_chat(self) -> dict[str, Any]:
        return parse_chat(self.file("chat").read_text(encoding="utf-8"))

    def append_chat_message(
        self,
        role: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        messages = list(self.read_chat()["messages"])
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        message = ChatMessage(
            role=role,
            content=content,
            created_at=timestamp,
            metadata=metadata or {},
        )
        messages.append(message)
        self.write_chat(messages)
        return message

    def write_plan(self, plan: ChatPlan | dict[str, Any]) -> None:
        target = self.file("plan")
        target.write_text(
            render_plan(plan, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_plan(self) -> dict[str, Any]:
        return parse_plan(self.file("plan").read_text(encoding="utf-8"))

    def write_memory(self, notes: list[dict[str, Any]]) -> None:
        target = self.file("memory")
        target.write_text(
            render_memory(notes, revision=self._next_revision(target)),
            encoding="utf-8",
        )

    def read_memory(self) -> dict[str, Any]:
        return parse_memory(self.file("memory").read_text(encoding="utf-8"))

    def append_memory_note(self, content: str, *, source: str = "chat") -> dict[str, Any]:
        notes = list(self.read_memory()["notes"])
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        note = {"content": content, "source": source, "created_at": timestamp}
        notes.append(note)
        self.write_memory(notes)
        return note

    def append_log(self, message: str, *, actor: str | None = None) -> None:
        target = self.file("log")
        if target.exists():
            doc = parse_front_matter(target.read_text(encoding="utf-8"))
            metadata = dict(doc.metadata)
            body = doc.body.rstrip() + "\n\n"
            metadata["revision"] = doc.revision + 1
        else:
            metadata = {"schema": "physical-agent/log/v1", "owner": "system", "revision": 1}
            body = "# Physical Agent Log\n\n"
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        prefix = f"**{actor}**: " if actor else ""
        body += f"## {timestamp}\n\n{prefix}{message}\n"
        target.write_text(render_front_matter(metadata, body), encoding="utf-8")
