from physical_agent.protocol.markdown import (
    extract_yaml_blocks,
    fenced_yaml,
    parse_front_matter,
    render_front_matter,
)
from physical_agent.protocol.parsers import (
    parse_actions,
    parse_capabilities,
    parse_feedback,
    parse_task,
)
from physical_agent.protocol.renderers import (
    render_actions,
    render_capabilities,
    render_feedback,
    render_task,
)
from physical_agent.protocol.schemas import Action


def test_front_matter_parse_render_roundtrip():
    text = render_front_matter(
        {"schema": "physical-agent/example/v1", "owner": "test", "revision": 1},
        "# Example\n\nHello",
    )
    doc = parse_front_matter(text)
    assert doc.schema == "physical-agent/example/v1"
    assert doc.owner == "test"
    assert doc.revision == 1
    assert "Hello" in doc.body


def test_fenced_yaml_parse_render():
    block = fenced_yaml({"items": ["a", "b"]})
    assert extract_yaml_blocks(block) == [{"items": ["a", "b"]}]


def test_task_render_parse():
    text = render_task("Pick the red block.", ["Stay inside bounds."], revision=3)
    parsed = parse_task(text)
    assert parsed["metadata"]["revision"] == 3
    assert "Pick the red block" in parsed["task"]
    assert parsed["constraints"] == ["Stay inside bounds."]


def test_actions_render_parse():
    action = Action(
        id="act_001",
        robot="arm_1",
        capability="pick",
        params={"object_id": "red_block"},
    )
    text = render_actions([action], [], [], revision=2)
    parsed = parse_actions(text)
    assert parsed["metadata"]["schema"] == "physical-agent/actions/v1"
    assert parsed["pending"][0].id == "act_001"
    assert parsed["pending"][0].params["object_id"] == "red_block"


def test_capabilities_render_parse():
    text = render_capabilities(
        {
            "arm_1": {
                "kind": "arm",
                "driver": "mock_arm",
                "status": "connected",
                "capabilities": [
                    {
                        "name": "observe",
                        "description": "Observe.",
                        "params_schema": {"type": "object"},
                    }
                ],
            }
        }
    )
    parsed = parse_capabilities(text)
    assert parsed["robots"]["arm_1"]["capabilities"][0]["name"] == "observe"


def test_feedback_render_parse():
    latest = {
        "action_id": "act_001",
        "status": "completed",
        "robot": "arm_1",
        "capability": "observe",
        "message": "ok",
    }
    text = render_feedback(latest, [latest])
    parsed = parse_feedback(text)
    assert parsed["latest"]["action_id"] == "act_001"
    assert parsed["history"][0]["status"] == "completed"

