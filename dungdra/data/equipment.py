"""Equipment data (SRD p.89-103). Costs are in copper pieces (CP)."""
from __future__ import annotations

GP, SP, CP, EP, PP = 100, 10, 1, 50, 1000


def _w(cat, kind, dmg, dtype, props="", mastery="", weight=0.0, cost=0, rng=None,
       versatile=None, ammo=None):
    return {"category": cat, "kind": kind, "damage": dmg, "dtype": dtype,
            "props": set(p.strip().lower() for p in props.split(",") if p.strip()),
            "mastery": mastery.lower(), "weight": weight, "cost": cost,
            "range": rng, "versatile": versatile, "ammo": ammo}


# p.91 Weapons table
WEAPONS = {
    # Simple Melee
    "club": _w("simple", "melee", "1d4", "bludgeoning", "light", "slow", 2, 1 * SP),
    "dagger": _w("simple", "melee", "1d4", "piercing", "finesse, light, thrown", "nick", 1, 2 * GP, (20, 60)),
    "greatclub": _w("simple", "melee", "1d8", "bludgeoning", "two-handed", "push", 10, 2 * SP),
    "handaxe": _w("simple", "melee", "1d6", "slashing", "light, thrown", "vex", 2, 5 * GP, (20, 60)),
    "javelin": _w("simple", "melee", "1d6", "piercing", "thrown", "slow", 2, 5 * SP, (30, 120)),
    "light hammer": _w("simple", "melee", "1d4", "bludgeoning", "light, thrown", "nick", 2, 2 * GP, (20, 60)),
    "mace": _w("simple", "melee", "1d6", "bludgeoning", "", "sap", 4, 5 * GP),
    "quarterstaff": _w("simple", "melee", "1d6", "bludgeoning", "versatile", "topple", 4, 2 * SP, versatile="1d8"),
    "sickle": _w("simple", "melee", "1d4", "slashing", "light", "nick", 2, 1 * GP),
    "spear": _w("simple", "melee", "1d6", "piercing", "thrown, versatile", "sap", 3, 1 * GP, (20, 60), "1d8"),
    # Simple Ranged
    "dart": _w("simple", "ranged", "1d4", "piercing", "finesse, thrown", "vex", 0.25, 5 * CP, (20, 60)),
    "light crossbow": _w("simple", "ranged", "1d8", "piercing", "ammunition, loading, two-handed", "slow", 5,
                         25 * GP, (80, 320), ammo="bolts"),
    "shortbow": _w("simple", "ranged", "1d6", "piercing", "ammunition, two-handed", "vex", 2, 25 * GP,
                   (80, 320), ammo="arrows"),
    "sling": _w("simple", "ranged", "1d4", "bludgeoning", "ammunition", "slow", 0, 1 * SP, (30, 120),
                ammo="sling bullets"),
    # Martial Melee
    "battleaxe": _w("martial", "melee", "1d8", "slashing", "versatile", "topple", 4, 10 * GP, versatile="1d10"),
    "flail": _w("martial", "melee", "1d8", "bludgeoning", "", "sap", 2, 10 * GP),
    "glaive": _w("martial", "melee", "1d10", "slashing", "heavy, reach, two-handed", "graze", 6, 20 * GP),
    "greataxe": _w("martial", "melee", "1d12", "slashing", "heavy, two-handed", "cleave", 7, 30 * GP),
    "greatsword": _w("martial", "melee", "2d6", "slashing", "heavy, two-handed", "graze", 6, 50 * GP),
    "halberd": _w("martial", "melee", "1d10", "slashing", "heavy, reach, two-handed", "cleave", 6, 20 * GP),
    "lance": _w("martial", "melee", "1d10", "piercing", "heavy, reach, two-handed", "topple", 6, 10 * GP),
    "longsword": _w("martial", "melee", "1d8", "slashing", "versatile", "sap", 3, 15 * GP, versatile="1d10"),
    "maul": _w("martial", "melee", "2d6", "bludgeoning", "heavy, two-handed", "topple", 10, 10 * GP),
    "morningstar": _w("martial", "melee", "1d8", "piercing", "", "sap", 4, 15 * GP),
    "pike": _w("martial", "melee", "1d10", "piercing", "heavy, reach, two-handed", "push", 18, 5 * GP),
    "rapier": _w("martial", "melee", "1d8", "piercing", "finesse", "vex", 2, 25 * GP),
    "scimitar": _w("martial", "melee", "1d6", "slashing", "finesse, light", "nick", 3, 25 * GP),
    "shortsword": _w("martial", "melee", "1d6", "piercing", "finesse, light", "vex", 2, 10 * GP),
    "trident": _w("martial", "melee", "1d8", "piercing", "thrown, versatile", "topple", 4, 5 * GP, (20, 60), "1d10"),
    "warhammer": _w("martial", "melee", "1d8", "bludgeoning", "versatile", "push", 5, 15 * GP, versatile="1d10"),
    "war pick": _w("martial", "melee", "1d8", "piercing", "versatile", "sap", 2, 5 * GP, versatile="1d10"),
    "whip": _w("martial", "melee", "1d4", "slashing", "finesse, reach", "slow", 3, 2 * GP),
    # Martial Ranged
    "blowgun": _w("martial", "ranged", "1", "piercing", "ammunition, loading", "vex", 1, 10 * GP, (25, 100),
                  ammo="needles"),
    "hand crossbow": _w("martial", "ranged", "1d6", "piercing", "ammunition, light, loading", "vex", 3, 75 * GP,
                        (30, 120), ammo="bolts"),
    "heavy crossbow": _w("martial", "ranged", "1d10", "piercing", "ammunition, heavy, loading, two-handed", "push",
                         18, 50 * GP, (100, 400), ammo="bolts"),
    "longbow": _w("martial", "ranged", "1d8", "piercing", "ammunition, heavy, two-handed", "slow", 2, 50 * GP,
                  (150, 600), ammo="arrows"),
    "musket": _w("martial", "ranged", "1d12", "piercing", "ammunition, loading, two-handed", "slow", 10, 500 * GP,
                 (40, 120), ammo="firearm bullets"),
    "pistol": _w("martial", "ranged", "1d10", "piercing", "ammunition, loading", "vex", 3, 250 * GP, (30, 90),
                 ammo="firearm bullets"),
}

