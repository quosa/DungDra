"""A small campaign, "The Goblin Trail", built only from subset content.

Scenes are data; the engine resolves everything. Danger is conveyed in the
fiction; encounter budgets stay in the GM log (R-03).
"""
from __future__ import annotations

import re

from . import combat as C, encounters as E, gm, magic_items as MI, traps as T
from .monster import Monster
from .rules import Refusal

SCENES = [
    {
        "id": "village",
        "name": "Millbrook",
        "text": ("Millbrook's square smells of bread and woodsmoke. The reeve has posted a notice: goblins have been "
                 "raiding carts on the forest road east of the village, and whoever clears the old watchtower they "
                 "use as a lair will be paid in coin. The general store is open if you need supplies."),
        "light": "bright", "sunlight": True,
        "next": "road",
    },
    {
        "id": "road",
        "name": "The Forest Road",
        "text": ("The road east narrows between old oaks. Six miles on, the trees crowd close and the birdsong "
                 "stops. Broken cart wheels lie in the ditch."),
        "travel": {"miles": 6, "pace": "normal", "terrain": "forest", "road": True},
        "ambush": {"monsters": ["goblin warrior"] * 4, "hide_total": 16,
                   "positions": [(30, 10), (35, -10), (40, 10), (45, -10)],
                   "text": "Arrows hiss out of the undergrowth: goblins, hidden in the ferns!"},
        "light": "bright", "sunlight": True,
        "next": "clearing",
    },
    {
        "id": "clearing",
        "name": "A Quiet Clearing",
        "text": "Past the ambush site, a mossy clearing offers a moment's peace, a good place for a short rest.",
        "light": "bright", "next": "tower",
    },
    {
        "id": "tower",
        "name": "The Ruined Watchtower",
        "text": ("The watchtower's lower hall is dim and dusty. The flagstones ahead look oddly uniform, and against "
                 "the far wall sits an iron-bound chest with a heavy lock."),
        "light": "dim", "traps": [("hidden pit", "the hall floor"), ("poisoned needle", "the chest lock")],
        "loot": {"items": ["potion of healing"], "gp": 30},
        "next": "lair",
    },
    {
        "id": "lair",
        "name": "The Goblin Lair",
        "text": ("Stairs lead down into a torchlit cellar that stinks of wet fur. A goblin in a dented chain shirt "
                 "barks orders from a crate throne, flanked by two warriors."),
        "encounter": {"monsters": ["goblin boss", "goblin warrior", "goblin warrior"],
                      "positions": [(40, 0), (35, 5), (35, -5)]},
        "light": "bright",
        "next": None,
        "ending": "With the lair cleared, the forest road is safe again. The reeve of Millbrook pays your reward.",
    },
]


