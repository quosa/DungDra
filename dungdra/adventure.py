"""An adventure: places joined by exits, read from an adventure file (`scenario`).

Places are data; the engine resolves everything. Danger is conveyed in the fiction; encounter
budgets stay in the GM log (R-03). A place's fight and traps happen the first time the party
enters it, and what is left there (a trap, a web, an opened chest) stays when the party leaves.
"""

from __future__ import annotations

import re
from collections import deque

from . import combat as C
from . import encounters as E
from . import gm, scenario
from . import magic_items as MI
from . import traps as T
from .rules import Refusal, norm


def _ways(places: dict) -> dict[str, list[tuple[str, dict]]]:
    """For each place, where its exits lead: its own exits in the file's order, then the way back
    along any other place's exit that isn't one-way."""
    ways: dict[str, list[tuple[str, dict]]] = {pid: [] for pid in places}
    for pid, p in places.items():
        for ex in p.get("exits", []):
            ways[pid].append((ex["to"], ex))
    for pid, p in places.items():
        for ex in p.get("exits", []):
            if not ex.get("one_way") and all(to != pid for to, _ in ways[ex["to"]]):
                ways[ex["to"]].append((pid, ex))
    return ways


class Adventure:
    def __init__(self, session, data: dict | None = None):
        self.session = session
        self.data = data or scenario.load()
        self.title = self.data["title"]
        self.places = self.data["places"]
        self.ways = _ways(self.places)
        self.current: str | None = None
        self.came_from: str | None = None
        self.visited: list[str] = []
        self.fought: set[str] = set()
        self.loot_taken: set[str] = set()
        self.left_behind: dict[str, tuple[dict, bool]] = {}  # a place's objects and Difficult Terrain

    @property
    def game(self):
        return self.session.game

    def start(self):
        return self.enter(self.data["start"])

    def name(self, pid: str) -> str:
        return self.places[pid]["name"]

    def describe(self):
        p = self.places[self.current]
        return f"{p['name']}\n{p['text']}\n{self.exits_text()}"

    def exits_text(self):
        ways = self.ways[self.current]
        own = self.places[self.current].get("exits", [])
        if not ways:
            return "(This is the end of the road.)"
        if len(ways) == 1 and own:
            return f"(Say 'continue' or 'go to {self.name(ways[0][0])}' to press on.)"
        hints = ["'go to <place>'"]
        if own:
            hints.append(f"'continue' for {self.name(own[0]['to'])}")
        if any(to == self.came_from for to, _ in ways):
            hints.append(f"'go back' for {self.name(self.came_from)}")
        return f"(Ways from here: {', '.join(self.name(to) for to, _ in ways)}. Say {' or '.join(hints)}.)"

    def map_text(self):
        lines = [f"Map of {self.title}:"]
        for pid in self.visited:
            here = " (you are here)" if pid == self.current else ""
            ways = ", ".join(self.name(to) for to, _ in self.ways[pid]) or "no way on"
            lines.append(f"  {self.name(pid)}{here}: ways to {ways}")
        return "\n".join(lines)

    def resolve(self, where: str):
        """Match a place the player names to a place id."""
        w = where.lower().strip(" .!?")
        w = re.sub(r"^(the|old|ruined)\s+", "", w)
        for pid, p in self.places.items():
            names = {pid, p["name"].lower()} | {a.lower() for a in p.get("aliases", [])}
            if any(w == n or w in n or n in w for n in names if len(n) > 3) or any(
                word in p["name"].lower().split() for word in w.split() if len(word) > 4
            ):
                return pid
        return None

    def _path(self, start: str, goal: str) -> list[str]:
        """The places on the shortest way from start to goal, goal included; [] if there's none."""
        prev = {start: None}
        todo = deque([start])
        while todo:
            here = todo.popleft()
            for to, _ in self.ways[here]:
                if to not in prev:
                    prev[to] = here
                    todo.append(to)
        if goal not in prev:
            return []
        path = [goal]
        while prev[path[-1]] != start:
            path.append(prev[path[-1]])
        return path[::-1]

    def enter(self, pid, way: dict | None = None):
        g = self.game
        if self.current is not None:
            self.left_behind[self.current] = (g.scene.objects, g.scene.difficult)
        first = pid not in self.visited
        self.came_from, self.current = self.current, pid
        if first:
            self.visited.append(pid)
        p = self.places[pid]
        g.scene.name = p["name"]
        g.scene.light = p.get("light", "bright")
        g.scene.sunlight = p.get("sunlight", False)
        g.scene.objects, g.scene.difficult = self.left_behind.get(pid, ({}, False))
        g.log.player("scene", f"== {p['name']} ==\n{p['text']}")
        fight = pid not in self.fought and (p.get("ambush") or p.get("encounter"))
        if self.ways[pid] and not fight:
            g.log.player("scene", self.exits_text())
        # lay out the party in marching order
        for i, pc in enumerate(g.pcs()):
            pc.position = (0, 5 * i)
        if way and way.get("travel"):
            self.session.execute({"cmd": "travel", **way["travel"]})
        if first:
            self._set_up(p)
        if self._fallen():  # the last dying character may die on the way (p.17)
            return self.describe()
        if fight:
            self.fought.add(pid)
            if p.get("ambush"):
                self._ambush(p["ambush"])
            else:
                self._encounter(p["encounter"])
        return self.describe()

    def _set_up(self, p):
        """What the place holds the first time the party comes: its traps and its ground."""
        g = self.game
        for t in p.get("traps", []):
            T.place(g, t["kind"], location=t.get("location", ""))
        ground = p.get("ground", [])
        for i, gr in enumerate([ground] if isinstance(ground, str) else ground):
            if isinstance(gr, str):
                g.scene.add_ground(gr)
            else:
                g.scene.add_ground(gr["kind"], "rect", None, gr["rect"], name=f"{norm(gr['kind'])} {i + 1}")

    def go(self, where=None):
        g = self.game
        if all(p.dead for p in g.pcs()):
            raise Refusal("The party has fallen and the adventure is over. Type 'quit' to start a new game.")
        here = self.places[self.current]
        target = self._target(where)
        path = self._path(self.current, target) if target else []
        if target and not path:
            if target in self.visited:
                raise Refusal(
                    f"There's no way back to {self.name(target)}: it's behind you. {self.exits_text()}"
                )
            raise Refusal(f"There's no way from here to {self.name(target)}. {self.exits_text()}")
        if len(path) > 1:
            g.log.player(
                "scene",
                f"You set off toward {self.name(target)}; the way leads through {self.name(path[0])} first.",
            )
        if g.combat is not None:
            raise Refusal("You can't leave in the middle of a fight")
        g.resolve_dying()
        if self._fallen():
            return "The End"
        if not path or path[0] != self.came_from:
            stop = self._before_moving_on(here)
            if stop:
                return stop
        if not path:
            if here.get("ending"):
                g.log.player("scene", here["ending"])
                return "The End"
            raise Refusal(f"There's no way on from here. {self.exits_text()}")
        way = next(ex for to, ex in self.ways[self.current] if to == path[0])
        return self.enter(path[0], way)

    def _target(self, where):
        """The place the player asks for: 'continue' takes the place's first exit, 'back' the way
        the party came; None where there's no exit to take."""
        if where is None:
            own = self.places[self.current].get("exits", [])
            return own[0]["to"] if own else None
        if norm(where) in ("back", "way back"):
            if self.came_from is None:
                raise Refusal(f"You've only just arrived; there's nowhere to go back to. {self.exits_text()}")
            return self.came_from
        target = self.resolve(where)
        if target is None:
            raise Refusal(f"I don't know a place called '{where}'. {self.exits_text()}")
        if target == self.current:
            raise Refusal(f"You're already at {self.name(target)}.")
        return target

    def _before_moving_on(self, here):
        """A pit in the floor ahead and a locked chest hold the party up when it presses on (not
        when it turns back). Returns the event to report when the floor gives way."""
        g = self.game
        pending = [
            o["trap"]
            for o in g.scene.objects.values()
            if "trap" in o and not o["trap"].disabled and not o["trap"].triggered
        ]
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
        if here.get("loot") and self.current not in self.loot_taken:
            chest = next((t for t in pending if t.kind == "poisoned needle"), None)
            if chest is not None:
                raise Refusal(
                    "The locked chest is still here. Open it (pick the lock, or disarm it) before moving on, "
                    "or say 'leave the chest'"
                )
            self.take_loot()
        return None

    def _fallen(self):
        """True once every PC is dead; says so the first time."""
        g = self.game
        if not all(p.dead for p in g.pcs()):
            return False
        if not g.defeated:
            g.defeated = True
            g.log.player("defeat", "The party has fallen. The adventure ends here.")
        return True

    def take_loot(self):
        g = self.game
        loot = self.places[self.current].get("loot")
        if not loot or self.current in self.loot_taken:
            return
        self.loot_taken.add(self.current)
        carrier = g.pcs()[0]
        for it in loot.get("items", []):
            carrier.inventory.add(MI.make(it, identified=True))
        if loot.get("gp"):
            carrier.purse.add(gp=loot["gp"])
        g.log.player(
            "loot",
            f"{carrier.name} takes the treasure: {', '.join(i.title() for i in loot.get('items', []))}"
            + (f" and {loot['gp']} GP" if loot.get("gp") else ""),
        )

    def _spawn(self, keys, positions):
        return E.spawn(self.game, keys, [tuple(p) for p in positions])

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