# p.92 Armor table
ARMOR = {
    "padded armor": {"category": "light", "base": 11, "dex_max": None, "str": 0, "stealth_dis": True, "weight": 8, "cost": 5 * GP},
    "leather armor": {"category": "light", "base": 11, "dex_max": None, "str": 0, "stealth_dis": False, "weight": 10, "cost": 10 * GP},
    "studded leather armor": {"category": "light", "base": 12, "dex_max": None, "str": 0, "stealth_dis": False, "weight": 13, "cost": 45 * GP},
    "hide armor": {"category": "medium", "base": 12, "dex_max": 2, "str": 0, "stealth_dis": False, "weight": 12, "cost": 10 * GP},
    "chain shirt": {"category": "medium", "base": 13, "dex_max": 2, "str": 0, "stealth_dis": False, "weight": 20, "cost": 50 * GP},
    "scale mail": {"category": "medium", "base": 14, "dex_max": 2, "str": 0, "stealth_dis": True, "weight": 45, "cost": 50 * GP},
    "breastplate": {"category": "medium", "base": 14, "dex_max": 2, "str": 0, "stealth_dis": False, "weight": 20, "cost": 400 * GP},
    "half plate armor": {"category": "medium", "base": 15, "dex_max": 2, "str": 0, "stealth_dis": True, "weight": 40, "cost": 750 * GP},
    "ring mail": {"category": "heavy", "base": 14, "dex_max": 0, "str": 0, "stealth_dis": True, "weight": 40, "cost": 30 * GP},
    "chain mail": {"category": "heavy", "base": 16, "dex_max": 0, "str": 13, "stealth_dis": True, "weight": 55, "cost": 75 * GP},
    "splint armor": {"category": "heavy", "base": 17, "dex_max": 0, "str": 15, "stealth_dis": True, "weight": 60, "cost": 200 * GP},
    "plate armor": {"category": "heavy", "base": 18, "dex_max": 0, "str": 15, "stealth_dis": True, "weight": 65, "cost": 1500 * GP},
}
SHIELD = {"category": "shield", "bonus": 2, "weight": 6, "cost": 10 * GP}
# p.92 don/doff times in seconds
DON_DOFF = {"light": (60, 60), "medium": (300, 60), "heavy": (600, 300)}

