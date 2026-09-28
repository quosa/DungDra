"""D20 Tests (SRD p.6-8): ability checks, saving throws, attack rolls.

Handles Advantage/Disadvantage (they don't stack; any mix cancels), natural
20/1 on attack rolls only, and rerolls (Heroic Inspiration p.8, Halfling Luck
p.86): only one die of an Advantage/Disadvantage pair is rerolled, chosen by
the player, and the new roll must be used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .events import PLAYER
from .rules import fmt_mod


@dataclass
class D20Roll:
    kind: str                  # 'check', 'save', 'attack', 'initiative', 'death save'
    label: str
    actor: str
    dice: list[int] = field(default_factory=list)
    mode: str = "normal"       # 'normal' | 'advantage' | 'disadvantage'
    adv: list[str] = field(default_factory=list)
    dis: list[str] = field(default_factory=list)
    mods: list[tuple[int, str]] = field(default_factory=list)
    target: int | None = None  # DC or AC
    auto: str | None = None    # 'fail' | 'success' (e.g. Paralyzed Str save)
    auto_reason: str = ""
    rerolls: list[str] = field(default_factory=list)
    crit_on: int = 20
    chosen: int | None = None  # d20 value used

    @property
    def natural(self) -> int | None:
        return self.chosen

    @property
    def modifier(self) -> int:
        return sum(v for v, _ in self.mods)

    @property
    def total(self) -> int:
        if self.chosen is None:
            return 0
        return self.chosen + self.modifier

    @property
    def crit(self) -> bool:
        return self.kind == "attack" and self.chosen is not None and self.chosen >= self.crit_on \
            and self.auto != "fail"

    @property
    def success(self) -> bool | None:
        if self.auto == "fail":
            return False
        if self.auto == "success":
            return True
        if self.target is None:
            return None
        if self.kind == "attack":
            if self.chosen == 1:
                return False     # p.7 natural 1 misses
            if self.chosen is not None and self.chosen >= self.crit_on:
                return True      # p.7 natural 20 (or expanded crit range) hits
        return self.total >= self.target

    def add_mod(self, value: int, source: str):
        self.mods.append((value, source))

    def describe(self) -> str:
        if self.auto and self.chosen is None:
            res = "success" if self.auto == "success" else "failure"
            return f"{self.actor} {self.label}: automatic {res} ({self.auto_reason})"
        dice = "/".join(str(d) for d in self.dice)
        parts = [f"d20={self.chosen}" + (f" ({self.mode}: {dice})" if len(self.dice) > 1 else "")]
        for v, src in self.mods:
            parts.append(f"{fmt_mod(v)} {src}")
        s = f"{self.actor} {self.label}: " + " ".join(parts) + f" = {self.total}"
        if self.target is not None:
            tgt = "AC" if self.kind == "attack" else "DC"
            s += f" vs {tgt} {self.target}"
            if self.kind == "attack":
                s += " → " + ("CRITICAL HIT" if self.crit and self.success else
                                   "hit" if self.success else "miss")
            else:
                s += " → " + ("success" if self.success else "failure")
        if self.adv:
            s += f"; Advantage from {', '.join(self.adv)}"
        if self.dis:
            s += f"; Disadvantage from {', '.join(self.dis)}"
        if self.rerolls:
            s += f"; rerolls: {', '.join(self.rerolls)}"
        return s

    def to_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label, "actor": self.actor,
                "dice": self.dice, "mode": self.mode, "adv": self.adv, "dis": self.dis,
                "mods": self.mods, "target": self.target, "chosen": self.chosen,
                "total": self.total, "success": self.success, "crit": self.crit,
                "auto": self.auto, "rerolls": self.rerolls}


def resolve_mode(adv: list[str], dis: list[str]) -> str:
    """p.8: any mix of Advantage and Disadvantage cancels out."""
    if adv and dis:
        return "normal"
    if adv:
        return "advantage"
    if dis:
        return "disadvantage"
    return "normal"


def choose(dice: list[int], mode: str) -> int:
    if mode == "advantage":
        return max(dice)
    if mode == "disadvantage":
        return min(dice)
    return dice[0]


def roll_d20_test(game, actor, roll: D20Roll, bonus_dice=(), page="6-8",
                  visibility=PLAYER, allow_rerolls=True) -> D20Roll:
    """Roll a prepared D20Roll: dice, rerolls, bonus dice. Logs the result."""
    if roll.auto and roll.auto in ("fail", "success") and roll.chosen is None and roll.auto_reason:
        game.log.add(roll.kind, roll.describe(), visibility, page=page, roll=roll.to_dict())
        return roll
    roll.mode = resolve_mode(roll.adv, roll.dis)
    n = 1 if roll.mode == "normal" else 2
    roll.dice = game.dice.roll_many(n, 20)

    if allow_rerolls and actor is not None:
        # Halfling Luck (p.86): reroll a d20 showing 1 on a D20 Test; offered, never automatic.
        if actor.has_trait("luck") and 1 in roll.dice:
            if game.decide(actor, "luck", [True, False], default=False,
                           prompt=f"{actor.name} rolled a 1 ({roll.label}). Use Luck to reroll it?"):
                i = roll.dice.index(1)
                old = roll.dice[i]
                roll.dice[i] = game.dice.d20()
                roll.rerolls.append(f"Luck {old}→{roll.dice[i]}")
        # Heroic Inspiration (p.8): reroll one die, chosen by the player.
        if getattr(actor, "heroic_inspiration", False):
            opts = [None] + list(range(len(roll.dice)))
            pick = game.decide(actor, "inspiration", opts, default=None,
                               prompt=f"{actor.name} rolled {roll.dice} ({roll.label}). "
                                      f"Spend Heroic Inspiration to reroll a die? (index or no)")
            if pick is not None and pick is not False:
                if pick is True:
                    pick = roll.dice.index(min(roll.dice))
                old = roll.dice[pick]
                roll.dice[pick] = game.dice.d20()
                actor.heroic_inspiration = False
                roll.rerolls.append(f"Heroic Inspiration {old}→{roll.dice[pick]}")
                game.log.player("inspiration", f"{actor.name} spends Heroic Inspiration", page=8)

    roll.chosen = choose(roll.dice, roll.mode)
    for expr, src in bonus_dice:
        total, rolled, _ = game.dice.roll_expr(expr)
        sign = -1 if src.startswith("-") else 1
        roll.add_mod(sign * total, f"{src.lstrip('-')} ({expr}={rolled})")
    game.log.add(roll.kind, roll.describe(), visibility, page=page, roll=roll.to_dict())
    return roll
