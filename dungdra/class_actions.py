"""Class and species feature actions (levels 1-3)."""

from __future__ import annotations

from . import actions
from .effects import AdvNext, Flag
from .rules import MINUTE, Refusal, norm


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
    game.log.player(
        "feature",
        f"{pc.name} uses Second Wind: 1d10={r} + {pc.level}",
        page=48,
        rule="CLASS.fighter.level-1-second-wind",
    )
    return pc.heal(r + pc.level, "Second Wind", rule="CLASS.fighter.level-1-second-wind")


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
        game.log.player(
            "feature",
            f"Tactical Mind: +{r} → {roll.total}, success; a Second Wind use is expended",
            page=48,
            rule="CLASS.fighter.level-2-tactical-mind",
        )
    else:
        game.log.player(
            "feature",
            f"Tactical Mind: +{r} → {roll.total}, still a failure; the Second Wind use isn't expended",
            page=48,
            rule="CLASS.fighter.level-2-tactical-mind",
        )
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
    game.log.player(
        "feature",
        f"{pc.name} uses Action Surge: one additional action (not the Magic action)",
        page=48,
        rule="CLASS.fighter.level-2-action-surge",
    )


# -- Features that let a creature take an action as a Bonus Action -----------------
# Each grant declares once who holds it and which actions it allows; every way of taking one
# of those actions as a Bonus Action (the feature itself, or a command's bonus=True) goes
# through `_take_granted`, so the check and the effect's source label live in one place.
_BONUS_TAKEABLE = {"dash": actions.dash, "disengage": actions.disengage, "hide": actions.hide}

ACTION_GRANTS = {
    # SRD[CLASS.rogue.level-2-cunning-action]: Dash, Disengage or Hide as a Bonus Action
    "cunning action": {
        "label": "Cunning Action",
        "holds": lambda c: hasattr(c, "has_feature") and c.has_feature("cunning action"),
        "allows": ("dash", "disengage", "hide"),
        "page": 62,
        "rule": "CLASS.rogue.level-2-cunning-action",
    },
    # SRD[MONSTER.goblins.goblin-warrior#24]: a stat-block Bonus Action, Disengage or Hide only
    "nimble escape": {
        "label": "Nimble Escape",
        "holds": lambda c: "nimble escape" in c.traits,
        "allows": ("disengage", "hide"),
        "page": 290,
        "rule": "MONSTER.goblins.goblin-warrior#24",
    },
}


def _take_granted(game, creature, feature, what, **kw):
    grant = ACTION_GRANTS[feature]
    if not grant["holds"](creature):
        raise Refusal(
            f"{creature.name} doesn't have {grant['label']}", page=grant["page"], rule=grant["rule"]
        )
    what = norm(what)
    if what not in grant["allows"]:
        allowed = ", ".join(a.title() for a in grant["allows"][:-1]) + f" or {grant['allows'][-1].title()}"
        raise Refusal(
            f"{grant['label']} allows only {allowed} as a Bonus Action",
            page=grant["page"],
            rule=grant["rule"],
        )
    source = f"{grant['label']} ({what.title()})"
    return _BONUS_TAKEABLE[what](game, creature, bonus=True, source=source, **kw)


def take_as_bonus(game, creature, what, **kw):
    """Take Dash, Disengage or Hide as a Bonus Action through the feature that grants it."""
    what = norm(what)
    for feature, grant in ACTION_GRANTS.items():
        if what in grant["allows"] and grant["holds"](creature):
            return _take_granted(game, creature, feature, what, **kw)
    # SRD[PLAY.actions.bonus-actions]: a Bonus Action exists only when a feature grants one
    raise Refusal(
        f"{creature.name} has no feature that lets it take the {what.title()} action as a Bonus Action",
        page=10,
        rule="PLAY.actions.bonus-actions",
    )


def cunning_action(game, pc, what="dash", **kw):
    return _take_granted(game, pc, "cunning action", what, **kw)


