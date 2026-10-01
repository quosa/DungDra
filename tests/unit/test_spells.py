"""Unit tests for dungdra.spells: casting logs the rule of the spell cast."""

import json
from pathlib import Path

import pytest

from dungdra.data.spells import SPELLS, spell_rule
from dungdra.rules import Refusal
from dungdra.spells import cast
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
