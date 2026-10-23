"""Adventure files: the places of an adventure, their exits and what waits in each, as JSON.

A file names a `start` place and its `places`. Each place has a `name` and `text`, and may have
`exits`, `light`, `sunlight`, `ground`, an `ambush` or `encounter`, `traps`, `loot` and an
`ending`. An exit leads both ways unless it is `one_way`, and may carry the `travel` it takes.
`load` checks the whole file against the engine's content, so a mistake is reported when the
file is read, not when the party reaches the place. `docs/adventure-format.md` describes it all.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from . import magic_items as MI
from .data.equipment import LIFESTYLE, canonical, item_cost
from .data.monsters import MONSTERS
from .explore import PACE_MPH, TERRAIN_MAX
from .rules import DIFFICULT_GROUND, Refusal, norm
from .traps import TRAPS

DEFAULT = "goblin-trail"

TOP = {"title", "about", "start", "places", "quests"}
PLACE = {
    "name",
    "text",
    "aliases",
    "exits",
    "light",
    "sunlight",
    "ground",
    "ambush",
    "encounter",
    "traps",
    "loot",
    "ending",
    "shop",
    "inn",
    "people",
}
SHOP = {"name", "sells", "buys"}
INN = {"name", "room"}
PERSON = {"id", "name", "text", "says", "quest", "creature", "attitude", "side", "position"}
QUEST = {"title", "giver", "offer", "goal", "reward", "done"}
GOAL = {"defeat", "bring"}
REWARD = {"gp", "xp", "items"}
EXIT = {"to", "one_way", "travel"}
TRAVEL = {"miles", "hours", "pace", "terrain", "road"}
FIGHT = {"monsters", "positions"}
AMBUSH = FIGHT | {"hide_total", "text"}
TRAP = {"kind", "location"}
LOOT = {"items", "gp"}
GROUND = {"kind", "rect"}


class AdventureError(ValueError):
    """An adventure file that doesn't fit the format or names content the engine doesn't have."""


def available() -> list[str]:
    """The adventures that come with the game, by name."""
    folder = resources.files("dungdra.data") / "adventures"
    return sorted(p.name.removesuffix(".json") for p in folder.iterdir() if p.name.endswith(".json"))


def load(name: str = DEFAULT) -> dict:
    """Read and check an adventure: one that comes with the game by name, or a file by path."""
    if name.endswith(".json") or "/" in name:
        path = Path(name)
        if not path.exists():
            raise AdventureError(f"There's no adventure file {name}")
        text = path.read_text(encoding="utf-8")
    else:
        if name not in available():
            raise AdventureError(f"There's no adventure called {name!r}; try one of {', '.join(available())}")
        text = (resources.files("dungdra.data") / "adventures" / f"{name}.json").read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AdventureError(f"{name}: not valid JSON ({e})") from e
    check(data, name)
    return data


def check(data: dict, name: str = "adventure") -> None:
    """Raise AdventureError naming the first thing in the adventure that doesn't fit."""
    _keys(data, TOP, name, required={"title", "start", "places"})
    places = data["places"]
    if not isinstance(places, dict) or not places:
        raise AdventureError(f"{name}: places must name at least one place")
    if data["start"] not in places:
        raise AdventureError(f"{name}: start: there's no place {data['start']!r}")
    for pid, place in places.items():
        _place(place, places, f"{name}: places.{pid}")
    people = {p["id"]: pid for pid, place in places.items() for p in place.get("people", [])}
    for qid, q in data.get("quests", {}).items():
        _quest(q, places, people, f"{name}: quests.{qid}")
    for pid, place in places.items():
        for i, p in enumerate(place.get("people", [])):
            if p.get("quest") is not None and p["quest"] not in data.get("quests", {}):
                raise AdventureError(
                    f"{name}: places.{pid}.people[{i}].quest: there's no quest {p['quest']!r}"
                )


def _place(p: dict, places: dict, at: str) -> None:
    _keys(p, PLACE, at, required={"name", "text"})
    if p.get("light", "bright") not in ("bright", "dim", "dark"):
        raise AdventureError(f"{at}.light: {p['light']!r} isn't bright, dim or dark")
    for i, ex in enumerate(p.get("exits", [])):
        _keys(ex, EXIT, f"{at}.exits[{i}]", required={"to"})
        if ex["to"] not in places:
            raise AdventureError(f"{at}.exits[{i}].to: there's no place {ex['to']!r}")
        if "travel" in ex:
            _travel(ex["travel"], f"{at}.exits[{i}].travel")
    if p.get("ambush") and p.get("encounter"):
        raise AdventureError(f"{at}: a place has an ambush or an encounter, not both")
    if "ambush" in p:
        _fight(p["ambush"], AMBUSH, f"{at}.ambush", required={"monsters", "positions", "hide_total", "text"})
    if "encounter" in p:
        _fight(p["encounter"], FIGHT, f"{at}.encounter", required={"monsters", "positions"})
    for i, t in enumerate(p.get("traps", [])):
        _keys(t, TRAP, f"{at}.traps[{i}]", required={"kind"})
        if t["kind"] not in TRAPS:
            raise AdventureError(
                f"{at}.traps[{i}].kind: no trap {t['kind']!r}; the traps are {', '.join(TRAPS)}"
            )
    if "loot" in p:
        _loot(p["loot"], f"{at}.loot")
    _ground(p.get("ground", []), f"{at}.ground")
    if "shop" in p:
        _keys(p["shop"], SHOP, f"{at}.shop", required=set())
        for it in p["shop"].get("sells", []):
            _item(it, f"{at}.shop.sells")
    if "inn" in p:
        _keys(p["inn"], INN, f"{at}.inn", required=set())
        if p["inn"].get("room", "modest") not in LIFESTYLE:
            raise AdventureError(f"{at}.inn.room: {p['inn']['room']!r} isn't one of {', '.join(LIFESTYLE)}")
    for i, person in enumerate(p.get("people", [])):
        _person(person, f"{at}.people[{i}]")


