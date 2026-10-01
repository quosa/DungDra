"""Unit tests for dungdra.effects: conditions' effects on the owner's D20 Tests."""

import json
from pathlib import Path

from dungdra.effects import Acc, Condition, Ctx, Effect, condition_rule
from dungdra.rules import CONDITIONS
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


def test_two_grapplers_record_ruling_r06_on_the_attack(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grappled_by(brom, gob, bandit)
    acc = brom.gather(Ctx("attack", actor=brom, target=gob, distance=5))
    assert [(rule, ruling) for rule, ruling, _ in acc.rulings] == [("GLOSS.grappled#2", "R-06")]


def test_one_grappler_needs_no_ruling(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    guard = mon(game, "guard", (-5, 0))
    grappled_by(brom, gob)
    assert brom.gather(Ctx("attack", actor=brom, target=guard, distance=5)).rulings == []


def test_acc_records_each_ruling_once():
    acc = Acc()
    acc.ruling("GLOSS.grappled#2", "R-06", "why")
    acc.ruling("GLOSS.grappled#2", "R-06", "why")
    assert acc.rulings == [("GLOSS.grappled#2", "R-06", "why")]


def test_remove_consumed_ends_only_the_consumed_effects(game):
    brom = pc(game, "BROM", (0, 0))
    used, kept = brom.add_effect(Effect("used up")), brom.add_effect(Effect("lasting"))
    acc = Acc()
    acc.consumed.append(used)
    acc.remove_consumed()
    assert used not in brom.effects
    assert kept in brom.effects


def test_remove_consumed_skips_an_effect_with_no_owner():
    acc = Acc()
    acc.consumed.append(Effect("never placed"))
    acc.remove_consumed()
    assert acc.consumed[0].owner is None


def test_a_condition_names_its_glossary_entry():
    assert Condition("prone").rule == "GLOSS.prone"
    assert condition_rule("grappled") == "GLOSS.grappled"


def test_every_condition_names_a_real_srd_unit():
    ids = {json.loads(line)["id"] for line in Path("docs/srd/units.jsonl").read_text().splitlines()}
    assert {condition_rule(n) for n in CONDITIONS} <= ids
