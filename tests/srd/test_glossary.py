"""SRD rule tests for the Rules Glossary (SRD 5.2.1 p.176-191)."""

import pytest

from dungdra import actions
from dungdra import combat as C
from dungdra.api import Session
from dungdra.effects import SpeedPenalty
from tests.support.helpers import mon, pc
from tests.support.srd import assert_refused_cleanly

U = "GLOSS.grappled"


def start(game, *cs):
    return C.roll_initiative(game, cs)


def set_turn(game, c):
    cb = game.combat
    if cb.current is not None:
        C._expire(game, "end", cb.current)
    cb.index = next(i for i, (cid, _) in enumerate(cb.order) if cid == c.id)
    C.start_turn(game)


def grab(game, grappler, target):
    """Grapple through the engine; a forced natural 1 makes the target fail its save."""
    game.dice.force_str("d20=[1]")
    assert C.grapple(game, grappler, target)
    assert target.has("grappled")


def brom_free_hand(game, pos=(0, 0)):
    brom = pc(game, "BROM", pos)
    brom.shield = None  # a free hand to grapple with
    return brom


def in_combat(game, mover, *others):
    """Start combat and give `mover` the turn. Initiative dice are forced so every roll is used."""
    game.dice.force_str("d20=[" + ",".join(["20"] + ["1"] * len(others)) + "]")
    start(game, mover, *others)
    set_turn(game, mover)


