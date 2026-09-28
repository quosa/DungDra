"""Dice with forced-result injection (harness contract §2.1.1).

Forced results are queued per die type and consumed in order; once a queue is
empty the seeded RNG takes over.
"""
from __future__ import annotations

import random
import re
from collections import defaultdict, deque

DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$")


class Dice:
    def __init__(self, seed: int | None = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.forced: dict[int, deque] = defaultdict(deque)
        self.history: list[tuple[int, int, bool]] = []  # (sides, value, forced)

    # -- injection -------------------------------------------------------
    def force(self, spec: str | int, values) -> None:
        """Queue forced results, e.g. force('d20', [11, 4]) or force(20, [11])."""
        sides = parse_sides(spec)
        for v in values:
            if not 1 <= v <= sides:
                raise ValueError(f"forced d{sides} value {v} out of range")
            self.forced[sides].append(v)

    def force_str(self, text: str) -> None:
        """Parse scenario notation: 'd20=[11,4]; d8=[5]'."""
        for part in text.split(";"):
            part = part.strip()
            if not part:
                continue
            die, _, vals = part.partition("=")
            vals = vals.strip().strip("[]")
            self.force(die.strip(), [int(v) for v in vals.split(",") if v.strip()])

    def pending(self, spec) -> int:
        return len(self.forced[parse_sides(spec)])

    def clear(self) -> None:
        self.forced.clear()

    # -- rolling ---------------------------------------------------------
    def roll(self, sides: int) -> int:
        q = self.forced.get(sides)
        if q:
            v = q.popleft()
            self.history.append((sides, v, True))
            return v
        v = self.rng.randint(1, sides)
        self.history.append((sides, v, False))
        return v

    def roll_many(self, n: int, sides: int) -> list[int]:
        return [self.roll(sides) for _ in range(n)]

    def d20(self) -> int:
        return self.roll(20)

    def roll_expr(self, expr: str) -> tuple[int, list[int], int]:
        """Roll 'NdS+M'. Returns (total, dice, modifier)."""
        n, s, m = parse_expr(expr)
        rolls = self.roll_many(n, s)
        return sum(rolls) + m, rolls, m

    # -- persistence -----------------------------------------------------
    def to_dict(self) -> dict:
        return {"seed": self.seed, "state": repr(self.rng.getstate()),
                "forced": {str(k): list(v) for k, v in self.forced.items() if v}}

    @classmethod
    def from_dict(cls, d: dict) -> "Dice":
        dice = cls(d.get("seed"))
        import ast
        st = ast.literal_eval(d["state"])
        dice.rng.setstate(st)
        for k, v in d.get("forced", {}).items():
            dice.forced[int(k)].extend(v)
        return dice


def parse_sides(spec) -> int:
    if isinstance(spec, int):
        return spec
    s = str(spec).strip().lower()
    s = s.split("d")[-1]
    return int(s)


def parse_expr(expr: str) -> tuple[int, int, int]:
    m = DICE_RE.match(str(expr))
    if not m:
        raise ValueError(f"bad dice expression {expr!r}")
    n = int(m.group(1) or 1)
    s = int(m.group(2))
    mod = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    return n, s, mod


def average(expr: str) -> int:
    n, s, m = parse_expr(expr)
    return (n * (s + 1)) // 2 + m
