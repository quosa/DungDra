"""Unit tests for dungdra.spells: casting logs the rule of the spell cast."""

import json
from pathlib import Path

import pytest

from dungdra.data.equipment import GP
from dungdra.data.spells import SPELLS, spell_rule
from dungdra.rules import Refusal
from dungdra.spells import _material, cast
from tests.support.helpers import mon, pc

UNITS = {json.loads(line)["id"] for line in Path("docs/srd/units.jsonl").read_text().splitlines()}


def test_every_spell_names_its_srd_unit():
    assert {n: spell_rule(n) for n in SPELLS if spell_rule(n) not in UNITS} == {}


def test_spell_rule_slugs_the_name():
    assert spell_rule("cure wounds") == "SPELL.cure-wounds"
    assert spell_rule("tasha's hideous laughter") == "SPELL.tashas-hideous-laughter"


def test_a_cast_logs_the_spells_rule(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    game.dice.force_str("d20=[15]")
    cast(game, mialee, "fire bolt", targets=[gob])
    assert game.log.last("cast").rule == "SPELL.fire-bolt"
    assert game.log.last("attack").rule == "SPELL.casting-spells.effects.attack-rolls"


def test_an_out_of_range_spell_is_refused_under_the_range_rule(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (500, 0))
    with pytest.raises(Refusal) as exc:
        cast(game, mialee, "fire bolt", targets=[gob])
    assert exc.value.rule == "SPELL.casting-spells.range"


def _jozan_holding_his_mace(game):
    jozan = pc(game, "JOZAN", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    assert jozan.wielded
    return jozan, brom


def _drop(c, name):
    while (it := c.inventory.find(name)) is not None:
        c.inventory.remove(it, it.qty)


def test_a_bless_refused_for_its_material_keeps_the_weapon_in_hand(game):
    jozan, brom = _jozan_holding_his_mace(game)
    _drop(jozan, "holy symbol")
    held = list(jozan.wielded)
    with pytest.raises(Refusal) as exc:
        cast(game, jozan, "bless", [brom])
    assert exc.value.rule == "SPELL.casting-spells.components.material-m"
    assert jozan.wielded == held
    assert game.log.last("interact") is None


def test_a_costed_component_is_checked_against_the_spells_own_item(game):
    jozan, _ = _jozan_holding_his_mace(game)
    _drop(jozan, "holy symbol")
    sd = dict(
        SPELLS["bless"], material="a spyglass worth 1,000+ GP", material_item="spyglass", material_cost=1000
    )
    with pytest.raises(Refusal, match="spyglass"):
        _material(jozan, "bless", sd, None)
    jozan.inventory.add("holy symbol")
    with pytest.raises(Refusal):  # a holy symbol doesn't stand in for another spell's component
        _material(jozan, "bless", sd, None)
    jozan.inventory.add("spyglass")
    _material(jozan, "bless", sd, None)


def test_a_costed_component_worth_less_than_its_price_is_refused(game):
    jozan, brom = _jozan_holding_his_mace(game)
    _drop(jozan, "holy symbol")
    jozan.inventory.add("holy symbol", cost=4 * GP)
    with pytest.raises(Refusal) as exc:
        cast(game, jozan, "bless", [brom])
    assert exc.value.rule == "SPELL.casting-spells.components.material-m"
    jozan.inventory.add("holy symbol", cost=5 * GP)
    cast(game, jozan, "bless", [brom])
    assert brom.find_effects("Bless")


def test_bless_names_its_holy_symbol_and_price():
    assert SPELLS["bless"]["material_item"] == "holy symbol"
    assert SPELLS["bless"]["material_cost"] == 5


def test_a_somatic_hand_is_freed_only_once_the_cast_goes_ahead(game):
    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))  # mace and shield: no free hand
    with pytest.raises(Refusal):
        cast(game, jozan, "cure wounds", [pc(game, "LIDDA", (500, 0))])  # out of range
    assert len(jozan.wielded) == 2
    cast(game, jozan, "cure wounds", [brom])
    assert len(jozan.wielded) == 1
    assert game.log.last("interact").rule == "SPELL.casting-spells.components.somatic-s"


def test_bless_with_a_holy_symbol_needs_no_free_hand(game):
    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))
    cast(game, jozan, "bless", [brom])
    assert len(jozan.wielded) == 2  # the Holy Symbol is the focus: the M hand also does the S
    assert brom.find_effects("Bless")


