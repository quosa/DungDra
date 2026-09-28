"""Core conventions (SRD p.5-9): ability modifiers, rounding, skills, sizes."""
from __future__ import annotations

import math

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_NAMES = {"str": "Strength", "dex": "Dexterity", "con": "Constitution",
                 "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"}

SKILLS = {
    "acrobatics": "dex", "animal handling": "wis", "arcana": "int",
    "athletics": "str", "deception": "cha", "history": "int", "insight": "wis",
    "intimidation": "cha", "investigation": "int", "medicine": "wis",
    "nature": "int", "perception": "wis", "performance": "cha",
    "persuasion": "cha", "religion": "int", "sleight of hand": "dex",
    "stealth": "dex", "survival": "wis",
}

SIZES = ["tiny", "small", "medium", "large", "huge", "gargantuan"]

DAMAGE_TYPES = ["acid", "bludgeoning", "cold", "fire", "force", "lightning",
                "necrotic", "piercing", "poison", "psychic", "radiant",
                "slashing", "thunder"]

CONDITIONS = ["blinded", "charmed", "deafened", "exhaustion", "frightened",
              "grappled", "incapacitated", "invisible", "paralyzed",
              "petrified", "poisoned", "prone", "restrained", "stunned",
              "unconscious"]

XP_BY_LEVEL = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000,
               8: 34000, 9: 48000, 10: 64000, 11: 85000, 12: 100000,
               13: 120000, 14: 140000, 15: 165000, 16: 195000, 17: 225000,
               18: 265000, 19: 305000, 20: 355000}
MAX_LEVEL_IN_SCOPE = 3

ROUND = 6            # seconds per combat round
MINUTE = 60
HOUR = 3600
DAY = 86400


class Refusal(Exception):
    """An attempted action the rules don't allow. Carries a player-facing reason."""

    def __init__(self, reason: str, page: str | int | None = None, ruling=None):
        super().__init__(reason)
        self.reason = reason
        self.page = page
        self.ruling = ruling


class OutOfScope(Refusal):
    """Content outside the implemented subset (§1.2 subset guard)."""


def ability_mod(score: int) -> int:
    """p.6: floor((score - 10) / 2)."""
    return (score - 10) // 2


def div(a: int, b: int) -> int:
    """p.5 Round Down: divide and round down."""
    return math.floor(a / b)


def mul(a, b) -> int:
    """p.5 Round Down also applies to multiplication."""
    return math.floor(a * b)


def div_up(a: int, b: int) -> int:
    return -(-a // b)


def proficiency_bonus(level_or_cr: float) -> int:
    """p.8 Proficiency Bonus table."""
    x = max(1, math.ceil(level_or_cr)) if level_or_cr >= 1 else 1
    return 2 + (x - 1) // 4


def level_for_xp(xp: int) -> int:
    lvl = 1
    for level, need in XP_BY_LEVEL.items():
        if xp >= need:
            lvl = level
    return lvl


def size_index(size: str) -> int:
    return SIZES.index(size.lower())


def fmt_mod(v: int) -> str:
    return f"+{v}" if v >= 0 else f"−{-v}"


def norm(s: str) -> str:
    return " ".join(str(s).lower().replace("_", " ").replace("-", " ").replace("’", "'").split())
