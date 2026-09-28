"""Player characters: derived statistics, class features, resources, advancement.

SRD p.19-24 (creation/advancement), p.36-82 (classes), p.83-88 (origins, feats),
p.89-103 (equipment).
"""
from __future__ import annotations

from .creature import Creature
from .data.classes import CLASSES, LIFE_DOMAIN_SPELLS, SUBCLASS_NAMES
from .data.equipment import ARMOR, DON_DOFF, WEAPONS, canonical
from .data.spells import SPELLS
from .effects import Acc, Ctx
from .items import Inventory, Purse, carrying_capacity
from .rules import (ABILITY_NAMES, MAX_LEVEL_IN_SCOPE, OutOfScope, Refusal, div_up, level_for_xp,
                    proficiency_bonus)

FEATURE_PAGES = {
    "fighting style": 47, "second wind": 48, "weapon mastery": 48, "action surge": 48, "tactical mind": 48,
    "fighter subclass": 48, "improved critical": 49, "remarkable athlete": 49,
    "expertise": 61, "sneak attack": 61, "thieves' cant": 62, "cunning action": 62, "rogue subclass": 62,
    "steady aim": 62, "fast hands": 64, "second-story work": 64,
    "spellcasting": 36, "divine order": 37, "channel divinity": 37, "cleric subclass": 37,
    "disciple of life": 40, "life domain spells": 40, "preserve life": 40,
    "ritual adept": 78, "arcane recovery": 78, "scholar": 78, "wizard subclass": 78,
    "evocation savant": 82, "potent cantrip": 82,
}


