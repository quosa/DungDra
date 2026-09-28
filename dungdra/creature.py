"""Creature: shared machinery for player characters and monsters.

Ability checks, saving throws, AC, Speed, conditions, damage and healing
(SRD p.5-18 and the Rules Glossary).
"""
from __future__ import annotations

import re

from .d20 import D20Roll, roll_d20_test
from .effects import Acc, Condition, Ctx, Effect, IMPLIES, INCAPACITATING
from .events import PLAYER
from .rules import (ABILITIES, ABILITY_NAMES, SKILLS, Refusal, ability_mod, div,
                    fmt_mod, size_index)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class Creature:
    kind = "creature"

    def __init__(self, name: str, abilities: dict | None = None, *, size="medium",
                 ctype="humanoid", tags=(), pb=2, max_hp=1, speed=30, team="neutral",
                 cid: str | None = None):
        self.name = name
        self.id = cid or slug(name)
        self.abilities = {a: 10 for a in ABILITIES}
        if abilities:
            self.abilities.update(abilities)
        self.size = size
        self.ctype = ctype
        self.type_tags = set(tags)
        self.pb = pb
        self.base_max_hp = max_hp
        self.max_hp_bonus = 0          # e.g. Aid
        self.max_hp_reduction = 0      # reductions restored by a Long Rest
        self.hp = max_hp
        self.temp_hp = 0
        self.speeds = {"walk": speed} if isinstance(speed, int) else dict(speed)
        self.save_profs: set[str] = set()
        self.save_bonus: dict[str, int] = {}     # monsters: fixed save modifiers
        self.skills: dict[str, int] = {}         # skill -> 1 proficient, 2 expertise
        self.skill_bonus_fixed: dict[str, int] = {}  # monsters: listed skill bonus
        self.tools: set[str] = set()
        self.resist: set[str] = set()
        self.vuln: set[str] = set()
        self.immune: set[str] = set()
        self.cond_immune: set[str] = set()
        self.senses: dict[str, int] = {}
        self.languages: list[str] = []
        self.traits: set[str] = set()
        self.effects: list[Effect] = []
        self.exhaustion = 0
        self.exhaustion_sources: dict[str, int] = {}   # suffocation/malnutrition/dehydration
        self.dead = False
        self.stable = False
        self.death_saves = {"success": 0, "failure": 0}
        self.heroic_inspiration = False
        self.team = team
        self.position = (0, 0)
        self.elevation = 0
        self.reach = 5
        self.game = None
        self.hidden_total: int | None = None
        self.concentrating: str | None = None
        self.gear_ac: int | None = None          # monsters: fixed AC
        self.held: list = []                      # held objects (dropped when Unconscious)
        self.notes: dict = {}

    # -- basic stats -------------------------------------------------------
    def mod(self, ability: str) -> int:
        return ability_mod(self.score(ability))

    def score(self, ability: str) -> int:
        return self.abilities[ability]

    @property
    def max_hp(self) -> int:
        return max(0, self.base_max_hp + self.max_hp_bonus - self.max_hp_reduction)

    @property
    def bloodied(self) -> bool:
        return self.hp <= self.max_hp // 2

    @property
    def alive(self) -> bool:
        return not self.dead

    @property
    def conscious(self) -> bool:
        return not self.dead and not self.has("unconscious")

    def has_trait(self, t: str) -> bool:
        return t in self.traits

    def is_pc(self) -> bool:
        return self.kind == "pc"

    # -- effects & conditions ---------------------------------------------
    def add_effect(self, eff: Effect) -> Effect:
        eff.owner = self
        self.effects.append(eff)
        return eff

    def remove_effect(self, eff: Effect, reason: str = "") -> None:
        if eff in self.effects:
            self.effects.remove(eff)
            eff.on_removed(self.game)
            if self.game and (eff.condition or reason):
                self.game.log.player("effect_end", f"{self.name}: {eff.describe()} ends"
                                     + (f" ({reason})" if reason else ""), page=eff.page)

    def find_effects(self, name=None, cls=None, source=None):
        out = []
        for e in self.effects:
            if name is not None and getattr(e, "name", None) != name and e.condition != name:
                continue
            if cls is not None and not isinstance(e, cls):
                continue
            if source is not None and e.source != source:
                continue
            out.append(e)
        return out

    def conditions(self) -> set[str]:
        out = set()
        for e in self.effects:
            if e.condition:
                out.add(e.condition)
                out |= IMPLIES.get(e.condition, set())
        if self.exhaustion > 0:
            out.add("exhaustion")
        return out

    def has(self, condition: str) -> bool:
        return condition in self.conditions()

    def is_immune_to_condition(self, name: str) -> bool:
        if name in self.cond_immune:
            return True
        if name == "poisoned" and self.has("petrified"):
            return True
        return False

    def add_condition(self, name: str, source: str = "", caster=None, ends=None,
                      until=None, page="176-191", **data) -> Condition | None:
        name = name.lower()
        if name == "exhaustion":
            self.gain_exhaustion(1, source)
            return None
        if self.is_immune_to_condition(name):
            if self.game:
                self.game.log.player("immune", f"{self.name} is immune to the {name.title()} condition",
                                     page=page)
            return None
        already = self.has(name)
        c = Condition(name, source=source or name.title(), caster=caster, ends=ends,
                      until=until, **data)
        self.add_effect(c)
        if self.game and not already:
            self.game.log.player("condition", f"{self.name} has the {name.title()} condition"
                                 + (f" ({source})" if source else ""), page=page)
        if name in INCAPACITATING or IMPLIES.get(name, set()) & INCAPACITATING:
            self._on_incapacitated()
        if name == "unconscious":
            if self.held:
                if self.game:
                    self.game.log.player("drop", f"{self.name} drops {', '.join(map(str, self.held))}",
                                         page=191)
                self.held = []
            self._drop_held()
        return c

    def _drop_held(self):
        pass

    def _on_incapacitated(self):
        if self.game:
            self.game.on_incapacitated(self)

    def remove_condition(self, name: str, source: str | None = None, reason: str = "") -> bool:
        removed = False
        for e in list(self.effects):
            if e.condition == name and (source is None or e.source == source):
                self.effects.remove(e)
                e.on_removed(self.game)
                removed = True
        if removed and self.game and not self.has(name):
            self.game.log.player("condition_end", f"{self.name} no longer has the {name.title()} condition"
                                 + (f" ({reason})" if reason else ""), page="176-191")
        return removed

    def gain_exhaustion(self, n: int = 1, source: str = "", page=181):
        if "exhaustion" in self.cond_immune:
            if self.game:
                self.game.log.player("immune", f"{self.name} is immune to Exhaustion", page=page)
            return
        self.exhaustion += n
        if source:
            self.exhaustion_sources[source] = self.exhaustion_sources.get(source, 0) + n
        if self.game:
            self.game.log.player("exhaustion", f"{self.name} gains {n} Exhaustion level"
                                 f"{'s' if n > 1 else ''} (now {self.exhaustion})"
                                 + (f" from {source}" if source else ""), page=page)
        if self.exhaustion >= 6:
            self.die("Exhaustion level 6")

    def lose_exhaustion(self, n: int = 1, source: str | None = None, reason="") -> int:
        """Remove exhaustion levels. Levels from a blocked source can't be removed."""
        blocked = sum(v for k, v in self.exhaustion_sources.items()
                      if k in self.notes.get("exhaustion_locked", set()))
        removable = max(0, self.exhaustion - blocked) if source is None else \
            self.exhaustion_sources.get(source, 0)
        take = min(n, removable)
        if take <= 0:
            return 0
        self.exhaustion -= take
        if source:
            self.exhaustion_sources[source] -= take
        else:
            # consume from unlocked sources first
            left = take
            for k in list(self.exhaustion_sources):
                if k in self.notes.get("exhaustion_locked", set()):
                    continue
                d = min(left, self.exhaustion_sources[k])
                self.exhaustion_sources[k] -= d
                left -= d
        if self.game:
            self.game.log.player("exhaustion", f"{self.name} loses {take} Exhaustion level"
                                 f"{'s' if take > 1 else ''} (now {self.exhaustion})"
                                 + (f" ({reason})" if reason else ""), page=181)
        return take

    # -- AC and speed ---------------------------------------------------------
    def base_ac(self) -> tuple[int, list[tuple[int, str]]]:
        if self.gear_ac is not None:
            return self.gear_ac, [(self.gear_ac, "stat block")]
        return 10 + self.mod("dex"), [(10, "base"), (self.mod("dex"), "Dex")]

    def ac(self) -> int:
        return sum(v for v, _ in self.ac_parts())

    def ac_parts(self) -> list[tuple[int, str]]:
        _, parts = self.base_ac()
        parts = list(parts)
        for e in self.effects:
            b = e.ac_bonus(self)
            if b:
                parts.append((b, e.source))
        return parts

    def speed(self, kind: str = "walk") -> int:
        base = self.speeds.get(kind, 0 if kind != "walk" else 0)
        if kind != "walk" and base == 0:
            return 0
        if any(e.speed_zero(self) for e in self.effects):
            return 0
        s = base
        for e in self.effects:
            s = e.speed(self, s)
        s -= 5 * self.exhaustion
        s = self.adjust_speed(s, kind)
        return max(0, s)

    def adjust_speed(self, s: int, kind: str) -> int:
        return s

    # -- D20 Tests -------------------------------------------------------------
    def gather(self, ctx: Ctx) -> Acc:
        acc = Acc()
        for e in list(self.effects):
            e.d20(ctx, acc)
        if ctx.target is not None and ctx.target is not self and hasattr(ctx.target, "effects"):
            for e in list(ctx.target.effects):
                e.as_target(ctx, acc)
        if self.exhaustion:
            acc.bonus(-2 * self.exhaustion, f"Exhaustion {self.exhaustion}")
        self.extra_gather(ctx, acc)
        if self.game:
            self.game.scene_gather(self, ctx, acc)
        return acc

    def extra_gather(self, ctx: Ctx, acc: Acc):
        """Hook for subclasses (armor training, class features ...)."""

    def skill_prof_bonus(self, skill: str | None, tool: str | None = None) -> tuple[int, str] | None:
        """Proficiency Bonus for a check (added once; Expertise doubles once)."""
        level = 0
        if skill and skill in self.skills:
            level = self.skills[skill]
        tool_prof = tool is not None and self.has_tool_prof(tool)
        if level == 2:
            return 2 * self.pb, f"PB×2 (Expertise: {skill.title()})"
        if level == 1 or tool_prof:
            what = skill.title() if level == 1 else tool
            return self.pb, f"PB ({what})"
        return None

    def has_tool_prof(self, tool: str) -> bool:
        from .rules import norm
        return norm(tool) in {norm(t) for t in self.tools}

    def check_modifier_parts(self, ability: str, skill: str | None = None,
                             tool: str | None = None) -> list[tuple[int, str]]:
        if skill and skill in self.skill_bonus_fixed and not tool:
            return [(self.skill_bonus_fixed[skill], f"{skill.title()} (stat block)")]
        parts = [(self.mod(ability), ABILITY_NAMES[ability][:3])]
        pb = self.skill_prof_bonus(skill, tool)
        if pb:
            parts.append(pb)
        return parts

    def check(self, skill: str | None = None, ability: str | None = None, dc: int | None = None,
              tool: str | None = None, tags=(), adv=(), dis=(), target=None, label=None,
              bonus=(), avoid=(), visibility=PLAYER, page="6", dice_bonus=()) -> D20Roll:
        if skill:
            skill = skill.lower()
            if skill not in SKILLS:
                raise Refusal(f"Unknown skill {skill!r}")
        ability = ability or (SKILLS[skill] if skill else None)
        if ability is None:
            raise Refusal("An ability check needs an ability or a skill")
        tags = set(tags)
        if skill == "perception":
            tags.add("sight") if "hearing" not in tags else None
        ctx = Ctx("check", self, ability=ability, skill=skill, tool=tool, target=target,
                  tags=tags, avoid=set(avoid))
        acc = self.gather(ctx)
        # p.9 Tool proficiency + skill proficiency on the same check -> Advantage
        if tool and self.has_tool_prof(tool) and skill and skill in self.skills:
            acc.advantage(f"proficient with both {tool} and {skill.title()}")
        name = label or (f"{ABILITY_NAMES[ability]} ({skill.title()}) check" if skill else
                         f"{ABILITY_NAMES[ability]} check")
        if tool:
            name += f" with {tool}"
        roll = D20Roll("check", name, self.name, target=dc)
        roll.mods = self.check_modifier_parts(ability, skill, tool) + list(bonus) + acc.mods
        roll.adv = acc.adv + list(adv)
        roll.dis = acc.dis + list(dis)
        roll.auto, roll.auto_reason = acc.auto, acc.auto_reason
        if acc.auto == "fail":
            roll.auto_reason = acc.auto_reason
            return self._finish(roll, acc, visibility, page, auto_only=True)
        return self._finish(roll, acc, visibility, page, list(dice_bonus))

    def _finish(self, roll, acc, visibility, page, bonus_dice=(), auto_only=False):
        for e in acc.consumed:
            if e.owner is not None:
                e.owner.remove_effect(e)
        if auto_only:
            return roll_d20_test(self.game, self, roll, page=page, visibility=visibility)
        roll.auto = None if roll.auto != "success" else roll.auto
        return roll_d20_test(self.game, self, roll, bonus_dice=list(acc.bonus_dice) + list(bonus_dice),
                             page=page, visibility=visibility)

    def save_modifier_parts(self, ability: str) -> list[tuple[int, str]]:
        if ability in self.save_bonus:
            return [(self.save_bonus[ability], f"{ABILITY_NAMES[ability][:3]} save (stat block)")]
        parts = [(self.mod(ability), ABILITY_NAMES[ability][:3])]
        if ability in self.save_profs:
            parts.append((self.pb, "PB"))
        return parts

    def save_bonus_total(self, ability: str) -> int:
        return sum(v for v, _ in self.save_modifier_parts(ability))

    def save(self, ability: str, dc: int, avoid=(), source=None, adv=(), dis=(), bonus=(),
             label=None, choose_to_fail=False, tags=(), visibility=PLAYER, page="7") -> D20Roll:
        name = label or f"{ABILITY_NAMES[ability]} saving throw"
        roll = D20Roll("save", name, self.name, target=dc)
        if choose_to_fail:
            roll.auto, roll.auto_reason = "fail", "chose to fail without rolling"
            return roll_d20_test(self.game, self, roll, page=187, visibility=visibility)
        if self.score(ability) is None:
            roll.auto, roll.auto_reason = "fail", "lacks the ability score"
            return roll_d20_test(self.game, self, roll, page=187, visibility=visibility)
        ctx = Ctx("save", self, ability=ability, avoid=set(avoid), source=source, tags=set(tags))
        acc = self.gather(ctx)
        roll.mods = self.save_modifier_parts(ability) + list(bonus) + acc.mods
        roll.adv = acc.adv + list(adv)
        roll.dis = acc.dis + list(dis)
        if acc.auto == "fail":
            roll.auto, roll.auto_reason = "fail", acc.auto_reason
            return self._finish(roll, acc, visibility, page, auto_only=True)
        if acc.auto == "success":
            roll.auto, roll.auto_reason = "success", acc.auto_reason
            return self._finish(roll, acc, visibility, page, auto_only=True)
        return self._finish(roll, acc, visibility, page)

    def skill_total(self, skill: str) -> int:
        return sum(v for v, _ in self.check_modifier_parts(SKILLS[skill], skill))

    def passive(self, skill: str = "perception", tags=()) -> int:
        """p.186: 10 + check bonus, +5 with Advantage, -5 with Disadvantage."""
        tags = set(tags) | ({"sight"} if skill == "perception" else set())
        ctx = Ctx("check", self, ability=SKILLS[skill], skill=skill, tags=tags)
        acc = self.gather(ctx)
        total = 10 + self.skill_total(skill) + sum(v for v, _ in acc.mods)
        if acc.adv and not acc.dis:
            total += 5
        elif acc.dis and not acc.adv:
            total -= 5
        return total

    # -- damage ----------------------------------------------------------------
    def damage_multiplier_parts(self, dtype: str) -> tuple[bool, bool, bool]:
        immune = dtype in self.immune
        resist = dtype in self.resist or "all" in self.resist or self.has("petrified")
        vuln = dtype in self.vuln
        for e in self.effects:
            f = getattr(e, "damage_traits", None)
            if f:
                r, v, i = f(self, dtype)
                resist, vuln, immune = resist or r, vuln or v, immune or i
        return resist, vuln, immune

    def adjust_damage(self, amount: int, dtype: str, reduction: int = 0) -> tuple[int, list[str]]:
        """p.17 order: modifiers (bonuses, penalties), then Resistance, then Vulnerability.
        Each is applied at most once per instance; damage can't go below 0."""
        notes = []
        resist, vuln, immune = self.damage_multiplier_parts(dtype)
        if immune:
            return 0, [f"Immunity to {dtype.title()}"]
        if reduction:
            amount = max(0, amount - reduction)
            notes.append(f"−{reduction} reduction")
        if resist:
            amount = div(amount, 2)
            notes.append(f"Resistance to {dtype.title()}")
        if vuln:
            amount = amount * 2
            notes.append(f"Vulnerability to {dtype.title()}")
        return max(0, amount), notes

    def take_damage(self, amount: int, dtype: str, attacker=None, crit=False, melee=False,
                    source: str = "", reduction: int = 0, adjusted=False, within5=False,
                    page="16-17") -> int:
        """Apply one instance of damage. Returns HP actually lost (incl. temp HP)."""
        if self.dead:
            return 0
        if adjusted:
            dealt, notes = amount, []
        else:
            dealt, notes = self.adjust_damage(amount, dtype, reduction)
        g = self.game
        src = f" from {source}" if source else ""
        msg = f"{self.name} takes {dealt} {dtype.title()} damage{src}"
        if notes:
            msg += f" ({amount} raw; {', '.join(notes)})"
        absorbed = 0
        if dealt > 0 and self.temp_hp > 0:
            absorbed = min(self.temp_hp, dealt)
            self.temp_hp -= absorbed
            msg += f"; {absorbed} absorbed by Temporary HP"
        rest = dealt - absorbed
        was_zero = self.hp == 0
        old = self.hp
        if g:
            g.log.player("damage", msg, page=page, target=self.id, amount=dealt, dtype=dtype,
                         raw=amount, crit=crit)
        if dealt <= 0:
            return 0
        if g:
            g.on_damaged(self, dealt)
        if rest > 0:
            if was_zero and self.is_pc():
                self._damage_at_zero(rest, crit)
            else:
                self.hp = max(0, self.hp - rest)
                if self.hp == 0:
                    self._drop_to_zero(rest - old, attacker, melee, dtype, crit, dealt)
        for e in list(self.effects):
            e.on_damaged(g, dealt, dtype, attacker, crit)
        if g and not self.dead and self.concentrating and dealt > 0:
            g.concentration_check(self, dealt)
        return dealt

    def _drop_to_zero(self, remainder, attacker, melee, dtype, crit, dealt):
        """Monsters die at 0 HP (p.17) unless a trait intervenes."""
        g = self.game
        for e in list(self.effects):
            hook = getattr(e, "at_zero_hp", None)
            if hook and hook(g, dealt, dtype, crit):
                return
        if melee and attacker is not None and g and g.decide(
                attacker, "knock_out", [True, False], default=False,
                prompt=f"Knock {self.name} out instead of killing it?"):
            self.knock_out()
            return
        self.die(f"reduced to 0 HP")

    def knock_out(self):
        """p.183 Knocking Out a Creature."""
        g = self.game
        self.hp = 1
        self.add_condition("unconscious", "knocked out")
        self.notes["knocked_out"] = True
        if g:
            g.log.player("knockout", f"{self.name} is knocked out: 1 HP, Unconscious, and starts a Short Rest",
                         page=183)

    def _damage_at_zero(self, amount, crit):
        pass

    def die(self, reason=""):
        if self.dead:
            return
        self.dead = True
        self.hp = 0
        if self.game:
            self.game.log.player("death", f"{self.name} dies" + (f" ({reason})" if reason else ""),
                                 page=17)
            self.game.on_death(self)

    def heal(self, amount: int, source: str = "", page="17") -> int:
        if self.dead:
            if self.game:
                self.game.log.player("heal", f"{self.name} is dead and can't regain Hit Points",
                                     page=180)
            return 0
        before = self.hp
        self.hp = min(self.max_hp, self.hp + max(0, amount))
        gained = self.hp - before
        if self.game:
            self.game.log.player("heal", f"{self.name} regains {gained} HP"
                                 + (f" from {source}" if source else "")
                                 + (f" ({amount} rolled, capped at max {self.max_hp})" if gained < amount else "")
                                 + f" → {self.hp}/{self.max_hp}", page=page, amount=gained)
        if before == 0 and self.hp > 0:
            self.regain_consciousness()
        return gained

    def regain_consciousness(self):
        self.stable = False
        self.death_saves = {"success": 0, "failure": 0}
        if self.notes.pop("dying", None) or self.notes.pop("knocked_out", None):
            for e in list(self.effects):
                if e.condition == "unconscious" and e.source in ("0 Hit Points", "knocked out", "dying"):
                    self.effects.remove(e)
            if self.game:
                self.game.log.player("conscious", f"{self.name} regains consciousness (still Prone)",
                                     page=191)
            if not self.has("prone"):
                self.add_condition("prone", "was Unconscious")

    def gain_temp_hp(self, amount: int, source: str = "") -> int:
        """p.18: Temporary HP don't stack; choose which to keep."""
        g = self.game
        if self.temp_hp > 0 and g:
            keep_new = g.decide(self, "temp_hp", [True, False], default=amount > self.temp_hp,
                                prompt=f"{self.name} has {self.temp_hp} temp HP; take {amount} instead?")
            if not keep_new:
                g.log.player("temp_hp", f"{self.name} keeps {self.temp_hp} Temporary HP (declines {amount})",
                             page=18)
                return self.temp_hp
        self.temp_hp = amount
        if g:
            g.log.player("temp_hp", f"{self.name} has {amount} Temporary HP"
                         + (f" from {source}" if source else ""), page=18)
        return self.temp_hp

    # -- misc ------------------------------------------------------------------
    def can_act(self) -> bool:
        return not self.dead and not self.has("incapacitated")

    def distance_to(self, other) -> int:
        from .geometry import distance
        return distance(self, other)

    def summary(self) -> str:
        cond = ", ".join(sorted(self.conditions())) or "none"
        return (f"{self.name}: HP {self.hp}/{self.max_hp}"
                + (f" (+{self.temp_hp} temp)" if self.temp_hp else "")
                + f", AC {self.ac()}, Speed {self.speed()}, conditions: {cond}"
                + (" [DEAD]" if self.dead else ""))

    def __repr__(self):
        return f"<{type(self).__name__} {self.name}>"