class Adventure:
    def __init__(self, session, scenes=None):
        self.session = session
        self.scenes = {s["id"]: s for s in (scenes or SCENES)}
        self.order = [s["id"] for s in (scenes or SCENES)]
        self.current = None
        self.loot_taken = set()

    @property
    def game(self):
        return self.session.game

    def start(self):
        return self.enter(self.order[0])

    def describe(self):
        s = self.scenes[self.current]
        return f"{s['name']}\n{s['text']}\n{self.exits_text()}"

    def exits_text(self):
        nxt = self.scenes[self.current].get("next")
        if nxt is None:
            return "(This is the end of the road.)"
        return f"(Say 'continue' or 'go to {self.scenes[nxt]['name']}' to press on.)"

    def resolve(self, where: str):
        """Match a place the player names to a scene id."""
        w = where.lower().strip(" .!?")
        w = re.sub(r"^(the|old|ruined)\s+", "", w)
        for sid, sc in self.scenes.items():
            names = {sid, sc["name"].lower()} | set(sc.get("aliases", []))
            if any(w == n or w in n or n in w for n in names if len(n) > 3) or \
                    any(word in sc["name"].lower().split() for word in w.split() if len(word) > 4):
                return sid
        return None

    def enter(self, sid):
        g = self.game
        s = self.scenes[sid]
        self.current = sid
        g.scene.name = s["name"]
        g.scene.light = s.get("light", "bright")
        g.scene.sunlight = s.get("sunlight", False)
        g.scene.objects = {k: v for k, v in g.scene.objects.items() if "trap" not in v}
        g.log.player("scene", f"== {s['name']} ==\n{s['text']}")
        if s.get("next") and not s.get("ambush") and not s.get("encounter"):
            g.log.player("scene", self.exits_text())
        # lay out the party in marching order
        for i, p in enumerate(g.pcs()):
            p.position = (0, 5 * i)
        if s.get("travel"):
            tv = s["travel"]
            self.session.execute({"cmd": "travel", **tv})
        for kind, where in s.get("traps", []):
            T.place(g, kind, location=where)
        if s.get("ambush"):
            self._ambush(s["ambush"])
        elif s.get("encounter"):
            self._encounter(s["encounter"])
        return self.describe()

    def go(self, where=None):
        g = self.game
        target = None
        if where:
            target = self.resolve(where)
            if target is None:
                raise Refusal(f"I don't know a place called '{where}'. {self.exits_text()}")
            order = self.order
            here, there = order.index(self.current), order.index(target)
            if there == here:
                raise Refusal(f"You're already at {self.scenes[target]['name']}.")
            if there < here:
                raise Refusal(f"This adventure only goes forward: {self.scenes[target]['name']} is behind you. "
                              f"{self.exits_text()}")
            if there > here + 1:
                nxt = self.scenes[self.scenes[self.current]["next"]]
                g.log.player("scene", f"You set off toward {self.scenes[target]['name']}; the way leads through "
                             f"{nxt['name']} first.")
        if g.combat is not None:
            raise Refusal("You can't leave in the middle of a fight")
        g.resolve_dying()
        s = self.scenes[self.current]
        pending = [o["trap"] for o in g.scene.objects.values() if "trap" in o and not o["trap"].disabled
                   and not o["trap"].triggered]
        pit = next((t for t in pending if t.kind in ("hidden pit", "spiked pit")), None)
        if pit is not None:
            lead = g.pcs()[0]
            T.passive_detection(g, g.pcs(), pit)
            if not pit.detected:
                T.trigger(g, lead, pit)
                lead.notes.pop("in_pit", None)
                g.log.player("scene", f"The others haul {lead.name} out of the pit with a rope.")
                return "The floor gives way!"
            if not pit.disabled:
                raise Refusal("There's a pit trap in the floor ahead; wedge it with an Iron Spike first")
        if s.get("loot") and self.current not in self.loot_taken:
            chest = next((t for t in pending if t.kind == "poisoned needle"), None)
            if chest is not None:
                raise Refusal("The locked chest is still here. Open it (pick the lock, or disarm it) before moving on, "
                              "or say 'leave the chest'")
            self.take_loot()
        nxt = s.get("next")
        if nxt is None:
            g.log.player("scene", s.get("ending", "The adventure is over."))
            return "The End"
        return self.enter(nxt)

    def take_loot(self):
        g = self.game
        s = self.scenes[self.current]
        loot = s.get("loot")
        if not loot or self.current in self.loot_taken:
            return
        self.loot_taken.add(self.current)
        carrier = g.pcs()[0]
        for it in loot.get("items", []):
            carrier.inventory.add(MI.make(it, identified=True))
        if loot.get("gp"):
            carrier.purse.add(gp=loot["gp"])
        g.log.player("loot", f"{carrier.name} takes the treasure: {', '.join(i.title() for i in loot.get('items', []))}"
                     + (f" and {loot['gp']} GP" if loot.get("gp") else ""))

    def _spawn(self, keys, positions):
        return E.spawn(self.game, keys, positions)

    def _ambush(self, spec):
        g = self.game
        mons = self._spawn(spec["monsters"], spec["positions"])
        levels = [p.level for p in g.pcs() if not p.dead]
        E.rate(g, levels, mons)
        for i, m in enumerate(mons):
            m.add_condition("invisible", f"Hide (Stealth {spec['hide_total']})")
            m.hidden_total = spec["hide_total"]
            m.notes["cover_nearby"] = i % 2 == 0
        g.log.player("scene", spec["text"])
        from .actions import notices
        surprised = [p for p in g.pcs() if not p.dead and not any(notices(g, p, m) for m in mons)]
        C.roll_initiative(g, [p for p in g.pcs() if not p.dead] + mons, surprised=surprised)
        gm.run_until_pc(g)

    def _encounter(self, spec):
        g = self.game
        mons = self._spawn(spec["monsters"], spec["positions"])
        levels = [p.level for p in g.pcs() if not p.dead]
        E.rate(g, levels, mons)
        C.roll_initiative(g, [p for p in g.pcs() if not p.dead] + mons)
        gm.run_until_pc(g)
