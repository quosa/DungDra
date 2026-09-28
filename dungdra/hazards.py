"""Hazards (glossary: Burning, Dehydration, Falling, Malnutrition, Suffocation)
and poisons (Gameplay Toolbox p.197-198)."""
from __future__ import annotations

from .effects import Effect
from .rules import MINUTE, ROUND, Refusal, div


# -- Falling (p.182) ---------------------------------------------------------------
def fall(game, c, feet: int, into_water=False, use_reaction=True):
    n = min(20, feet // 10)
    if n == 0:
        return 0
    halve = False
    if into_water and use_reaction and c.can_act():
        if game.combat is None or game.combat.has_reaction(c):
            if game.combat is not None:
                game.combat.spend(c, "reaction")
            skill = "athletics" if c.skill_total("athletics") >= c.skill_total("acrobatics") else "acrobatics"
            r = c.check(skill, dc=15, label=f"{skill.title()} check to hit the water feet or head first (DC 15)",
                        page=182)
            halve = r.success
    rolls = game.dice.roll_many(n, 6)
    dmg = sum(rolls)
    if halve:
        dmg = div(dmg, 2)
    game.log.player("fall", f"{c.name} falls {feet} ft: {n}d6={rolls}" + (" halved (good water entry)" if halve else ""),
                    page=182)
    dealt = c.take_damage(dmg, "bludgeoning", source="falling")
    if dealt > 0 and not c.dead:
        c.add_condition("prone", "fell")
    return dealt


# -- Suffocation (p.189) -------------------------------------------------------------
def breath_seconds(c) -> int:
    minutes = 1 + c.mod("con")
    return max(30, minutes * MINUTE)


class HoldingBreath(Effect):
    name = "holding breath"

    def __init__(self, start, **kw):
        super().__init__("Holding breath", **kw)
        self.start = start

    def on_turn_end(self, game):
        o = self.owner
        if game.clock - self.start >= breath_seconds(o):
            o.gain_exhaustion(1, "suffocation", page=189)


def start_holding_breath(game, c):
    e = HoldingBreath(game.clock)
    c.add_effect(e)
    game.log.player("hazard", f"{c.name} holds their breath: {breath_seconds(c) // 60} minutes before suffocating",
                    page=189)
    return e


def breathe_again(game, c):
    for e in list(c.effects):
        if isinstance(e, HoldingBreath):
            c.effects.remove(e)
    n = c.exhaustion_sources.get("suffocation", 0)
    if n:
        c.lose_exhaustion(n, source="suffocation", reason="can breathe again")


# -- Food and water (p.181, 185) --------------------------------------------------------
def end_of_day_food(game, c, food_fraction: float):
    """food_fraction: fraction of the day's food eaten (0 = nothing)."""
    locked = c.notes.setdefault("exhaustion_locked", set())
    if food_fraction >= 1:
        c.food_days_without = 0
        locked.discard("malnutrition")
        n = c.exhaustion_sources.get("malnutrition", 0)
        return
    locked.add("malnutrition")
    if food_fraction == 0:
        c.food_days_without = getattr(c, "food_days_without", 0) + 1
        if c.food_days_without >= 5:
            c.gain_exhaustion(1, "malnutrition", page=185)
        else:
            game.log.player("hazard", f"{c.name} has eaten nothing for {c.food_days_without} day(s)", page=185)
    elif food_fraction < 0.5:
        r = c.save("con", 10, label="Constitution save vs malnutrition (DC 10)", page=185)
        if not r.success:
            c.gain_exhaustion(1, "malnutrition", page=185)


def end_of_day_water(game, c, water_fraction: float):
    locked = c.notes.setdefault("exhaustion_locked", set())
    if water_fraction >= 1:
        locked.discard("dehydration")
        return
    if water_fraction < 0.5:
        locked.add("dehydration")
        c.gain_exhaustion(1, "dehydration", page=181)


# -- Burning (p.178) ---------------------------------------------------------------------
class Burning(Effect):
    name = "burning"

    def on_turn_start(self, game):
        r = game.dice.roll(4)
        game.log.player("hazard", f"{self.owner.name} is burning: 1d4={r} Fire damage", page=178)
        self.owner.take_damage(r, "fire", source="burning")


def set_burning(game, c):
    if not c.find_effects(cls=Burning):
        c.add_effect(Burning("Burning"))
        game.log.player("hazard", f"{c.name} starts burning", page=178)


def extinguish_by_rolling(game, c):
    if not c.find_effects(cls=Burning):
        raise Refusal(f"{c.name} isn't burning")
    if game.combat is not None:
        game.combat.spend(c, "action", "drop Prone and roll")
    c.add_condition("prone", "rolling to put out flames")
    for e in c.find_effects(cls=Burning):
        c.remove_effect(e, "rolled on the ground")


# -- Poisons (p.197-198) -----------------------------------------------------------------
POISONS = {
    "serpent venom": {"type": "injury", "dc": 11, "damage": "3d6", "half": True, "poisoned": None, "cost": 200},
    "basic poison": {"type": "injury", "extra": "1d4", "cost": 100},
}


def apply_poison_to_weapon(game, c, weapon_name: str, poison="serpent venom"):
    it = c.inventory.find(weapon_name)
    if it is None:
        raise Refusal(f"{c.name} has no {weapon_name}")
    dose = c.inventory.find(poison)
    if dose is None:
        raise Refusal(f"{c.name} has no {poison}")
    if game.combat is not None:
        game.combat.spend(c, "bonus", f"apply {poison}")
    c.inventory.remove(dose, 1)
    it.props["coating"] = poison
    warn = "" if it.weapon and it.weapon["dtype"] in ("piercing", "slashing") else \
        f" (it deals {it.weapon['dtype'].title()} damage, so the poison will never be delivered)"
    game.log.player("poison", f"{c.name} coats the {it.display} with {poison.title()} (Bonus Action){warn}", page=197)


def trigger_coating(game, attacker, target, item):
    poison = item.props.pop("coating")
    game.log.player("poison", f"The {poison.title()} on the {item.display} enters {target.name}'s wound", page=197)
    expose(game, target, poison)


def expose(game, target, poison):
    p = POISONS[poison]
    if "dc" in p:
        avoid = {"poisoned"} if p.get("poisoned") else set()
        r = target.save("con", p["dc"], avoid=avoid, label=f"Constitution save vs {poison.title()} (DC {p['dc']})",
                        page=198)
        total, rolls, _ = game.dice.roll_expr(p["damage"])
        dmg = div(total, 2) if r.success and p.get("half") else (0 if r.success else total)
        game.log.player("poison", f"{poison.title()}: {p['damage']}={rolls}" + (" halved" if r.success else ""), page=198)
        target.take_damage(dmg, "poison", source=poison.title())
    else:
        total, rolls, _ = game.dice.roll_expr(p["extra"])
        target.take_damage(total, "poison", source=poison.title())
