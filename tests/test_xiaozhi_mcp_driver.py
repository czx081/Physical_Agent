import asyncio

from physical_agent.drivers.loader import load_driver
from physical_agent.protocol.schemas import Action
from physical_agent.protocol.workspace import Workspace


def test_xiaozhi_mcp_mock_mode(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    loaded = load_driver(
        robot_id="xiaozhi_1",
        driver_ref="xiaozhi_mcp",
        config={
            "mode": "mock",
            "device_name": "demo-device",
            "tools": {
                "observe": "self.device.observe",
                "say": "self.audio.speaker.speak",
                "set_light": "self.light.set_rgb",
            },
        },
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )

    asyncio.run(loaded.driver.connect())
    observation = asyncio.run(loaded.driver.observe())
    assert observation.robots["xiaozhi_1"]["device"] == "demo-device"
    assert loaded.driver.capabilities()[1].name == "say"


def test_xiaozhi_mcp_mock_say_and_light(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    loaded = load_driver(
        robot_id="xiaozhi_1",
        driver_ref="xiaozhi_mcp",
        config={"mode": "mock"},
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )

    asyncio.run(loaded.driver.connect())
    say = asyncio.run(
        loaded.driver.execute(
            Action(
                id="act_001",
                robot="xiaozhi_1",
                capability="say",
                params={"text": "hello"},
            )
        )
    )
    light = asyncio.run(
        loaded.driver.execute(
            Action(
                id="act_002",
                robot="xiaozhi_1",
                capability="set_light",
                params={"r": 255, "g": 0, "b": 0},
            )
        )
    )

    assert say.status == "completed"
    assert light.status == "completed"
    assert loaded.driver.last_message == "hello"
    assert loaded.driver.state["light"]["color"] == {"r": 255, "g": 0, "b": 0}
