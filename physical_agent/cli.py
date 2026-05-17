from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
import yaml

from physical_agent.agent.runtime import AgentRuntime
from physical_agent.config import DEFAULT_CONFIG_NAME, load_config, write_default_config
from physical_agent.drivers.templates import create_driver_template
from physical_agent.protocol.workspace import Workspace
from physical_agent.watch.runtime import WatchRuntime


app = typer.Typer(help="Physical Agent: Markdown-native runtime for safe physical-world agents.")
driver_app = typer.Typer(help="Driver utilities.")
app.add_typer(driver_app, name="driver")


@app.command("init")
def init(
    config: Path = typer.Option(Path(DEFAULT_CONFIG_NAME), "--config", "-c", help="Config path."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config and workspace files."),
) -> None:
    config_path = write_default_config(config, overwrite=force)
    cfg = load_config(config_path)
    workspace = Workspace(cfg.workspace_path(config_path.parent))
    workspace.initialize(overwrite=force)
    typer.echo(f"Initialized Physical Agent project at {config_path.parent}")
    typer.echo(f"Config: {config_path}")
    typer.echo(f"Workspace: {workspace.path}")


@app.command("watch")
def watch(
    config: Path = typer.Option(Path(DEFAULT_CONFIG_NAME), "--config", "-c", help="Config path."),
) -> None:
    runtime = WatchRuntime(config)
    typer.echo("Starting physical-agent watch. Press Ctrl+C to stop.")
    try:
        asyncio.run(runtime.run_forever())
    except KeyboardInterrupt:
        typer.echo("Watch stopped.")


@app.command("run")
def run(
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Task to run once."),
    config: Path = typer.Option(Path(DEFAULT_CONFIG_NAME), "--config", "-c", help="Config path."),
    no_wait: bool = typer.Option(False, "--no-wait", help="Submit actions without waiting for feedback."),
) -> None:
    runtime = AgentRuntime(config)
    if task is None:
        asyncio.run(runtime.interactive())
        return
    result = asyncio.run(runtime.run_task(task, wait_for_feedback=not no_wait))
    typer.echo(result["message"])
    actions = result.get("actions", [])
    if actions:
        typer.echo("Actions:")
        for action in actions:
            typer.echo(
                f"- {action.id}: {action.robot}.{action.capability} "
                f"{yaml.safe_dump(action.params, sort_keys=False).strip()}"
            )
    feedback = result.get("feedback", [])
    if feedback:
        typer.echo("Feedback:")
        for item in feedback:
            typer.echo(f"- {item.get('action_id')}: {item.get('status')} - {item.get('message')}")
    elif actions and not no_wait:
        typer.echo("No feedback arrived before the timeout. Is `physical-agent watch` running?")


@app.command("inspect")
def inspect(
    config: Path = typer.Option(Path(DEFAULT_CONFIG_NAME), "--config", "-c", help="Config path."),
) -> None:
    cfg = load_config(config)
    workspace = Workspace(cfg.workspace_path(config.resolve().parent))
    if not workspace.exists():
        typer.echo("Workspace is not initialized. Run `physical-agent init` first.")
        raise typer.Exit(code=1)

    capabilities = workspace.read_capabilities()
    world = workspace.read_world()
    actions = workspace.read_actions()
    feedback = workspace.read_feedback()

    typer.echo("Robots:")
    robots = capabilities.get("robots", {})
    if robots:
        for robot_id, robot in robots.items():
            names = [cap.get("name") for cap in robot.get("capabilities", [])]
            typer.echo(f"- {robot_id}: {robot.get('kind')} via {robot.get('driver')} ({', '.join(names)})")
    else:
        typer.echo("- none published yet")

    typer.echo("\nWorld summary:")
    typer.echo(world.get("summary") or "No world summary.")

    typer.echo("\nPending actions:")
    if actions["pending"]:
        for action in actions["pending"]:
            typer.echo(f"- {action.id}: {action.robot}.{action.capability}")
    else:
        typer.echo("- none")

    typer.echo("\nCompleted actions:")
    if actions["completed"]:
        for action in actions["completed"]:
            typer.echo(f"- {action.id}: {action.robot}.{action.capability}")
    else:
        typer.echo("- none")

    typer.echo("\nLatest feedback:")
    latest = feedback.get("latest", {})
    if latest:
        typer.echo(yaml.safe_dump(latest, sort_keys=False).strip())
    else:
        typer.echo("- none")


@driver_app.command("new")
def driver_new(name: str = typer.Argument(..., help="Directory/name for the new driver.")) -> None:
    path = create_driver_template(name)
    typer.echo(f"Created driver template at {path}")
    typer.echo("Files: physical_driver.yaml, driver.py, README.md")


if __name__ == "__main__":
    app()

