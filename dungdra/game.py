"""Game: owns dice, event log, clock, creatures, scene and player decisions.

The engine owns every number. Player choices (Luck, Heroic Inspiration,
Reactions, temp HP ...) go through `decide`, which consults queued answers
(tests, the structured API), then an interactive decider (CLI/LLM), then a
default.
"""

from __future__ import annotations

from collections import defaultdict, deque

from .dice import Dice
from .effects import Acc, Ctx, grapples_on
from .events import EventLog
from .rules import DAY, HOUR, MINUTE, ROUND, SPACE, Refusal, norm


class Scene:
    """The environment around the party."""

    def __init__(self):
        self.name = "the wilds"
        self.light = "bright"  # ambient: bright | dim | dark
        self.sunlight = False
        self.underwater = False
        self.terrain = "open"
        self.difficult = False
        # (attacker id or point of origin (x, y), target id) -> degree
        self.cover: dict[tuple[str | tuple, str], str] = {}
        self.cover_all: dict[str, str] = {}  # target -> degree vs everyone
        self.no_los: set[tuple[str, str]] = set()  # blocked line of sight pairs
        self.silence = False
        self.heavily_obscured: set[str] = set()  # creature ids inside heavy obscurement
        self.lightly_obscured: set[str] = set()
        self.stone = True
        self.travel_pace: str | None = None
        self.objects: dict[str, dict] = {}  # named objects (crate, web, door ...)
        self.hidden: dict[str, dict] = {}  # hidden things (secret door, trap)

    def to_dict(self):
        return {
            k: (
                list(map(list, v))
                if isinstance(v, set) and v and isinstance(next(iter(v)), tuple)
                else sorted(v)
                if isinstance(v, set)
                else {"|".join(map(str, kk)): vv for kk, vv in v.items()}
                if k == "cover"
                else v
            )
            for k, v in self.__dict__.items()
        }


