"""The 32 subset spells (SRD p.107-175): metadata. Behaviour lives in dungdra/spells.py."""
from __future__ import annotations


def _s(level, school, lists, time, rng, comp, duration, conc=False, ritual=False, material=None,
       material_cost=0, page=None, **kw):
    d = {"level": level, "school": school, "lists": lists, "time": time, "range": rng,
         "components": set(comp), "duration": duration, "concentration": conc, "ritual": ritual,
         "material": material, "material_cost": material_cost, "page": page}
    d.update(kw)
    return d


C, W, CW = ["cleric"], ["wizard"], ["cleric", "wizard"]

SPELLS = {
    # Cantrips
    "fire bolt": _s(0, "evocation", W, "action", 120, "VS", 0, page=132, attack="ranged", dice="1d10",
                    dtype="fire"),
    "guidance": _s(0, "divination", ["cleric", "druid"], "action", "touch", "VS", 60, conc=True, page=138),
    "light": _s(0, "evocation", CW, "action", "touch", "VM", 3600, material="a firefly or phosphorescent moss",
                page=144),
    "mage hand": _s(0, "conjuration", W, "action", 30, "VS", 60, page=145),
    "minor illusion": _s(0, "illusion", W, "action", 30, "SM", 60, material="a bit of fleece", page=149),
    "prestidigitation": _s(0, "transmutation", W, "action", 10, "VS", 3600, page=155),
    "ray of frost": _s(0, "evocation", W, "action", 60, "VS", 0, page=157, attack="ranged", dice="1d8",
                       dtype="cold"),
    "sacred flame": _s(0, "evocation", C, "action", 60, "VS", 0, page=159, save="dex", dice="1d8",
                       dtype="radiant"),
    "spare the dying": _s(0, "necromancy", ["cleric", "druid"], "action", 15, "VS", 0, page=163),
    "thaumaturgy": _s(0, "transmutation", C, "action", 30, "V", 60, page=167),
    # Level 1
    "bless": _s(1, "enchantment", ["cleric", "paladin"], "action", 30, "VSM", 60, conc=True,
                material="a Holy Symbol worth 5+ GP", material_cost=5, page=113),
    "burning hands": _s(1, "evocation", W, "action", "self", "VS", 0, page=114, save="dex", dice="3d6",
                        dtype="fire", area=("cone", 15)),
    "command": _s(1, "enchantment", ["bard", "cleric", "paladin"], "action", 60, "V", 0, page=116,
                  save="wis"),
    "cure wounds": _s(1, "abjuration", ["bard", "cleric", "druid", "paladin", "ranger"], "action", "touch",
                      "VS", 0, page=121, healing="2d8"),
    "detect magic": _s(1, "divination", ["bard", "cleric", "druid", "paladin", "ranger", "sorcerer", "warlock",
                                         "wizard"], "action", "self", "VS", 600, conc=True, ritual=True,
                       page=125),
    "guiding bolt": _s(1, "evocation", C, "action", 120, "VS", 6, page=138, attack="ranged", dice="4d6",
                       dtype="radiant"),
    "healing word": _s(1, "abjuration", ["bard", "cleric", "druid"], "bonus action", 60, "V", 0, page=139,
                       healing="2d4"),
    "mage armor": _s(1, "abjuration", W, "action", "touch", "VSM", 8 * 3600,
                     material="a piece of cured leather", page=145),
    "magic missile": _s(1, "evocation", W, "action", 120, "VS", 0, page=146, dtype="force"),
    "sanctuary": _s(1, "abjuration", C, "bonus action", 30, "VSM", 60,
                    material="a shard of glass from a mirror", page=159),
    "shield": _s(1, "abjuration", W, "reaction", "self", "VS", 6, page=161),
    "shield of faith": _s(1, "abjuration", ["cleric", "paladin"], "bonus action", 60, "VSM", 600, conc=True,
                          material="a prayer scroll", page=161),
    "sleep": _s(1, "enchantment", W, "action", 60, "VSM", 60, conc=True,
                material="a pinch of sand or rose petals", page=163, save="wis", area=("sphere", 5)),
    "thunderwave": _s(1, "evocation", ["bard", "druid", "sorcerer", "wizard"], "action", "self", "VS", 0,
                      page=168, save="con", dice="2d8", dtype="thunder", area=("cube", 15)),
    # Level 2
    "aid": _s(2, "abjuration", ["bard", "cleric", "druid", "paladin", "ranger"], "action", 30, "VSM", 8 * 3600,
              material="a strip of white cloth", page=107),
    "hold person": _s(2, "enchantment", ["bard", "cleric", "druid", "sorcerer", "warlock", "wizard"], "action",
                      60, "VSM", 60, conc=True, material="a straight piece of iron", page=141, save="wis"),
    "invisibility": _s(2, "illusion", ["bard", "sorcerer", "warlock", "wizard"], "action", "touch", "VSM", 3600,
                       conc=True, material="an eyelash in gum arabic", page=143),
    "lesser restoration": _s(2, "abjuration", ["bard", "cleric", "druid", "paladin", "ranger"], "bonus action",
                             "touch", "VS", 0, page=144),
    "misty step": _s(2, "conjuration", ["sorcerer", "warlock", "wizard"], "bonus action", "self", "V", 0,
                     page=150),
    "scorching ray": _s(2, "evocation", ["sorcerer", "wizard"], "action", 120, "VS", 0, page=159,
                        attack="ranged", dice="2d6", dtype="fire"),
    "spiritual weapon": _s(2, "evocation", C, "bonus action", 60, "VS", 60, conc=True, page=165,
                           attack="melee", dice="1d8", dtype="force"),
    "web": _s(2, "conjuration", ["sorcerer", "wizard"], "action", 60, "VSM", 3600, conc=True,
              material="a bit of spiderweb", page=174, save="dex", area=("cube", 20)),
}

