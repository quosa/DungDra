"""Event-log audit: state must reconcile with what the log says happened (J1-J6)."""
from __future__ import annotations

import re


def _since_long_rest(game, pc):
    idx = 0
    for i, e in enumerate(game.log.events):
        if e.kind == "rest" and e.text.startswith(f"{pc.name} finishes a Long Rest"):
            idx = i + 1
    return game.log.events[idx:]


def reconcile(game) -> list[str]:
    problems = []
    for pc in game.pcs():
        evs = _since_long_rest(game, pc)
        hd = sum(1 for e in evs if e.kind == "heal" and e.text.startswith(f"{pc.name} regains") and "Hit Die" in e.text)
        if hd != pc.hit_dice_spent:
            problems.append(f"{pc.name}: {pc.hit_dice_spent} Hit Dice spent but {hd} logged")
        slots = {}
        for e in evs:
            m = re.match(rf"{re.escape(pc.name)} casts .* with a level (\d) slot", e.text)
            if e.kind == "cast" and m:
                slots[int(m.group(1))] = slots.get(int(m.group(1)), 0) + 1
        recovered = {}
        for e in evs:
            m = re.match(rf"{re.escape(pc.name)} uses Arcane Recovery: regains slot\(s\) of level ([\d, ]+)", e.text)
            if m:
                for lv in m.group(1).split(","):
                    recovered[int(lv)] = recovered.get(int(lv), 0) + 1
        for lvl in set(slots) | set(pc.slots_used):
            expect = slots.get(lvl, 0) - recovered.get(lvl, 0)
            if pc.slots_used.get(lvl, 0) != expect:
                problems.append(f"{pc.name}: level {lvl} slots used {pc.slots_used.get(lvl, 0)} but log says {expect}")
        if pc.hp > pc.max_hp or pc.hp < 0:
            problems.append(f"{pc.name}: HP {pc.hp} outside 0..{pc.max_hp}")
    return problems
