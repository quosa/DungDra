"""Unit tests for dungdra.features: level advancement logs the class rules it applies."""

import json
from pathlib import Path

import pytest

from tests.support.helpers import pc

UNITS = {json.loads(line)["id"] for line in Path("docs/srd/units.jsonl").read_text().splitlines()}


@pytest.mark.parametrize("name", ["BROM", "LIDDA", "MIALEE", "JOZAN"])
def test_levelling_to_3_logs_real_class_rules(game, name):
    hero = pc(game, name)
    hero.award_xp(900, "testing")
    assert hero.level == 3
    features = game.log.of_kind("features") + game.log.of_kind("subclass")
    assert features, "level advancement logged no class features"
    for ev in features:
        assert ev.rule in UNITS, f"{ev.kind}: {ev.rule!r} is not an SRD unit"
    assert all(e.rule in UNITS for e in game.log.events if e.rule)


def test_the_subclass_event_names_the_subclass_unit(game):
    brom = pc(game, "BROM")
    brom.award_xp(900, "testing")
    assert game.log.last("subclass").rule == "CLASS.fighter.fighter-subclass-champion"


def test_a_wizard_adds_the_spells_the_player_picks_not_the_first_two(game):
    mialee = pc(game, "MIALEE")
    game.answer("spellbook_add", ["Sleep", "burning hands"])
    mialee.award_xp(300, "testing")
    assert {"sleep", "burning hands"} <= set(mialee.spellbook)


def test_a_wizard_who_picks_a_spell_off_the_list_gets_the_default_two(game):
    mialee = pc(game, "MIALEE")
    before = set(mialee.spellbook)
    game.answer("spellbook_add", ["wish"])
    mialee.award_xp(300, "testing")
    assert "wish" not in mialee.spellbook and len(set(mialee.spellbook) - before) == 2
