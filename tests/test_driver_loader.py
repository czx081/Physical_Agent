import asyncio

from physical_agent.drivers.loader import load_driver
from physical_agent.drivers.mock_arm import MockArmDriver
from physical_agent.drivers.templates import create_driver_template
from physical_agent.protocol.workspace import Workspace


def test_load_builtin_mock_arm(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    loaded = load_driver(
        robot_id="arm_1",
        driver_ref="mock_arm",
        config={},
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )
    assert isinstance(loaded.driver, MockArmDriver)
    assert loaded.manifest.name == "mock_arm"


def test_load_local_generated_driver(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    driver_dir = create_driver_template(tmp_path / "my_arm_driver")
    loaded = load_driver(
        robot_id="local_1",
        driver_ref=str(driver_dir),
        config={},
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )
    asyncio.run(loaded.driver.connect())
    health = asyncio.run(loaded.driver.health())
    assert health.ok is True
    assert loaded.driver.capabilities()[0].name == "observe"

