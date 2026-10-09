"""SRD rule tests for the Rules Glossary (SRD 5.2.1 p.176-191)."""

import pytest

from dungdra import actions
from dungdra import class_actions as CA
from dungdra import combat as C
from dungdra import spells as S
from dungdra.api import Session
from dungdra.effects import SpeedPenalty
from tests.support import ready as RDY
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


@pytest.mark.srd(U, clause=f"{U}#1", kind="abuse", ruling="R-07")
def test_grappled_mid_turn_cant_climb_with_leftover_movement(game):
    """The turn's 30 ft budget is still there, so only a zeroed Climb Speed can stop the climb."""
    brom = brom_free_hand(game)
    rat = mon(game, "giant rat", (5, 0))
    in_combat(game, rat, brom)
    assert game.combat.turn.movement_left == 30
    rat.add_condition("grappled", "grappled mid-turn", grappler=brom.id)
    assert rat.speed("climb") == 0
    assert_refused_cleanly(game, C.move, game, rat, to=(10, 0), mode="climb", match="Speed")
    assert rat.position == (5, 0)


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
def test_small_grappler_drags_tiny_without_extra_cost(game):
    """Small to Tiny is one size apart: only the Tiny exemption, not the size gap, waives the cost."""
    gob = mon(game, "goblin warrior", (0, 0))  # Small
    rat = mon(game, "giant rat", (5, 0))
    rat.size = "tiny"
    grab(game, gob, rat)
    in_combat(game, gob, rat)
    assert C.move(game, gob, to=(-10, 0), drag=rat) == 10
    assert game.combat.turn.movement_left == 20


@pytest.mark.srd(U, clause=f"{U}#4", kind="negative")
def test_small_grappler_drags_small_at_double_cost(game):
    gob = mon(game, "goblin warrior", (0, 0))  # Small
    rat = mon(game, "giant rat", (5, 0))  # Small
    grab(game, gob, rat)
    in_combat(game, gob, rat)
    assert C.move(game, gob, to=(-10, 0), drag=rat) == 20


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


# =====================================================================================
# GLOSS.tremorsense (p.190)
# =====================================================================================
TS = "GLOSS.tremorsense"


def stonecunning_brom(game, pos=(0, 0)):
    """BROM (a dwarf) gains Tremorsense 60 ft through Stonecunning, the in-scope source."""
    brom = pc(game, "BROM", pos)
    CA.stonecunning(game, brom)
    assert brom.senses.get("tremorsense") == 60
    return brom


# ---------------- #4 · Tremorsense doesn't count as a form of sight ----------------
@pytest.mark.srd(TS, clause=f"{TS}#4", kind="positive", ruling="R-08")
def test_tremorsense_doesnt_see_an_invisible_creature(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.senses["tremorsense"] = 60
    brom.add_condition("invisible", "test")
    # same ground, well within range: it can pinpoint BROM, but it doesn't see him
    assert not game.can_see(gob, brom)
    game.dice.force_str("d20=[10,10]")
    r = C.attack(game, gob, brom, attack_name="scimitar")
    assert r.roll.mode == "disadvantage"
    assert any("can't see" in s for s in r.roll.dis)


@pytest.mark.srd(TS, clause=f"{TS}#4", kind="positive")
def test_blinded_creature_with_tremorsense_still_cant_see(game):
    brom = stonecunning_brom(game)
    gob = mon(game, "goblin warrior", (5, 0))
    brom.add_condition("blinded", "test")
    assert not game.can_see(brom, gob)
    game.dice.force_str("d20=[10,10]")
    r = C.attack(game, gob, brom, attack_name="scimitar")
    assert r.roll.mode == "advantage"
    assert any("can't see" in s for s in r.roll.adv)


@pytest.mark.srd(TS, clause=f"{TS}#4", kind="positive", ruling="R-08")
def test_tremorsense_attack_command_on_invisible_target_has_disadvantage(game):
    s = Session(game)
    brom = stonecunning_brom(game)
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("invisible", "test")
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10,10]")
    out = s.execute({"cmd": "attack", "actor": brom.id, "target": gob.id, "weapon": "longsword"})
    assert out["ok"], out
    assert "isadvantage" in game.log.last("attack").text


@pytest.mark.srd(TS, clause=f"{TS}#4", kind="negative")
def test_tremorsense_doesnt_take_away_normal_sight(game):
    brom = stonecunning_brom(game)
    gob = mon(game, "goblin warrior", (5, 0))
    assert game.can_see(brom, gob)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]")
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.roll.mode == "normal"
    assert not any("can't see" in s for s in r.roll.dis)


@pytest.mark.srd(TS, clause=f"{TS}#4", kind="negative")
def test_blindsight_counts_as_sight_where_tremorsense_doesnt(game):
    """Contrast: Blindsight sees the same unseen target, so the tremorsense result is about
    the sense, not the setup."""
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    brom.add_condition("invisible", "test")
    gob.senses["tremorsense"] = 60
    assert not game.can_see(gob, brom)
    gob.senses["blindsight"] = 60
    assert game.can_see(gob, brom)


@pytest.mark.srd(TS, clause=f"{TS}#4", kind="abuse")
def test_tremorsense_cant_target_unseen_creature_with_sight_spell(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.senses["tremorsense"] = 60
    gob = mon(game, "goblin warrior", (10, 0))
    gob.add_condition("invisible", "test")
    assert_refused_cleanly(game, S.cast, game, jozan, "sacred flame", gob, match="can see")


@pytest.mark.srd(TS, clause=f"{TS}#4", kind="abuse")
def test_blinded_tremorsense_cast_command_on_creature_refused(game):
    s = Session(game)
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.senses["tremorsense"] = 60
    jozan.add_condition("blinded", "test")
    gob = mon(game, "goblin warrior", (10, 0))
    assert_refused_cleanly(
        game, s.execute, {"cmd": "cast", "actor": jozan.id, "spell": "sacred flame", "targets": [gob.id]}
    )


# ================================================================ GLOSS.ready
RD = "GLOSS.ready"


def brom_readies_attack(game, gob_pos=(20, 0)):
    """BROM at (0, 0) readies a longsword attack against a goblin for when it steps next to him."""
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", gob_pos)
    s = RDY.combat_session(game, brom, gob)
    out = RDY.ready(s, brom, RDY.moves_within(gob, 5), {"cmd": "attack", "target": gob.id})
    assert out["ok"], out
    return s, brom, gob


def mialee_readies_missile(game, *others, gob_pos=(60, 0)):
    """MIALEE at (0, 0) readies Magic Missile (3 darts) at a goblin for when it comes within 30 ft."""
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", gob_pos)
    s = RDY.combat_session(game, mialee, *others, gob)
    out = RDY.ready(
        s, mialee, RDY.moves_within(gob, 30), {"cmd": "cast", "spell": "magic missile", "targets": [gob.id]}
    )
    assert out["ok"], out
    return s, mialee, gob


def ready_cmd(actor, trigger, response) -> dict:
    return {"cmd": "ready", "actor": actor.id, "trigger": trigger, "response": response}


# ---------------- #1 · Ready waits for a circumstance before acting ----------------
@pytest.mark.srd(RD, clause=f"{RD}#1", kind="positive")
def test_readied_attack_waits_for_the_trigger(game):
    s, brom, gob = brom_readies_attack(game)
    assert gob.hp == 10 and not RDY.reaction_used(game, brom)  # nothing happens yet
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=brom)
    game.dice.force_str("d20=[15]; d8=[2]")
    RDY.move(s, gob, (5, 0))
    assert gob.hp == 5  # 2 + 3 (Str) from the readied longsword
    assert RDY.reaction_used(game, brom)


@pytest.mark.srd(RD, clause=f"{RD}#1", kind="negative")
def test_readied_attack_not_taken_on_the_readying_turn(game):
    s, brom, gob = brom_readies_attack(game, (5, 0))  # the goblin already stands next to BROM
    assert gob.hp == 10
    assert not RDY.reaction_used(game, brom)


# ---------------- #2 · on your turn; a Reaction before the start of your next turn ----------------
@pytest.mark.srd(RD, clause=f"{RD}#2", kind="positive")
def test_ready_takes_the_action(game):
    s, brom, gob = brom_readies_attack(game, (5, 0))
    assert game.combat.turn.actions_used == 1
    assert_refused_cleanly(
        game,
        s.execute,
        {"cmd": "attack", "actor": brom.id, "target": gob.id},
        match="already taken their action",
    )


