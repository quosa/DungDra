"""Exploration: travel pace and terrain, extended travel, jumping, light
(SRD p.11-12, 192, glossary)."""
from __future__ import annotations

from .rules import HOUR, Refusal, div, norm

PACE_MPH = {"fast": 4, "normal": 3, "slow": 2}
PACE_ORDER = ["slow", "normal", "fast"]
TERRAIN_MAX = {"arctic": "fast", "coastal": "normal", "desert": "normal", "forest": "normal", "grassland": "fast",
               "hill": "normal", "mountain": "slow", "swamp": "slow", "underdark": "normal", "urban": "normal"}


def max_pace(terrain: str, road=False) -> str:
    base = TERRAIN_MAX[norm(terrain)]
    i = PACE_ORDER.index(base)
    if road:
        i = min(2, i + 1)                # p.192 Good Roads: one step faster
    return PACE_ORDER[i]


def travel(game, pcs, miles: float | None = None, hours: float | None = None, pace="normal", terrain="forest",
           road=False, day_hours_so_far: float = 0):
    pace = norm(pace)
    if pace not in PACE_MPH:
        raise Refusal("Travel pace must be Fast, Normal or Slow")
    mp = max_pace(terrain, road)
    if PACE_ORDER.index(pace) > PACE_ORDER.index(mp):
        raise Refusal(f"The {terrain} terrain allows at most a {mp.title()} pace"
                      + ("" if road else " (a good road raises it one step)"), page=192)
    for pc in pcs:
        if pc.speed() <= pc.speeds.get("walk", 30) // 2 and pace != "slow":
            raise Refusal(f"{pc.name}'s Speed is halved or worse: the group must move at a Slow pace", page=192)
    mph = PACE_MPH[pace]
    if hours is None:
        hours = miles / mph
    if miles is None:
        miles = hours * mph
    game.scene.travel_pace = pace
    game.scene.terrain = norm(terrain)
    game.log.player("travel", f"The party travels {miles:g} miles at a {pace.title()} pace through {terrain} "
                    + ("on a good road " if road else "") + f"({hours:g} hours)", page=12)
    # hour by hour so extended travel saves happen at the end of hours 9, 10, ...
    whole = int(hours)
    frac = hours - whole
    for h in range(1, whole + 1):
        game.advance(HOUR, None and "", log=False)
        hour_of_day = day_hours_so_far + h
        if hour_of_day > 8:
            extended_travel_saves(game, pcs, int(hour_of_day))
    if frac:
        game.advance(int(frac * HOUR), log=False)
    game.log.player("time", f"{hours:g} hours of travel pass", seconds=int(hours * HOUR))
    return hours


def extended_travel_saves(game, pcs, hour: int):
    dc = 10 + (hour - 8)
    for pc in pcs:
        r = pc.save("con", dc, label=f"Constitution save for hour {hour} of travel (DC {dc})", page=192)
        if not r.success:
            pc.gain_exhaustion(1, "extended travel", page=192)


# -- jumping (p.183-185) ------------------------------------------------------------------
def jump_score(pc) -> int:
    if pc.is_pc() and pc.has_feature("second-story work"):
        return max(pc.score("str"), pc.score("dex"))       # Thief: Jumper uses Dex
    return pc.score("str")


def long_jump_distance(pc, running=True) -> int:
    d = jump_score(pc)
    return d if running else div(d, 2)


def high_jump_distance(pc, running=True) -> int:
    ab = "dex" if pc.is_pc() and pc.has_feature("second-story work") and pc.mod("dex") > pc.mod("str") else "str"
    d = max(0, 3 + pc.mod(ab))
    return d if running else div(d, 2)


def long_jump(game, pc, distance: int, running=True):
    reach = long_jump_distance(pc, running)
    cb = game.combat
    if cb is not None and cb.is_turn(pc):
        if cb.turn.movement_left < distance:
            raise Refusal("Each foot of the jump costs a foot of movement", page=185)
        cb.turn.movement_left -= min(distance, reach)
    ok = distance <= reach
    game.log.player("jump", f"{pc.name} makes a {'running' if running else 'standing'} Long Jump: up to {reach} ft; "
                    f"the gap is {distance} ft → {'clears it' if ok else 'falls short'}", page=185)
    return ok


def high_jump(game, pc, running=True):
    h = high_jump_distance(pc, running)
    game.log.player("jump", f"{pc.name} makes a {'running' if running else 'standing'} High Jump of {h} ft", page=183)
    return h


# -- light sources ------------------------------------------------------------------------
def light_torch(game, pc):
    t = pc.inventory.find("torch")
    if t is None:
        raise Refusal(f"{pc.name} has no Torch")
    if t.qty > 1:
        pc.inventory.remove(t, 1)
        t = pc.inventory.add("torch", 1, lit=True, light=[20, 20], burns_until=game.clock + HOUR)
    else:
        t.props.update(lit=True, light=[20, 20], burns_until=game.clock + HOUR)
    if game.combat is not None:
        game.combat.spend(pc, "bonus", "light a Torch with a Tinderbox")
    game.log.player("light", f"{pc.name} lights a Torch: Bright Light 20 ft, Dim Light 20 ft more, for 1 hour",
                    page=100)
    return t
