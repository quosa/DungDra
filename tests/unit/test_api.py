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


# ---------------- the disengage command ----------------
def test_disengage_command_as_a_bonus_action_is_refused_without_a_feature(game):
    brom = pc(game, "BROM", (0, 0))
    bandit = mon(game, "bandit", (5, 0))
    game.dice.force_str("d20=[1,20]")
    roll_initiative(game, [brom, bandit])
    s = Session(game)
    s.auto_gm = False
    out = s.execute({"cmd": "disengage", "actor": bandit.id, "bonus": True})
    assert not out["ok"]
    assert game.log.last("refused").rule == "PLAY.actions.bonus-actions"
    assert not bandit.find_effects("disengage")
    assert s.execute({"cmd": "disengage", "actor": bandit.id})["ok"]
    assert game.combat.turn.bonus_used is False


def test_disengage_command_as_a_bonus_action_uses_nimble_escape(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[1,20]")
    roll_initiative(game, [brom, gob])
    s = Session(game)
    s.auto_gm = False
    assert s.execute({"cmd": "disengage", "actor": gob.id, "bonus": True})["ok"]
    assert gob.find_effects("disengage")[0].source == "Nimble Escape (Disengage)"


# ---------------- the dash command ----------------
def test_dash_command_as_a_bonus_action_is_refused_without_a_feature(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[1,20]")
    roll_initiative(game, [brom, gob])
    s = Session(game)
    s.auto_gm = False
    before = game.combat.turn.movement_left
    out = s.execute({"cmd": "dash", "actor": gob.id, "bonus": True})
    assert not out["ok"]
    assert game.log.last("refused").rule == "PLAY.actions.bonus-actions"
    assert game.combat.turn.bonus_used is False
    assert game.combat.turn.movement_left == before


def test_dash_command_as_a_bonus_action_uses_cunning_action(game):
    lidda = pc(game, "LIDDA", (0, 0))
    lidda.features.append("cunning action")
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [lidda, gob])
    s = Session(game)
    s.auto_gm = False
    before = game.combat.turn.movement_left
    assert s.execute({"cmd": "dash", "actor": lidda.id, "bonus": True})["ok"]
    assert game.combat.turn.bonus_used is True
    assert game.combat.turn.movement_left == before + lidda.speed()


def test_dash_command_without_bonus_uses_the_action(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [brom, gob])
    s = Session(game)
    s.auto_gm = False
    assert s.execute({"cmd": "dash", "actor": brom.id})["ok"]
    assert game.combat.turn.actions_used == 1
    assert game.combat.turn.bonus_used is False


# ---------------- the cunning_action command ----------------
def test_cunning_action_command_hides_behind_three_quarters_cover_by_default(game):
    lidda = pc(game, "LIDDA", (0, 0))
    lidda.features.append("cunning action")
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [lidda, gob])
    s = Session(game)
    s.auto_gm = False
    game.dice.force_str("d20=[15]")
    assert s.execute({"cmd": "cunning_action", "what": "hide", "actor": lidda.id})["ok"]
    assert game.combat.turn.bonus_used is True
    assert lidda.hidden_total is not None


def test_cunning_action_command_refuses_an_action_it_does_not_allow(game):
    lidda = pc(game, "LIDDA", (0, 0))
    lidda.features.append("cunning action")
    s = Session(game)
    out = s.execute({"cmd": "cunning_action", "what": "dodge", "actor": lidda.id})
    assert not out["ok"] and "Dash, Disengage or Hide" in out["error"]
    assert game.log.last("refused").rule == "CLASS.rogue.level-2-cunning-action"


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
