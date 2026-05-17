from __future__ import annotations

from typing import Any

from physical_agent.protocol.markdown import (
    extract_section_text,
    extract_yaml_block_after_heading,
    parse_front_matter,
)
from physical_agent.protocol.schemas import Action, Observation


def parse_task(text: str) -> dict[str, Any]:
    doc = parse_front_matter(text)
    return {
        "metadata": doc.metadata,
        "task": extract_section_text(doc.body, "Task", level=1),
        "constraints": extract_yaml_block_after_heading(doc.body, "Constraints", level=1) or [],
    }


def parse_capabilities(text: str) -> dict[str, Any]:
    doc = parse_front_matter(text)
    return {
        "metadata": doc.metadata,
        "robots": extract_yaml_block_after_heading(doc.body, "Robots", level=2) or {},
    }


def parse_world(text: str) -> dict[str, Any]:
    doc = parse_front_matter(text)
    state = extract_yaml_block_after_heading(doc.body, "State", level=2) or {}
    return {
        "metadata": doc.metadata,
        "summary": extract_section_text(doc.body, "Summary", level=2),
        "state": state,
        "observation": Observation(
            summary=extract_section_text(doc.body, "Summary", level=2),
            robots=state.get("robots", {}),
            objects=state.get("objects", {}),
            environment=state.get("environment", {}),
            artifacts=state.get("artifacts", []),
            raw=state.get("raw", {}),
        ),
    }


def _parse_action_list(items: Any) -> list[Action]:
    if not items:
        return []
    return [item if isinstance(item, Action) else Action.model_validate(item) for item in items]


def parse_actions(text: str) -> dict[str, Any]:
    doc = parse_front_matter(text)
    pending = extract_yaml_block_after_heading(doc.body, "Pending", level=2) or []
    completed = extract_yaml_block_after_heading(doc.body, "Completed", level=2) or []
    cancelled = extract_yaml_block_after_heading(doc.body, "Cancelled", level=2) or []
    return {
        "metadata": doc.metadata,
        "pending": _parse_action_list(pending),
        "completed": _parse_action_list(completed),
        "cancelled": _parse_action_list(cancelled),
    }


def parse_feedback(text: str) -> dict[str, Any]:
    doc = parse_front_matter(text)
    return {
        "metadata": doc.metadata,
        "latest": extract_yaml_block_after_heading(doc.body, "Latest", level=2) or {},
        "history": extract_yaml_block_after_heading(doc.body, "History", level=2) or [],
    }


def parse_safety(text: str) -> dict[str, Any]:
    doc = parse_front_matter(text)
    return {
        "metadata": doc.metadata,
        "rules": extract_yaml_block_after_heading(doc.body, "Rules", level=2) or {},
    }

