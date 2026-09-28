"""Spellcasting rules (SRD p.104-106)."""
from __future__ import annotations

from .rules import Refusal


def arcane_recovery_offer(game, pc, slots=None):
    """p.78: on finishing a Short Rest, recover expended slots totalling up to half the Wizard level (round up)."""
    budget = -(-pc.level // 2)
    expended = {lvl: n for lvl, n in pc.slots_used.items() if n > 0 and lvl < 6}
    if not expended:
        return None
    if slots is None:
        # default: recover the highest slots that fit
        slots = []
        left = budget
        for lvl in sorted(expended, reverse=True):
            for _ in range(expended[lvl]):
                if lvl <= left:
                    slots.append(lvl)
                    left -= lvl
        slots = game.decide(pc, "arcane_recovery", [slots, []], default=slots,
                            prompt=f"{pc.name}: use Arcane Recovery (up to {budget} slot levels)?")
    if not slots:
        return None
    return arcane_recovery(game, pc, slots)


def arcane_recovery(game, pc, slots):
    budget = -(-pc.level // 2)
    if pc.resource_left("arcane recovery") <= 0:
        raise Refusal("Arcane Recovery has already been used; it returns after a Long Rest", page=78)
    if sum(slots) > budget:
        raise Refusal(f"Arcane Recovery recovers at most {budget} slot levels", page=78)
    for lvl in slots:
        if pc.slots_used.get(lvl, 0) <= 0:
            raise Refusal(f"No expended level {lvl} slot to recover")
        pc.slots_used[lvl] -= 1
    pc.spend("arcane recovery")
    game.log.player("feature", f"{pc.name} uses Arcane Recovery: regains slot(s) of level {', '.join(map(str, slots))}",
                    page=78)
    return slots