@pytest.mark.srd(RD, clause=f"{RD}#2", kind="abuse")
def test_ready_refused_off_turn(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    s = RDY.combat_session(game, gob, brom)  # the goblin's turn
    cmd = ready_cmd(brom, RDY.moves_within(gob, 5), {"cmd": "attack", "target": gob.id})
    assert_refused_cleanly(game, s.execute, cmd, match="(?i)turn")


@pytest.mark.srd(RD, clause=f"{RD}#2", kind="abuse")
def test_ready_refused_after_the_action_is_spent(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    s = RDY.combat_session(game, brom, gob)
    game.dice.force_str("d20=[2]")  # a miss: the Attack action is spent
    assert s.execute({"cmd": "attack", "actor": brom.id, "target": gob.id})["ok"]
    cmd = ready_cmd(brom, RDY.moves_within(gob, 5), {"cmd": "attack", "target": gob.id})
    assert_refused_cleanly(game, s.execute, cmd, match="already taken their action")


@pytest.mark.srd(RD, clause=f"{RD}#2", kind="boundary")
def test_readied_attack_ends_at_the_start_of_your_next_turn(game):
    s, brom, gob = brom_readies_attack(game)
    RDY.end_turn(s)  # the goblin's turn: it stays put
    RDY.end_turn(s)  # BROM's next turn starts: the readied attack is gone
    assert game.combat.current is brom
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=brom)
    RDY.move(s, gob, (5, 0))
    assert gob.hp == 10
    assert not RDY.reaction_used(game, brom)


@pytest.mark.srd(RD, clause=f"{RD}#2", kind="abuse")
def test_readied_attack_lost_when_an_opportunity_attack_spent_the_reaction(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob2 = mon(game, "goblin warrior", (30, 0), name="Goblin 2")
    s = RDY.combat_session(game, brom, gob, gob2)
    assert RDY.ready(s, brom, RDY.moves_within(gob2, 5), {"cmd": "attack", "target": gob2.id})["ok"]
    RDY.end_turn(s)
    assert game.combat.current is gob
    game.answer("opportunity_attack", True, who=brom)
    game.dice.force_str("d20=[1]")  # the Opportunity Attack misses
    RDY.move(s, gob, (5, 20))
    assert RDY.reaction_used(game, brom)
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=brom)
    RDY.move(s, gob2, (5, 0))
    assert gob2.hp == 10  # one Reaction per round: nothing left for the readied attack


@pytest.mark.srd(RD, clause=f"{RD}#2", kind="abuse")
def test_no_opportunity_attack_after_the_readied_attack(game):
    s, brom, gob = brom_readies_attack(game)
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=brom)
    game.dice.force_str("d20=[15]; d8=[2]")
    RDY.move(s, gob, (5, 0))
    assert gob.hp == 5
    game.answer("opportunity_attack", True, who=brom)
    RDY.move(s, gob, (5, 15))  # leaves BROM's reach; his Reaction is spent
    assert gob.hp == 5
    assert any("no Reaction available" in str(e) for e in game.log.events)


# ---------------- #3 · a perceivable circumstance triggers the Reaction ----------------
@pytest.mark.srd(RD, clause=f"{RD}#3", kind="negative")
def test_readied_attack_not_taken_when_the_trigger_doesnt_happen(game):
    s, brom, gob = brom_readies_attack(game, (30, 0))
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=brom)
    RDY.move(s, gob, (15, 0))  # moves, but not next to BROM
    assert gob.hp == 10
    assert not RDY.reaction_used(game, brom)


@pytest.mark.srd(RD, clause=f"{RD}#3", kind="positive")
def test_only_the_chosen_circumstance_triggers_the_reaction(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    gob2 = mon(game, "goblin warrior", (0, 20), name="Goblin 2")
    s = RDY.combat_session(game, brom, gob, gob2)
    assert RDY.ready(s, brom, RDY.moves_within(gob2, 5), {"cmd": "attack", "target": gob2.id})["ok"]
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=brom)
    RDY.move(s, gob, (5, 0))  # the other goblin: not the circumstance BROM chose
    assert not RDY.reaction_used(game, brom)
    RDY.end_turn(s)
    game.dice.force_str("d20=[15]; d8=[2]")
    RDY.move(s, gob2, (0, 5))  # the chosen circumstance
    assert gob2.hp == 5
    assert gob.hp == 10
    assert RDY.reaction_used(game, brom)


