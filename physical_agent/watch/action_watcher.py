from __future__ import annotations

from physical_agent.protocol.schemas import Action


def completed_ids(actions: list[Action]) -> set[str]:
    return {action.id for action in actions}


def ready_actions(pending: list[Action], completed: list[Action]) -> list[Action]:
    done = completed_ids(completed)
    return [action for action in pending if all(dep in done for dep in action.depends_on)]

