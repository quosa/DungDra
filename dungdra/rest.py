"""Heroic Inspiration, Short Rests and Long Rests (SRD p.8, 185, 187)."""
from __future__ import annotations

from .rules import HOUR, Refusal


def grant_heroic_inspiration(game, pc, source="GM"):
    """p.8: only one at a time; a surplus may be given to a PC who lacks it, else lost."""
    if not pc.heroic_inspiration:
        pc.heroic_inspiration = True
        game.log.player("inspiration", f"{pc.name} gains Heroic Inspiration ({source})", page=8)
        return pc
    lacking = [c for c in game.pcs() if not c.heroic_inspiration and c is not pc and not c.dead]
    if lacking:
        pick = game.decide(pc, "give_inspiration", [c.id for c in lacking] + [None],
                           default=lacking[0].id,
                           prompt=f"{pc.name} already has Heroic Inspiration; give the new one to "
                                  f"({', '.join(c.name for c in lacking)})?")
        if pick:
            other = game.get(pick)
            other.heroic_inspiration = True
            game.log.player("inspiration", f"{pc.name} already has Heroic Inspiration and gives "
                            f"the new instance to {other.name}", page=8)
            return other
    game.log.player("inspiration", f"{pc.name} already has Heroic Inspiration; the new instance is lost",
                    page=8)
    return None
