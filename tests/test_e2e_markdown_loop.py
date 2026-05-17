import asyncio

from physical_agent.agent.runtime import AgentRuntime
from physical_agent.config import write_default_config
from physical_agent.protocol.workspace import Workspace
from physical_agent.watch.runtime import WatchRuntime


def test_e2e_markdown_pick_place_loop(tmp_path):
    config_path = write_default_config(tmp_path / "physical-agent.yaml", overwrite=True)
    watch = WatchRuntime(config_path)
    asyncio.run(watch.setup())

    agent = AgentRuntime(config_path)
    result = asyncio.run(
        agent.run_task(
            "pick the red block and place it on the tray",
            wait_for_feedback=False,
        )
    )
    assert result["ok"] is True

    workspace = Workspace(tmp_path / "workspace")
    planned = workspace.read_actions()["pending"]
    assert [action.capability for action in planned] == ["pick", "place"]

    count = asyncio.run(watch.step(setup=False))
    assert count == 2

    actions = workspace.read_actions()
    assert actions["pending"] == []
    assert [action.capability for action in actions["completed"]] == ["pick", "place"]

    feedback = workspace.read_feedback()
    assert feedback["latest"]["status"] == "completed"
    assert feedback["latest"]["capability"] == "place"

    world = workspace.read_world()
    assert world["state"]["objects"]["red_block"]["location"] == "tray"

