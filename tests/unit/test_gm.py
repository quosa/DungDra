"""Unit tests for dungdra.gm: the monster turn's Nimble Escape Hide."""

from dungdra import gm
from dungdra.combat import roll_initiative
from tests.support.helpers import mon, pc


def _goblin_turn_far_from_brom(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (500, 0))
    gob.notes["cover_nearby"] = True
    game.dice.force_str("d20=[1,20]")
    roll_initiative(game, [brom, gob])
    game.dice.rng.seed(1)  # first draw 0.13: the GM chooses to hide (it hides 40% of the time)
    return brom, gob


def test_a_goblin_with_cover_nearby_hides_with_nimble_escape(game):
    _, gob = _goblin_turn_far_from_brom(game)
    game.dice.force_str("d20=[15]")
    gm.monster_turn(game, gob)
    assert game.combat.turn.bonus_used is True
    assert gob.hidden_total == 21


def test_a_creature_without_nimble_escape_does_not_hide(game):
    _, gob = _goblin_turn_far_from_brom(game)
    gob.traits.remove("nimble escape")
    gm.monster_turn(game, gob)
    assert game.combat.turn.bonus_used is False
    assert gob.hidden_total is None