# p.93-94 Tools
TOOLS = {
    "alchemist's supplies": {"ability": "int", "cost": 50 * GP, "weight": 8, "artisan": True},
    "brewer's supplies": {"ability": "int", "cost": 20 * GP, "weight": 9, "artisan": True},
    "calligrapher's supplies": {"ability": "dex", "cost": 10 * GP, "weight": 5, "artisan": True},
    "carpenter's tools": {"ability": "str", "cost": 8 * GP, "weight": 6, "artisan": True,
                          "craft": ["club", "greatclub", "quarterstaff", "barrel", "chest", "ladder", "pole",
                                    "portable ram", "torch"]},
    "cartographer's tools": {"ability": "wis", "cost": 15 * GP, "weight": 6, "artisan": True},
    "cobbler's tools": {"ability": "dex", "cost": 5 * GP, "weight": 5, "artisan": True},
    "cook's utensils": {"ability": "wis", "cost": 1 * GP, "weight": 8, "artisan": True, "craft": ["rations"]},
    "glassblower's tools": {"ability": "int", "cost": 30 * GP, "weight": 5, "artisan": True},
    "jeweler's tools": {"ability": "int", "cost": 25 * GP, "weight": 2, "artisan": True,
                        "craft": ["arcane focus", "holy symbol"]},
    "leatherworker's tools": {"ability": "dex", "cost": 5 * GP, "weight": 5, "artisan": True,
                              "craft": ["sling", "whip", "hide armor", "leather armor", "studded leather armor",
                                        "backpack", "pouch", "quiver", "waterskin"]},
    "mason's tools": {"ability": "str", "cost": 10 * GP, "weight": 8, "artisan": True},
    "painter's supplies": {"ability": "wis", "cost": 10 * GP, "weight": 5, "artisan": True},
    "potter's tools": {"ability": "int", "cost": 10 * GP, "weight": 3, "artisan": True},
    "smith's tools": {"ability": "str", "cost": 20 * GP, "weight": 8, "artisan": True,
                      "craft": ["@melee_except_club_greatclub_quarterstaff_whip", "@medium_except_hide", "@heavy",
                                "iron spikes", "crowbar", "caltrops", "chain"]},
    "tinker's tools": {"ability": "dex", "cost": 50 * GP, "weight": 10, "artisan": True},
    "weaver's tools": {"ability": "dex", "cost": 1 * GP, "weight": 5, "artisan": True,
                       "craft": ["padded armor", "bedroll", "blanket", "net", "robe", "rope", "sack"]},
    "woodcarver's tools": {"ability": "dex", "cost": 1 * GP, "weight": 5, "artisan": True,
                           "craft": ["club", "greatclub", "quarterstaff", "@ranged_except_pistol_musket_sling",
                                     "arcane focus", "arrows", "bolts"]},
    "disguise kit": {"ability": "cha", "cost": 25 * GP, "weight": 3},
    "forgery kit": {"ability": "dex", "cost": 15 * GP, "weight": 5},
    "herbalism kit": {"ability": "int", "cost": 5 * GP, "weight": 3},
    "navigator's tools": {"ability": "wis", "cost": 25 * GP, "weight": 2},
    "poisoner's kit": {"ability": "int", "cost": 50 * GP, "weight": 2},
    "thieves' tools": {"ability": "dex", "cost": 25 * GP, "weight": 1,
                       "utilize": {"pick a lock": 15, "disarm a trap": 15}},
    # Gaming sets (variants each require separate proficiency)
    "dice set": {"ability": "wis", "cost": 1 * SP, "weight": 0, "gaming": True},
    "dragonchess set": {"ability": "wis", "cost": 1 * GP, "weight": 0, "gaming": True},
    "playing card set": {"ability": "wis", "cost": 5 * SP, "weight": 0, "gaming": True},
    "three-dragon ante set": {"ability": "wis", "cost": 1 * GP, "weight": 0, "gaming": True},
    # Musical instruments (a few)
    "lute": {"ability": "cha", "cost": 35 * GP, "weight": 2, "instrument": True},
    "flute": {"ability": "cha", "cost": 2 * GP, "weight": 1, "instrument": True},
    "drum": {"ability": "cha", "cost": 6 * GP, "weight": 3, "instrument": True},
}
ARTISAN_TOOLS = [k for k, v in TOOLS.items() if v.get("artisan")]
GAMING_SETS = [k for k, v in TOOLS.items() if v.get("gaming")]

