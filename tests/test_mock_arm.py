import asyncio

from physical_agent.drivers.mock_arm import MockArmDriver
from physical_agent.protocol.schemas import Action, DriverContext


def _driver(tmp_path):
    return MockArmDriver(
        DriverContext(
            robot_id="arm_1",
            config={},
            workspace_path=tmp_path,
            artifacts_path=tmp_path / "artifacts",
        )
    )


def test_mock_arm_observe(tmp_path):
    driver = _driver(tmp_path)
    asyncio.run(driver.connect())
    observation = asyncio.run(driver.observe())
    assert "arm_1" in observation.robots
    assert "red_block" in observation.objects


def test_mock_arm_pick_and_place(tmp_path):
    driver = _driver(tmp_path)
    asyncio.run(driver.connect())
    pick = asyncio.run(
        driver.execute(
            Action(
                id="act_001",
                robot="arm_1",
                capability="pick",
                params={"object_id": "red_block"},
            )
        )
    )
    assert pick.status == "completed"
    assert driver.holding == "red_block"
    place = asyncio.run(
        driver.execute(
            Action(
                id="act_002",
                robot="arm_1",
                capability="place",
                params={"target": "tray"},
            )
        )
    )
    assert place.status == "completed"
    assert driver.holding is None
    assert driver.objects["red_block"]["location"] == "tray"

