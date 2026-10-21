"""Unit tests for dungdra.rest: Heroic Inspiration and spending Hit Dice on a Short Rest."""

from dungdra.rest import grant_heroic_inspiration, short_rest_benefits
from tests.support.helpers import mon, pc


def test_a_surplus_inspiration_goes_to_the_named_pc_who_lacks_it(game):
    jozan = pc(game, "JOZAN", (0, 0))
    lidda = pc(game, "LIDDA", (5, 0))
    jozan.heroic_inspiration = True
    game.answer("give_inspiration", lidda.id)
    assert grant_heroic_inspiration(game, jozan) is lidda
    assert lidda.heroic_inspiration is True


def test_a_surplus_inspiration_named_for_a_monster_is_lost(game):
    jozan = pc(game, "JOZAN", (0, 0))
    lidda = pc(game, "LIDDA", (5, 0))
    ogre = mon(game, "ogre", (10, 0))
    jozan.heroic_inspiration = True
    game.answer("give_inspiration", ogre.id)
    assert grant_heroic_inspiration(game, jozan) is None
    assert ogre.heroic_inspiration is False
    assert lidda.heroic_inspiration is False
    lost = [e for e in game.log.of_kind("inspiration") if "lost" in e.text]
    assert lost and lost[-1].rule == "GLOSS.heroic-inspiration#3"


def test_a_surplus_inspiration_named_for_a_pc_who_has_it_is_lost(game):
    jozan = pc(game, "JOZAN", (0, 0))
    lidda = pc(game, "LIDDA", (5, 0))
    brom = pc(game, "BROM", (10, 0))
    jozan.heroic_inspiration = lidda.heroic_inspiration = True
    game.answer("give_inspiration", lidda.id)
    assert grant_heroic_inspiration(game, jozan) is None
    assert brom.heroic_inspiration is False
    assert not any("gives" in e.text for e in game.log.of_kind("inspiration"))


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
