"""The GM automaton: runs monster turns and ends combat. It can't change state
except through the same engine calls a player uses, and it never invents
stat-block abilities (MON-03)."""
from __future__ import annotations

from . import actions, combat as C, class_actions as CA
from .effects import can_see
from .rules import Refusal

LOW_INT = 6


def monster_turn(game, m):
    """Simple tactics: close in and attack; goblins snipe and use Nimble Escape; wolves
    flank for Pack Tactics; low-Int monsters just charge; weak foes flee when badly hurt."""
    cb = game.combat
    if m.dead or not m.can_act():
        game.log.player("turn", f"{m.name} can't act", page=184)
        return
    if m.notes.get("fled"):
        return
    foes = [p for p in game.enemies_of(m) if not p.dead]
    conscious = [p for p in foes if p.conscious]
    targets = conscious or foes
    if not targets:
        return
    # morale: intelligent low-HP monsters flee (neutralized, still worth XP)
    if m.score("int") > LOW_INT and m.hp <= max(1, m.max_hp // 4) and m.key not in ("goblin boss", "ogre") \
            and not m.notes.get("fearless"):
        if "nimble escape" in m.traits:
            try:
                CA.nimble_escape(game, m, "disengage")
            except Refusal:
                pass
        m.notes["fled"] = True
        game.log.player("flee", f"{m.name} flees the fight!", page=255)
        return
    turned = any(e.source == "Turn Undead" for e in m.effects)
    if turned:
        return
    melee = next((a for a in m.attacks if a["kind"] in ("melee", "both")), None)
    ranged = next((a for a in m.attacks if a["kind"] in ("ranged", "both") and a.get("range")), None)

    def score(p):
        d = m.distance_to(p)
        flank = 0
        if "pack tactics" in m.traits:
            flank = -20 if any(a.distance_to(p) <= 5 for a in game.allies_of(m)) else 0
        return d + flank + (0 if p.conscious else 50)
    target = min(targets, key=score)
    attacks = m.multiattack
    for i in range(attacks):
        if target.dead:
            alive = [p for p in targets if not p.dead]
            if not alive:
                break
            target = min(alive, key=score)
        d = m.distance_to(target)
        if melee and d <= melee["reach"]:
            _try_attack(game, m, target, melee["name"])
            continue
        if ranged and (m.key.startswith("goblin") or not melee) and d <= ranged["range"][1]:
            _try_attack(game, m, target, ranged["name"])
            continue
        if cb.turn.movement_left > 0 and i == 0:
            try:
                C.move(game, m, toward=target, feet=cb.turn.movement_left)
            except Refusal:
                pass
            if melee and m.distance_to(target) <= melee["reach"]:
                _try_attack(game, m, target, melee["name"])
            elif ranged and m.distance_to(target) <= ranged["range"][1]:
                _try_attack(game, m, target, ranged["name"])
    # goblins: Nimble Escape to hide after shooting, if there's cover about (and not every time)
    if "nimble escape" in m.traits and not cb.turn.bonus_used and m.notes.get("cover_nearby") \
            and game.dice.rng.random() < 0.4:
        try:
            actions.hide(game, m, cover="three-quarters", bonus=True, source="Nimble Escape (Hide)")
        except Refusal:
            pass


def _try_attack(game, m, target, name):
    try:
        C.attack(game, m, target, attack_name=name)
    except Refusal as e:
        game.log.gm("gm", f"{m.name} can't attack: {e.reason}")


def run_until_pc(game, max_steps=200):
    """Advance combat through monster turns until a conscious PC is up (or combat ends)."""
    cb = game.combat
    steps = 0
    while cb is not None and not cb.ended and steps < max_steps:
        steps += 1
        if combat_over(game):
            finish_combat(game)
            return None
        c = cb.current
        if c is None:
            return None
        if c.team == "party" and c.is_pc():
            if c.dead or c.hp == 0 or not c.can_act():
                C.end_turn(game)
                continue
            return c
        if c.team == "party":            # controlled mounts / allied creatures: the GM holds them
            C.end_turn(game)
            continue
        monster_turn(game, c)
        if combat_over(game):
            finish_combat(game)
            return None
        C.end_turn(game)
    return None


def combat_over(game) -> bool:
    cb = game.combat
    if cb is None:
        return True
    ids = cb.participants
    foes = [game.creatures[i] for i in ids if i in game.creatures and game.creatures[i].team == "enemy"]
    pcs = [game.creatures[i] for i in ids if i in game.creatures and game.creatures[i].team == "party"
           and game.creatures[i].is_pc()]
    foes_active = [f for f in foes if not f.dead and not f.notes.get("fled") and f.conscious]
    pcs_active = [p for p in pcs if not p.dead and p.hp > 0]
    return not foes_active or not pcs_active


def finish_combat(game):
    from .encounters import award_xp
    cb = game.combat
    if cb is None:
        return
    ids = [i for i, _ in cb.order if i in cb.participants] + sorted(i for i in cb.participants
                                                                  if i not in dict(cb.order))
    foes = [game.creatures[i] for i in ids if i in game.creatures and game.creatures[i].team == "enemy"]
    pcs = [p for p in game.pcs() if p.id in cb.participants]
    if not any(not p.dead and p.hp > 0 for p in pcs):
        C.end_combat(game, "the party has fallen")
        game.defeated = True
        game.log.player("defeat", "The party has fallen. The adventure ends here... unless you load an earlier game.")
        return
    C.end_combat(game, "the fight is over")
    beaten = [f for f in foes if f.dead or f.notes.get("fled") or not f.conscious or f.notes.get("surrendered")]
    if beaten and any(not p.dead for p in pcs):
        award_xp(game, beaten, pcs, "defeating or neutralizing foes")
    for f in beaten:
        f.notes["xp_awarded"] = True
