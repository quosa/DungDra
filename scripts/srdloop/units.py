"""Loading the approved SRD rule units and tagging their scope."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

UNITS = Path("docs/srd/units.jsonl")
APPROVED = Path("docs/srd/units.approved")

# Rules chapters: every unit is in scope. The loop starts here.
CORE_CHAPTERS = ("Rules Glossary", "Playing the Game", "Gameplay Toolbox", "Character Creation")
# Order in which the queue takes chapters.
CHAPTER_ORDER = (
    *CORE_CHAPTERS,
    "Equipment",
    "Feats",
    "Character Origins",
    "Classes",
    "Spells",
    "Monsters",
    "Monsters A–Z",
    "Animals",
    "Magic Items",
)
ITEM_PRICE = re.compile(r"\((?:[\d,]+ (?:GP|SP|CP|EP|PP)|Varies)\)$", re.I)
FEATURE_LEVEL = re.compile(r"^Level (\d+):")


class NotApproved(Exception):
    """units.jsonl changed since a person approved it (python scripts/srd/extract.py --approve)."""


def load(path: Path = UNITS, approved: Path = APPROVED, require_approval: bool = True) -> list[dict]:
    data = path.read_bytes()
    if require_approval:
        pinned = approved.read_text().strip() if approved.exists() else ""
        if hashlib.sha256(data).hexdigest() != pinned:
            raise NotApproved(f"{path} is not the approved version; review it and run extract.py --approve")
    return [json.loads(line) for line in data.decode().splitlines() if line.strip()]


def by_id(units: list[dict]) -> dict[str, dict]:
    return {u["id"]: u for u in units}


def norm_name(s: str) -> str:
    """Names as the engine's data tables spell them: lower case, straight apostrophes."""
    s = s.lower().replace("’", "'")
    s = ITEM_PRICE.sub("", s).strip()
    return re.sub(r"\s+", " ", s)


def engine_content() -> dict[str, set[str]]:
    """What the engine implements, by kind, as normalised names."""
    from dungdra import magic_items, rules
    from dungdra.data import classes, equipment, monsters, origins, spells

    items: set[str] = set()
    for table in (
        equipment.WEAPONS,
        equipment.ARMOR,
        equipment.GEAR,
        equipment.TOOLS,
        equipment.PACKS,
        equipment.MOUNTS,
        equipment.LIFESTYLE,
    ):
        items |= {norm_name(k) for k in table}
    items |= {norm_name(k) for k in equipment.GAMING_SETS} | {"shield"}
    return {
        "classes": {norm_name(c) for c in classes.CLASSES},
        "subclasses": {norm_name(s) for s in classes.SUBCLASS_NAMES.values()},
        "species": {norm_name(s) for s in origins.SPECIES},
        "backgrounds": {norm_name(b) for b in origins.BACKGROUNDS},
        "feats": {norm_name(f) for f in [*origins.ORIGIN_FEATS, *origins.FIGHTING_STYLES]},
        "items": items,
        "spells": {norm_name(s) for s in spells.SPELLS},
        "monsters": {norm_name(m) for m in monsters.MONSTERS},
        "magic_items": {norm_name(m) for m in magic_items.MAGIC_ITEMS},
        "max_level": {str(rules.MAX_LEVEL_IN_SCOPE)},
    }


def scope(unit: dict, content: dict[str, set[str]]) -> str:
    """ "core" (a rules chapter), "content-in" (rules or content the engine implements) or
    "content-out" (content the engine should refuse: only a refusal check, no model)."""
    ch, path, title = unit["chapter"], unit["heading_path"], norm_name(unit["title"])
    if ch in CORE_CHAPTERS:
        return "core"
    top = norm_name(path[0]) if path else ""
    if ch == "Classes":
        if top not in content["classes"]:
            return "content-out"
        sub = next((norm_name(h.split(":", 1)[1]) for h in path if "Subclass:" in h), None)
        if sub is not None and sub not in content["subclasses"]:
            return "content-out"
        level = FEATURE_LEVEL.match(unit["title"])
        if level and int(level.group(1)) > int(next(iter(content["max_level"]))):
            return "content-out"
        return "content-in"
    if ch == "Character Origins":
        if "Species Descriptions" in path:
            return "content-in" if title in content["species"] else "content-out"
        if "Background Descriptions" in path:
            return "content-in" if title in content["backgrounds"] else "content-out"
        return "content-in"
    if ch == "Feats":
        if len(path) >= 3:  # an individual feat
            return "content-in" if title in content["feats"] else "content-out"
        return "content-in"
    if ch == "Equipment":
        if ITEM_PRICE.search(unit["title"]) and not unit["title"].endswith("(Varies)"):  # "Crowbar (2 GP)"
            known = content["items"] | content["magic_items"]  # "Potion of Healing (50 GP)"
            head, _, tail = title.partition(", ")  # "Lantern, Hooded" is the engine's "hooded lantern"
            names = {title, f"{tail} {head}"} if tail else {title}
            return "content-in" if names & known else "content-out"
        return "content-in"
    if ch == "Spells":
        if path[:1] == ["Spell Descriptions"]:
            return "content-in" if title in content["spells"] else "content-out"
        return "content-in"
    if ch in ("Monsters A–Z", "Animals"):
        return "content-in" if title in content["monsters"] else "content-out"
    if ch == "Magic Items":
        if path[:1] == ["Magic Items A–Z"]:
            words = {w.removesuffix("s") for w in title.replace(",", " ").split()}  # "Potions of Healing"
            known = ({w.removesuffix("s") for w in m.split()} for m in content["magic_items"])
            return "content-in" if any(k <= words for k in known) else "content-out"
        return "content-in"
    return "content-in"  # Monsters introduction: how stat blocks work