class Game:
    def __init__(self, seed: int | None = 1, interactive=None):
        self.dice = Dice(seed)
        self.log = EventLog()
        self.clock = 0  # seconds since campaign start
        self.log.clock_fn = lambda: self.clock
        self.creatures: dict = {}
        self.party: list[str] = []
        self.combat = None
        self.scene = Scene()
        self.answers: dict = defaultdict(deque)
        self.decider = interactive  # fn(game, who, key, options, default, prompt)
        self.rest = None  # active rest (for interruption)
        self.turn_actor = None
        self.influence_cooldowns: dict = {}
        self.xp_log: list = []
        self.gm_mode = False
        self.fixed_monster_damage = False  # p.189: static damage numbers instead of dice
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
        if self.decider is not None and (
            who is None or getattr(who, "team", "party") == "party" or self.gm_mode
        ):
            v = self.decider(self, who, key, options, default, prompt)
            self._log_offer(who, key, prompt, v)
            return v
        self._log_offer(who, key, prompt, default, defaulted=True)
        return default

    def _log_offer(self, who, key, prompt, value, defaulted=False):
        if prompt:
            self.log.player(
                "offer",
                f"[choice] {prompt} → {value!r}" + (" (default)" if defaulted else ""),
                key=key,
                value=repr(value),
            )

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
        return self.cover_between(a, b) != "total"

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
        return self.perceived_light(viewer, target) != "dark"

    def cover_between(self, attacker, target) -> str | None:
        """Degree of cover the target has against an effect's origin: the scene's labels and the
        Half Cover of creatures standing in the line, for attacks and saves alike. The origin is
        the attacker (a creature) or a point (x, y) in feet where an area or other effect
        originates; the scene labels cover from a point under the key (point, target id)."""
        order = [None, "half", "three-quarters", "total"]
        # SRD[PLAY.combat.cover#3] cover counts against where the effect originates, which needn't
        # be the caster: a point of origin is looked up like a creature
        key = _origin_key(attacker)
        c1 = self.scene.cover.get((key, target.id)) if key is not None else None
        c2 = self.scene.cover_all.get(target.id)
        c3 = "half" if attacker is not None and self.creatures_in_the_way(attacker, target) else None
        # SRD[PLAY.combat.cover#4] only the most protective degree applies; never added together
        return max(c1, c2, c3, key=lambda c: order.index(c))

    def cover_bonus(self, attacker, target, against: str) -> list[tuple[int, str]]:
        """The Half or Three-Quarters Cover bonus the target gets to its AC or Dexterity save
        `against` the attacker, as modifier parts ([] without such cover); logs what it applied."""
        cover = self.cover_between(attacker, target)
        if cover not in ("half", "three-quarters"):
            return []
        # SRD[PLAY.combat.cover#5] Half: +2; SRD[PLAY.combat.cover#7] Three-Quarters: +5
        value, clause = (2, 5) if cover == "half" else (5, 7)
        label = f"{cover.title()} Cover"
        self.log.gm(
            "cover",
            f"{target.name} has {label} against {_origin_name(attacker)}: +{value} to {against}",
            page=15,
            rule=f"PLAY.combat.cover#{clause}",
        )
        return [(value, label)]

    def creatures_in_the_way(self, attacker, target) -> list:
        """Creatures standing on the line between the two (centre of space to centre of space); an
        origin that is a point (x, y) is the line's end itself."""
        from .geometry import segment_crosses_square

        def centre(c):
            if _is_point(c):
                return (float(c[0]), float(c[1]))
            s = SPACE.get(c.size, 5)
            return (c.position[0] + s / 2, c.position[1] + s / 2)

        def between(c):
            s = SPACE.get(c.size, 5)
            x, y = c.position
            # one sharing the attacker's or the target's space isn't between them
            if any(x <= px <= x + s and y <= py <= y + s for px, py in (p, q)):
                return False
            return segment_crosses_square(p, q, c.position, s)

        p, q = centre(attacker), centre(target)
        # SRD[PLAY.combat.cover#6] another creature gives Half Cover (never more, R-09);
        # SRD[PLAY.combat.cover#3] only one between the attack's origin and the target counts
        return [
            c
            for c in self.creatures.values()
            if c is not attacker and c is not target and not c.dead and between(c)
        ]

    def scene_gather(self, creature, ctx: Ctx, acc: Acc):
        """Environmental modifiers to D20 Tests (light, travel pace, sunlight)."""
        from . import world

        world.scene_gather(self, creature, ctx, acc)

    # -- time -------------------------------------------------------------
    def resolve_dying(self):
        """Outside combat, a dying character keeps making Death Saving Throws every 6 seconds
        until Stable, healed or dead (p.17-18)."""
        from .damage import death_save

        for c in self.pcs():
            guard = 0
            while c.hp == 0 and not c.dead and not c.stable and guard < 50:
                guard += 1
                self.clock += ROUND
                death_save(self, c)

    def advance(self, seconds: int, reason: str = "", log=True):
        if self.combat is None and seconds > ROUND:
            self.resolve_dying()
        start = self.clock
        self.clock += seconds
        if log and seconds:
            self.log.player(
                "time",
                f"{fmt_duration(seconds)} pass"
                + (f" ({reason})" if reason else "")
                + f"; clock {fmt_clock(self.clock)}",
                seconds=seconds,
            )
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
            for e in grapples_on(c, by=creature.id):
                c.remove_effect(e, f"grappler {creature.name} is Incapacitated")
            for e in list(c.effects):
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
        self.log.player(
            "concentration",
            f"{caster.name}'s Concentration on {what} ends" + (f" ({reason})" if reason else ""),
            page=179,
            rule="GLOSS.concentration",
        )
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
        r = caster.save(
            "con",
            dc,
            label=f"Concentration save (DC {dc}: {damage} damage)",
            page=179,
            rule="GLOSS.concentration",
        )
        if not r.success:
            self.end_concentration(caster, "failed Concentration save")
        return r

    # -- snapshot ---------------------------------------------------------
    def snapshot(self) -> dict:
        from .snapshot import snapshot

        return snapshot(self)


def _is_point(origin) -> bool:
    """An effect's origin given as a point (x, y) in feet rather than as a creature."""
    return isinstance(origin, (tuple, list))


def _origin_key(origin):
    """The scene's cover key for an origin: a creature's id, or the point itself."""
    if origin is None:
        return None
    return tuple(origin) if _is_point(origin) else origin.id


def _origin_name(origin) -> str:
    return f"the point of origin at {origin}" if _is_point(origin) else origin.name


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
