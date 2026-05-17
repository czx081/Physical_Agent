from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


DEFAULT_CONFIG_NAME = "physical-agent.yaml"


class ProjectConfig(BaseModel):
    name: str = "quickstart"


class WorkspaceConfig(BaseModel):
    path: str = "./workspace"


class WatchConfig(BaseModel):
    tick_ms: int = 500
    require_human_approval: bool = False


class AgentConfig(BaseModel):
    planner: str = "rule_based"
    model: str = "fake/local"
    max_steps: int = 8
    feedback_timeout_s: int = 30


class RobotConfig(BaseModel):
    driver: str
    config: dict[str, Any] = Field(default_factory=dict)


class PhysicalAgentConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    robots: dict[str, RobotConfig] = Field(default_factory=dict)

    def workspace_path(self, base_dir: Path) -> Path:
        path = Path(self.workspace.path)
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve()


def default_config_dict() -> dict[str, Any]:
    return {
        "project": {"name": "quickstart"},
        "workspace": {"path": "./workspace"},
        "watch": {"tick_ms": 500, "require_human_approval": False},
        "agent": {
            "planner": "rule_based",
            "model": "fake/local",
            "max_steps": 8,
            "feedback_timeout_s": 30,
        },
        "robots": {
            "arm_1": {
                "driver": "mock_arm",
                "config": {
                    "bounds": {
                        "x": [-1.0, 1.0],
                        "y": [-1.0, 1.0],
                        "z": [0.0, 1.0],
                    },
                    "objects": {
                        "red_block": {
                            "type": "block",
                            "color": "red",
                            "location": "table",
                            "pose": {"x": 0.3, "y": 0.1, "z": 0.0},
                        },
                        "tray": {
                            "type": "tray",
                            "location": "table",
                            "pose": {"x": -0.2, "y": 0.2, "z": 0.0},
                        },
                    },
                },
            }
        },
    }


def load_config(path: str | Path = DEFAULT_CONFIG_NAME) -> PhysicalAgentConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Could not find {config_path}. Run `physical-agent init` first."
        )
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return PhysicalAgentConfig.model_validate(data)


def write_default_config(path: str | Path = DEFAULT_CONFIG_NAME, *, overwrite: bool = False) -> Path:
    config_path = Path(path)
    if config_path.exists() and not overwrite:
        return config_path.resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(default_config_dict(), handle, sort_keys=False)
    return config_path.resolve()

