"""Species, backgrounds, feats and languages (SRD p.19-23, 83-88)."""
from __future__ import annotations

from .equipment import GP

STANDARD_LANGUAGES = ["common sign language", "draconic", "dwarvish", "elvish", "giant", "gnomish",
                      "goblin", "halfling", "orc"]
RARE_LANGUAGES = ["abyssal", "celestial", "deep speech", "druidic", "infernal", "primordial", "sylvan",
                  "thieves' cant", "undercommon"]

SPECIES = {
    "dwarf": {"size": ["medium"], "speed": 30, "darkvision": 120,
              "traits": ["darkvision", "dwarven resilience", "dwarven toughness", "stonecunning"],
              "resist": ["poison"], "page": 84},
    "elf": {"size": ["medium"], "speed": 30, "darkvision": 60,
            "traits": ["darkvision", "elven lineage", "fey ancestry", "keen senses", "trance"],
            "lineages": {
                "drow": {"darkvision": 120, "cantrip": "dancing lights", "spells": {3: "faerie fire", 5: "darkness"}},
                "high elf": {"cantrip": "prestidigitation", "spells": {3: "detect magic", 5: "misty step"}},
                "wood elf": {"speed": 35, "cantrip": "druidcraft", "spells": {3: "longstrider", 5: "pass without trace"}},
            },
            "keen_senses": ["insight", "perception", "survival"], "page": 84},
    "halfling": {"size": ["small"], "speed": 30,
                 "traits": ["brave", "halfling nimbleness", "luck", "naturally stealthy"], "page": 86},
    "human": {"size": ["medium", "small"], "speed": 30,
              "traits": ["resourceful", "skillful", "versatile"], "page": 86},
}
OUT_OF_SCOPE_SPECIES = ["dragonborn", "gnome", "goliath", "orc", "tiefling"]

BACKGROUNDS = {
    "acolyte": {"abilities": ["int", "wis", "cha"], "feat": ("magic initiate", "cleric"),
                "skills": ["insight", "religion"], "tool": "calligrapher's supplies",
                "equipment": {"A": [("calligrapher's supplies", 1), ("book", 1), ("holy symbol", 1),
                                    ("parchment", 10), ("robe", 1)], "A_gp": 8, "B_gp": 50}},
    "criminal": {"abilities": ["dex", "con", "int"], "feat": ("alert", None),
                 "skills": ["sleight of hand", "stealth"], "tool": "thieves' tools",
                 "equipment": {"A": [("dagger", 2), ("thieves' tools", 1), ("crowbar", 1), ("pouch", 2),
                                     ("traveler's clothes", 1)], "A_gp": 16, "B_gp": 50}},
    "sage": {"abilities": ["con", "int", "wis"], "feat": ("magic initiate", "wizard"),
             "skills": ["arcana", "history"], "tool": "calligrapher's supplies",
             "equipment": {"A": [("quarterstaff", 1), ("calligrapher's supplies", 1), ("book", 1),
                                 ("parchment", 8), ("robe", 1)], "A_gp": 8, "B_gp": 50}},
    "soldier": {"abilities": ["str", "dex", "con"], "feat": ("savage attacker", None),
                "skills": ["athletics", "intimidation"], "tool": "@gaming set",
                "equipment": {"A": [("spear", 1), ("shortbow", 1), ("arrows", 20), ("@gaming set", 1),
                                    ("healer's kit", 1), ("quiver", 1), ("traveler's clothes", 1)],
                              "A_gp": 14, "B_gp": 50}},
}

ORIGIN_FEATS = ["alert", "magic initiate", "savage attacker", "skilled"]
FIGHTING_STYLES = ["archery", "defense", "great weapon fighting", "two-weapon fighting"]
FEAT_PAGES = {"alert": 87, "magic initiate": 87, "savage attacker": 87, "skilled": 87,
              "archery": 87, "defense": 88, "great weapon fighting": 88, "two-weapon fighting": 88}

ALIGNMENTS = ["lawful good", "neutral good", "chaotic good", "lawful neutral", "neutral",
              "chaotic neutral", "lawful evil", "neutral evil", "chaotic evil"]

POINT_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
STANDARD_ARRAY_BY_CLASS = {
    "cleric": {"str": 14, "dex": 8, "con": 13, "int": 10, "wis": 15, "cha": 12},
    "fighter": {"str": 15, "dex": 14, "con": 13, "int": 8, "wis": 10, "cha": 12},
    "rogue": {"str": 12, "dex": 15, "con": 13, "int": 14, "wis": 10, "cha": 8},
    "wizard": {"str": 8, "dex": 12, "con": 13, "int": 15, "wis": 14, "cha": 10},
}
