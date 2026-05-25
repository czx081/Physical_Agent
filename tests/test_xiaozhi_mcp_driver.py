import asyncio

from physical_agent.drivers import xiaozhi_mcp as xiaozhi_mcp_module
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
                "observe": "self.get_device_status",
                "set_volume": "self.audio_speaker.set_volume",
                "otto_action": "self.otto.action",
                "home": "self.otto.action",
                "stop": "self.otto.stop",
            },
        },
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )

    asyncio.run(loaded.driver.connect())
    observation = asyncio.run(loaded.driver.observe())
    assert observation.robots["xiaozhi_1"]["device"] == "demo-device"
    assert loaded.driver.capabilities()[1].name == "set_volume"


def test_xiaozhi_mcp_mock_volume_and_motion(tmp_path):
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
    volume = asyncio.run(
        loaded.driver.execute(
            Action(
                id="act_001",
                robot="xiaozhi_1",
                capability="set_volume",
                params={"volume": 70},
            )
        )
    )
    motion = asyncio.run(
        loaded.driver.execute(
            Action(
                id="act_002",
                robot="xiaozhi_1",
                capability="otto_action",
                params={"action": "hand_wave", "direction": 1},
            )
        )
    )

    assert volume.status == "completed"
    assert motion.status == "completed"
    assert loaded.driver.last_action == "otto_action:hand_wave"
    assert loaded.driver.state["speaker"]["volume"] == 70
    assert loaded.driver.state["motion"]["last_action"] == {"action": "hand_wave", "direction": 1}


def test_xiaozhi_mcp_ws_mode(monkeypatch, tmp_path):
    calls: list[tuple[str, dict]] = []

    class FakeWsClient:
        def __init__(self, url, *, connect_timeout_s, timeout_s):
            self.url = url
            self.connect_timeout_s = connect_timeout_s
            self.timeout_s = timeout_s
            self.is_connected = False

        def connect(self):
            self.is_connected = True

        def close(self):
            self.is_connected = False

        def initialize(self):
            return {"sessionId": "ws-session"}

        def list_tools(self):
            return [
                {"name": "self.get_device_status"},
                {"name": "self.audio_speaker.set_volume"},
                {"name": "self.otto.action"},
                {"name": "self.otto.stop"},
            ]

        def call_tool(self, name, arguments=None):
            args = arguments or {}
            calls.append((name, dict(args)))
            if name == "self.get_device_status":
                return {"summary": "Device is online.", "state": {"online": True}}
            if name == "self.audio_speaker.set_volume":
                return {"volume": args.get("volume")}
            if name == "self.otto.action":
                return {"action": dict(args)}
            raise AssertionError(f"Unexpected tool call: {name}")

    monkeypatch.setattr(xiaozhi_mcp_module, "XiaozhiMcpWebSocketClient", FakeWsClient)

    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    loaded = load_driver(
        robot_id="xiaozhi_1",
        driver_ref="xiaozhi_mcp",
        config={
            "mode": "ws",
            "wait_for_responses": True,
            "host": "192.168.66.237",
            "port": 8080,
            "path": "/ws",
        },
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )

    async def scenario():
        await loaded.driver.connect()
        observation = await loaded.driver.observe()
        volume = await loaded.driver.execute(
            Action(
                id="act_001",
                robot="xiaozhi_1",
                capability="set_volume",
                params={"volume": 35},
            )
        )
        motion = await loaded.driver.execute(
            Action(
                id="act_002",
                robot="xiaozhi_1",
                capability="otto_action",
                params={"action": "hand_wave", "direction": 1},
            )
        )
        await loaded.driver.disconnect()
        return observation, volume, motion

    observation, volume, motion = asyncio.run(scenario())

    assert observation.summary == "Device is online."
    assert observation.robots["xiaozhi_1"]["mode"] == "ws"
    assert observation.robots["xiaozhi_1"]["endpoint"] == "ws://192.168.66.237:8080/ws"
    assert volume.status == "completed"
    assert motion.status == "completed"
    assert loaded.driver.session_id == "ws-session"
    assert calls == [
        ("self.get_device_status", {}),
        ("self.audio_speaker.set_volume", {"volume": 35}),
        ("self.otto.action", {"action": "hand_wave", "direction": 1}),
    ]


def test_xiaozhi_mcp_ws_fire_and_forget(monkeypatch, tmp_path):
    sent: list[tuple[str, dict]] = []

    class FakeWsClient:
        def __init__(self, url, *, connect_timeout_s, timeout_s):
            self.url = url
            self.is_connected = False
            self._next_id = 1

        def connect(self):
            self.is_connected = True

        def close(self):
            self.is_connected = False

        def send_tool_call(self, name, arguments=None):
            request_id = self._next_id
            self._next_id += 1
            sent.append((name, dict(arguments or {})))
            return request_id

    monkeypatch.setattr(xiaozhi_mcp_module, "XiaozhiMcpWebSocketClient", FakeWsClient)

    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    loaded = load_driver(
        robot_id="xiaozhi_1",
        driver_ref="xiaozhi_mcp",
        config={
            "mode": "ws",
            "wait_for_responses": False,
            "host": "192.168.66.237",
            "port": 8080,
            "path": "/ws",
        },
        workspace_path=workspace.path,
        artifacts_path=workspace.artifacts_path,
    )

    async def scenario():
        await loaded.driver.connect()
        observation = await loaded.driver.observe()
        motion = await loaded.driver.execute(
            Action(
                id="act_001",
                robot="xiaozhi_1",
                capability="otto_action",
                params={"action": "hand_wave", "direction": 1},
            )
        )
        await loaded.driver.disconnect()
        return observation, motion

    observation, motion = asyncio.run(scenario())

    assert "fire-and-forget" in observation.summary
    assert motion.status == "completed"
    assert motion.result["mcp_result"]["sent"] is True
    assert sent == [("self.otto.action", {"action": "hand_wave", "direction": 1})]