@pytest.mark.srd(RD, clause=f"{RD}#3", kind="abuse")
def test_ready_trigger_naming_no_creature_refused(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    s = RDY.combat_session(game, brom, gob)
    trigger = {"event": "moves_within", "creature": "ogre", "feet": 5}
    cmd = ready_cmd(brom, trigger, {"cmd": "attack", "target": gob.id})
    assert_refused_cleanly(game, s.execute, cmd, match="(?i)ogre")


# ---------------- #4 · an action, or a move up to your Speed ----------------
@pytest.mark.srd(RD, clause=f"{RD}#4", kind="positive")
def test_readied_move_away_when_the_goblin_steps_next_to_you(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    s = RDY.combat_session(game, lidda, gob)
    assert RDY.ready(s, lidda, RDY.moves_within(gob, 5), {"cmd": "move", "to": [-30, 0]})["ok"]
    assert lidda.position == (0, 0)
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=lidda)
    game.answer("opportunity_attack", False, who=gob)
    RDY.move(s, gob, (5, 0))
    assert lidda.position == (-30, 0)  # her whole Speed of 30 ft
    assert RDY.reaction_used(game, lidda)


@pytest.mark.srd(RD, clause=f"{RD}#4", kind="boundary", ruling="R-20")
def test_readied_move_beyond_speed_refused(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    s = RDY.combat_session(game, lidda, gob)
    cmd = ready_cmd(lidda, RDY.moves_within(gob, 5), {"cmd": "move", "to": [-35, 0]})
    assert_refused_cleanly(game, s.execute, cmd, match="Speed")


@pytest.mark.srd(RD, clause=f"{RD}#4", kind="negative", ruling="R-20")
def test_readying_a_bonus_action_refused(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    s = RDY.combat_session(game, brom, gob)
    cmd = ready_cmd(brom, RDY.moves_within(gob, 5), {"cmd": "second_wind"})
    assert_refused_cleanly(game, s.execute, cmd, match="(?i)bonus action")


@pytest.mark.srd(RD, clause=f"{RD}#4", kind="abuse", ruling="R-20")
def test_readying_an_action_and_a_move_together_refused(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    s = RDY.combat_session(game, brom, gob)
    both = [{"cmd": "attack", "target": gob.id}, {"cmd": "move", "to": [-30, 0]}]
    cmd = ready_cmd(brom, RDY.moves_within(gob, 5), both)
    assert_refused_cleanly(game, s.execute, cmd, match="(?i)one")


# ---------------- #5 · take the Reaction right after the trigger, or ignore it ----------------
@pytest.mark.srd(RD, clause=f"{RD}#5", kind="negative")
def test_ignored_trigger_keeps_the_reaction(game):
    s, brom, gob = brom_readies_attack(game)
    RDY.end_turn(s)
    game.answer(RDY.READIED, False, who=brom)
    RDY.move(s, gob, (5, 0))
    assert not game.answers[(brom.id, RDY.READIED)]  # BROM was asked, and said no
    assert gob.hp == 10
    assert not RDY.reaction_used(game, brom)


@pytest.mark.srd(RD, clause=f"{RD}#5", kind="positive", ruling="R-18")
def test_ignored_trigger_can_be_answered_the_next_time(game):
    s, brom, gob = brom_readies_attack(game, (15, 0))
    RDY.end_turn(s)
    game.answer(RDY.READIED, False, who=brom)
    RDY.move(s, gob, (5, 0))  # the trigger: BROM ignores it
    assert gob.hp == 10 and not RDY.reaction_used(game, brom)
    game.answer("opportunity_attack", False, who=brom)
    RDY.move(s, gob, (15, 0))  # leaves reach; BROM declines the Opportunity Attack
    assert not RDY.reaction_used(game, brom)
    game.answer(RDY.READIED, True, who=brom)
    game.dice.force_str("d20=[15]; d8=[2]")
    RDY.move(s, gob, (5, 0))  # the same circumstance again: BROM takes it
    assert gob.hp == 5 and RDY.reaction_used(game, brom)
    assert not any(game.answers.values()), "every queued answer was asked for"


# ---------------- #6 · a readied spell is cast now and released with the Reaction ----------------
@pytest.mark.srd(RD, clause=f"{RD}#6", kind="positive")
def test_readied_spell_spends_its_slot_when_readied(game):
    s, mialee, gob = mialee_readies_missile(game)
    assert mialee.slots_left(1) == 1
    assert gob.hp == 10  # the energy is held, not released
    assert not RDY.reaction_used(game, mialee)


@pytest.mark.srd(RD, clause=f"{RD}#6", kind="positive")
def test_readied_spell_released_with_the_reaction(game):
    s, mialee, gob = mialee_readies_missile(game)
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=mialee)
    game.dice.force_str("d4=[1,1,1]")
    RDY.move(s, gob, (30, 0))
    assert gob.hp == 4  # three darts of 1d4 + 1
    assert RDY.reaction_used(game, mialee)
    assert mialee.slots_left(1) == 1  # the release spends no second slot


@pytest.mark.srd(RD, clause=f"{RD}#6", kind="negative")
def test_held_spell_not_released_when_the_trigger_is_ignored(game):
    s, mialee, gob = mialee_readies_missile(game)
    RDY.end_turn(s)
    game.answer(RDY.READIED, False, who=mialee)
    RDY.move(s, gob, (30, 0))
    assert not game.answers[(mialee.id, RDY.READIED)]  # MIALEE was asked, and held the spell
    assert gob.hp == 10  # no Reaction, no release
    assert not RDY.reaction_used(game, mialee)
    assert mialee.slots_left(1) == 1  # the slot was spent when she readied it


@pytest.mark.srd(RD, clause=f"{RD}#6", kind="abuse")
def test_readying_a_spell_without_a_slot_refused(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (60, 0))
    mialee.slots_used[1] = mialee.slots_left(1)  # both level 1 slots spent earlier
    s = RDY.combat_session(game, mialee, gob)
    response = {"cmd": "cast", "spell": "magic missile", "targets": [gob.id]}
    cmd = ready_cmd(mialee, RDY.moves_within(gob, 30), response)
    assert_refused_cleanly(game, s.execute, cmd, match="spell slots")


@pytest.mark.srd(RD, clause=f"{RD}#6", kind="abuse", ruling="R-19")
def test_unreleased_readied_spell_doesnt_refund_its_slot(game):
    s, mialee, gob = mialee_readies_missile(game)
    RDY.end_turn(s)
    RDY.end_turn(s)  # MIALEE's next turn: the trigger never came
    assert game.combat.current is mialee
    assert mialee.slots_left(1) == 1


# ---------------- #7 · only a spell with a casting time of an action ----------------
@pytest.mark.srd(RD, clause=f"{RD}#7", kind="negative")
def test_readying_a_bonus_action_spell_refused(game):
    jozan = pc(game, "JOZAN", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    s = RDY.combat_session(game, jozan, brom, gob)
    response = {"cmd": "cast", "spell": "healing word", "targets": [brom.id]}
    cmd = ready_cmd(jozan, RDY.moves_within(gob, 5), response)
    assert_refused_cleanly(game, s.execute, cmd, match="(?i)casting time")
    assert jozan.slots_left(1) == 2


@pytest.mark.srd(RD, clause=f"{RD}#7", kind="abuse")
def test_readying_a_reaction_spell_refused(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    s = RDY.combat_session(game, mialee, gob)
    cmd = ready_cmd(mialee, RDY.moves_within(gob, 5), {"cmd": "cast", "spell": "shield"})
    assert_refused_cleanly(game, s.execute, cmd, match="(?i)casting time")
    assert mialee.slots_left(1) == 2


@pytest.mark.srd(RD, clause=f"{RD}#7", kind="positive")
def test_readying_an_action_cantrip_is_allowed(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (60, 0))
    s = RDY.combat_session(game, mialee, gob)
    response = {"cmd": "cast", "spell": "fire bolt", "targets": [gob.id]}
    out = RDY.ready(s, mialee, RDY.moves_within(gob, 30), response)
    assert out["ok"], out
    assert mialee.concentrating


# ---------------- #8 · holding the spell takes Concentration until your next turn ----------------
@pytest.mark.srd(RD, clause=f"{RD}#8", kind="positive")
def test_holding_a_readied_spell_takes_concentration(game):
    s, mialee, gob = mialee_readies_missile(game)
    assert mialee.concentrating


@pytest.mark.srd(RD, clause=f"{RD}#8", kind="boundary", ruling="R-19")
def test_held_spell_ends_at_the_start_of_your_next_turn(game):
    s, mialee, gob = mialee_readies_missile(game)
    RDY.end_turn(s)
    RDY.end_turn(s)  # MIALEE's next turn starts
    assert game.combat.current is mialee
    assert not mialee.concentrating
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=mialee)
    RDY.move(s, gob, (30, 0))
    assert gob.hp == 10
    assert not RDY.reaction_used(game, mialee)


@pytest.mark.srd(RD, clause=f"{RD}#8", kind="negative")
def test_readying_a_weapon_attack_needs_no_concentration(game):
    jozan = pc(game, "JOZAN", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    S.cast(game, jozan, "bless", [jozan])
    s = RDY.combat_session(game, jozan, gob)
    out = RDY.ready(s, jozan, RDY.moves_within(gob, 5), {"cmd": "attack", "target": gob.id})
    assert out["ok"], out
    assert "bless" in str(jozan.concentrating).lower()  # only a held spell takes Concentration


@pytest.mark.srd(RD, clause=f"{RD}#8", kind="abuse", ruling="R-17")
def test_readying_a_spell_ends_earlier_concentration(game):
    jozan = pc(game, "JOZAN", (0, 0))
    gob = mon(game, "goblin warrior", (60, 0))
    S.cast(game, jozan, "bless", [jozan])
    assert "bless" in str(jozan.concentrating).lower()
    s = RDY.combat_session(game, jozan, gob)
    response = {"cmd": "cast", "spell": "guiding bolt", "targets": [gob.id]}
    out = RDY.ready(s, jozan, RDY.moves_within(gob, 30), response)
    assert out["ok"], out
    assert "bless" not in str(jozan.concentrating).lower()  # holding Guiding Bolt is Concentration too
    assert jozan.concentrating


# ---------------- #9 · broken Concentration: the spell dissipates ----------------
@pytest.mark.srd(RD, clause=f"{RD}#9", kind="positive")
def test_held_spell_dissipates_when_concentration_breaks(game):
    gob1 = mon(game, "goblin warrior", (5, 0), name="Goblin 1")
    s, mialee, gob = mialee_readies_missile(game, gob1)
    RDY.end_turn(s)
    assert game.combat.current is gob1
    game.dice.force_str("d20=[15,1]; d6=[1]")  # a hit for 3, then a failed DC 10 Constitution save
    assert s.execute({"cmd": "attack", "actor": gob1.id, "target": mialee.id, "weapon": "Scimitar"})["ok"]
    assert mialee.hp == 5
    assert not mialee.concentrating
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=mialee)
    RDY.move(s, gob, (30, 0))
    assert gob.hp == 10  # dissipated without taking effect
    assert not RDY.reaction_used(game, mialee)
    assert mialee.slots_left(1) == 1  # and the slot stays spent


@pytest.mark.srd(RD, clause=f"{RD}#9", kind="negative")
def test_held_spell_survives_a_successful_concentration_save(game):
    gob1 = mon(game, "goblin warrior", (5, 0), name="Goblin 1")
    s, mialee, gob = mialee_readies_missile(game, gob1)
    RDY.end_turn(s)
    game.dice.force_str("d20=[15,20]; d6=[1]")  # a hit for 3, then a successful save
    assert s.execute({"cmd": "attack", "actor": gob1.id, "target": mialee.id, "weapon": "Scimitar"})["ok"]
    assert mialee.concentrating
    RDY.end_turn(s)
    game.answer(RDY.READIED, True, who=mialee)
    game.dice.force_str("d4=[1,1,1]")
    RDY.move(s, gob, (30, 0))
    assert gob.hp == 4


# ================ GLOSS.prone ================
PR = "GLOSS.prone"


def knock_prone(c):
    c.add_condition("prone", "knocked down")
    assert c.has("prone")


def melee_mode(game, attacker, target, weapon="longsword", d20="d20=[2,2]"):
    """A PC's weapon attack with low forced dice (a miss), returning the roll."""
    game.answer("use_savage_attacker", False)
    game.dice.force_str(d20)
    return C.attack(game, attacker, target, weapon=weapon).roll


# ---------------- #1 · Only crawling ----------------
@pytest.mark.srd(PR, clause=f"{PR}#1", kind="positive")
def test_prone_crawl_costs_double_and_stays_prone(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    C.move(game, gob, to=(10, 0), mode="crawl")
    assert gob.position == (10, 0)
    assert game.combat.turn.movement_left == 10
    assert gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#1", kind="positive")
def test_prone_walk_is_a_crawl_not_a_free_stand(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    C.move(game, gob, to=(10, 0))
    assert game.combat.turn.movement_left == 10
    assert gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#1", kind="positive")
def test_prone_move_command_crawls(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (40, 0))
    in_combat(game, brom, gob)
    knock_prone(brom)
    out = s.execute({"cmd": "move", "actor": brom.id, "to": [5, 0]})
    assert out["ok"], out
    assert game.combat.turn.movement_left == 20
    assert brom.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#1", kind="negative")
def test_after_standing_movement_costs_normal(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert C.stand_up(game, gob) == 15
    C.move(game, gob, to=(10, 0))
    assert game.combat.turn.movement_left == 5
    assert not gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#1", kind="positive")
def test_prone_crawl_through_difficult_terrain_stacks(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    C.move(game, gob, to=(5, 0), mode="crawl", difficult=True)
    assert game.combat.turn.movement_left == 15  # 5 ft + 5 crawling + 5 Difficult Terrain


@pytest.mark.srd(PR, clause=f"{PR}#1", kind="abuse")
def test_prone_cant_crawl_at_full_speed(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert_refused_cleanly(game, C.move, game, gob, to=(20, 0))
    assert gob.position == (0, 0)
    assert game.combat.turn.movement_left == 30


@pytest.mark.srd(PR, clause=f"{PR}#1", kind="abuse")
def test_prone_cant_climb_instead_of_crawling(game):
    rat = mon(game, "giant rat", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, rat, brom)
    assert rat.speed("climb") > 0
    knock_prone(rat)
    assert_refused_cleanly(game, C.move, game, rat, to=(10, 0), mode="climb")
    assert rat.position == (0, 0)


# ---------------- #2 · Righting yourself costs half your Speed ----------------
@pytest.mark.srd(PR, clause=f"{PR}#2", kind="positive")
def test_stand_costs_half_speed_and_ends_prone(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert C.stand_up(game, gob) == 15
    assert game.combat.turn.movement_left == 15
    assert not gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="positive")
def test_stand_cost_follows_the_creatures_speed(game):
    ogre = mon(game, "ogre", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, ogre, brom)
    assert ogre.speed() == 40
    knock_prone(ogre)
    assert C.stand_up(game, ogre) == 20
    assert game.combat.turn.movement_left == 20


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="positive")
def test_stand_command_spends_half_speed(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (40, 0))
    in_combat(game, brom, gob)
    knock_prone(brom)
    out = s.execute({"cmd": "stand", "actor": brom.id})
    assert out["ok"], out
    assert not brom.has("prone")
    assert game.combat.turn.movement_left == 15


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="boundary", ruling="R-21")
def test_stand_cost_rounds_down_for_an_odd_speed(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    gob.add_effect(SpeedPenalty("hobbled", 5))
    assert gob.speed() == 25
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert C.stand_up(game, gob) == 12
    assert game.combat.turn.movement_left == 13


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="boundary")
def test_stand_with_exactly_the_cost_left(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    C.move(game, gob, to=(15, 0))
    C.drop_prone(game, gob)
    assert game.combat.turn.movement_left == 15
    assert C.stand_up(game, gob) == 15
    assert game.combat.turn.movement_left == 0
    assert not gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="boundary", ruling="R-22")
def test_stand_refused_with_less_than_the_cost_left(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    C.move(game, gob, to=(20, 0))
    C.drop_prone(game, gob)
    assert game.combat.turn.movement_left == 10
    assert_refused_cleanly(game, C.stand_up, game, gob, match="15")
    assert gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="negative")
def test_dash_doesnt_raise_the_stand_cost(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    actions.dash(game, gob)
    assert game.combat.turn.movement_left == 60
    assert C.stand_up(game, gob) == 15  # half the Speed, not half the movement
    assert game.combat.turn.movement_left == 45


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="abuse")
def test_stand_when_not_prone_refused_cleanly(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    C.stand_up(game, gob)
    assert_refused_cleanly(game, C.stand_up, game, gob)
    assert game.combat.turn.movement_left == 15


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="abuse")
def test_cant_stand_up_for_free_on_another_creatures_turn(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    in_combat(game, gob, brom)
    knock_prone(brom)
    assert game.combat.current is gob
    assert_refused_cleanly(game, s.execute, {"cmd": "stand", "actor": brom.id})
    assert brom.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="abuse", ruling="R-22")
def test_drop_and_stand_repeatedly_pays_each_time(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert C.stand_up(game, gob) == 15
    C.drop_prone(game, gob)
    assert C.stand_up(game, gob) == 15
    C.drop_prone(game, gob)
    assert game.combat.turn.movement_left == 0
    assert_refused_cleanly(game, C.stand_up, game, gob)
    assert gob.has("prone")


# ---------------- #3 · Speed 0: can't right yourself ----------------
@pytest.mark.srd(PR, clause=f"{PR}#3", kind="positive")
def test_grappled_prone_creature_cant_stand(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert gob.speed() == 0
    assert_refused_cleanly(game, C.stand_up, game, gob, match="Speed 0")
    assert gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#3", kind="positive")
def test_restrained_prone_pc_stand_command_refused(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (40, 0))
    in_combat(game, brom, gob)
    brom.add_condition("restrained")
    knock_prone(brom)
    assert brom.speed() == 0
    out = assert_refused_cleanly(game, s.execute, {"cmd": "stand", "actor": brom.id})
    assert "Speed 0" in out["error"]
    assert brom.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#3", kind="negative")
def test_speed_zero_ends_and_the_creature_can_stand(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    grab(game, brom, gob)
    knock_prone(gob)
    C.release_grapple(game, gob)
    in_combat(game, gob, brom)
    assert gob.speed() == 30
    assert C.stand_up(game, gob) == 15
    assert not gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#3", kind="boundary")
def test_speed_reduced_to_zero_by_a_penalty_cant_stand(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    gob.add_effect(SpeedPenalty("crushed", 30))
    assert gob.speed() == 0
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert_refused_cleanly(game, C.stand_up, game, gob)
    assert gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#3", kind="boundary", ruling="R-21")
def test_speed_five_can_still_stand(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    gob.add_effect(SpeedPenalty("crushed", 25))
    assert gob.speed() == 5
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert C.stand_up(game, gob) == 2
    assert game.combat.turn.movement_left == 3
    assert not gob.has("prone")


@pytest.mark.srd(PR, clause=f"{PR}#3", kind="abuse")
def test_movement_left_from_before_a_grapple_cant_right_you(game):
    brom = brom_free_hand(game)
    gob = mon(game, "goblin warrior", (5, 0))
    in_combat(game, gob, brom)
    knock_prone(gob)
    assert game.combat.turn.movement_left == 30
    gob.add_condition("grappled", "grappled mid-turn", grappler=brom.id)
    assert_refused_cleanly(game, C.stand_up, game, gob)
    assert gob.has("prone")


# ---------------- #4 · Your attack rolls have Disadvantage ----------------
@pytest.mark.srd(PR, clause=f"{PR}#4", kind="positive")
def test_prone_attacker_melee_has_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(brom)
    r = melee_mode(game, brom, gob)
    assert r.mode == "disadvantage"
    assert any("Prone" in s for s in r.dis)


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="positive")
def test_prone_attacker_ranged_has_disadvantage(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    knock_prone(lidda)
    game.dice.force_str("d20=[2,2]")
    r = C.attack(game, lidda, gob, weapon="shortbow").roll
    assert r.mode == "disadvantage"
    assert any("Prone" in s for s in r.dis)


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="positive")
def test_prone_caster_spell_attack_has_disadvantage(game):
    m = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    knock_prone(m)
    game.dice.force_str("d20=[2,2]")
    S.cast(game, m, "fire bolt", gob)
    atk = game.log.last("attack")
    assert "isadvantage" in atk.text, atk.text


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="positive")
def test_prone_attack_command_has_disadvantage(game):
    s = Session(game)
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[2,2]")
    out = s.execute({"cmd": "attack", "actor": brom.id, "target": gob.id, "weapon": "longsword"})
    assert out["ok"], out
    assert "isadvantage" in game.log.last("attack").text


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="negative")
def test_standing_attacker_has_no_prone_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(brom)
    C.stand_up(game, brom)
    r = melee_mode(game, brom, gob, d20="d20=[2]")
    assert r.mode == "normal"
    assert not any("Prone" in s for s in r.dis)


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="negative")
def test_prone_doesnt_affect_saving_throws(game):
    gob = mon(game, "goblin warrior", (0, 0))
    knock_prone(gob)
    game.dice.force_str("d20=[10]")
    assert gob.save("dex", 10).mode == "normal"


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="positive")
def test_prone_attacker_against_prone_target_cancels(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(brom)
    knock_prone(gob)
    r = melee_mode(game, brom, gob, d20="d20=[2]")
    assert r.mode == "normal"
    assert any("Prone" in s for s in r.dis) and any("Prone" in s for s in r.adv)


@pytest.mark.srd(PR, clause=f"{PR}#4", kind="positive")
def test_prone_attacker_disadvantage_cancels_restrained_target_advantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("restrained")
    knock_prone(brom)
    r = melee_mode(game, brom, gob, d20="d20=[2]")
    assert r.mode == "normal"


# ---------------- #5 · Advantage from within 5 feet ----------------
@pytest.mark.srd(PR, clause=f"{PR}#5", kind="positive")
def test_adjacent_attack_on_prone_target_has_advantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(gob)
    r = melee_mode(game, brom, gob)
    assert r.mode == "advantage"
    assert any("Prone" in s for s in r.adv)


@pytest.mark.srd(PR, clause=f"{PR}#5", kind="boundary")
def test_diagonal_adjacent_attack_on_prone_target_has_advantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 5))
    knock_prone(gob)
    assert brom.distance_to(gob) == 5
    assert melee_mode(game, brom, gob).mode == "advantage"


@pytest.mark.srd(PR, clause=f"{PR}#5", kind="positive")
def test_monster_attack_on_adjacent_prone_pc_has_advantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(brom)
    game.dice.force_str("d20=[2,2]")
    r = C.attack(game, gob, brom, attack_name="scimitar").roll
    assert r.mode == "advantage"


@pytest.mark.srd(PR, clause=f"{PR}#5", kind="positive")
def test_ranged_attack_from_within_5_ft_on_prone_target_cancels(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    knock_prone(gob)
    game.dice.force_str("d20=[2]")
    r = C.attack(game, lidda, gob, weapon="shortbow").roll
    assert any("Prone" in s for s in r.adv)
    assert r.mode == "normal"  # Prone's Advantage cancels the ranged-in-melee Disadvantage


# ---------------- #6 · Otherwise Disadvantage ----------------
@pytest.mark.srd(PR, clause=f"{PR}#6", kind="positive")
def test_ranged_attack_on_distant_prone_target_has_disadvantage(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    knock_prone(gob)
    game.dice.force_str("d20=[2,2]")
    r = C.attack(game, lidda, gob, weapon="shortbow").roll
    assert r.mode == "disadvantage"
    assert any("Prone" in s for s in r.dis)


@pytest.mark.srd(PR, clause=f"{PR}#6", kind="boundary")
def test_reach_attack_from_10_ft_on_prone_target_has_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    brom.shield = None
    gob = mon(game, "goblin warrior", (10, 0))
    knock_prone(gob)
    r = melee_mode(game, brom, gob, weapon="glaive")
    assert r.mode == "disadvantage"
    assert any("Prone" in s for s in r.dis)
    assert not any("Prone" in s for s in r.adv)


@pytest.mark.srd(PR, clause=f"{PR}#6", kind="positive")
def test_distant_prone_restrained_target_cancels(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    gob.add_condition("restrained")
    knock_prone(gob)
    game.dice.force_str("d20=[2]")
    r = C.attack(game, lidda, gob, weapon="shortbow").roll
    assert any("Prone" in s for s in r.dis)
    assert r.mode == "normal"


@pytest.mark.srd(PR, clause=f"{PR}#6", kind="positive")
def test_spell_attack_on_distant_prone_target_has_disadvantage(game):
    m = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    knock_prone(gob)
    game.dice.force_str("d20=[2,2]")
    S.cast(game, m, "fire bolt", gob)
    assert "isadvantage" in game.log.last("attack").text


# ================ GLOSS.cone ================
CO = "GLOSS.cone"


def burn(game, spots, hits, point=None, named=(0,), slot=None, dice="d6=[2,2,2]", level=None):
    """MIALEE at (0, 0) casts Burning Hands (a 15-foot Cone) with goblins (30 HP) at `spots`,
    aimed at `point` or else the first goblin named (`named` indexes into `spots`). Every creature
    in the Cone fails its Dexterity save, so exactly `hits` d20s are forced."""
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    if level is not None:
        m.level = level
    gobs = []
    for i, p in enumerate(spots):
        g = mon(game, "goblin warrior", p, name=f"G{i}")
        g.hp = 30
        gobs.append(g)
    game.dice.force_str(dice + "".join("; d20=[1]" for _ in range(hits)))
    S.cast(game, m, "burning hands", [gobs[i] for i in named], point=point, slot=slot)
    return m, gobs


def hit(gobs):
    return [g.hp < 30 for g in gobs]


# ---------------- #1 · straight lines from a point of origin in a chosen direction ----------------
@pytest.mark.srd(CO, clause=f"{CO}#1", kind="positive")
def test_a_cone_goes_in_the_direction_its_creator_chooses(game):
    _, gobs = burn(game, [(10, 0), (0, 10)], hits=1, point=(0, 15))
    assert hit(gobs) == [False, True]


@pytest.mark.srd(CO, clause=f"{CO}#1", kind="positive")
def test_a_cone_can_be_aimed_along_a_diagonal(game):
    _, gobs = burn(game, [(10, 10), (10, 0)], hits=1, point=(15, 15))
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CO, clause=f"{CO}#1", kind="positive")
def test_a_cone_aimed_through_the_session_follows_the_chosen_point(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    east = mon(game, "goblin warrior", (5, 0), name="EAST")
    west = mon(game, "goblin warrior", (-5, 0), name="WEST")
    east.hp = west.hp = 30
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    out = Session(game).execute(
        {"cmd": "cast", "spell": "burning hands", "actor": m.id, "targets": [east.id], "point": [-15, 0]}
    )
    assert out.get("ok") is not False, out
    assert west.hp == 24 and east.hp == 30


@pytest.mark.srd(CO, clause=f"{CO}#1", kind="negative")
def test_a_cone_doesnt_reach_behind_its_point_of_origin(game):
    _, gobs = burn(game, [(5, 0), (-5, 0), (-10, 5)], hits=1)
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CO, clause=f"{CO}#1", kind="abuse", ruling="R-26")
def test_one_cone_cant_be_spread_to_both_flanks_by_naming_them(game):
    # A quarter-circle aimed between them would take both; the Cone aimed at the first can't.
    _, gobs = burn(game, [(10, 10), (10, -10)], hits=1, named=(0, 1))
    assert hit(gobs) == [True, False]


# ---------------- #2 · width at any point equals its distance from the origin ----------------
@pytest.mark.srd(CO, clause=f"{CO}#2", kind="positive")
def test_a_cone_is_10_ft_wide_10_ft_out(game):
    _, gobs = burn(game, [(10, 0), (10, 5), (10, -5)], hits=3)
    assert hit(gobs) == [True, True, True]


@pytest.mark.srd(CO, clause=f"{CO}#2", kind="negative", ruling="R-26")
def test_width_is_measured_across_the_cone_not_from_its_axis_to_each_side(game):
    # Measured from the axis out to each side, 10 ft out would reach 10 ft off the axis.
    _, gobs = burn(game, [(10, 0), (10, 10), (10, -10)], hits=1)
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CO, clause=f"{CO}#2", kind="boundary", ruling="R-27")
def test_a_cone_is_only_5_ft_wide_5_ft_out(game):
    # 5 ft out the Cone is 5 ft wide: the square straight ahead, not the diagonal ones beside it.
    _, gobs = burn(game, [(5, 0), (5, 5), (5, -5)], hits=1)
    assert hit(gobs) == [True, False, False]


# ---------------- #3 · 15 feet wide at 15 feet ----------------
@pytest.mark.srd(CO, clause=f"{CO}#3", kind="positive")
def test_a_cone_is_15_ft_wide_15_ft_from_its_origin(game):
    _, gobs = burn(game, [(15, -5), (15, 0), (15, 5)], hits=3, point=(15, 0))
    assert hit(gobs) == [True, True, True]


@pytest.mark.srd(CO, clause=f"{CO}#3", kind="negative")
def test_a_cone_isnt_30_ft_wide_15_ft_from_its_origin(game):
    _, gobs = burn(game, [(15, 0), (15, 15), (15, -15)], hits=1)
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CO, clause=f"{CO}#3", kind="boundary", ruling="R-27")
def test_the_squares_just_past_the_15_ft_width_arent_in_the_cone(game):
    # Three 5-ft squares make the 15-ft width; the squares either side of them are outside.
    _, gobs = burn(game, [(15, 5), (15, 10), (15, -10)], hits=1, point=(15, 0))
    assert hit(gobs) == [True, False, False]


# ---------------- #4 · the effect specifies the maximum length ----------------
@pytest.mark.srd(CO, clause=f"{CO}#4", kind="positive")
def test_a_15_ft_cone_reaches_15_ft(game):
    _, gobs = burn(game, [(15, 0), (5, 0)], hits=2)
    assert hit(gobs) == [True, True]


@pytest.mark.srd(CO, clause=f"{CO}#4", kind="boundary")
def test_a_15_ft_cone_stops_short_of_20_ft(game):
    _, gobs = burn(game, [(15, 0), (20, 0)], hits=1)
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CO, clause=f"{CO}#4", kind="boundary")
def test_a_15_ft_cone_along_a_diagonal_stops_at_15_ft(game):
    # Diagonal squares count 5 ft each, so (15, 15) is 15 ft away and (20, 20) is 20 ft.
    _, gobs = burn(game, [(15, 15), (20, 20)], hits=1, point=(20, 20))
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CO, clause=f"{CO}#4", kind="negative")
def test_upcasting_doesnt_lengthen_the_cone(game):
    _, gobs = burn(game, [(15, 0), (20, 0)], hits=1, slot=2, dice="d6=[2,2,2,2]", level=3)
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CO, clause=f"{CO}#4", kind="abuse")
def test_aiming_at_a_far_point_doesnt_stretch_the_cone(game):
    _, gobs = burn(game, [(10, 0), (25, 0)], hits=1, point=(60, 0))
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CO, clause=f"{CO}#4", kind="positive", ruling="R-28")
def test_aiming_at_a_near_point_still_gives_the_full_length(game):
    _, gobs = burn(game, [(5, 0), (15, 0)], hits=2, point=(5, 0))
    assert hit(gobs) == [True, True]


# ---------------- #5 · the point of origin isn't included ----------------
@pytest.mark.srd(CO, clause=f"{CO}#5", kind="positive", ruling="R-29")
def test_the_caster_at_the_cones_origin_isnt_affected(game):
    m, gobs = burn(game, [(5, 0)], hits=1)
    assert hit(gobs) == [True]
    assert m.hp == m.max_hp
    assert len(game.log.of_kind("save")) == 1


@pytest.mark.srd(CO, clause=f"{CO}#5", kind="abuse", ruling="R-29")
def test_naming_yourself_doesnt_aim_the_cone_or_put_you_in_it(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    gob = mon(game, "goblin warrior", (5, 0), name="GOB")
    gob.hp = 30
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [m, gob])
    assert gob.hp == 24
    assert m.hp == m.max_hp
    assert len(game.log.of_kind("save")) == 1


# ================ GLOSS.cube ================
CU = "GLOSS.cube"


def wave(game, spots, hits, point=None, named=(0,), slot=None, dice="d8=[2,2]", level=None, elev=None):
    """MIALEE at (0, 0) casts Thunderwave (a 15-foot Cube originating from her) with goblins
    (30 HP) at `spots`, aimed at `point` or else the first goblin named (`named` indexes into
    `spots`). Every creature in the Cube fails its Constitution save, so exactly `hits` d20s are
    forced; `hits=None` forces none (the saves roll freely, and any creature in the Cube still
    takes at least half damage). `elev` gives the goblins' elevations."""
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("thunderwave")
    if level is not None:
        m.level = level
    gobs = []
    for i, p in enumerate(spots):
        g = mon(game, "goblin warrior", p, name=f"G{i}")
        g.hp = 30
        if elev is not None:
            g.elevation = elev[i]
        gobs.append(g)
    game.dice.force_str(dice + "".join("; d20=[1]" for _ in range(hits or 0)))
    S.cast(game, m, "thunderwave", [gobs[i] for i in named], point=point, slot=slot)
    return m, gobs


# ---------------- #1 · extends in straight lines from a point of origin on a face ----------------
@pytest.mark.srd(CU, clause=f"{CU}#1", kind="positive")
def test_a_cube_extends_from_its_origin_in_the_chosen_direction(game):
    _, gobs = wave(game, [(5, 0), (0, 10)], hits=1, point=(0, 15))
    assert hit(gobs) == [False, True]


@pytest.mark.srd(CU, clause=f"{CU}#1", kind="positive")
def test_a_cube_aimed_through_the_session_follows_the_chosen_point(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("thunderwave")
    east = mon(game, "goblin warrior", (5, 0), name="EAST")
    west = mon(game, "goblin warrior", (-5, 0), name="WEST")
    east.hp = west.hp = 30
    game.dice.force_str("d8=[2,2]; d20=[1]")
    out = Session(game).execute(
        {"cmd": "cast", "spell": "thunderwave", "actor": m.id, "targets": [east.id], "point": [-15, 0]}
    )
    assert out.get("ok") is not False, out
    assert west.hp == 26 and east.hp == 30


@pytest.mark.srd(CU, clause=f"{CU}#1", kind="negative")
def test_a_cube_doesnt_reach_behind_the_face_its_origin_is_on(game):
    _, gobs = wave(game, [(5, 0), (-5, 0), (-10, 5)], hits=1)
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CU, clause=f"{CU}#1", kind="boundary", ruling="R-30")
def test_a_creature_beside_the_caster_is_level_with_the_face_and_outside_the_cube(game):
    # Aimed east, the Cube starts at the caster's face: the squares north and south of her aren't in it.
    _, gobs = wave(game, [(5, 0), (0, 5), (0, -5)], hits=1)
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CU, clause=f"{CU}#1", kind="abuse")
def test_one_cube_cant_cover_both_sides_of_its_origin_by_naming_them(game):
    _, gobs = wave(game, [(5, 0), (-5, 0)], hits=1, named=(0, 1))
    assert hit(gobs) == [True, False]
    assert len(game.log.of_kind("save")) == 1


@pytest.mark.srd(CU, clause=f"{CU}#1", kind="abuse")
def test_leaving_a_creature_in_the_cube_off_the_list_doesnt_spare_it(game):
    _, gobs = wave(game, [(5, 0), (10, 5)], hits=2, named=(0,))
    assert hit(gobs) == [True, True]


# ---------------- #2 · the effect gives the size: the length of each side ----------------
@pytest.mark.srd(CU, clause=f"{CU}#2", kind="positive", ruling="R-30")
def test_a_15_ft_cube_is_15_ft_deep_and_15_ft_across(game):
    spots = [(5, -5), (5, 0), (5, 5), (10, -5), (10, 0), (10, 5), (15, -5), (15, 0), (15, 5)]
    _, gobs = wave(game, spots, hits=9, named=(4,))
    assert hit(gobs) == [True] * 9


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="boundary")
def test_a_15_ft_cube_stops_short_of_20_ft(game):
    _, gobs = wave(game, [(15, 0), (20, 0)], hits=1)
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="boundary", ruling="R-30")
def test_the_squares_just_past_the_15_ft_width_arent_in_the_cube(game):
    # Three 5-ft squares make the 15-ft side; the squares either side of them are outside.
    _, gobs = wave(game, [(10, 5), (10, 10), (10, -10)], hits=1, point=(15, 0))
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="positive")
def test_a_cube_reaches_a_creature_above_the_ground_inside_its_height(game):
    _, gobs = wave(game, [(5, 0), (10, 0)], hits=2, elev=[0, 5])
    assert hit(gobs) == [True, True]


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="boundary")
def test_a_15_ft_cube_doesnt_reach_a_flyer_20_ft_up(game):
    _, gobs = wave(game, [(5, 0), (10, 0)], hits=1, elev=[0, 20])
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="abuse")
def test_upcasting_doesnt_enlarge_the_cube(game):
    _, gobs = wave(game, [(15, 0), (20, 0), (10, 10)], hits=1, slot=2, dice="d8=[2,2,2]", level=3)
    assert hit(gobs) == [True, False, False]


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="abuse")
def test_aiming_at_a_far_point_doesnt_stretch_the_cube(game):
    _, gobs = wave(game, [(10, 0), (25, 0)], hits=1, point=(60, 0))
    assert hit(gobs) == [True, False]


