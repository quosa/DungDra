"""Class and species feature actions (levels 1-3)."""
from __future__ import annotations

from . import actions
from .effects import AdvNext, Flag
from .rules import MINUTE, Refusal


def _need(pc, feature):
    if not (hasattr(pc, "has_feature") and pc.has_feature(feature)):
        raise Refusal(f"{pc.name} doesn't have {feature.title()}")


def second_wind(game, pc):
    """p.48: Bonus Action, regain 1d10 + Fighter level HP."""
    _need(pc, "second wind")
    if pc.resource_left("second wind") <= 0:
        raise Refusal(f"{pc.name} has no Second Wind uses left")
    actions.spend(game, pc, "bonus", "Second Wind")
    pc.spend("second wind")
    r = game.dice.roll(10)
    game.log.player("feature", f"{pc.name} uses Second Wind: 1d10={r} + {pc.level}", page=48)
    return pc.heal(r + pc.level, "Second Wind")


def tactical_mind(game, pc, roll):
    """p.48: after failing an ability check, add 1d10; the use is only expended if it now succeeds."""
    _need(pc, "tactical mind")
    if roll.kind != "check" or roll.success:
        raise Refusal("Tactical Mind applies to a failed ability check")
    if pc.resource_left("second wind") <= 0:
        raise Refusal(f"{pc.name} has no Second Wind uses left")
    r = game.dice.roll(10)
    roll.add_mod(r, f"Tactical Mind (1d10={r})")
    if roll.success:
        pc.spend("second wind")
        game.log.player("feature", f"Tactical Mind: +{r} → {roll.total}, success; a Second Wind use is expended",
                        page=48)
    else:
        game.log.player("feature", f"Tactical Mind: +{r} → {roll.total}, still a failure; the Second Wind use "
                        f"isn't expended", page=48)
    return roll


def action_surge(game, pc):
    _need(pc, "action surge")
    if pc.resource_left("action surge") <= 0:
        raise Refusal(f"{pc.name} has already used Action Surge; it recharges on a Short or Long Rest")
    cb = game.combat
    if cb is None or not cb.is_turn(pc):
        raise Refusal("Action Surge is used on your turn")
    if cb.turn.action_surge_used:
        raise Refusal("Action Surge can be used only once on a turn")
    pc.spend("action surge")
    cb.turn.actions += 1
    cb.turn.action_surge_used = True
    cb.turn.surge_active = True
    cb.turn.attacks_left = 0
    game.log.player("feature", f"{pc.name} uses Action Surge: one additional action (not the Magic action)", page=48)


def cunning_action(game, pc, what):
    _need(pc, "cunning action")
    what = what.lower()
    if what == "dash":
        return actions.dash(game, pc, bonus=True, source="Cunning Action (Dash)")
    if what == "disengage":
        return actions.disengage(game, pc, bonus=True, source="Cunning Action (Disengage)")
    if what == "hide":
        return None  # caller uses actions.hide(..., bonus=True)
    raise Refusal("Cunning Action allows only Dash, Disengage or Hide as a Bonus Action", page=62)


def steady_aim(game, pc):
    _need(pc, "steady aim")
    cb = game.combat
    if cb is not None and cb.is_turn(pc) and cb.turn.moved > 0:
        raise Refusal("Steady Aim can be used only if you haven't moved this turn", page=62)
    actions.spend(game, pc, "bonus", "Steady Aim")
    pc.add_effect(AdvNext("Steady Aim", kinds=("attack",), ends=[("end", pc.id)]))
    pc.add_effect(Flag("speed 0", "Steady Aim: Speed 0", ends=[("end", pc.id)]))
    pc.effects[-1].speed_zero = lambda owner: True
    if cb is not None and cb.is_turn(pc):
        cb.turn.movement_left = 0
    game.log.player("feature", f"{pc.name} uses Steady Aim: Advantage on the next attack this turn; Speed 0", page=62)


def nimble_escape(game, monster, what="disengage", **kw):
    if "nimble escape" not in monster.traits:
        raise Refusal(f"{monster.name} doesn't have Nimble Escape")
    if what == "disengage":
        return actions.disengage(game, monster, bonus=True, source="Nimble Escape")
    return actions.hide(game, monster, bonus=True, source="Nimble Escape (Hide)", **kw)


