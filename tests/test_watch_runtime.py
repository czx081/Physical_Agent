import asyncio

from physical_agent.config import write_default_config
from physical_agent.protocol.schemas import Action
from physical_agent.protocol.workspace import Workspace
from physical_agent.watch.runtime import WatchRuntime


def test_watch_runtime_step_executes_action(tmp_path):
    config_path = write_default_config(tmp_path / "physical-agent.yaml", overwrite=True)
    runtime = WatchRuntime(config_path)
    asyncio.run(runtime.setup())
    workspace = Workspace(tmp_path / "workspace")
    assert workspace.read_capabilities()["robots"]["arm_1"]["driver"] == "mock_arm"
    workspace.write_actions(
        [
            Action(
                id="act_001",
                robot="arm_1",
                capability="pick",
                params={"object_id": "red_block"},
            )
        ],
        [],
        [],
    )
    count = asyncio.run(runtime.step(setup=False))
    assert count == 1
    actions = workspace.read_actions()
    assert actions["pending"] == []
    assert actions["completed"][0].id == "act_001"
    assert workspace.read_feedback()["latest"]["status"] == "completed"