@pytest.mark.srd(CU, clause=f"{CU}#2", kind="abuse")
def test_naming_a_creature_far_outside_a_20_ft_web_cube_doesnt_catch_it(game):
    m = pc(game, "MIALEE", (0, 0))
    m.level = 3
    m.prepared.append("web")
    far = mon(game, "goblin warrior", (30, 100), name="FAR")
    S.cast(game, m, "web", [far], point=(30, 0), slot=2)
    assert not far.has("restrained")
    assert all("FAR" not in s.text for s in game.log.of_kind("save"))


# ---------------- #3 · the point of origin isn't included ----------------
@pytest.mark.srd(CU, clause=f"{CU}#3", kind="positive", ruling="R-31")
def test_the_caster_at_the_cubes_origin_isnt_affected(game):
    m, gobs = wave(game, [(5, 0)], hits=1)
    assert hit(gobs) == [True]
    assert m.hp == m.max_hp and tuple(m.position) == (0, 0)
    assert len(game.log.of_kind("save")) == 1


@pytest.mark.srd(CU, clause=f"{CU}#3", kind="abuse", ruling="R-31")
def test_naming_yourself_doesnt_aim_the_cube_or_put_you_in_it(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("thunderwave")
    gob = mon(game, "goblin warrior", (5, 0), name="GOB")
    gob.hp = 30
    game.dice.force_str("d8=[2,2]; d20=[1]")
    S.cast(game, m, "thunderwave", [m, gob])
    assert gob.hp == 26
    assert m.hp == m.max_hp
    assert len(game.log.of_kind("save")) == 1


# ================ GLOSS.sphere ================
SP = "GLOSS.sphere"


def sleeper(game):
    """MIALEE at (0, 0) with Sleep prepared."""
    m = pc(game, "MIALEE", (0, 0))
    if "sleep" not in m.prepared:
        m.prepared.append("sleep")
    return m


def lull(game, spots, fails, point=(30, 0), named=None, elev=None, slot=None, level=None):
    """MIALEE at (0, 0) casts Sleep (a 5-foot-radius Sphere, 'each creature of your choice') at
    `point` (None: centred on the first creature named) with goblins at `spots`, all of them named
    unless `named` indexes a subset. Every creature in the Sphere fails its Wisdom save, so exactly
    `fails` d20s are forced. `elev` gives the goblins' elevations."""
    m = sleeper(game)
    if level is not None:
        m.level = level
    gobs = []
    for i, p in enumerate(spots):
        g = mon(game, "goblin warrior", p, name=f"G{i}")
        if elev is not None:
            g.elevation = elev[i]
        gobs.append(g)
    if fails:
        game.dice.force_str("; ".join("d20=[1]" for _ in range(fails)))
    chosen = gobs if named is None else [gobs[i] for i in named]
    S.cast(game, m, "sleep", chosen, point=point, slot=slot)
    return m, gobs


def asleep(gobs):
    return [g.has("incapacitated") for g in gobs]


def save_texts(game):
    return [e.text for e in game.log.of_kind("save")]


# ---------------- #1 · straight lines from a point of origin outward in all directions ----------------
@pytest.mark.srd(SP, clause=f"{SP}#1", kind="positive", ruling="R-32")
def test_a_sphere_extends_from_its_origin_in_every_direction(game):
    _, gobs = lull(game, [(35, 0), (25, 0), (30, 5), (30, -5)], fails=4)
    assert asleep(gobs) == [True, True, True, True]
    assert len(save_texts(game)) == 4


@pytest.mark.srd(SP, clause=f"{SP}#1", kind="positive", ruling="R-32")
def test_a_sphere_extends_upward_from_its_origin_too(game):
    _, gobs = lull(game, [(30, 0)], fails=1, elev=[5])
    assert asleep(gobs) == [True]


@pytest.mark.srd(SP, clause=f"{SP}#1", kind="positive")
def test_a_sphere_placed_through_the_session_is_centred_on_the_chosen_point(game):
    m = sleeper(game)
    near = mon(game, "goblin warrior", (25, 0), name="NEAR")
    far = mon(game, "goblin warrior", (45, 0), name="FAR")
    game.dice.force_str("d20=[1]")
    out = Session(game).execute(
        {"cmd": "cast", "spell": "sleep", "actor": m.id, "targets": [near.id, far.id], "point": [30, 0]}
    )
    assert out.get("ok") is not False, out
    assert near.has("incapacitated") and not far.has("incapacitated")
    assert len(save_texts(game)) == 1


@pytest.mark.srd(SP, clause=f"{SP}#1", kind="negative")
def test_a_sphere_doesnt_reach_past_its_radius_in_any_direction(game):
    _, gobs = lull(game, [(40, 0), (20, 0), (30, 10), (30, -10)], fails=0)
    assert asleep(gobs) == [False, False, False, False]
    assert save_texts(game) == []


@pytest.mark.srd(SP, clause=f"{SP}#1", kind="negative", ruling="R-10")
def test_a_sphere_doesnt_reach_a_creature_behind_total_cover_from_its_origin(game):
    # The Sphere extends in straight lines from its origin: Total Cover from that point blocks them.
    m = sleeper(game)
    open_ = mon(game, "goblin warrior", (25, 0), name="OPEN")
    walled = mon(game, "goblin warrior", (35, 0), name="WALLED")
    game.scene.cover[((30, 0), walled.id)] = "total"
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "sleep", [open_, walled], point=(30, 0))
    assert open_.has("incapacitated") and not walled.has("incapacitated")
    assert len(save_texts(game)) == 1