# Class spell lists restricted to the subset (p.38-39, 79-80)
CLASS_LISTS = {
    "cleric": [n for n, s in SPELLS.items() if "cleric" in s["lists"]],
    "wizard": [n for n, s in SPELLS.items() if "wizard" in s["lists"]],
    "druid": [n for n, s in SPELLS.items() if "druid" in s["lists"]],
}
# Wizard list per SRD p.79-80 includes these subset spells even though our table lists 'sorcerer' etc.
for _n in ("hold person", "invisibility", "misty step", "scorching ray", "web", "burning hands", "detect magic",
           "sleep", "thunderwave", "mage armor", "magic missile", "shield"):
    if _n not in CLASS_LISTS["wizard"]:
        CLASS_LISTS["wizard"].append(_n)

# Other SRD Wizard spells of levels 1-2 (p.79-80). They may be written into a
# spellbook (so book sizes follow the class rules) but casting them is refused
# by the subset guard: they are out of scope.
OTHER_WIZARD_SPELLS = {
    1: ["alarm", "charm person", "chromatic orb", "color spray", "comprehend languages", "disguise self",
        "expeditious retreat", "false life", "feather fall", "find familiar", "floating disk", "fog cloud",
        "grease", "hideous laughter", "ice knife", "identify", "illusory script", "jump", "longstrider",
        "protection from evil and good", "ray of sickness", "silent image", "unseen servant"],
    2: ["acid arrow", "alter self", "arcane lock", "arcanist's magic aura", "augury", "blindness/deafness", "blur",
        "continual flame", "darkness", "darkvision", "detect thoughts", "dragon's breath", "enhance ability",
        "enlarge/reduce", "flaming sphere", "gentle repose", "gust of wind", "knock", "levitate", "locate object",
        "magic mouth", "magic weapon", "mind spike", "mirror image", "ray of enfeeblement", "rope trick",
        "see invisibility", "shatter", "spider climb", "suggestion"],
}
OTHER_EVOCATION = {"acid arrow": 2, "flaming sphere": 2, "gust of wind": 2, "shatter": 2, "continual flame": 2,
                   "darkness": 2, "ice knife": 1}


def spell_level(name: str) -> int | None:
    if name in SPELLS:
        return SPELLS[name]["level"]
    for lvl, names in OTHER_WIZARD_SPELLS.items():
        if name in names:
            return lvl
    return None
