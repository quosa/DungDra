import pytest

from dungdra import class_actions as CA
from dungdra.rules import Refusal
from tests.support.helpers import mon, pc


def test_is_bonus_action_comes_from_the_bonus_action_registry():
    for name in CA.BONUS_ACTIONS:
        assert CA.is_bonus_action(name)
    assert CA.is_bonus_action("second_wind")
    assert CA.is_bonus_action("Steady-Aim")
    assert CA.is_bonus_action("cunning action: dash")


def test_is_bonus_action_is_false_for_actions_and_unknown_names():
    for name in ("attack", "cast", "move", "action surge", "dodge", None):
        assert not CA.is_bonus_action(name)


def test_parse_feature_splits_the_feature_from_its_option():
    assert CA.parse_feature("Cunning Action: Disengage") == ("cunning action", "Disengage")
    assert CA.parse_feature("second_wind") == ("second wind", None)


def test_bonus_action_dispatches_cunning_action_with_its_option(game):
    lidda = pc(game, "LIDDA")
    lidda.features.append("cunning action")
    CA.bonus_action(game, lidda, "Cunning Action: disengage")
    assert lidda.find_effects("disengage")
    assert "Disengage action as a Bonus Action" in game.log.last("action").text


def test_bonus_action_refuses_an_option_the_feature_does_not_allow(game):
    lidda = pc(game, "LIDDA")
    lidda.features.append("cunning action")
    with pytest.raises(Refusal) as e:
        CA.bonus_action(game, lidda, "cunning_action: dodge")
    assert e.value.rule == "CLASS.rogue.level-2-cunning-action"


def test_bonus_action_refuses_a_name_no_feature_grants(game):
    lidda = pc(game, "LIDDA")
    with pytest.raises(Refusal) as e:
        CA.bonus_action(game, lidda, "dash")
    assert e.value.rule == "PLAY.actions.bonus-actions"


def test_nimble_escape_is_refused_with_a_citation_for_a_creature_without_the_trait(game):
    bandit = mon(game, "bandit")
    with pytest.raises(Refusal) as e:
        CA.nimble_escape(game, bandit, "disengage")
    assert e.value.rule == "MONSTER.goblins.goblin-warrior#24"
    assert e.value.page == 290
    assert not bandit.find_effects("disengage")


def test_nimble_escape_allows_only_disengage_or_hide(game):
    gob = mon(game, "goblin warrior")
    with pytest.raises(Refusal) as e:
        CA.nimble_escape(game, gob, "dash")
    assert e.value.rule == "MONSTER.goblins.goblin-warrior#24"
    CA.nimble_escape(game, gob, "Disengage")
    assert gob.find_effects("disengage")


def test_bonus_disengage_is_refused_with_a_citation_without_a_granting_feature(game):
    bandit = mon(game, "bandit")
    with pytest.raises(Refusal) as e:
        CA.bonus_disengage(game, bandit)
    assert e.value.rule == "MONSTER.goblins.goblin-warrior#24"
    assert e.value.page == 290
    assert not bandit.find_effects("disengage")


def test_bonus_disengage_goes_through_nimble_escape(game):
    gob = mon(game, "goblin warrior")
    CA.bonus_disengage(game, gob)
    assert gob.find_effects("disengage")[0].source == "Nimble Escape"


def test_bonus_disengage_goes_through_cunning_action(game):
    lidda = pc(game, "LIDDA")
    lidda.features.append("cunning action")
    CA.bonus_disengage(game, lidda)
    assert lidda.find_effects("disengage")[0].source == "Cunning Action (Disengage)"