def _person(p: dict, at: str) -> None:
    _keys(p, PERSON, at, required={"id", "name", "text"})
    if "creature" in p and p["creature"] not in MONSTERS:
        raise AdventureError(
            f"{at}.creature: no monster {p['creature']!r}; the monsters are {', '.join(MONSTERS)}"
        )
    if p.get("attitude", "indifferent") not in ("friendly", "indifferent", "hostile"):
        raise AdventureError(f"{at}.attitude: {p['attitude']!r} isn't friendly, indifferent or hostile")
    if p.get("side", "neutral") not in ("neutral", "party", "enemy"):
        raise AdventureError(f"{at}.side: {p['side']!r} isn't neutral, party or enemy")


def _quest(q: dict, places: dict, people: dict, at: str) -> None:
    _keys(q, QUEST, at, required={"title", "giver", "offer", "goal", "reward"})
    if q["giver"] not in people:
        raise AdventureError(f"{at}.giver: nobody in the adventure has the id {q['giver']!r}")
    goal = q["goal"]
    _keys(goal, GOAL, f"{at}.goal", required=set())
    if len(goal) != 1:
        raise AdventureError(f"{at}.goal: one of defeat (a place) or bring (an item)")
    if "defeat" in goal and goal["defeat"] not in places:
        raise AdventureError(f"{at}.goal.defeat: there's no place {goal['defeat']!r}")
    if "defeat" in goal and not (
        places[goal["defeat"]].get("encounter") or places[goal["defeat"]].get("ambush")
    ):
        raise AdventureError(f"{at}.goal.defeat: {goal['defeat']!r} has no encounter or ambush to defeat")
    if "bring" in goal:
        _item(goal["bring"], f"{at}.goal.bring")
    _keys(q["reward"], REWARD, f"{at}.reward", required=set())
    for it in q["reward"].get("items", []):
        _item(it, f"{at}.reward.items")


def _item(name: str, at: str) -> None:
    """An item the engine knows: equipment with a price, or a magic item it can make."""
    if item_cost(canonical(name)) is not None:
        return
    try:
        MI.make(name)
    except Refusal as e:
        raise AdventureError(f"{at}: no item {name!r} ({e.reason})") from e


def _travel(tv: dict, at: str) -> None:
    _keys(tv, TRAVEL, at, required=set())
    if tv.get("pace", "normal") not in PACE_MPH:
        raise AdventureError(f"{at}.pace: {tv['pace']!r} isn't one of {', '.join(PACE_MPH)}")
    if norm(tv.get("terrain", "forest")) not in TERRAIN_MAX:
        raise AdventureError(f"{at}.terrain: {tv['terrain']!r} isn't one of {', '.join(TERRAIN_MAX)}")


def _fight(f: dict, allowed: set, at: str, required: set) -> None:
    _keys(f, allowed, at, required=required)
    for m in f["monsters"]:
        if m not in MONSTERS:
            raise AdventureError(f"{at}.monsters: no monster {m!r}; the monsters are {', '.join(MONSTERS)}")
    if len(f["positions"]) != len(f["monsters"]):
        raise AdventureError(f"{at}.positions: one [x, y] per monster ({len(f['monsters'])})")


def _loot(loot: dict, at: str) -> None:
    _keys(loot, LOOT, at, required=set())
    for it in loot.get("items", []):
        _item(it, f"{at}.items")


def _ground(ground, at: str) -> None:
    for i, g in enumerate([ground] if isinstance(ground, str) else ground):
        kind = g if isinstance(g, str) else g.get("kind")
        if not isinstance(g, str):
            _keys(g, GROUND, f"{at}[{i}]", required={"kind", "rect"})
            if len(g["rect"]) != 4:
                raise AdventureError(f"{at}[{i}].rect: two corners, [x0, y0, x1, y1]")
        if norm(kind) not in DIFFICULT_GROUND:
            raise AdventureError(
                f"{at}[{i}]: no rules for {kind!r} ground; the kinds are {', '.join(DIFFICULT_GROUND)}"
            )


def _keys(d, allowed: set, at: str, required: set) -> None:
    if not isinstance(d, dict):
        raise AdventureError(f"{at}: expected an object")
    if unknown := sorted(set(d) - allowed):
        raise AdventureError(f"{at}: unknown {', '.join(unknown)} (allowed: {', '.join(sorted(allowed))})")
    if missing := sorted(required - set(d)):
        raise AdventureError(f"{at}: missing {', '.join(missing)}")
