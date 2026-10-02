"""Unit tests for dungdra.api: the move command, and how refusals are logged."""

from dungdra.api import Session
from tests.support.helpers import mon, pc
from tests.unit.helpers import grappled_by


def test_move_command_carries_a_grappled_creature_while_flying(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["fly"] = 30
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    out = Session(game).execute(
        {"cmd": "move", "actor": brom.id, "to": [-10, 0], "mode": "fly", "drag": gob.id}
    )
    assert out["ok"], out
    assert brom.position == (-10, 0)
    assert gob.position == (-5, 0)


def test_move_command_without_drag_leaves_the_grappled_creature(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    out = Session(game).execute({"cmd": "move", "actor": brom.id, "to": [-10, 0]})
    assert out["ok"], out
    assert brom.position == (-10, 0)
    assert gob.position == (5, 0)


def test_a_refused_command_logs_the_rule_and_ruling_that_refused_it(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    grappled_by(rat, brom)
    out = Session(game).execute({"cmd": "move", "actor": rat.id, "to": [5, 10], "mode": "climb"})
    assert not out["ok"]
    ev = game.log.last("refused")
    assert (ev.page, ev.rule, ev.ruling) == ("182", "GLOSS.grappled#1", "R-07")


def test_a_refusal_without_a_rule_logs_none(game):
    out = Session(game).execute({"cmd": "move", "actor": "nobody", "to": [5, 10]})
    assert not out["ok"]
    ev = game.log.last("refused")
    assert (ev.page, ev.rule, ev.ruling) == (None, None, None)
