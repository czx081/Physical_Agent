from physical_agent.protocol.parsers import parse_chat, parse_memory, parse_plan
from physical_agent.protocol.renderers import render_chat, render_memory, render_plan
from physical_agent.protocol.schemas import ChatMessage, ChatPlan
from physical_agent.protocol.workspace import Workspace


def test_chat_plan_memory_render_parse_roundtrip():
    chat = render_chat([ChatMessage(role="user", content="hello")])
    parsed_chat = parse_chat(chat)
    assert parsed_chat["messages"][0].content == "hello"

    plan = render_plan(
        ChatPlan(
            status="answered",
            intent="chat",
            summary="hello back",
            steps=["read chat"],
        )
    )
    parsed_plan = parse_plan(plan)
    assert parsed_plan["plan"].summary == "hello back"
    assert parsed_plan["plan"].steps == ["read chat"]

    memory = render_memory([{"content": "prefers cautious execution", "source": "test"}])
    parsed_memory = parse_memory(memory)
    assert parsed_memory["notes"][0]["content"] == "prefers cautious execution"


def test_workspace_chat_helpers(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    workspace.append_chat_message("user", "remember that I prefer simulation first")
    workspace.append_chat_message("assistant", "Noted.")
    workspace.append_memory_note("User prefers simulation first.")
    workspace.write_plan({"status": "answered", "intent": "remember", "summary": "Noted."})

    assert workspace.read_chat()["messages"][0].role == "user"
    assert workspace.read_memory()["notes"][0]["content"] == "User prefers simulation first."
    assert workspace.read_plan()["plan"].intent == "remember"

