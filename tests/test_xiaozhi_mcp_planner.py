from physical_agent.agent.rule_based import RuleBasedPlanner


CAPABILITIES = {
    "robots": {
        "xiaozhi_1": {
            "capabilities": [
                {"name": "observe"},
                {"name": "say"},
                {"name": "set_light"},
            ]
        }
    }
}


def test_planner_asks_device_to_speak():
    actions = RuleBasedPlanner().plan(
        task='请设备说 "你好，小智"',
        capabilities=CAPABILITIES,
        world={},
    )
    assert actions[0].capability == "say"
    assert actions[0].params["text"] == "你好，小智"


def test_planner_turns_light_rgb_request_into_light_action():
    actions = RuleBasedPlanner().plan(
        task="把灯调成 red",
        capabilities=CAPABILITIES,
        world={},
    )
    assert actions[0].capability == "set_light"
    assert actions[0].params == {"r": 255, "g": 0, "b": 0}