def stonecunning(game, pc, on_stone=True):
    if "stonecunning" not in pc.traits:
        raise Refusal(f"{pc.name} doesn't have Stonecunning")
    if not on_stone:
        raise Refusal("Stonecunning works only while on or touching a stone surface", page=84)
    if pc.resource_left("stonecunning") <= 0:
        raise Refusal("No Stonecunning uses left")
    actions.spend(game, pc, "bonus", "Stonecunning")
    pc.spend("stonecunning")
    pc.senses["tremorsense"] = 60
    pc.add_effect(Flag("tremorsense", "Stonecunning: Tremorsense 60 ft", until=game.clock + 10 * MINUTE))
    game.log.player("feature", f"{pc.name} gains Tremorsense 60 ft for 10 minutes (Stonecunning)", page=84)


BONUS_ACTIONS = {
    "second wind": second_wind, "steady aim": steady_aim, "stonecunning": stonecunning,
}


def bonus_action(game, actor, name, *args, **kw):
    """Generic entry point: a Bonus Action exists only when a feature grants one (p.10)."""
    n = name.lower()
    if n.startswith("cunning action"):
        return cunning_action(game, actor, n.split(":")[-1].strip() if ":" in n else kw.pop("what", "dash"))
    fn = BONUS_ACTIONS.get(n)
    if fn is None:
        raise Refusal(f"{actor.name} has no feature that grants a Bonus Action to {name}", page=10)
    return fn(game, actor, *args, **kw)


# -- Cleric: Channel Divinity (p.37, 40) -------------------------------------------
def _channel(game, pc):
    _need(pc, "channel divinity")
    if pc.inventory.find("holy symbol") is None:
        raise Refusal(f"{pc.name} must present a Holy Symbol")
    if pc.resource_left("channel divinity") <= 0:
        raise Refusal(f"{pc.name} has no Channel Divinity uses left")
    actions.spend(game, pc, "action", "Magic")
    pc.spend("channel divinity")


def divine_spark(game, pc, target, mode="heal", dtype="radiant"):
    if pc.distance_to(target) > 30:
        raise Refusal("Divine Spark reaches a creature within 30 feet")
    _channel(game, pc)
    n = 1 if pc.level < 7 else 2
    total, rolls, _ = game.dice.roll_expr(f"{n}d8")
    amount = total + pc.mod("wis")
    game.log.player("feature", f"{pc.name} uses Channel Divinity: Divine Spark ({n}d8={rolls} + Wis {pc.mod('wis')} "
                    f"= {amount})", page=37)
    if mode == "heal":
        return target.heal(amount, "Divine Spark", page=37)
    r = target.save("con", pc.spell_dc(), label=f"Constitution save vs Divine Spark (DC {pc.spell_dc()})", page=37)
    return target.take_damage(amount // 2 if r.success else amount, dtype, attacker=pc, source="Divine Spark")


def turn_undead(game, pc, targets):
    from .spells import TurnedEffect
    _channel(game, pc)
    game.log.player("feature", f"{pc.name} uses Channel Divinity: Turn Undead", page=37)
    for t in targets:
        if t.ctype != "undead" or pc.distance_to(t) > 30:
            continue
        r = t.save("wis", pc.spell_dc(), label=f"Wisdom save vs Turn Undead (DC {pc.spell_dc()})", page=37)
        if not r.success:
            for cond in ("frightened", "incapacitated"):
                t.add_effect(TurnedEffect(cond, source="Turn Undead", caster=pc, until=game.clock + MINUTE))
            game.log.player("condition", f"{t.name} is Frightened and Incapacitated for 1 minute and flees from "
                            f"{pc.name} (ends if it takes damage)", page=37)
            game.on_incapacitated(t)


def preserve_life(game, pc, allocation: dict):
    """p.40: restore 5 x Cleric level HP divided among Bloodied creatures within 30 ft,
    none above half its HP maximum."""
    _need(pc, "preserve life")
    pool = 5 * pc.level
    if sum(allocation.values()) > pool:
        raise Refusal(f"Preserve Life restores at most {pool} HP in total", page=40)
    for cid, amt in allocation.items():
        t = game.get(cid)
        if not t.bloodied:
            raise Refusal(f"{t.name} isn't Bloodied", page=40)
        if pc.distance_to(t) > 30:
            raise Refusal(f"{t.name} is more than 30 ft away", page=40)
    _channel(game, pc)
    game.log.player("feature", f"{pc.name} uses Channel Divinity: Preserve Life ({pool} HP to divide)", page=40)
    out = {}
    for cid, amt in allocation.items():
        t = game.get(cid)
        cap = t.max_hp // 2
        give = max(0, min(amt, cap - t.hp))
        if give < amt:
            game.log.player("feature", f"{t.name} can be restored only to half its HP maximum ({cap})", page=40)
        out[cid] = t.heal(give, "Preserve Life", page=40)
    return out