# p.95 Adventuring Gear (subset used by the fixtures + common items)
GEAR = {
    "acid": (1, 25 * GP), "alchemist's fire": (1, 50 * GP), "antitoxin": (0, 50 * GP),
    "backpack": (5, 2 * GP), "ball bearings": (2, 1 * GP), "bedroll": (7, 1 * GP), "bell": (0, 1 * GP),
    "blanket": (3, 5 * SP), "book": (5, 25 * GP), "caltrops": (2, 1 * GP), "candle": (0, 1 * CP),
    "chain": (10, 5 * GP), "chest": (25, 5 * GP), "climber's kit": (12, 25 * GP),
    "fine clothes": (6, 15 * GP), "traveler's clothes": (4, 2 * GP), "component pouch": (2, 25 * GP),
    "crowbar": (5, 2 * GP), "flask": (1, 2 * CP), "grappling hook": (4, 2 * GP), "healer's kit": (3, 5 * GP),
    "holy symbol": (1, 5 * GP), "holy water": (1, 25 * GP), "ink": (0, 10 * GP), "ink pen": (0, 2 * CP),
    "lamp": (1, 5 * SP), "hooded lantern": (2, 5 * GP), "bullseye lantern": (2, 10 * GP),
    "lock": (1, 10 * GP), "manacles": (6, 2 * GP), "map": (0, 1 * GP), "mirror": (0.5, 5 * GP),
    "net": (3, 1 * GP), "oil": (1, 1 * SP), "paper": (0, 2 * SP), "parchment": (0, 1 * SP),
    "basic poison": (0, 100 * GP), "pole": (7, 5 * CP), "potion of healing": (0.5, 50 * GP),
    "pouch": (1, 5 * SP), "quiver": (1, 1 * GP), "rations": (2, 5 * SP), "robe": (4, 1 * GP),
    "rope": (5, 1 * GP), "sack": (0.5, 1 * CP), "shovel": (5, 2 * GP), "signal whistle": (0, 5 * CP),
    "iron spikes": (5, 1 * GP), "spyglass": (1, 1000 * GP), "string": (0, 1 * SP), "tent": (20, 2 * GP),
    "tinderbox": (1, 5 * SP), "torch": (1, 1 * CP), "vial": (0, 1 * GP), "waterskin": (5, 2 * SP),
    "arcane focus": (1, 10 * GP), "spellbook": (3, 50 * GP), "barrel": (70, 2 * GP), "ladder": (25, 1 * SP),
    "serpent venom": (0, 200 * GP),
    # ammunition bundles (p.96) — stored per piece
    "arrows": (1 / 20, 1 * GP / 20), "bolts": (1.5 / 20, 1 * GP / 20),
    "sling bullets": (1.5 / 20, 4 * CP / 20), "firearm bullets": (2 / 10, 3 * GP / 10),
    "needles": (1 / 50, 1 * GP / 50),
}
AMMO_BUNDLE = {"arrows": 20, "bolts": 20, "sling bullets": 20, "firearm bullets": 10, "needles": 50}

