"""Unit tests for dungdra.monster: rolling a monster's Hit Points from its Hit Dice."""

import pytest

from dungdra.monster import Monster
from dungdra.rules import Refusal
from tests.support.helpers import mon


def test_rolled_hp_rolls_the_hit_dice_and_its_modifier_when_the_monster_joins(game):
    game.dice.force_str("d10=[1,2,3,4,5,6,7,8]")
    ogre = mon(game, "ogre", hp="roll")
    assert ogre.hp == ogre.max_hp == 36 + 24
    (ev,) = game.log.of_kind("hp_rolled")
    assert ev.rule == "MONSTER.parts-of-a-stat-block.hit-points" and ev.page == "255"
    assert "8d10+24" in ev.text


def test_a_rolled_total_below_1_still_leaves_1_hp(game):
    game.dice.force_str("d6=[1,1,1]")
    kobold = mon(game, "kobold warrior", hp="roll")
    assert kobold.hp == kobold.max_hp == 1


def test_rolled_hp_is_not_rolled_again_when_re_added(game):
    game.dice.force_str("d6=[1,2,3]")
    gob = mon(game, "goblin warrior", hp="roll")
    game.remove(gob)
    game.add(gob, team="enemy")
    assert gob.max_hp == 6 and len(game.log.of_kind("hp_rolled")) == 1


def test_average_and_fixed_hp_roll_nothing(game):
    avg = mon(game, "goblin warrior")
    fixed = mon(game, "goblin warrior", name="Fixed", hp=4)
    assert avg.hp == avg.max_hp == 10 and fixed.hp == fixed.max_hp == 4
    assert game.log.of_kind("hp_rolled") == []


def test_a_monster_keeps_the_average_until_it_joins_a_game():
    gob = Monster("goblin warrior", hp="roll")
    assert gob.hp == gob.max_hp == 10


def test_attack_named_finds_a_listed_attack_by_name_or_defaults_to_the_first():
    gob = Monster("goblin warrior")
    assert gob.attack_named("Shortbow")["name"] == "Shortbow"
    assert gob.attack_named(None) is gob.attacks[0]


def test_an_attack_the_stat_block_doesnt_list_is_refused_citing_the_actions_rule():
    gob = Monster("goblin warrior", name="Gob")
    with pytest.raises(Refusal) as exc:
        gob.attack_named("longsword")
    assert exc.value.page == 256 and exc.value.rule == "MONSTER.parts-of-a-stat-block.actions"
    assert "Scimitar, Shortbow" in exc.value.reason


def test_passive_perception_is_the_printed_number_without_advantage_or_disadvantage(game):
    gob = mon(game, "goblin warrior", (30, 0))
    gob.fixed_passive = 13  # a stat block whose printed score isn't 10 + its Wisdom modifier
    assert gob.passive("perception") == 13


def test_disadvantage_on_perception_checks_lowers_the_printed_passive_by_5(game):
    gob = mon(game, "goblin warrior", (30, 0))
    gob.fixed_passive = 13
    gob.add_condition("poisoned", "test")
    assert gob.passive("perception") == 8


def test_other_passive_skills_still_come_from_the_check_bonus(game):
    gob = mon(game, "goblin warrior", (30, 0))
    assert gob.passive("stealth") == 16
    gob.add_condition("poisoned", "test")
    assert gob.passive("stealth") == 11
