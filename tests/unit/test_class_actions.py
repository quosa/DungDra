from dungdra import class_actions as CA


def test_is_bonus_action_comes_from_the_bonus_action_registry():
    for name in CA.BONUS_ACTIONS:
        assert CA.is_bonus_action(name)
    assert CA.is_bonus_action("second_wind")
    assert CA.is_bonus_action("Steady-Aim")
    assert CA.is_bonus_action("cunning action: dash")


def test_is_bonus_action_is_false_for_actions_and_unknown_names():
    for name in ("attack", "cast", "move", "action surge", "dodge", None):
        assert not CA.is_bonus_action(name)
