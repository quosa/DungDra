"""Game: owns dice, event log, clock, creatures, scene and player decisions.

The engine owns every number. Player choices (Luck, Heroic Inspiration,
Reactions, temp HP ...) go through `decide`, which consults queued answers
(tests, the structured API), then an interactive decider (CLI/LLM), then a
default.
"""
from __future__ import annotations

from collections import defaultdict, deque

from .dice import Dice
from .effects import Acc, Ctx
from .events import EventLog
from .rules import DAY, HOUR, MINUTE, ROUND, Refusal, norm


class Scene:
    """The environment around the party."""

    def __init__(self):
        self.name = "the wilds"
        self.light = "bright"          # ambient: bright | dim | dark
        self.sunlight = False
        self.underwater = False
        self.terrain = "open"
        self.difficult = False
        self.cover: dict[tuple[str, str], str] = {}     # (attacker, target) -> degree
        self.cover_all: dict[str, str] = {}              # target -> degree vs everyone
        self.no_los: set[tuple[str, str]] = set()        # blocked line of sight pairs
        self.silence = False
        self.heavily_obscured: set[str] = set()          # creature ids inside heavy obscurement
        self.lightly_obscured: set[str] = set()
        self.stone = True
        self.travel_pace: str | None = None
        self.objects: dict[str, dict] = {}               # named objects (crate, web, door ...)
        self.hidden: dict[str, dict] = {}                # hidden things (secret door, trap)

    def to_dict(self):
        return {k: (list(map(list, v)) if isinstance(v, set) and v and isinstance(next(iter(v)), tuple)
                    else sorted(v) if isinstance(v, set)
                    else {"|".join(kk): vv for kk, vv in v.items()} if k == "cover" else v)
                for k, v in self.__dict__.items()}


