from physical_agent.agent.chat_runtime import ChatRuntime
from physical_agent.quickstart import setup_project
from physical_agent.protocol.workspace import Workspace


def test_chat_runtime_rule_based_remembers(tmp_path):
    config_path = tmp_path / "physical-agent.yaml"
    setup_project(config_path, publish=True)

    result = ChatRuntime(config_path, planner_name="rule_based").respond(
        "remember that I prefer simulation before real hardware"
    )

    assert result["ok"] is True
    assert "I will remember" in result["reply"]
    workspace = Workspace(tmp_path / "workspace")
    assert "simulation before real hardware" in workspace.read_memory()["notes"][0]["content"]
    assert len(workspace.read_chat()["messages"]) == 2


def test_chat_runtime_rule_based_proposes_actions(tmp_path):
    config_path = tmp_path / "physical-agent.yaml"
    setup_project(config_path, publish=True)

    result = ChatRuntime(config_path, planner_name="rule_based").respond(
        "pick the red block and place it on the tray"
    )

    assert result["ok"] is True
    assert [action["capability"] for action in result["actions"]] == ["pick", "place"]
    workspace = Workspace(tmp_path / "workspace")
    assert [action.capability for action in workspace.read_actions()["pending"]] == ["pick", "place"]
    assert workspace.read_plan()["plan"].needs_watch is True


def test_chat_runtime_auto_step_executes_actions(tmp_path):
    config_path = tmp_path / "physical-agent.yaml"
    setup_project(config_path, publish=True)

    result = ChatRuntime(config_path, planner_name="rule_based").respond(
        "pick the red block and place it on the tray",
        auto_step=True,
    )

    assert result["executed"] == 2
    workspace = Workspace(tmp_path / "workspace")
    assert workspace.read_world()["state"]["objects"]["red_block"]["location"] == "tray"
    assert workspace.read_actions()["pending"] == []


def test_chat_runtime_auto_falls_back_when_llm_fails(tmp_path, monkeypatch):
    config_path = tmp_path / "physical-agent.yaml"
    setup_project(config_path, publish=True)
    runtime = ChatRuntime(config_path, planner_name="auto")

    def fail(*args, **kwargs):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(runtime, "_mode", lambda: "llm")
    monkeypatch.setattr(runtime, "_respond_with_llm", fail)

    result = runtime.respond("what is the world status?")

    assert result["mode"] == "rule_based"
    assert "LLM chat was unavailable" in result["reply"]


def test_chat_runtime_recognizes_chinese_integration_request(tmp_path):
    config_path = tmp_path / "physical-agent.yaml"
    setup_project(config_path, publish=True)
    runtime = ChatRuntime(config_path, planner_name="rule_based")
    runtime.setup()

    assert runtime._looks_like_integration_request("帮我接入这个硬件 SDK ./vendor_sdk")
