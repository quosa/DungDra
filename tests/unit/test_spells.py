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