# p.96-99 Packs
PACKS = {
    "burglar's pack": {"cost": 16 * GP, "contents": [("backpack", 1), ("ball bearings", 1), ("bell", 1),
                       ("candle", 10), ("crowbar", 1), ("hooded lantern", 1), ("oil", 7), ("rations", 5),
                       ("rope", 1), ("tinderbox", 1), ("waterskin", 1)]},
    "dungeoneer's pack": {"cost": 12 * GP, "contents": [("backpack", 1), ("caltrops", 1), ("crowbar", 1),
                          ("oil", 2), ("rations", 10), ("rope", 1), ("tinderbox", 1), ("torch", 10),
                          ("waterskin", 1)]},
    "explorer's pack": {"cost": 10 * GP, "contents": [("backpack", 1), ("bedroll", 1), ("oil", 2), ("rations", 10),
                        ("rope", 1), ("tinderbox", 1), ("torch", 10), ("waterskin", 1)]},
    "priest's pack": {"cost": 33 * GP, "contents": [("backpack", 1), ("blanket", 1), ("holy water", 1), ("lamp", 1),
                      ("rations", 7), ("robe", 1), ("tinderbox", 1)]},
    "scholar's pack": {"cost": 40 * GP, "contents": [("backpack", 1), ("book", 1), ("ink", 1), ("ink pen", 1),
                       ("lamp", 1), ("oil", 10), ("parchment", 10), ("tinderbox", 1)]},
}

# p.101 Lifestyle expenses per day
LIFESTYLE = {"wretched": 0, "squalid": 1 * SP, "poor": 2 * SP, "modest": 1 * GP,
             "comfortable": 2 * GP, "wealthy": 4 * GP, "aristocratic": 10 * GP}

MOUNTS = {"riding horse": {"cost": 75 * GP, "carry": 480}}


def item_cost(name: str) -> int | None:
    n = name.lower()
    if n in WEAPONS:
        return WEAPONS[n]["cost"]
    if n in ARMOR:
        return ARMOR[n]["cost"]
    if n == "shield":
        return SHIELD["cost"]
    if n in TOOLS:
        return TOOLS[n]["cost"]
    if n in PACKS:
        return PACKS[n]["cost"]
    if n in GEAR:
        return GEAR[n][1]
    if n in MOUNTS:
        return MOUNTS[n]["cost"]
    return None


def item_weight(name: str) -> float:
    n = name.lower()
    if n in WEAPONS:
        return WEAPONS[n]["weight"]
    if n in ARMOR:
        return ARMOR[n]["weight"]
    if n == "shield":
        return SHIELD["weight"]
    if n in TOOLS:
        return TOOLS[n]["weight"]
    if n in GEAR:
        return GEAR[n][0]
    return 0.0


ALIASES = {
    "chainmail": "chain mail", "short sword": "shortsword", "long sword": "longsword",
    "leather": "leather armor", "studded leather": "studded leather armor", "half plate": "half plate armor",
    "plate": "plate armor", "splint": "splint armor", "padded": "padded armor", "hide": "hide armor",
    "thieves tools": "thieves' tools", "healers kit": "healer's kit", "arrow": "arrows", "bolt": "bolts",
    "javelins": "javelin", "daggers": "dagger", "torches": "torch", "ration": "rations",
    "potion": "potion of healing", "healing potion": "potion of healing", "potions of healing": "potion of healing",
    "spikes": "iron spikes", "iron spike": "iron spikes", "woodcarvers tools": "woodcarver's tools",
    "dice": "dice set", "playing cards": "playing card set", "dragonchess": "dragonchess set",
    "calligraphers supplies": "calligrapher's supplies", "light crossbows": "light crossbow",
}


def canonical(name: str) -> str:
    from ..rules import norm
    n = norm(name)
    n2 = n.replace("'", "")
    if n in ALIASES:
        return ALIASES[n]
    if n2 in ALIASES:
        return ALIASES[n2]
    for table in (WEAPONS, ARMOR, TOOLS, PACKS, GEAR, MOUNTS):
        for k in table:
            if k.replace("'", "") == n2:
                return k
    if n == "shield" or n == "shields":
        return "shield"
    if n.endswith("s") and canonical_exists(n[:-1]):
        return canonical(n[:-1])
    return n


def canonical_exists(n):
    return any(n in t for t in (WEAPONS, ARMOR, TOOLS, PACKS, GEAR, MOUNTS)) or n == "shield"
