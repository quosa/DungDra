"""Effects: the hook system every rule plugs into.

An Effect is attached to a creature (conditions, features, spell effects,
weapon-mastery riders ...). The engine asks effects about D20 Tests the owner
makes (`d20`), D20 Tests aimed at the owner (`as_target`), AC, Speed, and
notifies them of turn boundaries and damage.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

_ids = itertools.count(1)


@dataclass
class Ctx:
    """Context of a D20 Test."""
    kind: str                       # 'check' | 'save' | 'attack' | 'initiative' | 'death save'
    actor: Any = None
    ability: str | None = None
    skill: str | None = None
    tool: str | None = None
    target: Any = None
    melee: bool = False
    ranged: bool = False
    weapon: Any = None
    spell: Any = None
    distance: int | None = None
    tags: set = field(default_factory=set)    # 'sight', 'hearing', 'social', 'initiative' ...
    avoid: set = field(default_factory=set)   # conditions a save/check avoids or ends
    source: Any = None                         # creature that caused the save

    @property
    def is_attack(self):
        return self.kind == "attack"


class Acc:
    """Accumulates modifiers gathered from effects for one D20 Test."""

    def __init__(self):
        self.adv: list[str] = []
        self.dis: list[str] = []
        self.mods: list[tuple[int, str]] = []
        self.bonus_dice: list[tuple[str, str]] = []
        self.auto: str | None = None
        self.auto_reason: str = ""
        self.ac: list[tuple[int, str]] = []        # AC adjustments (attack vs owner)
        self.auto_crit: list[str] = []
        self.consumed: list = []                  # effects to remove if the roll happens

    def advantage(self, src):
        if src not in self.adv:
            self.adv.append(src)

    def disadvantage(self, src):
        if src not in self.dis:
            self.dis.append(src)

    def bonus(self, v, src):
        self.mods.append((v, src))

    def dice(self, expr, src):
        self.bonus_dice.append((expr, src))

    def fail(self, reason):
        if self.auto != "fail":
            self.auto, self.auto_reason = "fail", reason

    def succeed(self, reason):
        if self.auto is None:
            self.auto, self.auto_reason = "success", reason


class Effect:
    name = "effect"
    condition: str | None = None     # set when this effect *is* a condition
    page = None

    def __init__(self, source: str = "", caster=None, concentration=False,
                 ends=None, until=None, **data):
        self.id = next(_ids)
        self.source = source or self.name
        self.caster_id = getattr(caster, "id", caster)
        self.concentration = concentration
        self.ends = list(ends or [])       # [('start'|'end', creature_id)]
        self.until = until                 # absolute game time (s) at which it expires
        self.owner = None
        self.data = data

    # -- hooks (defaults do nothing) ------------------------------------
    def d20(self, ctx: Ctx, acc: Acc):
        pass

    def as_target(self, ctx: Ctx, acc: Acc):
        pass

    def ac_bonus(self, owner) -> int:
        return 0

    def speed(self, owner, speed: int) -> int:
        return speed

    def speed_zero(self, owner) -> bool:
        return False

    def on_turn_start(self, game):
        pass

    def on_turn_end(self, game):
        pass

    def on_damaged(self, game, amount: int, dtype: str, attacker=None, crit=False):
        pass

    def on_attack_roll(self, game, roll, ctx):
        """Called after the owner makes an attack roll."""

    def on_removed(self, game):
        pass

    def describe(self) -> str:
        return self.source

    def __repr__(self):
        return f"<{type(self).__name__} {self.source}>"


# ---------------------------------------------------------------------------
# Conditions (Rules Glossary p.176-191)
# ---------------------------------------------------------------------------

INCAPACITATING = {"incapacitated", "paralyzed", "petrified", "stunned", "unconscious"}
IMPLIES = {
    "paralyzed": {"incapacitated"},
    "petrified": {"incapacitated"},
    "stunned": {"incapacitated"},
    "unconscious": {"incapacitated", "prone"},
}


def _within5(ctx):
    return ctx.distance is not None and ctx.distance <= 5


class Condition(Effect):
    page = "176-191"

    def __init__(self, name: str, source: str = "", **kw):
        super().__init__(source or name.title(), **kw)
        self.condition = name
        self.name = name

    # ---- d20 tests made by the owner
    def d20(self, ctx, acc):
        n = self.condition
        o = self.owner
        if n == "blinded":
            if ctx.kind == "check" and "sight" in ctx.tags:
                acc.fail("Blinded: can't see")
        elif n == "deafened":
            if ctx.kind == "check" and "hearing" in ctx.tags:
                acc.fail("Deafened: can't hear")
        elif n == "frightened":
            if ctx.kind in ("check", "attack") and _source_in_sight(o, self):
                acc.disadvantage("Frightened")
        elif n == "grappled":
            grappler = self.data.get("grappler")
            if ctx.kind == "attack" and ctx.target is not None and ctx.target.id != grappler:
                acc.disadvantage("Grappled (attacking someone other than the grappler)")
        elif n == "incapacitated":
            if ctx.kind == "initiative":
                acc.disadvantage("Incapacitated")
        elif n == "invisible":
            if ctx.kind == "initiative":
                acc.advantage("Invisible")
        elif n in ("paralyzed", "stunned", "unconscious", "petrified"):
            if ctx.kind == "save" and ctx.ability in ("str", "dex"):
                acc.fail(f"{n.title()}: automatically fails Str and Dex saves")
        elif n == "poisoned":
            if ctx.kind in ("attack", "check"):
                acc.disadvantage("Poisoned")
        elif n == "prone":
            if ctx.kind == "attack":
                acc.disadvantage("Prone")
        elif n == "restrained":
            if ctx.kind == "attack":
                acc.disadvantage("Restrained")
            if ctx.kind == "save" and ctx.ability == "dex":
                acc.disadvantage("Restrained")

    # ---- attack rolls (and social checks) aimed at the owner
    def as_target(self, ctx, acc):
        n = self.condition
        o = self.owner
        if ctx.kind == "attack":
            # Blinded/Invisible attack effects are resolved by the attack code's
            # "can see" test (p.14 Unseen Attackers and Targets).
            if n in ("paralyzed", "stunned", "unconscious", "petrified", "restrained"):
                acc.advantage(f"target {o.name} is {n.title()}")
                if n in ("paralyzed", "unconscious") and _within5(ctx):
                    acc.auto_crit.append(f"{n.title()} target within 5 ft")
            elif n == "prone":
                if _within5(ctx):
                    acc.advantage(f"target {o.name} is Prone (attacker within 5 ft)")
                else:
                    acc.disadvantage(f"target {o.name} is Prone (attacker beyond 5 ft)")
        elif ctx.kind == "check" and n == "charmed" and "social" in ctx.tags:
            if ctx.actor is not None and ctx.actor.id == self.caster_id:
                acc.advantage(f"{o.name} is Charmed by {ctx.actor.name}")

    def speed_zero(self, owner):
        return self.condition in ("grappled", "paralyzed", "petrified", "restrained", "unconscious")


def _source_in_sight(owner, eff) -> bool:
    game = getattr(owner, "game", None)
    if game is None or eff.caster_id is None:
        return True
    src = game.creatures.get(eff.caster_id)
    if src is None:
        return False
    return game.line_of_sight(owner, src)


def can_see(viewer, target) -> bool:
    """Whether `viewer` can see `target` (Invisible, Blinded, Darkness, senses)."""
    if viewer is None or target is None:
        return True
    game = getattr(viewer, "game", None)
    if game is not None:
        return game.can_see(viewer, target)
    return not target.has("invisible") and not viewer.has("blinded")


def _sees_by_other_means(viewer, target) -> bool:
    if viewer is None:
        return False
    return viewer.senses.get("blindsight", 0) > 0 or viewer.senses.get("truesight", 0) > 0


# ---------------------------------------------------------------------------
# Generic, reusable effects
# ---------------------------------------------------------------------------

class AdvNext(Effect):
    """Advantage (or Disadvantage) on the owner's next matching D20 Test.

    Used by Help (checks), Vex, Steady Aim, Sap (disadvantage) ...
    kinds: which roll kinds it applies to; skill/tool/target filters optional.
    """
    name = "next roll"

    def __init__(self, source, kinds=("attack",), mode="adv", skill=None, tool=None,
                 target=None, **kw):
        super().__init__(source, **kw)
        self.kinds = set(kinds)
        self.mode = mode
        self.skill = skill
        self.tool = tool
        self.target_id = getattr(target, "id", target)

    def matches(self, ctx):
        if ctx.kind not in self.kinds:
            return False
        if self.skill and ctx.skill != self.skill and not (self.tool and ctx.tool == self.tool):
            return False
        if self.tool and not self.skill and ctx.tool != self.tool:
            return False
        if self.target_id and (ctx.target is None or ctx.target.id != self.target_id):
            return False
        return True

    def d20(self, ctx, acc):
        if self.matches(ctx):
            (acc.advantage if self.mode == "adv" else acc.disadvantage)(self.source)
            acc.consumed.append(self)


class HelpAttack(Effect):
    """Help: Assist an Attack Roll (p.183). Placed on the enemy; the next attack
    roll by one of the helper's allies against it has Advantage."""
    name = "Help (attack)"

    def as_target(self, ctx, acc):
        helper = self.owner.game.creatures.get(self.caster_id) if self.owner.game else None
        if ctx.kind == "attack" and ctx.actor is not None and helper is not None \
                and ctx.actor.id != helper.id and ctx.actor.team == helper.team:
            acc.advantage(self.source)
            acc.consumed.append(self)


