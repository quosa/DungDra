"""State snapshot as JSON-compatible data (harness contract §2.1.2)."""
from __future__ import annotations


def creature_state(c) -> dict:
    d = {
        "id": c.id, "name": c.name, "kind": c.kind, "team": c.team,
        "hp": c.hp, "max_hp": c.max_hp, "temp_hp": c.temp_hp, "ac": c.ac(),
        "speed": c.speed(), "abilities": dict(c.abilities),
        "conditions": sorted(c.conditions()), "exhaustion": c.exhaustion,
        "effects": [e.describe() for e in c.effects if not e.condition],
        "dead": c.dead, "stable": c.stable, "death_saves": dict(c.death_saves),
        "heroic_inspiration": c.heroic_inspiration, "position": list(c.position),
        "concentrating": c.concentrating,
    }
    extra = getattr(c, "state_extra", None)
    if extra:
        d.update(extra())
    return d


def snapshot(game) -> dict:
    from .game import fmt_clock
    return {
        "clock": game.clock, "clock_text": fmt_clock(game.clock),
        "location": game.scene.name,
        "party": list(game.party),
        "creatures": {cid: creature_state(c) for cid, c in game.creatures.items()},
        "initiative": game.combat.order_state() if game.combat else None,
        "scene": {"light": game.scene.light, "travel_pace": game.scene.travel_pace},
    }
