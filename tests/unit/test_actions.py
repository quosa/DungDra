import pytest

from dungdra import actions
from dungdra.effects import AdvNext, HelpAttack
from dungdra.rules import Refusal
from tests.support.helpers import mon, pc


def test_help_check_refuses_the_helper_as_their_own_ally(game):
    lidda = pc(game, "LIDDA")
    with pytest.raises(Refusal) as e:
        actions.help_check(game, lidda, lidda, skill="perception")
    assert e.value.rule == "GLOSS.ally#1"
    assert e.value.ruling == "R-36"
    assert e.value.page == 176
    assert not lidda.find_effects(cls=AdvNext)
    assert game.log.last("help") is None


def test_help_check_gives_another_creature_advantage_on_the_check(game):
    lidda = pc(game, "LIDDA")
    brom = pc(game, "BROM", (5, 0))
    eff = actions.help_check(game, lidda, brom, skill="perception")
    assert eff in brom.effects
    assert eff.caster_id == lidda.id
    assert "LIDDA Helps BROM" in game.log.last("help").text


def test_help_check_refuses_an_enemy_as_the_ally(game):
    lidda = pc(game, "LIDDA")
    gob = mon(game, "goblin warrior")
    with pytest.raises(Refusal) as e:
        actions.help_check(game, lidda, gob, skill="perception")
    assert e.value.rule == "GLOSS.ally#3"
    assert e.value.page == 176
    assert not gob.find_effects(cls=AdvNext)
    assert game.log.last("help") is None


def test_help_check_assists_a_friendly_creature_off_the_party(game):
    lidda = pc(game, "LIDDA")
    gob = mon(game, "goblin warrior")
    gob.attitude = "friendly"
    eff = actions.help_check(game, lidda, gob, skill="perception")
    assert eff in gob.effects


def test_help_attack_refuses_to_distract_the_helpers_companion(game):
    lidda = pc(game, "LIDDA")
    brom = pc(game, "BROM", (5, 0))
    with pytest.raises(Refusal) as e:
        actions.help_attack(game, lidda, brom)
    assert e.value.rule == "GLOSS.enemy#1"
    assert e.value.ruling == "R-44"
    assert e.value.page == 181
    assert not brom.find_effects(cls=HelpAttack)
    assert game.log.last("help") is None


def test_help_attack_distracts_an_adjacent_enemy(game):
    lidda = pc(game, "LIDDA")
    gob = mon(game, "goblin warrior")
    eff = actions.help_attack(game, lidda, gob)
    assert eff in gob.effects
    assert "LIDDA distracts" in game.log.last("help").text


def test_study_refuses_a_creature_type_not_on_the_list(game):
    mialee = pc(game, "MIALEE")
    game.dice.force_str("d20=[12]")
    with pytest.raises(Refusal) as e:
        actions.study(game, mialee, creature_type="goblinoid")
    assert e.value.rule == "GLOSS.creature-type#3"
    assert e.value.ruling == "R-39"
    assert e.value.page == 179
    assert "Goblinoid isn't a creature type" in str(e.value)
    assert game.dice.pending(20) == 1  # no check was rolled
    game.dice.clear()


def test_study_of_a_listed_type_uses_that_types_skill(game):
    mialee = pc(game, "MIALEE")
    game.dice.force_str("d20=[12]")
    r = actions.study(game, mialee, creature_type="Undead")
    assert "Religion" in r.label