class Dodge(Effect):
    """Dodge action (p.181)."""
    name = "Dodge"

    def active(self):
        o = self.owner
        return not o.has("incapacitated") and o.speed() > 0

    def as_target(self, ctx, acc):
        if ctx.kind == "attack" and self.active() and can_see(self.owner, ctx.actor):
            acc.disadvantage(f"{self.owner.name} is Dodging")

    def d20(self, ctx, acc):
        if ctx.kind == "save" and ctx.ability == "dex" and self.active():
            acc.advantage("Dodge")


class Flag(Effect):
    """A named marker effect with optional expiry (Disengage, Sap, Slow, ...)."""

    def __init__(self, name, source="", **kw):
        super().__init__(source or name, **kw)
        self.name = name


class SpeedPenalty(Effect):
    """Reduce Speed by N feet (Slow mastery, Ray of Frost). Named effects of the
    same `group` don't stack."""

    def __init__(self, source, amount, group=None, **kw):
        super().__init__(source, **kw)
        self.amount = amount
        self.group = group or source
        self.name = self.group

    def speed(self, owner, speed):
        # Only the first penalty of a group applies (no stacking past the amount).
        first = next(e for e in owner.effects if isinstance(e, SpeedPenalty) and e.group == self.group)
        return speed - self.amount if first is self else speed


class ACBonus(Effect):
    def __init__(self, source, amount, **kw):
        super().__init__(source, **kw)
        self.amount = amount
        self.name = source

    def ac_bonus(self, owner):
        return self.amount


class SaveBonus(Effect):
    """Flat bonus to saving throws (Cloak of Protection)."""

    def __init__(self, source, amount, **kw):
        super().__init__(source, **kw)
        self.amount = amount
        self.name = source

    def d20(self, ctx, acc):
        if ctx.kind == "save":
            acc.bonus(self.amount, self.source)


class Trait(Effect):
    """A permanent feature hook built from simple declarative rules."""

    def __init__(self, name, fn_d20=None, fn_target=None, **kw):
        super().__init__(name, **kw)
        self.name = name
        self._d20 = fn_d20
        self._target = fn_target

    def d20(self, ctx, acc):
        if self._d20:
            self._d20(self, ctx, acc)

    def as_target(self, ctx, acc):
        if self._target:
            self._target(self, ctx, acc)
