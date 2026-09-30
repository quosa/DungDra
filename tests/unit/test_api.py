"""Unit tests for dungdra.api: the move command."""

from dungdra.api import Session
from dungdra.effects import Condition
from tests.support.helpers import mon, pc


def grappled_by(target, grappler):
    target.add_effect(
        Condition("grappled", f"grappled by {grappler.name}", caster=grappler, grappler=grappler.id)
    )


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
