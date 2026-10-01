"""Death Saving Throws gather the effects on the dying creature (SRD p.17-18)."""

from dungdra.damage import death_save
from dungdra.effects import AdvNext
from dungdra.spells import cast
from tests.support.helpers import pc


def _dying(game):
    jozan = pc(game, "JOZAN", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    return jozan, brom


def test_exhaustion_lowers_a_death_saving_throw(game):
    _, brom = _dying(game)
    brom.exhaustion = 1
    brom.hp = 0
    game.dice.force_str("d20=[11]")
    r = death_save(game, brom)
    assert (-2, "Exhaustion 1") in r.mods
    assert brom.death_saves == {"success": 0, "failure": 1}


def test_bless_d4_is_added_to_a_death_saving_throw(game):
    jozan, brom = _dying(game)
    cast(game, jozan, "bless", [brom])
    brom.hp = 0
    game.dice.force_str("d20=[9]; d4=[1]")
    r = death_save(game, brom)
    assert (1, "Bless (1d4=[1])") in r.mods
    assert brom.death_saves == {"success": 1, "failure": 0}


def test_a_next_roll_effect_is_spent_by_the_death_saving_throw(game):
    _, brom = _dying(game)
    brom.add_effect(AdvNext("Test Advantage", kinds=("death save",)))
    brom.hp = 0
    game.dice.force_str("d20=[3, 15]")
    r = death_save(game, brom)
    assert r.mode == "advantage" and r.chosen == 15
    assert not any(isinstance(e, AdvNext) for e in brom.effects)
    assert brom.death_saves == {"success": 1, "failure": 0}


def test_a_natural_1_is_two_failures_whatever_bless_adds(game):
    jozan, brom = _dying(game)
    cast(game, jozan, "bless", [brom])
    brom.hp = 0
    game.dice.force_str("d20=[1]; d4=[4]")
    death_save(game, brom)
    assert brom.death_saves == {"success": 0, "failure": 2}
