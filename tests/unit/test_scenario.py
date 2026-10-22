"""Unit tests for dungdra.scenario: reading adventure files and catching mistakes in them."""

import copy
import json

import pytest

from dungdra import scenario
from dungdra.scenario import AdventureError, check, load

GOOD = {
    "title": "Test",
    "start": "a",
    "places": {
        "a": {"name": "A", "text": "Here.", "exits": [{"to": "b", "travel": {"miles": 1, "pace": "slow"}}]},
        "b": {
            "name": "B",
            "text": "There.",
            "light": "dim",
            "ground": [{"kind": "rubble", "rect": [0, 0, 10, 10]}],
            "encounter": {"monsters": ["giant rat"], "positions": [[30, 0]]},
            "traps": [{"kind": "hidden pit", "location": "the floor"}],
            "loot": {"items": ["potion of healing"], "gp": 5},
        },
    },
}


def test_the_adventures_that_come_with_the_game_load():
    assert "goblin-trail" in scenario.available()
    for name in scenario.available():
        assert load(name)["places"]
    assert load()["title"] == "The Goblin Trail"


def bad(path, value):
    """GOOD with the value at `path` (keys separated by dots, list indexes as ints) replaced."""
    data = copy.deepcopy(GOOD)
    *parents, last = path.split(".")
    node = data
    for k in parents:
        node = node[int(k) if k.isdigit() else k]
    node[int(last) if last.isdigit() else last] = value
    return data


@pytest.mark.parametrize(
    ("path", "value", "says"),
    [
        ("start", "z", "start: there's no place 'z'"),
        ("places", {}, "at least one place"),
        ("places.a.colour", "red", "places.a: unknown colour"),
        ("places.a.exits.0.to", "z", "places.a.exits[0].to: there's no place 'z'"),
        ("places.a.exits.0.travel.pace", "sprint", "travel.pace: 'sprint'"),
        ("places.a.exits.0.travel.terrain", "lava", "travel.terrain: 'lava'"),
        ("places.b.light", "gloomy", "places.b.light"),
        ("places.b.encounter.monsters", ["dragon"], "no monster 'dragon'"),
        ("places.b.encounter.positions", [], "one [x, y] per monster (1)"),
        ("places.b.ambush", {"monsters": [], "positions": [], "hide_total": 10, "text": "!"}, "not both"),
        ("places.b.traps.0.kind", "rolling boulder", "no trap 'rolling boulder'"),
        ("places.b.loot.items", ["vorpal sword"], "places.b.loot.items"),
        ("places.b.ground.0.kind", "lava", "no rules for 'lava' ground"),
        ("places.b.ground.0.rect", [0, 0], "two corners"),
        ("places.b.ground", "quicksand", "no rules for 'quicksand' ground"),
        ("places.a.exits.0", "b", "places.a.exits[0]: expected an object"),
    ],
)
def test_a_mistake_in_an_adventure_is_named_with_where_it_is(path, value, says):
    with pytest.raises(AdventureError) as e:
        check(bad(path, value))
    assert says in str(e.value)


def test_a_place_without_its_text_is_reported():
    data = copy.deepcopy(GOOD)
    del data["places"]["b"]["text"]
    with pytest.raises(AdventureError, match="places.b: missing text"):
        check(data)


def test_a_good_adventure_file_is_read_and_checked_by_path(tmp_path):
    path = tmp_path / "mine.json"
    path.write_text(json.dumps(GOOD))
    assert load(str(path))["title"] == "Test"


@pytest.mark.parametrize(
    ("name", "says"),
    [("no-such-adventure", "no adventure called"), ("missing/file.json", "no adventure file")],
)
def test_an_adventure_that_isnt_there_is_reported(name, says):
    with pytest.raises(AdventureError, match=says):
        load(name)


def test_a_file_that_isnt_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ not json")
    with pytest.raises(AdventureError, match="not valid JSON"):
        load(str(path))