# ---------------- #2 · the effect specifies the radius ----------------


@pytest.mark.srd(SP, clause=f"{SP}#2", kind="negative")
def test_the_radius_isnt_the_spheres_width(game):
    # Read as a 5-ft width, the Sphere would hold only the origin's square; it reaches 5 ft each way.
    _, gobs = lull(game, [(25, 0), (30, 0), (35, 0)], fails=3)
    assert asleep(gobs) == [True, True, True]


@pytest.mark.srd(SP, clause=f"{SP}#2", kind="boundary")
def test_a_5_ft_sphere_stops_short_of_10_ft(game):
    _, gobs = lull(game, [(35, 0), (40, 0)], fails=1)
    assert asleep(gobs) == [True, False]
    assert len(save_texts(game)) == 1


@pytest.mark.srd(SP, clause=f"{SP}#2", kind="boundary", ruling="R-32")
def test_a_5_ft_sphere_along_a_diagonal_takes_the_next_square_but_not_the_one_after(game):
    # Diagonal squares count 5 ft each, as for range and movement: (35, 5) is 5 ft away, (40, 10) 10 ft.
    _, gobs = lull(game, [(35, 5), (40, 10)], fails=1)
    assert asleep(gobs) == [True, False]


@pytest.mark.srd(SP, clause=f"{SP}#2", kind="abuse")
def test_a_higher_slot_doesnt_enlarge_the_sphere(game):
    _, gobs = lull(game, [(35, 0), (40, 0)], fails=1, slot=2, level=3)
    assert asleep(gobs) == [True, False]
    assert len(save_texts(game)) == 1