class Character(Creature):
    kind = "pc"

    def __init__(self, name: str, cls: str, **kw):
        super().__init__(name, team="party", **kw)
        self.cls = cls
        self.cdata = CLASSES[cls]
        self.level = 1
        self.xp = 0
        self.subclass: str | None = None
        self.species = ""
        self.lineage = None
        self.background = ""
        self.alignment = ""
        self.base_scores: dict = {}
        self.features: list[str] = []
        self.feats: list[dict] = []
        self.fighting_style: str | None = None
        self.weapon_masteries: list[str] = []
        self.weapon_profs: set[str] = set(self.cdata["weapons"])
        self.armor_training: set[str] = set(self.cdata["armor"])
        self.divine_order: str | None = None
        self.scholar_skill: str | None = None
        self.hit_die = self.cdata["hit_die"]
        self.hit_dice_spent = 0
        self.inventory = Inventory()
        self.purse = Purse()
        self.armor = None              # Item worn
        self.shield = None             # Item held (Shield)
        self.wielded: list = []        # Items in hand (weapons, focus ...)
        self.attuned: list = []
        self.resources: dict[str, dict] = {}
        # spellcasting
        self.spell_ability: str | None = self.cdata.get("spellcasting", {}).get("ability")
        self.cantrips: list[tuple[str, str, str]] = []     # (spell, ability, source)
        self.prepared: list[str] = []
        self.spellbook: list[str] = []
        self.always_prepared: dict[str, tuple[str, str]] = {}   # spell -> (ability, source)
        self.free_casts: dict[str, dict] = {}                    # spell -> {available, ability, source}
        self.slots_used: dict[int, int] = {}
        self.pending_choices: list[str] = []
        self.long_rest_finished_at: int | None = None
        self.food_days_without = 0

    # -- derived ---------------------------------------------------------------
    @property
    def character_level(self) -> int:
        return self.level

    def hit_dice_max(self) -> int:
        return self.level

    def hit_dice_left(self) -> int:
        return self.level - self.hit_dice_spent

    def slots_max(self) -> dict[int, int]:
        sc = self.cdata.get("spellcasting")
        if not sc:
            return {}
        return {i + 1: n for i, n in enumerate(sc["slots"][self.level])}

    def slots_left(self, level: int) -> int:
        return self.slots_max().get(level, 0) - self.slots_used.get(level, 0)

    def spell_dc(self, ability: str | None = None) -> int:
        ab = ability or self.spell_ability
        return 8 + self.mod(ab) + self.pb

    def spell_attack_bonus(self, ability: str | None = None) -> int:
        ab = ability or self.spell_ability
        return self.mod(ab) + self.pb

    def prepared_limit(self) -> int:
        sc = self.cdata.get("spellcasting")
        return sc["prepared"][self.level] if sc else 0

    def cantrip_limit(self) -> int:
        sc = self.cdata.get("spellcasting")
        if not sc:
            return 0
        n = sc["cantrips"][self.level]
        if self.divine_order == "thaumaturge":
            n += 1
        return n

    def has_feature(self, f: str) -> bool:
        return f in self.features

    def has_feat(self, f: str) -> bool:
        return any(x["name"] == f for x in self.feats) or self.fighting_style == f

    # -- AC (p.22, p.92, p.88) ----------------------------------------------------
    def wearing_armor(self) -> bool:
        return self.armor is not None

    def armor_category(self) -> str | None:
        return self.armor.armor["category"] if self.armor is not None else None

    def trained_in(self, category: str) -> bool:
        return category in self.armor_training

    def base_ac(self):
        dex = self.mod("dex")
        options = []
        if self.armor is not None:
            a = self.armor.armor
            d = dex if a["dex_max"] is None else min(dex, a["dex_max"])
            parts = [(a["base"], self.armor.display)]
            if a["category"] != "heavy":
                parts.append((d, "Dex" + (" (max 2)" if a["dex_max"] == 2 else "")))
            if self.armor.magic_bonus:
                parts.append((self.armor.magic_bonus, f"{self.armor.display} magic bonus"))
            options.append(parts)
        else:
            options.append([(10, "base"), (dex, "Dex")])
            if self.notes.get("mage_armor"):
                options.append([(13, "Mage Armor"), (dex, "Dex")])
        best = max(options, key=lambda p: sum(v for v, _ in p))
        parts = list(best)
        if self.shield is not None:
            if self.trained_in("shield"):
                parts.append((2, "Shield"))
                if self.shield.magic_bonus:
                    parts.append((self.shield.magic_bonus, "Shield magic bonus"))
            elif self.game:
                pass  # untrained: no AC benefit (p.92)
        if self.fighting_style == "defense" and self.armor is not None:
            parts.append((1, "Defense"))
        return sum(v for v, _ in parts), parts

    # -- Speed -----------------------------------------------------------------
    def adjust_speed(self, s, kind):
        if self.armor is not None and self.armor.armor["str"] and self.score("str") < self.armor.armor["str"]:
            s -= 10
        carry, drag = carrying_capacity(self.size, self.score("str"))
        load = self.load()
        if self.notes.get("dragging"):
            load += self.notes["dragging"]
        if load > carry:
            s = min(s, 5)
        return s

    def load(self) -> float:
        return self.inventory.weight() + self.purse.weight()

    def capacity(self) -> tuple[float, float]:
        return carrying_capacity(self.size, self.score("str"))

    # -- D20 modifiers from features & gear -----------------------------------
    def extra_gather(self, ctx: Ctx, acc: Acc):
        # Armor training (p.92/177): untrained armor -> Disadvantage on Str/Dex D20 Tests
        if self.armor is not None and not self.trained_in(self.armor_category()):
            if ctx.ability in ("str", "dex"):
                acc.disadvantage(f"untrained in {self.armor_category()} armor ({self.armor.display})")
        if ctx.kind == "check" and ctx.skill == "stealth" and self.armor is not None \
                and self.armor.armor["stealth_dis"]:
            acc.disadvantage(f"{self.armor.display} (Stealth Disadvantage)")
        t = self.traits
        if ctx.kind == "save":
            if "dwarven resilience" in t and "poisoned" in ctx.avoid:
                acc.advantage("Dwarven Resilience")
            if "fey ancestry" in t and "charmed" in ctx.avoid:
                acc.advantage("Fey Ancestry")
            if "brave" in t and "frightened" in ctx.avoid:
                acc.advantage("Brave")
        if ctx.kind == "initiative":
            if self.has_feat("alert"):
                acc.bonus(self.pb, "Alert (PB)")
            if self.has_feature("remarkable athlete"):
                acc.advantage("Remarkable Athlete")
        if ctx.kind == "check":
            if self.has_feature("remarkable athlete") and ctx.skill == "athletics":
                acc.advantage("Remarkable Athlete")
            if self.divine_order == "thaumaturge" and ctx.ability == "int" and ctx.skill in ("arcana", "religion"):
                acc.bonus(max(1, self.mod("wis")), "Thaumaturge (Wis)")

    # -- weapons ---------------------------------------------------------------
    def proficient_with(self, item) -> bool:
        w = item.weapon if hasattr(item, "weapon") else WEAPONS.get(item)
        if w is None:
            return False
        if w["category"] in self.weapon_profs:
            return True
        if w["category"] == "martial":
            if "martial:finesse" in self.weapon_profs and "finesse" in w["props"]:
                return True
            if "martial:light" in self.weapon_profs and "light" in w["props"]:
                return True
        return False

    def has_mastery(self, item) -> bool:
        base = item.base if hasattr(item, "base") else canonical(item)
        return self.has_feature("weapon mastery") and base in self.weapon_masteries

    # -- resources -------------------------------------------------------------
    def add_resource(self, name, maximum, short=0, long="all"):
        old = self.resources.get(name)
        used = old["used"] if old else 0
        self.resources[name] = {"max": maximum, "used": min(used, maximum), "short": short, "long": long}

    def resource_left(self, name) -> int:
        r = self.resources.get(name)
        return 0 if r is None else r["max"] - r["used"]

    def spend(self, name, n=1):
        if self.resource_left(name) < n:
            raise Refusal(f"{self.name} has no {name} uses left")
        self.resources[name]["used"] += n

    def regain(self, name, n=None):
        r = self.resources.get(name)
        if r:
            r["used"] = 0 if n is None else max(0, r["used"] - n)

    # -- spells known ------------------------------------------------------------
    def castable(self, spell: str) -> list[dict]:
        """All the ways this character can cast `spell` (with the ability used)."""
        out = []
        sc = self.cdata.get("spellcasting")
        for name, ab, src in self.cantrips:
            if name == spell:
                out.append({"source": src, "ability": ab, "slot": False})
        if spell in self.prepared or (spell in self.always_prepared):
            ab, src = self.always_prepared.get(spell, (self.spell_ability, self.cls.title()))
            out.append({"source": src, "ability": ab, "slot": True})
        if spell in self.free_casts:
            fc = self.free_casts[spell]
            out.append({"source": fc["source"], "ability": fc["ability"], "slot": False, "free": True})
        return out

    def all_known_spells(self) -> list[str]:
        s = [c[0] for c in self.cantrips] + list(self.prepared) + list(self.always_prepared) + list(self.free_casts)
        return list(dict.fromkeys(s))

    # -- light sources carried (torches etc.) -------------------------------------
    def light_sources(self):
        out = []
        for it in self.inventory:
            if it.props.get("lit"):
                out.append(tuple(it.props.get("light", (20, 20))))
        return out

    def on_time_passed(self, start, end):
        for it in list(self.inventory):
            if it.props.get("lit") and it.props.get("burns_until") is not None and end >= it.props["burns_until"]:
                it.props["lit"] = False
                if it.name == "torch":
                    self.inventory.remove(it, 1) if it.qty == 1 else None
                    if self.game:
                        self.game.log.player("light", f"{self.name}'s Torch burns out", page=100)

    # -- XP and levels (p.23) ------------------------------------------------------
    def award_xp(self, amount: int, reason: str = "", ruling=None):
        g = self.game
        self.xp += amount
        if g:
            g.log.player("xp", f"{self.name} gains {amount} XP (total {self.xp})" + (f" — {reason}" if reason else ""),
                         page=23, ruling=ruling)
        target = level_for_xp(self.xp)
        while self.level < min(target, MAX_LEVEL_IN_SCOPE):
            self.gain_level()
        if target > MAX_LEVEL_IN_SCOPE and g:
            g.log.player("scope", f"{self.name} has {self.xp} XP, enough for level {target}, but level 4+ is "
                         f"out of scope; {self.name} stays at level {MAX_LEVEL_IN_SCOPE}.", page=23)

    def gain_level(self, rolled: bool = False):
        from . import features
        if self.level >= MAX_LEVEL_IN_SCOPE:
            raise OutOfScope("Level 4+ is out of scope")
        g = self.game
        self.level += 1
        self.pb = proficiency_bonus(self.level)
        con = self.mod("con")
        if rolled and g:
            r = g.dice.roll(self.hit_die)
            gain = max(1, r + con)
            how = f"rolled d{self.hit_die}={r} + Con {con}"
        else:
            gain = max(1, self.cdata["hp_fixed"] + con)
            how = f"fixed {self.cdata['hp_fixed']} + Con {con}"
        if "dwarven toughness" in self.traits:
            gain += 1
            how += " + 1 Dwarven Toughness"
        self.base_max_hp += gain
        self.hp += gain
        if g:
            g.log.player("level", f"{self.name} reaches level {self.level}: +{gain} HP ({how}) → max "
                         f"{self.max_hp}; Proficiency Bonus +{self.pb}", page=23)
        features.on_level_up(self)

    # -- state ----------------------------------------------------------------------
    def state_extra(self) -> dict:
        return {
            "class": self.cls, "subclass": self.subclass, "level": self.level, "xp": self.xp,
            "species": self.species, "lineage": self.lineage, "background": self.background, "pb": self.pb,
            "hit_dice": {"die": f"d{self.hit_die}", "max": self.level, "spent": self.hit_dice_spent},
            "slots": {lvl: {"max": m, "used": self.slots_used.get(lvl, 0)} for lvl, m in self.slots_max().items()},
            "resources": {k: dict(v) for k, v in self.resources.items()},
            "free_casts": {k: v["available"] for k, v in self.free_casts.items()},
            "inventory": [it.to_dict() for it in self.inventory],
            "coins": dict(self.purse.coins), "gp_total": self.purse.gp,
            "armor": self.armor.display if self.armor else None,
            "shield": bool(self.shield), "attuned": [i.display for i in self.attuned],
            "prepared": list(self.prepared), "spellbook": list(self.spellbook),
            "cantrips": [c[0] for c in self.cantrips], "features": list(self.features),
            "feats": [f["name"] for f in self.feats] + ([self.fighting_style] if self.fighting_style else []),
            "skills": {k: v for k, v in self.skills.items()}, "tools": sorted(self.tools),
            "languages": list(self.languages), "masteries": list(self.weapon_masteries),
        }

    def sheet(self) -> str:
        from .rules import SKILLS, fmt_mod
        lines = [f"{self.name} — {self.species.title()}{' (' + self.lineage.title() + ')' if self.lineage else ''} "
                 f"{self.cls.title()} {self.level}{' (' + self.subclass.title() + ')' if self.subclass else ''}, "
                 f"{self.background.title()}, {self.alignment.title()}",
                 f"HP {self.hp}/{self.max_hp}  AC {self.ac()}  Speed {self.speed()} ft  Initiative "
                 f"{fmt_mod(self.initiative_bonus())}  PB +{self.pb}  XP {self.xp}",
                 "  ".join(f"{ABILITY_NAMES[a][:3]} {s} ({fmt_mod(self.mod(a))})" for a, s in self.abilities.items()),
                 "Saves: " + ", ".join(f"{a.title()} {fmt_mod(self.save_bonus_total(a))}" for a in self.abilities),
                 "Skills: " + ", ".join(f"{s.title()} {fmt_mod(self.skill_total(s))}{'*' if v == 2 else ''}"
                                        for s, v in sorted(self.skills.items())),
                 f"Passive Perception {self.passive('perception')}",
                 f"Tools: {', '.join(sorted(self.tools)) or '-'}   Languages: {', '.join(self.languages)}",
                 f"Features: {', '.join(self.features)}",
                 f"Feats: {', '.join(f['name'].title() for f in self.feats)}"
                 + (f", {self.fighting_style.title()}" if self.fighting_style else ""),
                 ]
        if self.weapon_masteries:
            lines.append(f"Weapon Mastery: {', '.join(m.title() for m in self.weapon_masteries)}")
        if self.cdata.get("spellcasting") or self.cantrips:
            if self.spell_ability:
                lines.append(f"Spell save DC {self.spell_dc()}, spell attack {fmt_mod(self.spell_attack_bonus())}; "
                             f"slots " + ", ".join(f"L{l}: {self.slots_left(l)}/{m}" for l, m in self.slots_max().items()))
            lines.append(f"Cantrips: {', '.join(c[0].title() for c in self.cantrips)}")
            if self.prepared or self.always_prepared:
                lines.append(f"Prepared: {', '.join(s.title() for s in self.prepared)}"
                             + (f" (always: {', '.join(s.title() for s in self.always_prepared)})" if self.always_prepared else ""))
            if self.spellbook:
                lines.append(f"Spellbook: {', '.join(s.title() for s in self.spellbook)}")
        if self.resources:
            lines.append("Resources: " + ", ".join(f"{k.title()} {v['max'] - v['used']}/{v['max']}"
                                                   for k, v in self.resources.items()))
        lines.append(f"Equipment: {', '.join(str(i) for i in self.inventory)}")
        lines.append(f"Coins: {self.purse}")
        return "\n".join(lines)

    def initiative_bonus(self) -> int:
        b = self.mod("dex")
        if self.has_feat("alert"):
            b += self.pb
        return b
