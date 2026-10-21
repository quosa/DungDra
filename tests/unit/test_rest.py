"""Unit tests for dungdra.rest: spending Hit Dice on a Short Rest."""

from dungdra.rest import short_rest_benefits
from tests.support.helpers import pc


def test_a_hit_die_can_be_rerolled_with_heroic_inspiration(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.hp, jozan.heroic_inspiration = 1, True
    game.answer("inspiration", 0)
    game.dice.force_str(f"d{jozan.hit_die}=[1,6]")
    short_rest_benefits(game, jozan, max_dice=1)
    assert jozan.hp == 1 + max(1, 6 + jozan.mod("con"))
    assert jozan.heroic_inspiration is False
    assert jozan.hit_dice_spent == 1


def test_without_heroic_inspiration_the_hit_die_stands(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.hp = 1
    game.dice.force_str(f"d{jozan.hit_die}=[3]")
    short_rest_benefits(game, jozan, max_dice=1)
    assert jozan.hp == 1 + max(1, 3 + jozan.mod("con"))
