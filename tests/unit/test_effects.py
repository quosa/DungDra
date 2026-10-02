"""Unit tests for dungdra.effects: conditions' effects on the owner's D20 Tests."""

import json
from pathlib import Path

from dungdra.effects import (
    Acc,
    Condition,
    Ctx,
    Dodge,
    Effect,
    SaveBonus,
    condition_rule,
    grapplers_of,
    grapples_on,
)
from dungdra.rules import CONDITIONS
from tests.support.helpers import mon, pc
from tests.unit.helpers import grappled_by

GRAPPLED_DIS = "Grappled (attacking someone other than the grappler)"


def test_is_save_covers_saving_throws_and_death_saves_only():
    assert Ctx("save").is_save
    assert Ctx("death save").is_save
    assert not any(Ctx(k).is_save for k in ("attack", "check", "initiative"))


def test_save_bonus_applies_to_a_death_saving_throw_but_not_a_check(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(SaveBonus("Cloak of Protection", 1))
    assert (1, "Cloak of Protection") in brom.gather(Ctx("death save", actor=brom)).mods
    assert (1, "Cloak of Protection") in brom.gather(Ctx("save", actor=brom, ability="con")).mods
    assert (1, "Cloak of Protection") not in brom.gather(Ctx("check", actor=brom, ability="str")).mods


def test_paralyzed_fails_str_dex_saves_but_not_a_death_save(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(Condition("paralyzed", "paralyzed"))
    assert brom.gather(Ctx("save", actor=brom, ability="dex")).auto == "fail"
    assert brom.gather(Ctx("save", actor=brom, ability="wis")).auto is None
    assert brom.gather(Ctx("death save", actor=brom)).auto is None


def test_restrained_gives_disadvantage_on_dex_saves_only(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(Condition("restrained", "restrained"))
    assert "Restrained" in brom.gather(Ctx("save", actor=brom, ability="dex")).dis
    assert "Restrained" not in brom.gather(Ctx("save", actor=brom, ability="con")).dis
    assert "Restrained" not in brom.gather(Ctx("death save", actor=brom)).dis


def test_dodge_gives_advantage_on_dex_saves_only(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(Dodge("Dodge"))
    assert "Dodge" in brom.gather(Ctx("save", actor=brom, ability="dex")).adv
    assert "Dodge" not in brom.gather(Ctx("save", actor=brom, ability="con")).adv
    assert "Dodge" not in brom.gather(Ctx("check", actor=brom, ability="dex")).adv
    assert "Dodge" not in brom.gather(Ctx("death save", actor=brom)).adv


def test_grapplers_of_names_every_grappler_and_nothing_else(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    assert grapplers_of(brom) == set()
    brom.add_effect(Condition("prone", "prone"))
    grappled_by(brom, gob, bandit)
    assert grapplers_of(brom) == {gob.id, bandit.id}
    assert grapplers_of(gob) == set()


def test_grapples_on_filters_by_grappler(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    brom.add_effect(Condition("prone", "prone"))
    grappled_by(brom, gob, bandit)
    assert [e.data["grappler"] for e in grapples_on(brom)] == [gob.id, bandit.id]
    assert [e.data["grappler"] for e in grapples_on(brom, by=bandit.id)] == [bandit.id]
    assert grapples_on(gob) == []


def test_grapples_on_is_safe_to_remove_from_while_iterating(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grappled_by(brom, gob, bandit)
    for e in grapples_on(brom):
        brom.remove_effect(e, "escaped")
    assert grapplers_of(brom) == set()


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
