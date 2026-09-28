"""The four shared scenario fixtures (golden scenarios §4), built through the
same validating CharacterBuilder a player uses."""
from __future__ import annotations

from .creation import CharacterBuilder

FIXTURES = {
    "BROM": dict(
        name="BROM", cls="fighter", species="dwarf", background="soldier", ability_method="standard",
        scores={"str": 15, "dex": 14, "con": 13, "int": 8, "wis": 10, "cha": 12},
        background_bonus={"str": 2, "con": 1}, alignment="lawful good",
        languages=["dwarvish", "giant"], class_skills=["perception", "survival"],
        fighting_style="defense", masteries=["longsword", "javelin", "glaive"], gaming_set="dice set",
        class_equipment="C", bg_equipment="A",
        purchases=[("chain mail", 1), ("shield", 1), ("longsword", 1), ("glaive", 1), ("javelin", 4),
                   ("dungeoneer's pack", 1)],
    ),
    "LIDDA": dict(
        name="LIDDA", cls="rogue", species="halfling", background="criminal", ability_method="standard",
        scores={"str": 12, "dex": 15, "con": 13, "int": 14, "wis": 10, "cha": 8},
        background_bonus={"dex": 2, "con": 1}, alignment="chaotic good",
        languages=["halfling", "elvish"], rogue_language="goblin",
        class_skills=["acrobatics", "deception", "investigation", "perception"],
        expertise=["stealth", "sleight of hand"], masteries=["shortsword", "dagger"],
        replacement_tool="disguise kit", class_equipment="A", bg_equipment="A",
    ),
    "MIALEE": dict(
        name="MIALEE", cls="wizard", species="elf", lineage="high elf", lineage_ability="int",
        background="sage", ability_method="standard",
        scores={"str": 8, "dex": 12, "con": 13, "int": 15, "wis": 14, "cha": 10},
        background_bonus={"int": 2, "con": 1}, alignment="neutral good",
        languages=["elvish", "draconic"], keen_senses="perception",
        class_skills=["investigation", "medicine"],
        cantrips=["fire bolt", "mage hand", "light"],
        bg_feat={"name": "magic initiate", "list": "wizard", "ability": "int",
                 "cantrips": ["ray of frost", "minor illusion"], "spell": "thunderwave"},
        spellbook=["magic missile", "shield", "sleep", "burning hands", "mage armor", "detect magic"],
        prepared=["magic missile", "shield", "sleep", "mage armor"],
        class_equipment="A", bg_equipment="A",
    ),
    "JOZAN": dict(
        name="JOZAN", cls="cleric", species="human", size="medium", background="acolyte",
        ability_method="standard",
        scores={"str": 14, "dex": 8, "con": 13, "int": 10, "wis": 15, "cha": 12},
        background_bonus={"wis": 2, "cha": 1}, alignment="lawful good",
        languages=["dwarvish", "halfling"], divine_order="protector",
        bg_feat={"name": "magic initiate", "list": "cleric", "ability": "wis",
                 "cantrips": ["light", "thaumaturgy"], "spell": "command"},
        versatile={"name": "skilled", "choices": ["athletics", "survival", "woodcarver's tools"]},
        skillful="perception", class_skills=["medicine", "persuasion"],
        cantrips=["sacred flame", "guidance", "spare the dying"],
        prepared=["bless", "cure wounds", "healing word", "guiding bolt"],
        class_equipment="A", bg_equipment="A",
    ),
}


def make(game, name: str, position=None):
    pc = CharacterBuilder(game).update(**dict(FIXTURES[name.upper()])).build()
    if position is not None:
        pc.position = tuple(position)
    return pc


def party(game):
    return [make(game, n) for n in ("BROM", "LIDDA", "MIALEE", "JOZAN")]