def steady_aim(game, pc):
    _need(pc, "steady aim")
    cb = game.combat
    if cb is not None and cb.is_turn(pc) and cb.turn.moved > 0:
        raise Refusal(
            "Steady Aim can be used only if you haven't moved this turn",
            page=62,
            rule="CLASS.rogue.level-3-steady-aim",
        )
    actions.spend(game, pc, "bonus", "Steady Aim")
    pc.add_effect(AdvNext("Steady Aim", kinds=("attack",), ends=[("end", pc.id)]))
    pc.add_effect(Flag("speed 0", "Steady Aim: Speed 0", ends=[("end", pc.id)]))
    pc.effects[-1].speed_zero = lambda owner: True
    if cb is not None and cb.is_turn(pc):
        cb.turn.movement_left = 0
    game.log.player(
        "feature",
        f"{pc.name} uses Steady Aim: Advantage on the next attack this turn; Speed 0",
        page=62,
        rule="CLASS.rogue.level-3-steady-aim",
    )


def nimble_escape(game, monster, what="disengage", **kw):
    return _take_granted(game, monster, "nimble escape", what, **kw)


def stonecunning(game, pc, on_stone=True):
    if "stonecunning" not in pc.traits:
        raise Refusal(f"{pc.name} doesn't have Stonecunning")
    if not on_stone:
        raise Refusal(
            "Stonecunning works only while on or touching a stone surface",
            page=84,
            rule="ORIGIN.character-species.species-descriptions.dwarf",
        )
    if pc.resource_left("stonecunning") <= 0:
        raise Refusal("No Stonecunning uses left")
    actions.spend(game, pc, "bonus", "Stonecunning")
    pc.spend("stonecunning")
    pc.senses["tremorsense"] = 60
    pc.add_effect(Flag("tremorsense", "Stonecunning: Tremorsense 60 ft", until=game.clock + 10 * MINUTE))
    game.log.player(
        "feature",
        f"{pc.name} gains Tremorsense 60 ft for 10 minutes (Stonecunning)",
        page=84,
        rule="ORIGIN.character-species.species-descriptions.dwarf",
    )


BONUS_ACTIONS = {
    "second wind": second_wind,
    "steady aim": steady_aim,
    "stonecunning": stonecunning,
    "cunning action": cunning_action,
    "nimble escape": nimble_escape,
}


def parse_feature(name) -> tuple[str, str | None]:
    """Split "cunning action: dash" into the feature ("cunning action") and its option ("dash")."""
    feature, sep, option = str(name).partition(":")
    return norm(feature), (option.strip() if sep else None)


def is_bonus_action(name) -> bool:
    """Whether the feature `name` ("cunning action: dash", "second_wind", ...) costs a Bonus Action."""
    return parse_feature(name)[0] in BONUS_ACTIONS


def bonus_action(game, actor, name, *args, **kw):
    """Generic entry point: a Bonus Action exists only when a feature grants one (p.10).

    An option after a colon ("cunning action: dash") is passed as the feature's first argument."""
    feature, option = parse_feature(name)
    fn = BONUS_ACTIONS.get(feature)
    if fn is None:
        raise Refusal(
            f"{actor.name} has no feature that grants a Bonus Action to {name}",
            page=10,
            rule="PLAY.actions.bonus-actions",
        )
    if option is not None:
        args = (option, *args)
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
    game.log.player(
        "feature",
        f"{pc.name} uses Channel Divinity: Divine Spark ({n}d8={rolls} + Wis {pc.mod('wis')} = {amount})",
        page=37,
        rule="CLASS.cleric.level-2-channel-divinity",
    )
    if mode == "heal":
        return target.heal(amount, "Divine Spark", page=37, rule="CLASS.cleric.level-2-channel-divinity")
    r = target.save(
        "con",
        pc.spell_dc(),
        label=f"Constitution save vs Divine Spark (DC {pc.spell_dc()})",
        source=pc,
        page=37,
        rule="CLASS.cleric.level-2-channel-divinity",
    )
    return target.take_damage(
        amount // 2 if r.success else amount,
        dtype,
        attacker=pc,
        source="Divine Spark",
        rule="CLASS.cleric.level-2-channel-divinity",
    )


