"""Monsters built from stat blocks (SRD p.254-255, glossary "Stat Block" p.188-189)."""
from __future__ import annotations

import itertools

from .creature import Creature
from .data.monsters import MONSTERS
from .dice import parse_expr
from .effects import Effect
from .rules import OutOfScope, norm, proficiency_bonus

_counter = itertools.count(1)


class UndeadFortitude(Effect):
    """p.343: DC 5 + damage Con save to drop to 1 HP instead (not vs Radiant or crits)."""
    name = "Undead Fortitude"

    def at_zero_hp(self, game, dealt, dtype, crit):
        o = self.owner
        if dtype == "radiant" or crit:
            game.log.player("trait", f"{o.name}'s Undead Fortitude doesn't apply "
                            f"({'Radiant damage' if dtype == 'radiant' else 'Critical Hit'})", page=343)
            return False
        dc = 5 + dealt
        r = o.save("con", dc, label=f"Undead Fortitude Con save (DC {dc})", page=343)
        if r.success:
            o.hp = 1
            game.log.player("trait", f"{o.name} drops to 1 HP instead (Undead Fortitude)", page=343)
            return True
        return False


class Monster(Creature):
    kind = "monster"

    def __init__(self, key: str, name: str | None = None, hp: str | int = "average"):
        key = norm(key)
        if key not in MONSTERS:
            raise OutOfScope(f"{key.title()} isn't one of the monsters in scope")
        d = MONSTERS[key]
        self.key = key
        self.data = d
        nm = name or key.title()
        super().__init__(nm, d["abilities"], size=d["size"], ctype=d["type"], tags=d["tags"],
                         pb=proficiency_bonus(max(d["cr"], 1)), max_hp=d["hp"], speed=dict(d["speed"]),
                         team="enemy")
        self.save_bonus = dict(d["saves"])
        self.skill_bonus_fixed = dict(d["skills"])
        self.skills = {k: 1 for k in d["skills"]}
        self.gear_ac = d["ac"]
        self.init_bonus = d["init"]
        self.cr = d["cr"]
        self.xp = d["xp"]
        self.senses = dict(d["senses"])
        self.fixed_passive = d["passive"]
        self.languages = list(d["languages"])
        self.attacks = [dict(a) for a in d["attacks"]]
        self.traits = set(d.get("traits", []))
        self.vuln = set(d.get("vuln", []))
        self.immune = set(d.get("immune", []))
        self.cond_immune = set(d.get("cond_immune", []))
        self.multiattack = d.get("multiattack", 1)
        self.attitude = "hostile"
        self.hd = d["hd"]
        self.uses = {"divine aid": 1} if "divine aid" in self.traits else {}
        if hp == "roll":
            self.notes["roll_hp"] = True
        elif isinstance(hp, int):
            self.base_max_hp = self.hp = hp
        if "undead fortitude" in self.traits:
            self.add_effect(UndeadFortitude())

    def roll_hp(self, dice):
        n, s, m = parse_expr(self.hd)
        total = sum(dice.roll_many(n, s)) + m
        self.base_max_hp = self.hp = max(1, total)

    def attack_named(self, name: str | None):
        if name is None:
            return self.attacks[0]
        n = norm(name)
        for a in self.attacks:
            if norm(a["name"]) == n or (a.get("weapon") and a["weapon"] == n):
                return a
        from .rules import Refusal
        raise Refusal(f"{self.name} has no attack called {name!r}; it has "
                      f"{', '.join(a['name'] for a in self.attacks)} (the GM can't invent stat-block abilities)")

    def check_modifier_parts(self, ability, skill=None, tool=None):
        if skill and skill in self.skill_bonus_fixed:
            return [(self.skill_bonus_fixed[skill], f"{skill.title()} (stat block)")]
        return super().check_modifier_parts(ability, skill, tool)

    def passive(self, skill="perception", tags=()):
        if skill == "perception" and not tags:
            return self.fixed_passive
        return super().passive(skill, tags)

    def extra_gather(self, ctx, acc):
        if "sunlight sensitivity" in self.traits and self.game and self.game.scene.sunlight \
                and ctx.kind in ("attack", "check"):
            acc.disadvantage("Sunlight Sensitivity")
        if ctx.kind == "initiative":
            pass

    def state_extra(self):
        return {"monster": self.key, "cr": self.cr, "xp": self.xp}
