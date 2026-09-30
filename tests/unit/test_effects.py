"""Unit tests for dungdra.effects: conditions' effects on the owner's D20 Tests."""

from dungdra.effects import Condition, Ctx
from tests.support.helpers import mon, pc

GRAPPLED_DIS = "Grappled (attacking someone other than the grappler)"


def grappled_by(target, *grapplers):
    for g in grapplers:
        target.add_effect(Condition("grappled", f"grappled by {g.name}", caster=g, grappler=g.id))


def test_grappled_attack_on_the_grappler_has_no_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(brom, gob)
    acc = brom.gather(Ctx("attack", actor=brom, target=gob, distance=5))
    assert GRAPPLED_DIS not in acc.dis


def test_grappled_attack_on_another_target_has_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    guard = mon(game, "guard", (-5, 0))
    grappled_by(brom, gob)
    acc = brom.gather(Ctx("attack", actor=brom, target=guard, distance=5))
    assert acc.dis == [GRAPPLED_DIS]


def test_two_grapplers_attacking_either_has_no_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grappled_by(brom, gob, bandit)
    for grappler in (gob, bandit):
        acc = brom.gather(Ctx("attack", actor=brom, target=grappler, distance=5))
        assert GRAPPLED_DIS not in acc.dis, grappler.name


def test_two_grapplers_attacking_a_third_has_one_disadvantage(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    guard = mon(game, "guard", (-5, 0))
    grappled_by(brom, gob, bandit)
    acc = brom.gather(Ctx("attack", actor=brom, target=guard, distance=5))
    assert acc.dis == [GRAPPLED_DIS]


def test_grappled_does_not_affect_saves(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(brom, gob)
    acc = brom.gather(Ctx("save", actor=brom, ability="str"))
    assert GRAPPLED_DIS not in acc.dis