# ---------------- #3 · the point of origin is included ----------------
@pytest.mark.srd(SP, clause=f"{SP}#3", kind="positive")
def test_a_creature_on_the_point_of_origin_is_in_the_sphere(game):
    _, gobs = lull(game, [(30, 0), (35, 0)], fails=2)
    assert asleep(gobs) == [True, True]


@pytest.mark.srd(SP, clause=f"{SP}#3", kind="positive")
def test_a_sphere_centred_on_a_named_creature_includes_that_creature(game):
    _, gobs = lull(game, [(30, 0), (35, 5), (40, 0)], fails=2, point=None)
    assert asleep(gobs) == [True, True, False]


@pytest.mark.srd(SP, clause=f"{SP}#3", kind="positive", ruling="R-33")
def test_a_caster_who_centres_a_sphere_on_themself_is_in_it(game):
    # Unlike a Cone or Cube, a Sphere includes its origin, even when the caster stands on it.
    # MIALEE is an elf (Trance), so being in the Sphere shows as her automatic success.
    m = sleeper(game)
    gob = mon(game, "goblin warrior", (5, 0), name="GOB")
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "sleep", [m, gob], point=(0, 0))
    texts = save_texts(game)
    assert len(texts) == 2
    assert any("MIALEE automatically succeeds" in t for t in texts)
    assert gob.has("incapacitated")