# ---------------- #1 · Speed 0 and can't increase ----------------
@pytest.mark.srd(U, clause=f"{U}#1", kind="positive")
def test_grappled_speed_is_zero(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.speed() == 30
    grab(game, brom, gob)
    assert gob.speed() == 0


@pytest.mark.srd(U, clause=f"{U}#1", kind="positive", ruling="R-07")
def test_grappled_special_speed_is_zero_too(game):
    brom = brom_free_hand(game)
    rat = mon(game, "giant rat", (5, 0))
    assert rat.speed("climb") == 30
    grab(game, brom, rat)
    assert rat.speed("climb") == 0


@pytest.mark.srd(U, clause=f"{U}#1", kind="negative")
def test_grappler_and_escaped_creature_keep_their_speed(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    assert brom.speed() == 30  # the grappler isn't Grappled
    C.release_grapple(game, gob)
    assert not gob.has("grappled") and gob.speed() == 30


@pytest.mark.srd(U, clause=f"{U}#1", kind="boundary")
def test_grappled_turn_starts_with_no_movement(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, gob, brom)
    assert game.combat.turn.movement_left == 0


@pytest.mark.srd(U, clause=f"{U}#1", kind="boundary", ruling="R-07")
def test_grappled_speed_cant_increase_with_a_bonus(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    gob.add_effect(SpeedPenalty("speed bonus", -10))  # a +10 ft Speed increase
    assert gob.speed() == 0


@pytest.mark.srd(U, clause=f"{U}#1", kind="abuse")
def test_grappled_dash_adds_no_movement(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, gob, brom)
    actions.dash(game, gob)
    assert game.combat.turn.movement_left == 0
    assert_refused_cleanly(game, C.move, game, gob, to=(10, 0))


@pytest.mark.srd(U, clause=f"{U}#1", kind="abuse")
def test_grappled_cant_move_even_one_step(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, gob, brom)
    assert_refused_cleanly(game, C.move, game, gob, to=(10, 0), match="Speed")


@pytest.mark.srd(U, clause=f"{U}#1", kind="abuse")
def test_grappled_mid_turn_cant_spend_leftover_movement(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    in_combat(game, gob, brom)
    assert game.combat.turn.movement_left == 30
    gob.add_condition("grappled", "grappled mid-turn", grappler=brom.id)
    assert_refused_cleanly(game, C.move, game, gob, to=(10, 0), match="Speed")


@pytest.mark.srd(U, clause=f"{U}#1", kind="abuse")
def test_grappled_pc_move_command_refused(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, gob, brom)
    in_combat(game, brom, gob)
    assert_refused_cleanly(game, s.execute, {"cmd": "move", "actor": brom.id, "to": [-5, 0]})
    assert brom.position == (0, 0)


# ---------------- #2 · Disadvantage against anyone but the grappler ----------------
@pytest.mark.srd(U, clause=f"{U}#2", kind="positive")
def test_grappled_attack_on_other_target_has_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grab(game, gob, brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10,10]")
    r = C.attack(game, brom, bandit, weapon="longsword")
    assert r.roll.mode == "disadvantage"
    assert any("Grappled" in s for s in r.roll.dis)


@pytest.mark.srd(U, clause=f"{U}#2", kind="negative")
def test_grappled_attack_on_grappler_has_no_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, gob, brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]")
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.roll.mode == "normal"
    assert not any("Grappled" in s for s in r.roll.dis)


@pytest.mark.srd(U, clause=f"{U}#2", kind="negative")
def test_grappler_attacks_without_grappled_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (5, 5))
    grab(game, gob, brom)
    game.dice.force_str("d20=[10]")
    r = C.attack(game, gob, bandit, attack_name="scimitar")
    assert not any("Grappled" in s for s in r.roll.dis)


@pytest.mark.srd(U, clause=f"{U}#2", kind="negative")
def test_disadvantage_ends_with_the_grapple(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grab(game, gob, brom)
    C.release_grapple(game, brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]")
    r = C.attack(game, brom, bandit, weapon="longsword")
    assert r.roll.mode == "normal"


@pytest.mark.srd(U, clause=f"{U}#2", kind="boundary", ruling="R-06")
def test_two_grapplers_neither_attack_has_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    guard = mon(game, "guard", (-5, 0))
    grab(game, gob, brom)
    grab(game, bandit, brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10,10]")
    assert C.attack(game, brom, guard, weapon="longsword").roll.mode == "disadvantage"
    for grappler in (gob, bandit):
        game.answer("use_savage_attacker", False)
        game.dice.force_str("d20=[10]")
        r = C.attack(game, brom, grappler, weapon="longsword")
        assert not any("Grappled" in s for s in r.roll.dis), f"attack on {grappler.name}: {r.roll.dis}"


@pytest.mark.srd(U, clause=f"{U}#2", kind="positive")
def test_grappled_attack_command_has_disadvantage(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grab(game, gob, brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10,10]")
    out = s.execute({"cmd": "attack", "actor": brom.id, "target": bandit.id, "weapon": "longsword"})
    assert out["ok"], out
    assert game.log.last("attack") is not None
    assert "isadvantage" in game.log.last("attack").text


# ---------------- #3 · The grappler can drag you ----------------
@pytest.mark.srd(U, clause=f"{U}#3", kind="positive")
def test_grappler_drags_target_along(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, brom, gob)
    C.move(game, brom, to=(-10, 0), drag=gob)
    assert brom.position == (-10, 0)
    assert brom.distance_to(gob) <= 5
    assert gob.has("grappled")


@pytest.mark.srd(U, clause=f"{U}#3", kind="negative")
def test_grappler_moving_without_dragging_leaves_target(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, brom, gob)
    C.move(game, brom, to=(-10, 0))
    assert gob.position == (5, 0)


@pytest.mark.srd(U, clause=f"{U}#3", kind="abuse")
def test_cant_drag_a_creature_you_arent_grappling(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    in_combat(game, brom, gob)
    assert_refused_cleanly(game, C.move, game, brom, to=(-10, 0), drag=gob)


@pytest.mark.srd(U, clause=f"{U}#3", kind="abuse")
def test_cant_drag_a_creature_someone_else_grapples(game):
    brom = brom_free_hand(game)
    lidda = pc(game, "LIDDA", (5, 5))
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, lidda, brom, gob)
    assert_refused_cleanly(game, C.move, game, lidda, to=(15, 5), drag=gob)


# ---------------- #4 · 1 extra foot per foot, unless Tiny or 2+ sizes smaller ----------------
@pytest.mark.srd(U, clause=f"{U}#4", kind="positive")
def test_dragging_one_size_smaller_costs_double(game):
    brom = brom_free_hand(game)  # Medium
    gob = mon(game, "goblin warrior", (5, 0))  # Small
    grab(game, brom, gob)
    in_combat(game, brom, gob)
    assert C.move(game, brom, to=(-10, 0), drag=gob) == 20
    assert game.combat.turn.movement_left == 10


@pytest.mark.srd(U, clause=f"{U}#4", kind="positive")
def test_dragging_same_size_costs_double(game):
    brom = brom_free_hand(game)  # Medium
    bandit = mon(game, "bandit", (5, 0))  # Medium
    grab(game, brom, bandit)
    in_combat(game, brom, bandit)
    assert C.move(game, brom, to=(-5, 0), drag=bandit) == 10


@pytest.mark.srd(U, clause=f"{U}#4", kind="boundary")
def test_dragging_exactly_two_sizes_smaller_costs_nothing_extra(game):
    ogre = mon(game, "ogre", (0, 0))  # Large
    gob = mon(game, "goblin warrior", (5, 0))  # Small
    grab(game, ogre, gob)
    in_combat(game, ogre, gob)
    assert C.move(game, ogre, to=(-10, 0), drag=gob) == 10


@pytest.mark.srd(U, clause=f"{U}#4", kind="boundary")
def test_dragging_exactly_one_size_smaller_for_large_costs_double(game):
    ogre = mon(game, "ogre", (0, 0))  # Large
    bandit = mon(game, "bandit", (5, 0))  # Medium
    grab(game, ogre, bandit)
    in_combat(game, ogre, bandit)
    assert C.move(game, ogre, to=(-10, 0), drag=bandit) == 20


@pytest.mark.srd(U, clause=f"{U}#4", kind="boundary", ruling="R-05")
def test_tiny_dragging_tiny_costs_nothing_extra(game):
    gob = mon(game, "goblin warrior", (0, 0))
    gob.size = "tiny"
    rat = mon(game, "giant rat", (5, 0))
    rat.size = "tiny"
    grab(game, gob, rat)
    in_combat(game, gob, rat)
    assert C.move(game, gob, to=(-10, 0), drag=rat) == 10


@pytest.mark.srd(U, clause=f"{U}#4", kind="boundary")
def test_drag_cost_uses_whole_speed_exactly(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, brom, gob)
    assert game.combat.turn.movement_left == 30
    assert C.move(game, brom, to=(-15, 0), drag=gob) == 30
    assert game.combat.turn.movement_left == 0


@pytest.mark.srd(U, clause=f"{U}#4", kind="abuse")
def test_drag_beyond_speed_refused(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, brom, gob)
    assert_refused_cleanly(game, C.move, game, brom, to=(-20, 0), drag=gob)


@pytest.mark.srd(U, clause=f"{U}#4", kind="positive")
def test_drag_cost_stacks_with_difficult_terrain(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, brom, gob)
    assert C.move(game, brom, to=(-10, 0), drag=gob, difficult=True) == 30