def test_a_material_component_without_pouch_or_focus_is_refused(game):
    mialee = pc(game, "MIALEE", (0, 0))
    cast(game, mialee, "mage armor", [mialee])  # spellbook and quarterstaff are her focus
    assert mialee.find_effects("Mage Armor")
    _drop(mialee, "spellbook")
    _drop(mialee, "quarterstaff")
    with pytest.raises(Refusal, match="Component Pouch") as exc:
        cast(game, mialee, "mage armor", [mialee])
    assert exc.value.rule == "SPELL.casting-spells.components.material-m"


def test_no_weapon_is_stowed_once_the_free_interaction_is_spent(game):
    from dungdra import combat

    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))
    game.dice.force_str("d20=[20,1]")
    combat.roll_initiative(game, [jozan, brom])
    assert game.combat.is_turn(jozan)
    game.combat.turn.free_interaction = True
    with pytest.raises(Refusal, match="free object interaction"):
        cast(game, jozan, "cure wounds", [brom])
    assert len(jozan.wielded) == 2
    assert game.combat.turn.actions_used == 0


def _bless_party(game):
    return [pc(game, n, (5 * i, 0)) for i, n in enumerate(("JOZAN", "BROM", "LIDDA", "MIALEE"))]


def test_too_many_bless_targets_are_refused_before_anything_is_spent(game):
    jozan, *others = party = _bless_party(game)
    with pytest.raises(Refusal, match="up to 3 creatures") as exc:
        cast(game, jozan, "bless", party)
    assert (exc.value.rule, exc.value.page) == ("SPELL.bless#6", 113)
    assert jozan.slots_left(1) == 2 and jozan.concentrating is None
    assert not any(c.find_effects("Bless") for c in party)
    assert game.log.last("cast") is None


def test_naming_a_creature_more_than_once_still_counts_against_the_cap(game):
    jozan, brom, _, _ = _bless_party(game)
    with pytest.raises(Refusal, match="up to 3 creatures"):
        cast(game, jozan, "bless", [brom] * 4)
    assert jozan.slots_left(1) == 2


def test_a_higher_slot_raises_the_cap_and_cites_the_upcast_clause(game):
    jozan, *_ = party = _bless_party(game)
    jozan.award_xp(900)  # level 3: level 2 slots
    gob = mon(game, "goblin warrior", (20, 0))
    with pytest.raises(Refusal, match="up to 4 creatures") as exc:
        cast(game, jozan, "bless", [*party, gob], slot=2)
    assert exc.value.rule == "SPELL.bless#8"
    assert jozan.slots_left(2) == 2
    cast(game, jozan, "bless", party, slot=2)
    assert all(c.find_effects("Bless") for c in party)


def test_an_object_among_bless_targets_is_refused_before_anything_is_spent(game):
    jozan, brom, _, _ = _bless_party(game)
    game.scene.objects["door"] = {}
    with pytest.raises(Refusal, match="'door' isn't one") as exc:
        cast(game, jozan, "bless", [brom, "door"])
    assert (exc.value.rule, exc.value.page) == ("SPELL.bless#6", 113)
    assert jozan.slots_left(1) == 2 and jozan.concentrating is None
    assert not brom.find_effects("Bless")
    assert game.log.last("cast") is None


@pytest.mark.parametrize("spell", ["command", "hold person", "aid", "invisibility"])
def test_each_capped_spell_refuses_a_non_creature_target_under_its_own_rule(game, spell):
    from dungdra.spells import _target_cap

    with pytest.raises(Refusal, match="targets creatures") as exc:
        _target_cap(spell, SPELLS[spell], 4, ["door"])
    assert (exc.value.rule, exc.value.page) == (spell_rule(spell), SPELLS[spell]["page"])


@pytest.mark.parametrize(
    "spell, level, cap",
    [("command", 1, 1), ("command", 3, 3), ("hold person", 2, 1), ("hold person", 4, 3), ("aid", 4, 3)],
)
def test_each_capped_spell_refuses_one_target_over_its_cap_under_its_own_rule(game, spell, level, cap):
    from dungdra.spells import _target_cap

    gobs = [mon(game, "goblin warrior", (5 * i, 0)) for i in range(cap + 1)]
    _target_cap(spell, SPELLS[spell], level, gobs[:cap])
    with pytest.raises(Refusal, match=f"up to {cap} creature") as exc:
        _target_cap(spell, SPELLS[spell], level, gobs)
    assert (exc.value.rule, exc.value.page) == (spell_rule(spell), SPELLS[spell]["page"])
