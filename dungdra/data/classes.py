"""Class data for the four subset classes, levels 1-3 (SRD p.36-82)."""
from __future__ import annotations

CLASSES = {
    "fighter": {
        "hit_die": 10, "hp1": 10, "hp_fixed": 6, "saves": ["str", "con"],
        "skill_choices": ["acrobatics", "animal handling", "athletics", "history", "insight",
                          "intimidation", "persuasion", "perception", "survival"], "skill_count": 2,
        "weapons": ["simple", "martial"], "armor": ["light", "medium", "heavy", "shield"], "tools": [],
        "equipment": {"A": [("chain mail", 1), ("greatsword", 1), ("flail", 1), ("javelin", 8),
                            ("dungeoneer's pack", 1)], "A_gp": 4,
                      "B": [("studded leather armor", 1), ("scimitar", 1), ("shortsword", 1), ("longbow", 1),
                            ("arrows", 20), ("quiver", 1), ("dungeoneer's pack", 1)], "B_gp": 11,
                      "C_gp": 155},
        "features": {1: ["fighting style", "second wind", "weapon mastery"],
                     2: ["action surge", "tactical mind"], 3: ["fighter subclass"]},
        "subclasses": {"champion": {3: ["improved critical", "remarkable athlete"]}},
        "mastery_count": 3, "second_wind": 2, "page": 47,
    },
    "rogue": {
        "hit_die": 8, "hp1": 8, "hp_fixed": 5, "saves": ["dex", "int"],
        "skill_choices": ["acrobatics", "athletics", "deception", "insight", "intimidation", "investigation",
                          "perception", "persuasion", "sleight of hand", "stealth"], "skill_count": 4,
        "weapons": ["simple", "martial:finesse", "martial:light"], "armor": ["light"],
        "tools": ["thieves' tools"],
        "equipment": {"A": [("leather armor", 1), ("dagger", 2), ("shortsword", 1), ("shortbow", 1),
                            ("arrows", 20), ("quiver", 1), ("thieves' tools", 1), ("burglar's pack", 1)],
                      "A_gp": 8, "B_gp": 100},
        "features": {1: ["expertise", "sneak attack", "thieves' cant", "weapon mastery"],
                     2: ["cunning action"], 3: ["rogue subclass", "steady aim"]},
        "subclasses": {"thief": {3: ["fast hands", "second-story work"]}},
        "mastery_count": 2, "sneak_attack": {1: 1, 2: 1, 3: 2}, "page": 61,
    },
    "cleric": {
        "hit_die": 8, "hp1": 8, "hp_fixed": 5, "saves": ["wis", "cha"],
        "skill_choices": ["history", "insight", "medicine", "persuasion", "religion"], "skill_count": 2,
        "weapons": ["simple"], "armor": ["light", "medium", "shield"], "tools": [],
        "equipment": {"A": [("chain shirt", 1), ("shield", 1), ("mace", 1), ("holy symbol", 1),
                            ("priest's pack", 1)], "A_gp": 7, "B_gp": 110},
        "features": {1: ["spellcasting", "divine order"], 2: ["channel divinity"], 3: ["cleric subclass"]},
        "subclasses": {"life domain": {3: ["disciple of life", "life domain spells", "preserve life"]}},
        "spellcasting": {"ability": "wis", "cantrips": {1: 3, 2: 3, 3: 3}, "prepared": {1: 4, 2: 5, 3: 6},
                         "slots": {1: [2], 2: [3], 3: [4, 2]}, "focus": "holy symbol"},
        "channel_divinity": {2: 2, 3: 2}, "page": 36,
    },
    "wizard": {
        "hit_die": 6, "hp1": 6, "hp_fixed": 4, "saves": ["int", "wis"],
        "skill_choices": ["arcana", "history", "insight", "investigation", "medicine", "nature", "religion"],
        "skill_count": 2, "weapons": ["simple"], "armor": [], "tools": [],
        "equipment": {"A": [("dagger", 2), ("quarterstaff", 1), ("robe", 1), ("spellbook", 1),
                            ("scholar's pack", 1)], "A_gp": 5, "B_gp": 55},
        "features": {1: ["spellcasting", "ritual adept", "arcane recovery"], 2: ["scholar"],
                     3: ["wizard subclass"]},
        "subclasses": {"evoker": {3: ["evocation savant", "potent cantrip"]}},
        "spellcasting": {"ability": "int", "cantrips": {1: 3, 2: 3, 3: 3}, "prepared": {1: 4, 2: 5, 3: 6},
                         "slots": {1: [2], 2: [3], 3: [4, 2]}, "focus": "arcane focus"},
        "page": 77,
    },
}
OUT_OF_SCOPE_CLASSES = ["barbarian", "bard", "druid", "monk", "paladin", "ranger", "sorcerer", "warlock"]
SUBCLASS_NAMES = {"fighter": "champion", "rogue": "thief", "cleric": "life domain", "wizard": "evoker"}

LIFE_DOMAIN_SPELLS = {3: ["aid", "bless", "cure wounds", "lesser restoration"]}
SCHOLAR_SKILLS = ["arcana", "history", "investigation", "medicine", "nature", "religion"]
