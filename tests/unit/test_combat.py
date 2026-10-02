"""Unit tests for dungdra.combat: moving while dragging a creature."""

import pytest

from dungdra.combat import attack, escape_grapple, move, release_grapple
from dungdra.effects import Condition, Flag, SpeedPenalty, grapplers_of
from dungdra.events import GM
from dungdra.rules import Refusal
from tests.support.helpers import mon, pc
from tests.unit.helpers import grappled_by


def test_drag_refused_when_target_isnt_grappled(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    with pytest.raises(Refusal) as exc:
        move(game, brom, to=(-10, 0), drag=gob)
    assert exc.value.page == 182
    assert brom.position == (0, 0)
    assert gob.position == (5, 0)


def test_drag_refused_when_someone_else_is_the_grappler(game):
    brom = pc(game, "BROM", (0, 0))
    lidda = pc(game, "LIDDA", (5, 5))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    with pytest.raises(Refusal):
        move(game, lidda, to=(15, 5), drag=gob)
    assert lidda.position == (5, 5)
    assert gob.position == (5, 0)


def test_grappler_drags_its_grappled_target_along(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(-10, 0), drag=gob)
    assert brom.position == (-10, 0)
    assert gob.position == (-5, 0)


def test_grappler_carries_its_target_while_flying_at_extra_cost(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["fly"] = 30
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    cost = move(game, brom, to=(-10, 0), mode="fly", drag=gob)
    assert cost == 20
    assert gob.position == (-5, 0)


def test_flying_refused_without_a_fly_speed(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    with pytest.raises(Refusal) as exc:
        move(game, brom, to=(-10, 0), mode="fly", drag=gob)
    assert exc.value.page == 182
    assert brom.position == (0, 0)
    assert gob.position == (5, 0)


def test_grappler_carries_its_target_while_climbing_with_a_climb_speed(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["climb"] = 30
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    cost = move(game, brom, to=(-10, 0), mode="climb", drag=gob)
    assert cost == 20
    assert gob.position == (-5, 0)


def test_dragging_logs_the_movable_clause(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(-10, 0), drag=gob)
    [ev] = game.log.applied("GLOSS.grappled#4")
    assert ev.kind == "move" and ev.ruling is None


def test_a_tiny_grappler_dragging_a_tiny_creature_logs_ruling_r05(game):
    gob = mon(game, "goblin warrior", (0, 0))
    gob.size = "tiny"
    rat = mon(game, "giant rat", (5, 0))
    rat.size = "tiny"
    grappled_by(rat, gob)
    assert move(game, gob, to=(-10, 0), drag=rat) == 10
    game.log.assert_applied("GLOSS.grappled#4", ruling="R-05")


def test_dragging_a_creature_two_sizes_smaller_needs_no_ruling(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    rat.size = "tiny"
    grappled_by(rat, brom)
    assert move(game, brom, to=(-10, 0), drag=rat) == 10
    assert game.log.applied("GLOSS.grappled#4") and not game.log.applied(ruling="R-05")


def test_walking_logs_movement_without_a_grapple_rule(game):
    brom = pc(game, "BROM", (0, 0))
    move(game, brom, to=(-10, 0))
    assert game.log.last("move").rule == "PLAY.combat.movement-and-position"
    assert not game.log.applied("GLOSS.grappled")


def test_a_grappled_climber_is_refused_under_ruling_r07(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    grappled_by(rat, brom)
    with pytest.raises(Refusal) as exc:
        move(game, rat, to=(5, 10), mode="climb")
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.grappled#1", "R-07")


def test_a_grappled_walker_is_refused_by_the_rule_alone(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    with pytest.raises(Refusal) as exc:
        move(game, gob, to=(5, 10))
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.grappled#1", None)


def test_speed_zero_without_a_grapple_cites_speed(game):
    gob = mon(game, "goblin warrior", (5, 0))
    gob.speeds["walk"] = 0
    with pytest.raises(Refusal) as exc:
        move(game, gob, to=(5, 10))
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.speed", None)


def test_an_attack_by_a_creature_with_two_grapplers_logs_r06(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grappled_by(brom, gob)
    grappled_by(brom, bandit)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]")
    attack(game, brom, gob, weapon="longsword")
    [ev] = game.log.assert_applied("GLOSS.grappled#2", ruling="R-06")
    assert ev.visibility == GM
    assert game.log.last("attack").rule == "PLAY.combat.making-an-attack"


def test_a_grappler_walking_away_without_dragging_ends_the_grapple(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(-5, 0))
    assert grapplers_of(gob) == set()


def test_a_grappler_staying_within_5_feet_keeps_the_grapple(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(5, 5))
    assert grapplers_of(gob) == {brom.id}


def test_a_grappled_creature_moved_out_of_reach_is_freed_of_that_grappler_only(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (10, 0))
    grappled_by(gob, brom)
    grappled_by(gob, bandit)
    move(game, gob, to=(15, 0), teleport=True)
    assert grapplers_of(gob) == {bandit.id}


def test_release_grapple_ends_the_condition_and_the_grapplers_flag(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    brom.add_effect(Flag("grappling", f"grappling {gob.name}", target=gob.id))
    release_grapple(game, gob)
    assert grapplers_of(gob) == set()
    assert not any(f.name == "grappling" for f in brom.effects)


def test_escape_grapple_refused_when_not_grappled(game):
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("restrained", "net", escape_dc=10)
    with pytest.raises(Refusal):
        escape_grapple(game, gob)
    assert gob.has("restrained")


def test_escape_grapple_checks_against_the_grapples_escape_dc(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("restrained", "net", escape_dc=30)
    gob.add_effect(Condition("grappled", "grappled", grappler=brom.id, escape_dc=15))
    game.dice.force_str("d20=[20]")
    r = escape_grapple(game, gob, skill="acrobatics")
    assert r.target == 15 and r.success
    assert grapplers_of(gob) == set()


def test_climbing_without_a_climb_speed_costs_an_extra_foot(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds.pop("climb", None)
    assert move(game, brom, to=(10, 0), mode="climb") == 20
    assert "climbing" in game.log.last("move").text


def test_swimming_without_a_swim_speed_in_difficult_terrain_costs_two_extra_feet(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds.pop("swim", None)
    assert move(game, brom, to=(10, 0), mode="swim", difficult=True) == 30
    assert "Difficult Terrain" not in game.log.last("move").text


def test_swimming_with_a_swim_speed_costs_no_extra(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["swim"] = 30
    assert move(game, brom, to=(10, 0), mode="swim") == 10
    assert "Swim Speed" in game.log.last("move").text


def test_a_climb_speed_reduced_to_0_falls_back_to_climbing_by_walking(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["climb"] = 10
    brom.add_effect(SpeedPenalty("Ray of Frost", 10))
    assert move(game, brom, to=(10, 0), mode="climb") == 20
    assert "climbing" in game.log.last("move").text


def test_a_grappled_flyer_is_refused_for_speed_0_not_for_lacking_a_fly_speed(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    rat.speeds["fly"] = 30
    grappled_by(rat, brom)
    with pytest.raises(Refusal) as exc:
        move(game, rat, to=(5, 10), mode="fly")
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.grappled#1", "R-07")
    assert rat.position == (5, 0)