def turn_undead(game, pc, targets):
    from .spells import TurnedEffect

    _channel(game, pc)
    game.log.player(
        "feature",
        f"{pc.name} uses Channel Divinity: Turn Undead",
        page=37,
        rule="CLASS.cleric.level-2-channel-divinity",
    )
    for t in targets:
        if t.ctype != "undead" or pc.distance_to(t) > 30:
            continue
        r = t.save(
            "wis",
            pc.spell_dc(),
            label=f"Wisdom save vs Turn Undead (DC {pc.spell_dc()})",
            source=pc,
            page=37,
            rule="CLASS.cleric.level-2-channel-divinity",
        )
        if not r.success:
            for cond in ("frightened", "incapacitated"):
                t.add_effect(TurnedEffect(cond, source="Turn Undead", caster=pc, until=game.clock + MINUTE))
            game.log.player(
                "condition",
                f"{t.name} is Frightened and Incapacitated for 1 minute and flees from "
                f"{pc.name} (ends if it takes damage)",
                page=37,
                rule="CLASS.cleric.level-2-channel-divinity",
            )
            game.on_incapacitated(t)


def preserve_life(game, pc, allocation: dict):
    """p.40: restore 5 x Cleric level HP divided among Bloodied creatures within 30 ft,
    none above half its HP maximum."""
    _need(pc, "preserve life")
    pool = 5 * pc.level
    if sum(allocation.values()) > pool:
        raise Refusal(
            f"Preserve Life restores at most {pool} HP in total",
            page=40,
            rule="CLASS.cleric.cleric-subclass-life-domain.level-3-preserve-life",
        )
    for cid in allocation:
        t = game.get(cid)
        if not t.bloodied:
            raise Refusal(
                f"{t.name} isn't Bloodied",
                page=40,
                rule="CLASS.cleric.cleric-subclass-life-domain.level-3-preserve-life",
            )
        if pc.distance_to(t) > 30:
            raise Refusal(
                f"{t.name} is more than 30 ft away",
                page=40,
                rule="CLASS.cleric.cleric-subclass-life-domain.level-3-preserve-life",
            )
    _channel(game, pc)
    game.log.player(
        "feature",
        f"{pc.name} uses Channel Divinity: Preserve Life ({pool} HP to divide)",
        page=40,
        rule="CLASS.cleric.cleric-subclass-life-domain.level-3-preserve-life",
    )
    out = {}
    for cid, amt in allocation.items():
        t = game.get(cid)
        cap = t.max_hp // 2
        give = max(0, min(amt, cap - t.hp))
        if give < amt:
            game.log.player(
                "feature",
                f"{t.name} can be restored only to half its HP maximum ({cap})",
                page=40,
                rule="CLASS.cleric.cleric-subclass-life-domain.level-3-preserve-life",
            )
        out[cid] = t.heal(
            give,
            "Preserve Life",
            page=40,
            rule="CLASS.cleric.cleric-subclass-life-domain.level-3-preserve-life",
        )
    return out


def change_mastery(game, pc, old: str, new: str):
    """Weapon Mastery (p.48, p.62): after a Long Rest a Fighter may change one choice; a Rogue may change
    both. Only allowed before anything else wears off the rest (tracked per Long Rest)."""
    from .data.equipment import WEAPONS, canonical

    old, new = canonical(old), canonical(new)
    if pc.long_rest_finished_at is None:
        raise Refusal(
            "Weapon Mastery choices change only when you finish a Long Rest",
            page=48,
            rule=f"CLASS.{pc.cls}.level-1-weapon-mastery",
        )
    if old not in pc.weapon_masteries:
        raise Refusal(f"{pc.name} doesn't have mastery with {old}")
    if new not in WEAPONS or not pc.proficient_with(new):
        raise Refusal(f"{pc.name} must be proficient with {new} to master it")
    limit = 1 if pc.cls == "fighter" else len(pc.weapon_masteries)
    if pc.notes.get("mastery_swaps", 0) >= limit:
        raise Refusal(
            f"{pc.name} can change only {limit} Weapon Mastery choice(s) per Long Rest",
            page=48,
            rule=f"CLASS.{pc.cls}.level-1-weapon-mastery",
        )
    pc.weapon_masteries[pc.weapon_masteries.index(old)] = new
    pc.notes["mastery_swaps"] = pc.notes.get("mastery_swaps", 0) + 1
    game.log.player(
        "feature",
        f"{pc.name} practices weapon drills: mastery {old.title()} → {new.title()}",
        page=48,
        rule=f"CLASS.{pc.cls}.level-1-weapon-mastery",
    )
