"""What can a character still do this turn? Used for turn hints and auto-ending turns."""
from __future__ import annotations

from .data.spells import SPELLS
from .effects import can_see


def bonus_options(game, pc) -> list[str]:
    cb = game.combat
    t = cb.turn
    if t.bonus_used or not pc.can_act():
        return []
    out = []
    hurt = any(a.hp < a.max_hp for a in [pc] + game.allies_of(pc))
    if pc.has_feature("cunning action"):
        out.append("Cunning Action (Dash/Disengage/Hide)")
    if pc.has_feature("second wind") and pc.resource_left("second wind") and pc.hp < pc.max_hp:
        out.append("Second Wind")
    if pc.has_feature("steady aim") and t.moved == 0:
        out.append("Steady Aim")
    if t.attack_action_taken and not t.light_attack_done and t.notes.get("light_weapon") is not None:
        others = [w for w in pc.inventory if w.weapon and "light" in w.weapon["props"]
                  and w.uid != t.notes["light_weapon"]]
        if others:
            out.append(f"extra attack with {others[0].display} (Light)")
    if hurt and pc.inventory.find("potion of healing"):
        out.append("drink/administer a Potion of Healing")
    for sp in pc.all_known_spells():
        d = SPELLS.get(sp)
        if not d or d["time"] != "bonus action":
            continue
        if d.get("healing") and not hurt:
            continue
        ways = pc.castable(sp)
        free = any(w.get("free") and pc.free_casts[sp]["available"] for w in ways)
        slot_ok = any(pc.slots_left(l) > 0 for l in range(max(1, d["level"]), 4)) and not t.slot_spell_cast
        if free or slot_ok or d["level"] == 0:
            out.append(f"cast {sp.title()}")
    if any(e.name == "Spiritual Weapon" for e in pc.effects):
        out.append("attack with the Spiritual Weapon")
    return out


def turn_summary(game, pc) -> tuple[str, bool]:
    """Return (hint text, anything_left). Movement alone doesn't count as something left to do."""
    cb = game.combat
    t = cb.turn
    parts = []
    action = t.action_available() and pc.can_act()
    if action:
        parts.append("action available")
    else:
        parts.append("action used")
    bonus = bonus_options(game, pc)
    if bonus:
        parts.append("Bonus Action: " + ", ".join(bonus))
    if t.movement_left > 0:
        parts.append(f"{t.movement_left} ft of movement left")
    foes_left = any(not e.dead and e.conscious and not e.notes.get("fled") for e in game.enemies_of(pc))
    return "; ".join(parts), bool((action or bonus) and foes_left)
