"""Traps (Gameplay Toolbox p.199-201)."""
from __future__ import annotations

from . import actions
from .rules import Refusal, div

TRAPS = {
    "collapsing roof": {"detect": ("search", "perception", 11), "page": 199},
    "falling net": {"detect": ("search", "perception", 11), "page": 199},
    "hidden pit": {"detect": ("study", "investigation", 15), "page": 200, "depth": 10},
    "poisoned needle": {"detect": ("search", "perception", 15), "disarm": ("sleight of hand", 15), "page": 200},
    "spiked pit": {"detect": ("study", "investigation", 15), "page": 201, "depth": 10},
}


class Trap:
    def __init__(self, kind, location="", name=None):
        if kind not in TRAPS:
            from .rules import OutOfScope
            raise OutOfScope(f"The {kind} trap isn't in scope")
        self.kind = kind
        self.name = name or kind
        self.location = location
        self.detected = False
        self.disabled = False
        self.triggered = False
        self.data = TRAPS[kind]

    def __repr__(self):
        return f"<Trap {self.name}>"


def place(game, kind, location="", name=None):
    t = Trap(kind, location, name)
    game.scene.objects[t.name] = {"trap": t}
    return t


def get(game, name) -> Trap:
    o = game.scene.objects.get(name)
    if o is None or "trap" not in o:
        raise Refusal(f"There's no trap called {name!r}")
    return o["trap"]


def detect(game, c, trap: Trap, **kw):
    """Detection uses exactly what the trap specifies (exceptions supersede general rules, p.5)."""
    how, skill, dc = trap.data["detect"]
    if how == "study":
        r = actions.study(game, c, skill=skill, dc=dc, topic=f"examining the floor for a {trap.kind}", **kw)
    else:
        r = actions.search(game, c, skill=skill, dc=dc, what=f"examining for a {trap.kind}", **kw)
    if r.success:
        trap.detected = True
        game.log.player("trap", f"{c.name} detects the {trap.kind}", page=trap.data["page"])
    return r


def passive_detection(game, pcs, trap: Trap):
    """Only traps that are found with a Wisdom (Perception) Search can be noticed passively."""
    how, skill, dc = trap.data["detect"]
    if how != "search" or skill != "perception":
        game.log.gm("trap", f"The {trap.kind} can only be found with a {how.title()} action ({skill.title()} DC {dc}); "
                    f"Passive Perception doesn't reveal it", page=trap.data["page"])
        return None
    for c in pcs:
        if c.passive("perception") >= dc:
            trap.detected = True
            game.log.player("trap", f"{c.name} notices the {trap.kind}", page=trap.data["page"])
            return c
    return None


def wedge_spike(game, c, trap: Trap):
    if trap.kind not in ("hidden pit", "spiked pit"):
        raise Refusal("An Iron Spike doesn't disarm that trap")
    if not trap.detected:
        raise Refusal("You haven't found anything to wedge")
    if c.inventory.find("iron spikes") is None:
        raise Refusal(f"{c.name} has no Iron Spikes")
    c.inventory.remove("iron spikes", 1)
    trap.disabled = True
    game.log.player("trap", f"{c.name} wedges an Iron Spike under the lid: the {trap.kind} is safe to cross",
                    page=trap.data["page"])


def trigger(game, c, trap: Trap):
    if trap.disabled:
        game.log.player("trap", f"{c.name} crosses the disabled {trap.kind} safely", page=trap.data["page"])
        return None
    trap.triggered = True
    k = trap.kind
    game.log.player("trap", f"{c.name} triggers the {k}!", page=trap.data["page"])
    if k in ("hidden pit", "spiked pit"):
        r = game.dice.roll(6)
        game.log.player("trap", f"{c.name} falls {trap.data['depth']} ft into the pit: 1d6={r}", page=trap.data["page"])
        c.take_damage(r, "bludgeoning", source="the fall into the pit")
        if k == "spiked pit" and not c.dead:
            t, rolls, _ = game.dice.roll_expr("2d8")
            c.take_damage(t, "piercing", source="the spikes")
        if not c.dead:
            c.add_condition("prone", "fell into the pit")
        c.notes["in_pit"] = trap.name
    elif k == "collapsing roof":
        sv = c.save("dex", 13, label="Dexterity save vs the collapsing roof (DC 13)", page=199)
        t, rolls, _ = game.dice.roll_expr("2d10")
        c.take_damage(div(t, 2) if sv.success else t, "bludgeoning", source="falling rubble")
        game.scene.difficult = True
    elif k == "falling net":
        if c.size in ("huge", "gargantuan"):
            return None
        sv = c.save("dex", 10, label="Dexterity save vs the falling net (DC 10)", page=199)
        if not sv.success:
            c.add_condition("restrained", "falling net", escape_dc=10)
    elif k == "poisoned needle":
        sv = c.save("con", 11, avoid={"poisoned"}, label="Constitution save vs the poisoned needle (DC 11)", page=200)
        d = game.dice.roll(10)
        c.take_damage(div(d, 2) if sv.success else d, "poison", source="the poisoned needle")
        if not sv.success:
            c.add_condition("poisoned", "poisoned needle", until=game.clock + 3600)
    return True


def disarm(game, c, trap: Trap, bonus_action=False, **kw):
    """Disarm with Thieves' Tools (p.94 Utilize: disarm a trap, DC 15); failing triggers the needle."""
    if "disarm" not in trap.data:
        raise Refusal(f"The {trap.kind} can't be disarmed that way")
    if not trap.detected:
        raise Refusal("You have to find the trap before you can disarm it")
    if c.inventory.find("thieves' tools") is None:
        game.log.gm("ruling", f"{c.name} tries to disarm without Thieves' Tools: engine ruling R-04 applies the "
                    f"general check without the tool (no tool proficiency or Advantage)", ruling="R-04")
        skill, dc = trap.data["disarm"]
        if game.combat is not None:
            game.combat.spend(c, "action", "disarm")
        r = c.check(skill, dc=dc, label=f"Disarm the {trap.kind} without tools", **kw)
    else:
        r = actions.use_tool(game, c, "disarm a trap", bonus_action=bonus_action, **kw)
    if r.success:
        trap.disabled = True
        game.log.player("trap", f"{c.name} disarms the {trap.kind}", page=trap.data["page"])
    else:
        trigger(game, c, trap)
    return r


def climb_out(game, c):
    if not c.notes.get("in_pit"):
        raise Refusal(f"{c.name} isn't in a pit")
    has_gear = c.inventory.find("climber's kit") is not None if hasattr(c, "inventory") else False
    if c.speed("climb") > 0 or has_gear:
        c.notes.pop("in_pit")
        game.log.player("trap", f"{c.name} climbs out of the pit" + (" (Climb Speed)" if c.speed("climb") else
                                                                      " (climbing gear)"), page=200)
        return True
    raise Refusal(f"The pit's walls are smooth: {c.name} needs a Climb Speed, climbing gear or magic to get out",
                  page=200)
