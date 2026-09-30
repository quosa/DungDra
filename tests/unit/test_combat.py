"""Unit tests for dungdra.combat: moving while dragging a creature."""

import pytest

from dungdra.combat import move
from dungdra.effects import Condition
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
