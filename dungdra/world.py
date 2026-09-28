"""Environment rules: light & obscurement, travel pace modifiers, time passing."""
from __future__ import annotations


def scene_gather(game, creature, ctx, acc):
    sc = game.scene
    if ctx.kind == "check" and "sight" in ctx.tags:
        # Explicit tags let the GM (or a test) state what is being looked at.
        if "heavily_obscured" in ctx.tags or "darkness" in ctx.tags:
            acc.fail("can't see into a Heavily Obscured area (effectively Blinded, p.182)")
        elif "lightly_obscured" in ctx.tags or "dim_light" in ctx.tags:
            acc.disadvantage("Lightly Obscured / Dim Light (p.184)")
        elif ctx.skill == "perception":
            look_at = ctx.target or creature
            light = game.perceived_light(creature, look_at)
            if light == "dark":
                acc.fail("Darkness: effectively Blinded (p.180, p.182)")
            elif light == "dim":
                acc.disadvantage("Dim Light: Lightly Obscured (p.184)")
    pace = sc.travel_pace if creature.team == "party" else None
    if pace and ctx.kind == "check":
        if ctx.skill == "stealth" and pace in ("normal", "fast"):
            acc.disadvantage(f"{pace.title()} travel pace (p.12)")
        if ctx.skill in ("perception", "survival"):
            if pace == "fast":
                acc.disadvantage("Fast travel pace (p.12)")
            elif pace == "slow":
                acc.advantage("Slow travel pace (p.12)")


def on_time_passed(game, start, end):
    for c in list(game.creatures.values()):
        hook = getattr(c, "on_time_passed", None)
        if hook:
            hook(start, end)


def on_death(game, creature):
    pass