@pytest.mark.srd(SP, clause=f"{SP}#3", kind="negative")
def test_the_caster_isnt_in_a_sphere_placed_away_from_them(game):
    # The origin is the chosen point, not the creator: a Sphere isn't an Emanation from the caster.
    m = sleeper(game)
    gob = mon(game, "goblin warrior", (30, 0), name="GOB")
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "sleep", [m, gob], point=(30, 0))
    assert gob.has("incapacitated") and not m.has("incapacitated")
    assert len(save_texts(game)) == 1 and "MIALEE" not in save_texts(game)[0]


# ================ GLOSS.area-of-effect ================
AOE = "GLOSS.area-of-effect"


def aoe_exclusions(game):
    """The log events that drop a creature from an area because it is cut off from the origin."""
    return [e for e in game.log.events if "point of origin" in e.text and "isn't affected" in e.text]


# ---------------- #1 · an area has a point of origin, where its energy erupts ----------------


@pytest.mark.srd(AOE, clause=f"{AOE}#1", kind="negative")
def test_total_cover_from_some_other_point_doesnt_cut_a_creature_off(game):
    # Cover from (40, 0) isn't cover from the origin at (30, 0): G0 is still in the Sphere.
    m = sleeper(game)
    g = mon(game, "goblin warrior", (35, 0), name="G0")
    game.scene.cover[((40, 0), g.id)] = "total"
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "sleep", [g], point=(30, 0))
    assert g.has("incapacitated")
    assert len(save_texts(game)) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#1", kind="abuse")
