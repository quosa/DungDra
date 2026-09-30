"""Unit tests for dungdra.combat: moving while dragging a creature."""

import pytest

from dungdra.combat import attack, move
from dungdra.effects import Condition
from dungdra.events import GM
from dungdra.rules import Refusal
from tests.support.helpers import mon, pc


def grappled_by(target, grappler):
    target.add_effect(
        Condition("grappled", f"grappled by {grappler.name}", caster=grappler, grappler=grappler.id)
    )


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
