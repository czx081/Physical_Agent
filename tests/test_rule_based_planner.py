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

XIAOZHI_CAPABILITIES = {
    "robots": {
        "xiaozhi_1": {
            "capabilities": [
                {"name": "observe"},
                {"name": "set_volume"},
                {"name": "otto_action"},
                {"name": "home"},
                {"name": "stop"},
            ]
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


def test_wave_generates_otto_action():
    actions = RuleBasedPlanner().plan(task="wave to me", capabilities=XIAOZHI_CAPABILITIES, world=WORLD)
    assert actions[0].capability == "otto_action"
    assert actions[0].params["action"] == "hand_wave"


def test_home_generates_home_action():
    actions = RuleBasedPlanner().plan(task="go home", capabilities=XIAOZHI_CAPABILITIES, world=WORLD)
    assert actions[0].capability == "home"


def test_stop_generates_stop_action():
    actions = RuleBasedPlanner().plan(task="stop now", capabilities=XIAOZHI_CAPABILITIES, world=WORLD)
    assert actions[0].capability == "stop"


def test_set_volume_generates_volume_action():
    actions = RuleBasedPlanner().plan(task="set volume to 35", capabilities=XIAOZHI_CAPABILITIES, world=WORLD)
    assert actions[0].capability == "set_volume"
    assert actions[0].params["volume"] == 35
