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


# ---------------------------------------------------------------------------
# Rests (p.185 Long Rest, p.187 Short Rest)
# ---------------------------------------------------------------------------
LONG_REST_GAP = 16 * HOUR


def begin_rest(game, kind: str, pcs, focus=None):
    if game.combat is not None:
        raise Refusal("You can't rest during combat")
    for pc in pcs:
        if pc.dead:
            raise Refusal(f"{pc.name} is dead")
        if pc.hp < 1:
            raise Refusal(f"{pc.name} has 0 Hit Points; a rest needs at least 1 Hit Point to start", page=185 if kind == "long" else 187)
        if kind == "long" and pc.long_rest_finished_at is not None \
                and game.clock - pc.long_rest_finished_at < LONG_REST_GAP:
            wait = LONG_REST_GAP - (game.clock - pc.long_rest_finished_at)
            raise Refusal(f"{pc.name} finished a Long Rest {(game.clock - pc.long_rest_finished_at) / HOUR:g} hours ago; "
                          f"must wait at least 16 hours between Long Rests ({wait / HOUR:g} more)", page=185)
    game.rest = {"kind": kind, "members": [p.id for p in pcs], "start": game.clock, "interrupted": None,
                 "interruptions": 0, "focus": focus or {}}
    game.log.player("rest", f"{', '.join(p.name for p in pcs)} begin a {kind.title()} Rest", page=185 if kind == "long" else 187)
    return game.rest


def interrupt_rest(game, reason: str):
    if game.rest is not None:
        game.rest["interrupted"] = reason


def short_rest(game, pcs, hit_dice: dict | None = None, focus=None):
    """1 hour. hit_dice: {pc_id: max dice to spend} (the player decides after each roll)."""
    begin_rest(game, "short", pcs, focus)
    game.advance(HOUR, "Short Rest")
    return finish_short_rest(game, pcs, hit_dice)


def finish_short_rest(game, pcs, hit_dice=None):
    r = game.rest
    game.rest = None
    if r is None:
        return False
    if r["interrupted"]:
        game.log.player("rest", f"The Short Rest is interrupted ({r['interrupted']}); it confers no benefits", page=187)
        return False
    for pc in pcs:
        short_rest_benefits(game, pc, (hit_dice or {}).get(pc.id), r.get("focus", {}).get(pc.id))
    return True


def short_rest_benefits(game, pc, max_dice=None, focus=None):
    from .rules import div
    con = pc.mod("con")
    spent = 0
    while pc.hit_dice_left() > 0 and pc.hp < pc.max_hp and (max_dice is None or spent < max_dice):
        want = game.decide(pc, "spend_hit_die", [True, False], default=True,
                           prompt=f"{pc.name} ({pc.hp}/{pc.max_hp} HP, {pc.hit_dice_left()} Hit Dice): spend a Hit Die?")
        if not want:
            break
        roll = game.dice.roll(pc.hit_die)
        pc.hit_dice_spent += 1
        spent += 1
        pc.heal(max(1, roll + con), f"Hit Die (d{pc.hit_die}={roll} + Con {con})", page=187)
    for name, res in pc.resources.items():
        if res["short"] == "all":
            res["used"] = 0
        elif res["short"]:
            res["used"] = max(0, res["used"] - res["short"])
    game.log.player("rest", f"{pc.name} finishes a Short Rest: {pc.hp}/{pc.max_hp} HP, {pc.hit_dice_left()} Hit Dice "
                    f"left; " + ", ".join(f"{k} {v['max'] - v['used']}/{v['max']}" for k, v in pc.resources.items()),
                    page=187)
    if pc.cls == "wizard" and pc.resource_left("arcane recovery") > 0:
        from .spellcasting import arcane_recovery_offer
        arcane_recovery_offer(game, pc)
    if focus:
        from .magic_items import short_rest_focus
        short_rest_focus(game, pc, focus)


def long_rest(game, pcs, interrupt_after_hours=None, interruption="combat", resume=True, focus=None):
    """8 hours (4 for an Elf in Trance). Optionally interrupted after N hours."""
    begin_rest(game, "long", pcs)
    need = {pc.id: (4 if "trance" in pc.traits else 8) for pc in pcs}
    longest = max(need.values())
    if interrupt_after_hours is not None and interrupt_after_hours < longest:
        game.advance(int(interrupt_after_hours * HOUR), "Long Rest")
        game.rest["interrupted"] = interruption
        rested = interrupt_after_hours
        game.log.player("rest", f"The Long Rest is interrupted after {rested:g} hours ({interruption})", page=185)
        if rested >= 1:
            game.log.player("rest", "At least 1 hour had passed: the rest grants Short Rest benefits", page=185)
            for pc in pcs:
                short_rest_benefits(game, pc)
        if not resume:
            game.rest = None
            return False
        game.rest["interrupted"] = None
        game.rest["interruptions"] += 1
        extra = game.rest["interruptions"]
        remaining = longest - rested + extra
        game.log.player("rest", f"The Long Rest resumes; it needs {extra} extra hour(s) per interruption "
                        f"({remaining:g} hours to go)", page=185)
        game.advance(int(remaining * HOUR), "Long Rest (resumed)")
    else:
        game.advance(longest * HOUR, "Long Rest")
    return finish_long_rest(game, pcs, need)


def finish_long_rest(game, pcs, need=None):
    r = game.rest
    game.rest = None
    if r is None or r["interrupted"]:
        game.log.player("rest", "The Long Rest was interrupted and gives no Long Rest benefits", page=185)
        return False
    for pc in pcs:
        long_rest_benefits(game, pc, trance=(need or {}).get(pc.id) == 4)
    return True


def long_rest_benefits(game, pc, trance=False):
    pc.max_hp_reduction = 0
    pc.hp = pc.max_hp
    pc.hit_dice_spent = 0
    pc.temp_hp = 0
    for name, res in pc.resources.items():
        res["used"] = 0
    pc.slots_used = {}
    for fc in pc.free_casts.values():
        fc["available"] = True
    if pc.exhaustion:
        pc.lose_exhaustion(1, reason="Long Rest")
    pc.long_rest_finished_at = game.clock
    pc.notes["may_change_prepared"] = True
    pc.notes["mastery_swaps"] = 0
    game.log.player("rest", f"{pc.name} finishes a Long Rest{' (4-hour Trance)' if trance else ''}: all HP and Hit "
                    f"Dice restored, spell slots and features recharged", page=185)
    if "resourceful" in pc.traits:
        grant_heroic_inspiration(game, pc, "Resourceful")
