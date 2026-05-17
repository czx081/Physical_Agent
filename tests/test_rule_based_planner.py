from physical_agent.agent.rule_based import RuleBasedPlanner


CAPABILITIES = {
    "robots": {
        "arm_1": {
            "capabilities": [
                {"name": "observe"},
                {"name": "move_to", "params_schema": {"required": ["x", "y", "z"]}},
                {"name": "pick"},
                {"name": "place"},
            ]
        }
    }
}

WORLD = {
    "state": {
        "objects": {
            "red_block": {"type": "block", "color": "red"},
            "tray": {"type": "tray"},
        }
    }
}


def test_look_around_to_observe():
    actions = RuleBasedPlanner().plan(task="look around", capabilities=CAPABILITIES, world=WORLD)
    assert actions[0].capability == "observe"


def test_pick_red_block_to_pick():
    actions = RuleBasedPlanner().plan(task="pick the red block", capabilities=CAPABILITIES, world=WORLD)
    assert actions[0].capability == "pick"
    assert actions[0].params["object_id"] == "red_block"


def test_place_on_tray_to_place():
    actions = RuleBasedPlanner().plan(task="place it on the tray", capabilities=CAPABILITIES, world=WORLD)
    assert actions[0].capability == "place"
    assert actions[0].params["target"] == "tray"


def test_pick_and_place_generates_dependency():
    actions = RuleBasedPlanner().plan(
        task="pick the red block and place it on the tray",
        capabilities=CAPABILITIES,
        world=WORLD,
    )
    assert [action.capability for action in actions] == ["pick", "place"]
    assert actions[1].depends_on == [actions[0].id]