def test_cover_from_the_caster_doesnt_shield_a_creature_from_a_sphere_placed_elsewhere(game):
    # The energy erupts at the chosen point, not at the caster: a wall between caster and goblin
    # doesn't stand between the goblin and the Sphere's origin.
    m = sleeper(game)
    g = mon(game, "goblin warrior", (35, 0), name="G0")
    game.scene.cover[(m.id, g.id)] = "total"
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "sleep", [g], point=(30, 0))
    assert g.has("incapacitated")
    assert len(save_texts(game)) == 1


# ---------------- #2 · each shape's rules position its point of origin ----------------
@pytest.mark.srd(AOE, clause=f"{AOE}#2", kind="positive", ruling="R-10")
def test_a_cone_from_the_caster_is_cut_off_by_total_cover_from_the_caster(game):
    # Burning Hands' Cone originates at the caster, so cover from her is cover from the origin.
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g0 = mon(game, "goblin warrior", (5, 0), name="G0")
    g1 = mon(game, "goblin warrior", (10, 5), name="G1")
    g0.hp = g1.hp = 30
    game.scene.cover[(m.id, g1.id)] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g0, g1])
    assert hit([g0, g1]) == [True, False]
    assert len(game.log.of_kind("save")) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#2", kind="positive", ruling="R-10")
def test_a_cube_from_the_caster_is_cut_off_by_total_cover_from_the_caster(game):
    # Thunderwave's Cube has its origin on the caster's face: a creature walled off from her
    # neither saves, takes damage, nor is pushed.
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("thunderwave")
    g0 = mon(game, "goblin warrior", (5, 0), name="G0")
    g1 = mon(game, "goblin warrior", (10, 5), name="G1")
    g0.hp = g1.hp = 30
    game.scene.cover[(m.id, g1.id)] = "total"
    game.dice.force_str("d8=[2,2]; d20=[1]")
    S.cast(game, m, "thunderwave", [g0, g1])
    assert hit([g0, g1]) == [True, False]
    assert tuple(g1.position) == (10, 5)
    assert len(game.log.of_kind("save")) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#2", kind="negative")
def test_a_cone_doesnt_originate_at_the_point_it_is_aimed_at(game):
    # The point (15, 0) only sets the Cone's direction; Total Cover from it doesn't matter.
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g = mon(game, "goblin warrior", (10, 0), name="G0")
    g.hp = 30
    game.scene.cover[((15, 0), g.id)] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g], point=(15, 0))
    assert g.hp == 24
    assert len(game.log.of_kind("save")) == 1


# ---------------- #3 · a location cut off by blocked lines isn't in the area ----------------
@pytest.mark.srd(AOE, clause=f"{AOE}#3", kind="positive", ruling="R-10")
def test_a_creature_cut_off_from_the_origin_rolls_no_save_and_takes_nothing(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g0 = mon(game, "goblin warrior", (5, 0), name="G0")
    g1 = mon(game, "goblin warrior", (10, -5), name="G1")
    g0.hp = g1.hp = 30
    game.scene.cover_all[g1.id] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g0, g1])
    assert hit([g0, g1]) == [True, False]
    texts = save_texts(game)
    assert len(texts) == 1 and "G1" not in texts[0]
    (e,) = aoe_exclusions(game)
    assert "G1" in e.text and str(e.page) == "177"


@pytest.mark.srd(AOE, clause=f"{AOE}#3", kind="positive")
def test_the_exclusion_is_logged_against_the_blocked_lines_clause(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g0 = mon(game, "goblin warrior", (5, 0), name="G0")
    g1 = mon(game, "goblin warrior", (10, 0), name="G1")
    g0.hp = g1.hp = 30
    game.scene.cover[(m.id, g1.id)] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g0, g1])
    assert hit([g0, g1]) == [True, False]
    (e,) = aoe_exclusions(game)
    assert e.rule == f"{AOE}#3" and str(e.page) == "177"


@pytest.mark.srd(AOE, clause=f"{AOE}#3", kind="positive", ruling="R-10")
def test_a_sphere_placed_through_the_session_leaves_out_a_creature_cut_off_from_its_origin(game):
    m = sleeper(game)
    open_ = mon(game, "goblin warrior", (30, 0), name="OPEN")
    walled = mon(game, "goblin warrior", (30, 5), name="WALLED")
    game.scene.cover[((30, 0), walled.id)] = "total"
    game.dice.force_str("d20=[1]")
    out = Session(game).execute(
        {"cmd": "cast", "spell": "sleep", "actor": m.id, "targets": [open_.id, walled.id], "point": [30, 0]}
    )
    assert out.get("ok") is not False, out
    assert open_.has("incapacitated") and not walled.has("incapacitated")
    assert len(save_texts(game)) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#3", kind="positive")
@pytest.mark.xfail(
    strict=True,
    reason="T-83: Burning Hands sets fire to a flammable object inside its Cone even when the "
    "object is behind Total Cover; scene objects are placed in the area by geometry alone and "
    "the blocked-lines check is made only for creatures",
)
def test_an_object_cut_off_from_the_origin_isnt_in_the_area(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g = mon(game, "goblin warrior", (5, 0), name="G0")
    g.hp = 30
    game.scene.objects["open hay"] = {"flammable": True, "position": (10, 5)}
    game.scene.objects["walled hay"] = {"flammable": True, "position": (10, 0)}
    game.scene.cover_all["walled hay"] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g])
    assert game.scene.objects["open hay"].get("burning")
    assert not game.scene.objects["walled hay"].get("burning")


@pytest.mark.srd(AOE, clause=f"{AOE}#3", kind="negative")
def test_a_creature_in_the_area_with_no_cover_is_affected(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g = mon(game, "goblin warrior", (10, 5), name="G0")
    g.hp = 30
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g])
    assert g.hp == 24
    assert aoe_exclusions(game) == []


@pytest.mark.srd(AOE, clause=f"{AOE}#3", kind="abuse", ruling="R-10")
def test_naming_a_creature_cut_off_from_the_origin_doesnt_put_it_in_the_area(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g0 = mon(game, "goblin warrior", (5, 0), name="G0")
    g1 = mon(game, "goblin warrior", (10, 5), name="G1")
    g0.hp = g1.hp = 30
    game.scene.cover[(m.id, g1.id)] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [g1, g0], point=(15, 0))
    assert hit([g0, g1]) == [True, False]
    assert len(game.log.of_kind("save")) == 1


# ---------------- #4 · only an obstruction giving Total Cover blocks a line ----------------
@pytest.mark.srd(AOE, clause=f"{AOE}#4", kind="positive", ruling="R-10")
def test_an_obstruction_giving_total_cover_blocks_the_area(game):
    m = sleeper(game)
    g = mon(game, "goblin warrior", (35, 5), name="G0")
    game.scene.cover_all[g.id] = "total"
    S.cast(game, m, "sleep", [g], point=(30, 0))
    assert not g.has("incapacitated")
    assert save_texts(game) == []
    assert m.slots_left(1) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#4", kind="negative", ruling="R-34")
def test_half_cover_from_the_origin_doesnt_block_the_area(game):
    m = sleeper(game)
    g = mon(game, "goblin warrior", (35, 0), name="G0")
    game.scene.cover[((30, 0), g.id)] = "half"
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "sleep", [g], point=(30, 0))
    assert g.has("incapacitated")
    assert len(save_texts(game)) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#4", kind="boundary", ruling="R-34")
def test_three_quarters_cover_just_short_of_total_doesnt_block_but_total_does(game):
    # An arrow slit's Three-Quarters Cover leaves lines through it: the creature is still in the Cone.
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    slit = mon(game, "goblin warrior", (10, 0), name="SLIT")
    wall = mon(game, "goblin warrior", (10, 5), name="WALL")
    slit.hp = wall.hp = 30
    game.scene.cover[(m.id, slit.id)] = "three-quarters"
    game.scene.cover[(m.id, wall.id)] = "total"
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [slit, wall], point=(15, 0))
    assert hit([slit, wall]) == [True, False]
    assert len(game.log.of_kind("save")) == 1


@pytest.mark.srd(AOE, clause=f"{AOE}#4", kind="negative", ruling="R-09")
def test_a_creature_in_the_line_doesnt_block_the_area(game):
    # A creature gives at most Half Cover, so G0 in front of G1 leaves G1 in the Cube.
    _, gobs = wave(game, [(5, 0), (10, 0)], hits=2)
    assert hit(gobs) == [True, True]
    assert len(game.log.of_kind("save")) == 2


@pytest.mark.srd(AOE, clause=f"{AOE}#4", kind="abuse", ruling="R-09")
def test_a_column_of_creatures_cant_be_used_as_a_wall_against_the_area(game):
    _, gobs = burn(game, [(5, 0), (10, 0), (15, 0)], hits=3)
    assert hit(gobs) == [True, True, True]
    assert aoe_exclusions(game) == []
