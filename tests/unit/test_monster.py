"""Unit tests for dungdra.monster: rolling a monster's Hit Points from its Hit Dice."""

from dungdra.monster import Monster
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
