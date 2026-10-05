"""Unit tests for dungdra.api: the move command, and how refusals are logged."""

from dungdra.api import Session
from dungdra.combat import roll_initiative
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


# ---------------- the ready command ----------------
def _ready_session(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [brom, gob])
    s = Session(game)
    s.auto_gm = False
    return s, brom, gob


def _ready(s, brom, gob, response, trigger=None):
    trigger = trigger or {"event": "moves_within", "creature": gob.id, "feet": 5}
    return s.execute({"cmd": "ready", "actor": brom.id, "trigger": trigger, "response": response})


def test_ready_command_readies_an_attack(game):
    s, brom, gob = _ready_session(game)
    out = _ready(s, brom, gob, {"cmd": "attack", "target": gob.id})
    assert out["ok"], out
    assert game.combat.readied[brom.id].trigger == gob.id


def test_ready_command_readies_a_move(game):
    s, brom, gob = _ready_session(game)
    assert _ready(s, brom, gob, {"cmd": "move", "to": [-30, 0]})["ok"]
    assert brom.position == (0, 0)
    assert "move" in game.combat.readied[brom.id].what


def test_ready_command_readies_a_spell_and_holds_it(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (60, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [mialee, gob])
    s = Session(game)
    out = _ready(s, mialee, gob, {"cmd": "cast", "spell": "magic missile", "targets": gob.id})
    assert out["ok"], out
    assert game.combat.readied[mialee.id].held == mialee.concentrating
    assert game.combat.turn.actions_used == 1


def test_cast_command_casts_with_the_named_item_only(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    s = Session(game)
    out = s.execute(
        {"cmd": "cast", "actor": mialee.id, "spell": "fire bolt", "targets": gob.id, "item": "wand"}
    )
    assert not out["ok"] and "has no wand" in out["error"]
    game.dice.force_str("d20=[1]")
    assert s.execute({"cmd": "cast", "actor": mialee.id, "spell": "fire bolt", "targets": gob.id})["ok"]


def test_ready_command_refuses_a_bonus_action_under_ruling_r20(game):
    s, brom, gob = _ready_session(game)
    out = _ready(s, brom, gob, {"cmd": "second_wind"})
    assert not out["ok"] and "Bonus Action" in out["error"]
    ev = game.log.last("refused")
    assert (ev.page, ev.rule, ev.ruling) == ("187", "GLOSS.ready#4", "R-20")
    assert game.combat.turn.actions_used == 0


def test_ready_command_refuses_each_registered_bonus_action(game):
    s, brom, gob = _ready_session(game)
    for cmd in ("cunning_action", "steady_aim", "stonecunning"):
        out = _ready(s, brom, gob, {"cmd": cmd})
        assert not out["ok"] and f"{cmd} is a Bonus Action" in out["error"]
        assert game.log.last("refused").rule == "GLOSS.ready#4"
    assert game.combat.turn.actions_used == 0


def test_ready_command_refuses_two_responses(game):
    s, brom, gob = _ready_session(game)
    out = _ready(s, brom, gob, [{"cmd": "attack", "target": gob.id}, {"cmd": "move", "to": [-5, 0]}])
    assert not out["ok"] and "one" in out["error"]
    assert game.combat.readied == {}


def test_ready_command_puts_other_actions_and_triggers_out_of_scope(game):
    s, brom, gob = _ready_session(game)
    out = _ready(s, brom, gob, {"cmd": "dodge"})
    assert out["error"].startswith("Out of scope")
    out = _ready(s, brom, gob, {"cmd": "attack", "target": gob.id}, trigger={"event": "opens_door"})
    assert out["error"].startswith("Out of scope")
    assert game.combat.turn.actions_used == 0
