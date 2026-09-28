"""Items, inventory, coins and carrying capacity (SRD p.89-103, 178)."""
from __future__ import annotations

import itertools

from .data.equipment import (AMMO_BUNDLE, ARMOR, GEAR, GP, PACKS, SHIELD, SP, TOOLS, WEAPONS,
                             canonical, item_cost, item_weight)
from .rules import Refusal, div

_ids = itertools.count(1)

COIN_VALUE = {"pp": 1000, "gp": 100, "ep": 50, "sp": 10, "cp": 1}


class Item:
    def __init__(self, name: str, qty: int = 1, **props):
        self.name = canonical(name)
        self.qty = qty
        self.uid = next(_ids)
        self.props = dict(props)
        base = self.props.get("base")          # magic items built on a mundane item
        self.base = canonical(base) if base else self.name
        if self.name == "healer's kit" and "uses" not in self.props:
            self.props["uses"] = 10

    # --- classification ---
    @property
    def kind(self) -> str:
        b = self.base
        if b in WEAPONS:
            return "weapon"
        if b in ARMOR:
            return "armor"
        if b == "shield":
            return "shield"
        if b in TOOLS:
            return "tool"
        if b in PACKS:
            return "pack"
        return self.props.get("kind", "gear")

    @property
    def weapon(self) -> dict | None:
        return WEAPONS.get(self.base)

    @property
    def armor(self) -> dict | None:
        return ARMOR.get(self.base)

    @property
    def magic_bonus(self) -> int:
        return self.props.get("bonus", 0)

    @property
    def magical(self) -> bool:
        return bool(self.props.get("magic"))

    @property
    def display(self) -> str:
        return self.props.get("title") or titlecase(self.name)

    def unit_weight(self) -> float:
        if "weight" in self.props:
            return self.props["weight"]
        return item_weight(self.base)

    def weight(self) -> float:
        return self.unit_weight() * self.qty

    def stackable(self) -> bool:
        return not self.props or set(self.props) <= {"kind"}

    def __repr__(self):
        return f"{self.display}" + (f" x{self.qty}" if self.qty != 1 else "")

    def __str__(self):
        return self.__repr__()

    def to_dict(self):
        return {"name": self.name, "qty": self.qty, **{k: v for k, v in self.props.items()
                                                       if isinstance(v, (int, str, float, bool, list, type(None)))}}


def titlecase(s: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in s.split())


class Inventory:
    def __init__(self):
        self.items: list[Item] = []

    def add(self, name_or_item, qty: int = 1, **props) -> Item:
        if isinstance(name_or_item, Item):
            it = name_or_item
            if it.stackable():
                ex = self.find(it.name, stack_only=True)
                if ex:
                    ex.qty += it.qty
                    return ex
            self.items.append(it)
            return it
        name = canonical(name_or_item)
        if name in PACKS:
            for n, q in PACKS[name]["contents"]:
                self.add(n, q * qty)
            return self.find(PACKS[name]["contents"][0][0])
        it = Item(name, qty, **props)
        return self.add(it)

    def find(self, name: str, stack_only=False) -> Item | None:
        n = canonical(name)
        for it in self.items:
            if (it.name == n or it.base == n or (it.props.get("title", "").lower() == name.lower())) and \
                    (not stack_only or it.stackable()):
                return it
        return None

    def find_all(self, name: str) -> list[Item]:
        n = canonical(name)
        return [it for it in self.items if it.name == n or it.base == n]

    def count(self, name: str) -> int:
        return sum(it.qty for it in self.find_all(name))

    def remove(self, name_or_item, qty: int = 1) -> Item:
        it = name_or_item if isinstance(name_or_item, Item) else self.find(name_or_item)
        if it is None or it.qty < qty:
            raise Refusal(f"You don't have {qty} × {name_or_item}")
        it.qty -= qty
        if it.qty <= 0:
            self.items.remove(it)
        return it

    def weight(self) -> float:
        return sum(it.weight() for it in self.items if not it.props.get("in_bag"))

    def __iter__(self):
        return iter(self.items)

    def __contains__(self, name):
        return self.find(name) is not None


class Purse:
    """Coins (p.89). Fifty coins weigh a pound."""

    def __init__(self, **coins):
        self.coins = {k: 0 for k in COIN_VALUE}
        self.coins.update(coins)

    def total_cp(self) -> int:
        return sum(COIN_VALUE[k] * v for k, v in self.coins.items())

    @property
    def gp(self) -> float:
        return self.total_cp() / 100

    def count(self) -> int:
        return sum(self.coins.values())

    def weight(self) -> float:
        return self.count() / 50

    def add(self, cp: int = 0, **coins):
        for k, v in coins.items():
            self.coins[k] += v
        if cp:
            gp, rest = divmod(cp, 100)
            sp, c = divmod(rest, 10)
            self.coins["gp"] += gp
            self.coins["sp"] += sp
            self.coins["cp"] += c

    def pay(self, cost_cp: int) -> dict:
        """Pay an amount; returns coin breakdown of what's left. Refuses if short."""
        total = self.total_cp()
        if cost_cp > total:
            raise Refusal(f"Not enough money: costs {fmt_cp(cost_cp)}, you have {fmt_cp(total)}")
        left = total - cost_cp
        self.coins = {k: 0 for k in COIN_VALUE}
        self.add(left)
        return dict(self.coins)

    def __str__(self):
        parts = [f"{v} {k.upper()}" for k, v in self.coins.items() if v]
        return ", ".join(parts) or "0 GP"


def make_change(paid_cp: int, cost_cp: int) -> dict:
    if paid_cp < cost_cp:
        raise Refusal("That doesn't cover the cost")
    left = paid_cp - cost_cp
    gp, r = divmod(left, 100)
    sp, cp = divmod(r, 10)
    return {"gp": gp, "sp": sp, "cp": cp}


def fmt_cp(cp: int) -> str:
    gp, r = divmod(cp, 100)
    sp, c = divmod(r, 10)
    parts = []
    if gp:
        parts.append(f"{gp} GP")
    if sp:
        parts.append(f"{sp} SP")
    if c:
        parts.append(f"{c} CP")
    return " ".join(parts) or "0 GP"


def sale_price(name: str) -> int:
    """p.89: equipment sells for half its cost (trade goods keep full value)."""
    c = item_cost(canonical(name))
    if c is None:
        raise Refusal(f"Unknown item {name!r}")
    return div(c, 2)


def carrying_capacity(size: str, strength: int) -> tuple[float, float]:
    """p.178: (carry, drag/lift/push) in pounds."""
    mult = {"tiny": 7.5, "small": 15, "medium": 15, "large": 30, "huge": 60, "gargantuan": 120}[size]
    return strength * mult, strength * mult * 2