class Game:
    def __init__(self, seed: int | None = 1, interactive=None):
        self.dice = Dice(seed)
        self.log = EventLog()
        self.clock = 0                    # seconds since campaign start
        self.log.clock_fn = lambda: self.clock
        self.creatures: dict = {}
        self.party: list[str] = []
        self.combat = None
        self.scene = Scene()
        self.answers: dict = defaultdict(deque)
        self.decider = interactive        # fn(game, who, key, options, default, prompt)
        self.rest = None                  # active rest (for interruption)
        self.turn_actor = None
        self.influence_cooldowns: dict = {}
        self.xp_log: list = []
        self.gm_mode = False
        self.content = None

    # -- decisions --------------------------------------------------------
    def answer(self, key: str, value, who=None):
        """Queue an answer for a future decision (tests/API)."""
        k = (getattr(who, "id", who), key) if who is not None else key
        self.answers[k].append(value)

    def decide(self, who, key: str, options, default=None, prompt: str = ""):
        wid = getattr(who, "id", who)
        for k in ((wid, key), key):
            if self.answers.get(k):
                v = self.answers[k].popleft()
                self._log_offer(who, key, prompt, v)
                return v
        if self.decider is not None and (who is None or getattr(who, "team", "party") == "party"
                                         or self.gm_mode):
            v = self.decider(self, who, key, options, default, prompt)
            self._log_offer(who, key, prompt, v)
            return v
        self._log_offer(who, key, prompt, default, defaulted=True)
        return default

    def _log_offer(self, who, key, prompt, value, defaulted=False):
        if prompt:
            self.log.player("offer", f"[choice] {prompt} → {value!r}"
                            + (" (default)" if defaulted else ""), key=key, value=repr(value))

    # -- creatures --------------------------------------------------------
    def add(self, creature, team: str | None = None, position=None):
        base = creature.id
        n = 2
        while creature.id in self.creatures and self.creatures[creature.id] is not creature:
            creature.id = f"{base}_{n}"
            n += 1
        self.creatures[creature.id] = creature
        creature.game = self
        if team:
            creature.team = team
        if position is not None:
            creature.position = tuple(position)
        if creature.team == "party" and creature.id not in self.party:
            self.party.append(creature.id)
        return creature

    def remove(self, creature):
        self.creatures.pop(creature.id, None)
        if creature.id in self.party:
            self.party.remove(creature.id)

    def get(self, ref):
        if hasattr(ref, "id"):
            return ref
        if ref in self.creatures:
            return self.creatures[ref]
        r = norm(ref)
        for c in self.creatures.values():
            if norm(c.name) == r or c.id == r.replace(" ", "_"):
                return c
        for c in self.creatures.values():
            if norm(c.name).startswith(r):
                return c
        raise Refusal(f"There is no creature called {ref!r} here")

    def pcs(self):
        return [self.creatures[i] for i in self.party if i in self.creatures]

    def enemies_of(self, c):
        return [x for x in self.creatures.values() if x.team not in (c.team, "neutral") and not x.dead]

    def allies_of(self, c):
        return [x for x in self.creatures.values() if x.team == c.team and x is not c and not x.dead]

    # -- perception -------------------------------------------------------
    def line_of_sight(self, a, b) -> bool:
        if (a.id, b.id) in self.scene.no_los or (b.id, a.id) in self.scene.no_los:
            return False
        if self.cover_between(a, b) == "total":
            return False
        return True

    def light_at(self, creature) -> str:
        """Illumination at a creature's position: ambient upgraded by light sources."""
        from .geometry import dist_points
        order = ["dark", "dim", "bright"]
        best = order.index(self.scene.light)
        for c in self.creatures.values():
            for src in getattr(c, "light_sources", lambda: [])():
                bright, dim = src
                d = dist_points(c.position, creature.position)
                if d <= bright:
                    best = max(best, 2)
                elif d <= bright + dim:
                    best = max(best, 1)
        for obj in self.scene.objects.values():
            if obj.get("light"):
                bright, dim = obj["light"]
                d = dist_points(obj.get("position", (0, 0)), creature.position)
                if d <= bright:
                    best = max(best, 2)
                elif d <= bright + dim:
                    best = max(best, 1)
        return order[best]

    def perceived_light(self, viewer, target) -> str:
        """Light level as the viewer perceives it at the target (Darkvision p.180)."""
        light = self.light_at(target)
        dv = viewer.senses.get("darkvision", 0)
        if dv and viewer.distance_to(target) <= dv:
            if light == "dim":
                return "bright"
            if light == "dark":
                return "dim"
        return light

    def can_see(self, viewer, target) -> bool:
        if viewer is target:
            return True
        if viewer.has("blinded") and not viewer.senses.get("blindsight"):
            return False
        d = viewer.distance_to(target)
        special = max(viewer.senses.get("truesight", 0), viewer.senses.get("blindsight", 0))
        if special and d <= special:
            return self.line_of_sight(viewer, target)
        if target.has("invisible"):
            return False
        if not self.line_of_sight(viewer, target):
            return False
        if target.id in self.scene.heavily_obscured:
            return False
        if self.perceived_light(viewer, target) == "dark":
            return False
        return True

    def cover_between(self, attacker, target) -> str | None:
        order = [None, "half", "three-quarters", "total"]
        c1 = self.scene.cover.get((attacker.id, target.id)) if attacker else None
        c2 = self.scene.cover_all.get(target.id)
        # p.179: only the most protective degree applies
        return max(c1, c2, key=lambda c: order.index(c))

    def scene_gather(self, creature, ctx: Ctx, acc: Acc):
        """Environmental modifiers to D20 Tests (light, travel pace, sunlight)."""
        from . import world
        world.scene_gather(self, creature, ctx, acc)

    # -- time -------------------------------------------------------------
    def advance(self, seconds: int, reason: str = "", log=True):
        start = self.clock
        self.clock += seconds
        if log and seconds:
            self.log.player("time", f"{fmt_duration(seconds)} pass" + (f" ({reason})" if reason else "")
                            + f"; clock {fmt_clock(self.clock)}", seconds=seconds)
        self.expire_effects()
        from . import world
        world.on_time_passed(self, start, self.clock)

    def expire_effects(self):
        for c in list(self.creatures.values()):
            for e in list(c.effects):
                if e.until is not None and self.clock >= e.until:
                    c.remove_effect(e, "duration expired")
                    if e.concentration and e.caster_id:
                        caster = self.creatures.get(e.caster_id)
                        if caster and caster.concentrating and not self._conc_effects(caster):
                            caster.concentrating = None

    # -- hooks called by creatures ----------------------------------------
    def on_damaged(self, creature, amount):
        if self.rest is not None and creature.id in self.rest.get("members", []):
            self.rest["interrupted"] = f"{creature.name} took damage"

    def on_death(self, creature):
        if creature.concentrating:
            self.end_concentration(creature, "died")
        if self.combat:
            self.combat.on_death(creature)
        from . import world
        world.on_death(self, creature)

    def on_incapacitated(self, creature):
        if creature.concentrating:
            self.end_concentration(creature, "Incapacitated")
        # p.182 grapple ends if the grappler is Incapacitated
        for c in self.creatures.values():
            for e in list(c.effects):
                if e.condition == "grappled" and e.data.get("grappler") == creature.id:
                    c.remove_effect(e, f"grappler {creature.name} is Incapacitated")
                if getattr(e, "ends_if_caster_incapacitated", False) and e.caster_id == creature.id:
                    c.remove_effect(e, f"{creature.name} is Incapacitated")

    # -- concentration (p.179) --------------------------------------------
    def _conc_effects(self, caster):
        out = []
        for c in self.creatures.values():
            for e in c.effects:
                if e.concentration and e.caster_id == caster.id:
                    out.append((c, e))
        for obj in self.scene.objects.values():
            if obj.get("concentration") == caster.id:
                out.append((None, obj))
        return out

    def start_concentration(self, caster, what: str):
        if caster.concentrating:
            self.end_concentration(caster, f"started concentrating on {what}")
        caster.concentrating = what

    def end_concentration(self, caster, reason: str = ""):
        what = caster.concentrating
        if not what:
            return
        caster.concentrating = None
        self.log.player("concentration", f"{caster.name}'s Concentration on {what} ends"
                        + (f" ({reason})" if reason else ""), page=179)
        for c, e in self._conc_effects(caster):
            if c is None:
                name = next(k for k, v in self.scene.objects.items() if v is e)
                del self.scene.objects[name]
            else:
                c.remove_effect(e, f"{what} ended")
        hook = caster.notes.pop("on_concentration_end", None)
        if hook:
            hook(self)

    def concentration_check(self, caster, damage: int):
        dc = min(30, max(10, damage // 2))
        r = caster.save("con", dc, label=f"Concentration save (DC {dc}: {damage} damage)", page=179)
        if not r.success:
            self.end_concentration(caster, "failed Concentration save")
        return r

    # -- snapshot ---------------------------------------------------------
    def snapshot(self) -> dict:
        from .snapshot import snapshot
        return snapshot(self)


def fmt_duration(s: int) -> str:
    if s % DAY == 0 and s >= DAY:
        n = s // DAY
        return f"{n} day{'s' if n != 1 else ''}"
    if s % HOUR == 0 and s >= HOUR:
        n = s // HOUR
        return f"{n} hour{'s' if n != 1 else ''}"
    if s % MINUTE == 0 and s >= MINUTE:
        n = s // MINUTE
        return f"{n} minute{'s' if n != 1 else ''}"
    if s % ROUND == 0:
        n = s // ROUND
        return f"{n} round{'s' if n != 1 else ''}"
    return f"{s} seconds"


def fmt_clock(s: int) -> str:
    d, r = divmod(s, DAY)
    h, r = divmod(r, HOUR)
    m, sec = divmod(r, MINUTE)
    return f"day {d + 1}, {h:02d}:{m:02d}" + (f":{sec:02d}" if sec else "")
