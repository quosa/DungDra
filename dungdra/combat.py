"""Combat: Initiative, turns and the action economy, movement, attacks, damage,
Opportunity Attacks, the Ready action, grappling and shoving (SRD p.13-18, glossary)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .d20 import D20Roll, inspiration_reroll, roll_d20_test
from .data.equipment import WEAPONS
from .dice import parse_expr
from .effects import AdvNext, Ctx, Flag, SpeedPenalty, can_see, grapplers_of, grapples_on
from .geometry import dist_points, squares_overlap, step_away, step_toward, steps_between
from .mounted import moves_on_riders_turn
from .rules import ROUND, SPACE, Refusal, fmt_mod, size_index


# ---------------------------------------------------------------------------
# Turn state and initiative
# ---------------------------------------------------------------------------
@dataclass
class TurnState:
    cid: str
    actions: int = 1
    actions_used: int = 0
    bonus_used: bool = False
    movement_left: int = 0
    moved: int = 0
    dashes: int = 0
    free_interaction: bool = False
    attack_equip_used: bool = False
    attacks_left: int = 0  # attacks remaining in the current Attack action
    attack_action_taken: bool = False
    light_attack_done: bool = False
    nick_used: bool = False
    sneak_attack_used: bool = False
    savage_used: bool = False
    slot_spell_cast: bool = False
    action_surge_used: bool = False
    surge_active: bool = False
    loading_fired: set = field(default_factory=set)
    notes: dict = field(default_factory=dict)
    log: list = field(default_factory=list)

    def action_available(self) -> bool:
        return self.actions_used < self.actions


class Combat:
    def __init__(self, game):
        self.game = game
        self.order: list[tuple[str, int]] = []
        self.round = 1
        self.index = 0
        self.reaction_used: set[str] = set()
        self.turn: TurnState | None = None
        self.start_clock = game.clock
        self.participants: set[str] = set()
        self.ammo_spent: dict[tuple[str, str], int] = {}
        self.defeated: list[str] = []
        self.ended = False
        self.readied: dict[str, Readied] = {}  # readier id -> its readied response

    # -- queries --
    @property
    def current(self):
        if not self.order:
            return None
        return self.game.creatures.get(self.order[self.index][0])

    def initiative_of(self, c) -> int | None:
        for cid, v in self.order:
            if cid == c.id:
                return v
        return None

    def order_state(self):
        return {
            "round": self.round,
            "current": self.current.id if self.current else None,
            "order": [{"id": cid, "initiative": v} for cid, v in self.order],
        }

    def is_turn(self, c) -> bool:
        return self.current is c

    def has_reaction(self, c) -> bool:
        return c.id not in self.reaction_used and c.can_act()

    # -- action economy --
    def spend_movement(
        self,
        c,
        cost: int,
        what: str,
        *,
        page: int,
        rule: str,
        ruling: str | None = None,
        free_off_turn: bool = False,
    ) -> bool:
        """Spend `cost` ft of the turn's movement on `what`, or refuse before anything changes.

        Movement is a budget of the creature's own turn, so off-turn there is none to spend and
        the cost is refused. `free_off_turn` is for voluntary moves another feature grants
        off-turn under its own limit (a readied move, a controlled mount on its rider's turn):
        they are allowed without touching the turn's budget. Returns whether the budget was
        spent."""
        if not self.is_turn(c):
            if free_off_turn:
                return False
            raise Refusal(
                f"{what} costs {cost} ft of movement, which {c.name} has only on their own turn",
                page=page,
                rule=rule,
                ruling=ruling,
            )
        # R-22: no partial spend; the full cost must be left
        if cost > self.turn.movement_left:
            raise Refusal(
                f"{what} costs {cost} ft of movement; {c.name} has {self.turn.movement_left} ft left",
                page=page,
                rule=rule,
                ruling=ruling,
            )
        self.turn.movement_left -= cost
        return True

    def _require_turn(self, actor, what="action"):
        """Refuse unless it is `actor`'s turn and it can act; returns the turn's budget."""
        if not self.is_turn(actor):
            if what == "bonus":
                # SRD[PLAY.actions.bonus-actions]: a Bonus Action is "an additional action on your turn"
                raise Refusal(f"It isn't {actor.name}'s turn", page=10, rule="PLAY.actions.bonus-actions")
            # SRD[PLAY.combat.the-order-of-combat]: a combatant acts during its own turn
            raise Refusal(f"It isn't {actor.name}'s turn", page=13, rule="PLAY.combat.the-order-of-combat")
        if not actor.can_act():
            raise Refusal(
                f"{actor.name} can't take actions (Incapacitated)", page=184, rule="GLOSS.incapacitated"
            )
        return self.turn

    def require_action(self, actor, label=""):
        """Refuse unless it is `actor`'s turn and its action is still free; spends nothing."""
        t = self._require_turn(actor)
        if not t.action_available():
            raise Refusal(
                f"{actor.name} has already taken their action this turn",
                page=13,
                rule="PLAY.combat.the-order-of-combat",
            )
        if label == "Magic" and t.surge_active and t.actions_used == 1:
            raise Refusal(
                "Action Surge grants an additional action other than the Magic action",
                page=48,
                rule="CLASS.fighter.level-2-action-surge",
            )

    def spend(self, actor, what="action", label=""):
        if what == "reaction":
            if actor.id in self.reaction_used:
                raise Refusal(
                    f"{actor.name} has already used their Reaction this round",
                    page=186,
                    rule="GLOSS.reaction",
                )
            if not actor.can_act():
                raise Refusal(
                    f"{actor.name} can't take Reactions (Incapacitated)", page=184, rule="GLOSS.incapacitated"
                )
            self.reaction_used.add(actor.id)
            return
        if what == "action":
            self.require_action(actor, label)
            t = self.turn
            t.actions_used += 1
            t.log.append(label or "action")
            return
        t = self._require_turn(actor, what)
        if what == "bonus":
            if t.bonus_used:
                raise Refusal(
                    f"{actor.name} has already taken a Bonus Action this turn",
                    page=10,
                    rule="PLAY.actions.bonus-actions",
                )
            t.bonus_used = True
            t.log.append(f"bonus: {label}")
        elif what == "free":
            if t.free_interaction:
                raise Refusal(
                    f"{actor.name} already used their free object interaction; "
                    f"another needs the Utilize action",
                    page=13,
                    rule="PLAY.combat.the-order-of-combat",
                )
            t.free_interaction = True

    def on_death(self, creature):
        if creature.id not in self.defeated:
            self.defeated.append(creature.id)


def roll_initiative(game, participants, surprised=(), groups=None):
    """Start combat. `surprised`: creatures unaware at the start (Disadvantage).
    Identical monsters share a single roll (p.13)."""
    from .monster import Monster

    if game.combat is not None and not game.combat.ended:
        raise Refusal("Combat is already under way")
    cb = Combat(game)
    game.combat = cb
    if game.rest is not None:
        game.rest["interrupted"] = "Initiative was rolled"
    surprised = {getattr(s, "id", s) for s in surprised}
    results: dict[str, int] = {}
    group_rolls: dict[str, int] = {}
    game.log.player("combat", "Roll Initiative!", page=13, rule="PLAY.combat.the-order-of-combat")
    for c in participants:
        if c.dead:
            continue
        cb.participants.add(c.id)
        gkey = c.key if isinstance(c, Monster) and (groups is None or groups) else None
        if gkey and gkey in group_rolls:
            results[c.id] = group_rolls[gkey]
            game.log.player(
                "initiative",
                f"{c.name} shares its group's Initiative {group_rolls[gkey]}",
                page=13,
                rule="PLAY.combat.the-order-of-combat",
            )
            continue
        r = initiative_roll(game, c, c.id in surprised)
        results[c.id] = r.total
        if gkey:
            group_rolls[gkey] = r.total
    # Ties: players order their PCs, the GM the rest (ties PC vs monster: GM's call)
    ordered = sorted(
        results.items(),
        key=lambda kv: (
            -kv[1],
            0 if game.creatures[kv[0]].team == "party" else 1,
            -game.creatures[kv[0]].score("dex"),
        ),
    )
    cb.order = ordered
    _tie_log(game, ordered)
    # Alert: Initiative Swap immediately after rolling (p.87)
    for cid, _ in list(cb.order):
        c = game.creatures[cid]
        if getattr(c, "has_feat", None) and c.has_feat("alert"):
            # SRD[GLOSS.ally#2] SRD[GLOSS.ally#3] any ally, Friendly NPCs included (R-37)
            allies = [x for x, _ in cb.order if game.is_ally(c, game.creatures[x])]
            pick = game.decide(
                c,
                "alert_swap",
                [None] + allies,
                default=None,
                prompt=f"{c.name} (Alert): swap Initiative with a willing ally?",
            )
            if pick:
                swap_initiative(game, c, game.get(pick))
    game.log.player(
        "combat",
        "Initiative order: " + ", ".join(f"{game.creatures[i].name} {v}" for i, v in cb.order),
        page=13,
        rule="PLAY.combat.the-order-of-combat",
    )
    cb.index = 0
    start_turn(game)
    return cb


def _tie_log(game, ordered):
    seen = {}
    for cid, v in ordered:
        seen.setdefault(v, []).append(cid)
    for v, ids in seen.items():
        if len(ids) > 1:
            teams = {game.creatures[i].team for i in ids}
            who = (
                "players (PCs)"
                if teams == {"party"}
                else "GM (monsters)"
                if "party" not in teams
                else "GM (PC vs monster)"
            )
            game.log.player(
                "initiative",
                f"Tie at {v} between {', '.join(game.creatures[i].name for i in ids)}; "
                f"order decided by the {who}",
                page=13,
                rule="PLAY.combat.the-order-of-combat",
            )


def initiative_roll(game, c, surprised=False) -> D20Roll:
    ctx = Ctx("initiative", c, ability="dex", tags={"initiative"})
    acc = c.gather(ctx)
    roll = D20Roll("initiative", "Initiative (Dex check)", c.name)
    base = c.init_bonus if hasattr(c, "init_bonus") else c.mod("dex")
    roll.mods = [(base, "Initiative" if hasattr(c, "init_bonus") else "Dex")] + acc.mods
    roll.adv = list(acc.adv)
    roll.dis = list(acc.dis) + (["surprised"] if surprised else [])
    return roll_d20_test(
        game,
        c,
        roll,
        bonus_dice=acc.bonus_dice,
        page=13,
        rule="PLAY.combat.the-order-of-combat",
        rulings=acc.rulings,
    )


def swap_initiative(game, a, b):
    if a.has("incapacitated") or b.has("incapacitated"):
        raise Refusal(
            "Initiative Swap isn't possible while either creature is Incapacitated",
            page=87,
            rule="FEAT.feat-descriptions.origin-feats.alert",
        )
    cb = game.combat
    ia, ib = cb.initiative_of(a), cb.initiative_of(b)
    cb.order = [(cid, ib if cid == a.id else ia if cid == b.id else v) for cid, v in cb.order]
    cb.order.sort(key=lambda kv: -kv[1])
    game.log.player(
        "initiative",
        f"{a.name} swaps Initiative with {b.name}: {a.name} {ib}, {b.name} {ia}",
        page=87,
        rule="FEAT.feat-descriptions.origin-feats.alert",
    )


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------
def start_turn(game):
    cb = game.combat
    c = cb.current
    if c is None:
        return
    cb.turn = TurnState(c.id)
    cb.reaction_used.discard(c.id)
    _readied_lapses(game, c)
    cb.turn.movement_left = c.speed()
    game.turn_actor = c
    game.log.player(
        "turn", f"Round {cb.round}: {c.name}'s turn", page=13, rule="PLAY.combat.the-order-of-combat"
    )
    _expire(game, "start", c)
    for e in list(c.effects):
        e.on_turn_start(game)
    if c.dead:
        return
    if c.is_pc() and c.hp == 0 and not c.stable and not c.dead:
        from .damage import death_save

        death_save(game, c)
    cb.turn.movement_left = c.speed()


def end_turn(game):
    cb = game.combat
    c = cb.current
    if c is not None:
        for e in list(c.effects):
            e.on_turn_end(game)
        _expire(game, "end", c)
        # Hide/Invisible from Hide doesn't expire, Disengage does
    cb.index += 1
    if cb.index >= len(cb.order):
        cb.index = 0
        cb.round += 1
        game.clock += ROUND
        game.expire_effects()
    # skip dead creatures (monsters) but keep dying PCs (they make death saves)
    guard = 0
    while guard < len(cb.order):
        nxt = game.creatures.get(cb.order[cb.index][0])
        if nxt is not None and not nxt.dead:
            break
        cb.index += 1
        if cb.index >= len(cb.order):
            cb.index = 0
            cb.round += 1
            game.clock += ROUND
            game.expire_effects()
        guard += 1
    start_turn(game)


def _expire(game, when, c):
    for cr in list(game.creatures.values()):
        for e in list(cr.effects):
            if (when, c.id) in e.ends:
                skip = e.data.get("skip", {})
                if skip.get((when, c.id)):
                    skip[(when, c.id)] -= 1
                    continue
                cr.remove_effect(e, f"{'start' if when == 'start' else 'end'} of {c.name}'s turn")


def end_combat(game, reason=""):
    cb = game.combat
    if cb is None:
        return
    cb.ended = True
    rounds = cb.round
    for cid in list(cb.readied):
        _readied_lapses(game, game.creatures[cid], "combat ended")
    # the final round counts in full, even when the fight ends partway through it
    game.clock = max(game.clock, cb.start_clock + rounds * ROUND)
    game.log.player(
        "combat",
        f"Combat ends after {rounds} round{'s' if rounds != 1 else ''}" + (f" ({reason})" if reason else ""),
        page=14,
        rule="PLAY.combat",
        rounds=rounds,
    )
    game.combat = None
    game.turn_actor = None
    for c in game.creatures.values():
        for e in list(c.effects):
            if (
                any(k in ("start", "end") for k, _ in e.ends)
                and e.until is None
                and not e.concentration
                and not e.condition
            ):
                c.remove_effect(e)
    return rounds


# ---------------------------------------------------------------------------
# Movement (p.14, glossary)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MoveMode:
    """How a mode of movement uses Speed: the Speed it spends, whether a creature without
    that Speed may still move by walking, whether doing so costs extra feet, and whether the
    mode is crawling (each foot costs 1 extra foot)."""

    speed: str
    walk_fallback: bool = True
    extra_without: bool = False
    extra_note: str = ""
    crawling: bool = False


MOVE_MODES = {
    "walk": MoveMode("walk"),
    "crawl": MoveMode("walk", crawling=True),
    "climb": MoveMode("climb", extra_without=True, extra_note="climbing"),
    "swim": MoveMode("swim", extra_without=True, extra_note="swimming"),
    "fly": MoveMode("fly", walk_fallback=False),
}


def move(
    game,
    c,
    to=None,
    feet: int | None = None,
    toward=None,
    away_from=None,
    mode="walk",
    difficult=False,
    forced=False,
    teleport=False,
    drag=None,
    provoke=True,
    reaction=False,
):
    """Move a creature. Returns feet of movement spent.

    mode: walk | climb | crawl | swim | fly.  forced/teleport never provoke OAs.
    drag: a creature this mover grapples, dragged or carried along in any mode.
    reaction: the move is a Reaction's (a readied move), which may be taken off-turn."""
    cb = game.combat
    start = tuple(c.position)
    # SRD[GLOSS.grappled#3] only "the grappler" can drag the Grappled creature
    if drag is not None and c.id not in grapplers_of(drag):
        raise Refusal(
            f"{c.name} isn't grappling {drag.name}, so it can't drag it",
            page=182,
            rule="GLOSS.grappled#3",
        )
    if toward is not None:
        dest = step_toward(start, toward.position, feet if feet is not None else 1000)
        # stop adjacent rather than inside the target's space
        while dist_points(dest, toward.position) < 5 and dest != start:
            dest = step_toward(start, toward.position, dist_points(start, dest) - 5)
    elif away_from is not None:
        dest = step_away(start, away_from.position, feet or 5)
    elif to is not None:
        dest = tuple(to)
    else:
        dest = (start[0] + (feet or 0), start[1])
    dist = dist_points(start, dest)
    if teleport or forced:
        _check_leave_reach(game, c, start, dest, provoke=False)
        c.position = dest
        _after_move(game, c, start)
        game.log.player(
            "move",
            f"{c.name} {'teleports' if teleport else 'is moved'} {dist} ft",
            page=190,
            rule="GLOSS.teleportation" if teleport else "PLAY.combat.movement-and-position",
        )
        _readied_triggers(game, c, start)
        return 0
    if c.has("frightened"):
        for e in c.effects:
            if e.condition == "frightened" and e.caster_id in game.creatures:
                src = game.creatures[e.caster_id]
                if dist_points(dest, src.position) < dist_points(start, src.position):
                    raise Refusal(
                        f"{c.name} is Frightened and can't willingly move closer to {src.name}",
                        page=182,
                        rule="GLOSS.frightened",
                    )
    spec = MOVE_MODES.get(mode)
    # SRD[GLOSS.prone#1] a Prone creature's only movement is crawling (or righting itself):
    # only the modes that spend walking Speed are open to it
    if c.has("prone") and (spec is None or spec.speed != "walk") and dist > 0:
        raise Refusal(
            f"{c.name} is Prone and can only crawl, not {mode}",
            page=186,
            rule="GLOSS.prone#1",
        )
    spec = spec or MOVE_MODES["walk"]
    cost = dist
    notes = []
    terrain_charged = False
    crowded, occupants = 0, []
    if spec.crawling or (c.has("prone") and spec.speed == "walk" and dist > 0):
        cost += dist
        notes.append("crawling")
    if spec.walk_fallback:
        # a Speed reduced to 0 falls back to walking, like having none
        has_speed = spec.speed == "walk" or c.speed(spec.speed) > 0
    else:
        has_speed = c.speeds.get(spec.speed, 0) > 0
    if not has_speed and not spec.walk_fallback:
        # SRD[GLOSS.fly-speed#1] flying needs a Fly Speed
        raise Refusal(f"{c.name} has no {spec.speed.title()} Speed", page=182, rule="GLOSS.fly-speed#1")
    if spec.speed != "walk":
        if has_speed:
            notes.append(f"{spec.speed.title()} Speed")
        elif spec.extra_without:
            # without the Speed, each foot costs 1 extra foot (2 extra in Difficult Terrain)
            cost += dist * (2 if difficult else 1)
            notes.append(spec.extra_note)
            terrain_charged = difficult
            difficult = False
    # SRD[GLOSS.difficult-terrain#1] a scene's Difficult Terrain charges every foot moved over
    # its ground, walking or crawling. SRD[GLOSS.difficult-terrain#3] R-42: not cumulative only
    # among terrain sources, so crawling's own extra foot adds on top (3 ft per foot)
    if not terrain_charged and (difficult or (game.scene.difficult and spec.speed == "walk")):
        cost += dist
        notes.append("Difficult Terrain")
    elif not terrain_charged:
        # SRD[GLOSS.difficult-terrain#3] only the feet not already charged as Difficult Terrain
        crowded, occupants = _feet_in_crowded_spaces(game, c, start, dest, drag)
        if crowded:
            cost += crowded
            notes.append(f"Difficult Terrain for {crowded} ft")
    # SRD[GLOSS.grappled#3] "drag or carry" — the extra foot applies whatever the mode of movement
    two_smaller = drag is not None and size_index(c.size) - size_index(drag.size) >= 2
    if drag is not None and not (drag.size == "tiny" or two_smaller):
        cost += dist
        notes.append(f"dragging {drag.name}")
    # SRD[GLOSS.grappled#4] R-05: a Tiny grappled creature never adds extra cost, whatever the
    # grappler's size; the ruling decides only when the grappler isn't two sizes larger anyway
    drag_ruling = "R-05" if drag is not None and drag.size == "tiny" and not two_smaller else None
    speed = c.speed(spec.speed if has_speed else "walk")
    if speed == 0 and dist > 0:
        if c.has("grappled"):
            # SRD[GLOSS.grappled#1] Speed 0; R-07: that covers every Speed, not just walking
            raise Refusal(
                f"{c.name}'s Speed is 0",
                page=182,
                rule="GLOSS.grappled#1",
                ruling="R-07" if c.has_special_speed(mode) else None,
            )
        raise Refusal(f"{c.name}'s Speed is 0", page=188, rule="GLOSS.speed")
    # outside combat, movement isn't budgeted per turn. SRD[PLAY.combat.movement-and-position]
    # "On your turn, you can move": off-turn, only a Reaction's move (limited by its own
    # feature, GLOSS.ready#4) and a controlled mount moving on its rider's turn are allowed;
    # any other voluntary move is refused.
    budgeted = cb is not None and cb.spend_movement(
        c,
        cost,
        f"Moving {dist} ft",
        page=14,
        rule="GLOSS.grappled#4" if drag is not None else "PLAY.combat.movement-and-position",
        ruling=drag_ruling,
        free_off_turn=reaction or moves_on_riders_turn(game, c),
    )
    if budgeted:
        cb.turn.moved += dist
    if crowded:
        game.log.player(
            "difficult-terrain",
            f"{c.name} moves {crowded} ft through a creature's space: Difficult Terrain",
            page=181,
            rule="GLOSS.difficult-terrain#5",
            # R-43: the space of a creature that isn't hostile but isn't your ally counts too
            ruling="R-43" if any(getattr(o, "attitude", None) != "hostile" for o in occupants) else None,
        )
    if provoke:
        _check_leave_reach(game, c, start, dest, provoke=True)
        if c.dead or c.has("incapacitated") and c.hp == 0:
            return 0
    c.position = dest
    if drag is not None:
        # SRD[GLOSS.grappled#3] the carried creature ends beside its grappler
        drag.position = step_toward(dest, start, 5) if dist_points(dest, start) >= 5 else start
    _after_move(game, c, start)
    game.log.player(
        "move",
        f"{c.name} moves {dist} ft"
        + (f" ({', '.join(notes)}; costs {cost} ft)" if notes else "")
        + (f"; {cb.turn.movement_left} ft left" if budgeted else ""),
        page=14,
        rule="GLOSS.grappled#4" if drag is not None else "PLAY.combat.movement-and-position",
        ruling=drag_ruling,
    )
    _readied_triggers(game, c, start)
    return cost


def _feet_in_crowded_spaces(game, c, start, dest, drag=None) -> tuple[int, list]:
    """Feet of a move from start to dest that enter a space Difficult Terrain because another
    creature occupies it, and the creatures whose spaces they are."""
    side = SPACE.get(c.size, 5)
    # SRD[GLOSS.difficult-terrain#5] a creature that isn't Tiny or your ally (R-43: an
    # Indifferent bystander counts too); a creature dragged along moves with the mover
    others = [
        o
        for o in game.creatures.values()
        if o is not c
        and o is not drag
        and not o.dead
        and o.size != "tiny"
        and o.elevation == c.elevation
        and not game.is_ally(c, o)
    ]
    feet, occupants = 0, []
    for sq in steps_between(start, dest):
        here = [o for o in others if squares_overlap(sq, side, o.position, SPACE.get(o.size, 5))]
        feet += 5 if here else 0
        occupants += [o for o in here if o not in occupants]
    return feet, occupants


def _after_move(game, c, start):
    # grapples end if the distance exceeds the grapple's range
    for other in game.creatures.values():
        for e in grapples_on(other, by=c.id):
            if other.distance_to(c) > 5:
                other.remove_effect(e, f"{c.name} moved out of range")
    for e in grapples_on(c):
        g = game.creatures.get(e.data.get("grappler"))
        if g and c.distance_to(g) > 5:
            c.remove_effect(e, "out of the grappler's reach")
    mount = c.notes.get("mount")
    if mount and mount in game.creatures:
        game.creatures[mount].position = c.position
    rider = c.notes.get("rider")
    if rider and rider in game.creatures:
        game.creatures[rider].position = c.position


def _check_leave_reach(game, mover, start, dest, provoke=True):
    """Opportunity Attacks (p.15, 185): leaving an enemy's reach with your own
    movement provokes, unless you Disengaged; forced movement and teleports don't."""
    if game.combat is None:
        return
    for enemy in list(game.creatures.values()):
        if enemy is mover or enemy.dead or enemy.team == mover.team or enemy.team == "neutral":
            continue
        reach = oa_reach(enemy)
        d0 = dist_points(enemy.position, start)
        d1 = dist_points(enemy.position, dest)
        if not (d0 <= reach < d1):
            continue
        if not provoke:
            game.log.player(
                "oa",
                f"{mover.name} leaves {enemy.name}'s reach without provoking "
                f"(not moving under its own power)",
                page=15,
                rule="GLOSS.opportunity-attacks",
            )
            continue
        if mover.find_effects("disengage"):
            game.log.player(
                "oa",
                f"{mover.name} leaves {enemy.name}'s reach without provoking (Disengage)",
                page=181,
                rule="GLOSS.disengage",
            )
            continue
        if not game.combat.has_reaction(enemy):
            game.log.player(
                "oa",
                f"{enemy.name} can't make an Opportunity Attack (no Reaction available)",
                page=185,
                rule="GLOSS.opportunity-attacks",
            )
            continue
        if not can_see(enemy, mover):
            continue
        default = enemy.team != "party"
        if game.decide(
            enemy,
            "opportunity_attack",
            [True, False],
            default=default,
            prompt=f"{mover.name} is leaving {enemy.name}'s reach: make an Opportunity Attack?",
        ):
            game.combat.spend(enemy, "reaction")
            game.log.player(
                "oa",
                f"{enemy.name} makes an Opportunity Attack against {mover.name} as it leaves its reach",
                page=185,
                rule="GLOSS.opportunity-attacks",
            )
            opportunity_attack(game, enemy, mover)


def oa_reach(c) -> int:
    reach = c.reach
    wielded = getattr(c, "wielded", [])
    for w in wielded:
        if w.weapon and "reach" in w.weapon["props"]:
            reach = max(reach, 10)
    return reach


def opportunity_attack(game, attacker, target):
    if attacker.is_pc():
        weapon = next((w for w in attacker.wielded if w.weapon and w.weapon["kind"] == "melee"), None)
        return attack(game, attacker, target, weapon=weapon, opportunity=True, unarmed=weapon is None)
    melee = next((a for a in attacker.attacks if a["kind"] in ("melee", "both")), None)
    if melee is None:
        return None
    return attack(game, attacker, target, attack_name=melee["name"], opportunity=True)


# ---------------------------------------------------------------------------
# The Ready action (glossary p.186-187)
# ---------------------------------------------------------------------------
@dataclass
class Readied:
    """A readied response. The trigger is `trigger` (a creature id) moving to within `feet` ft
    of the readier; `release` runs the response; `held` names the Concentration holding a spell."""

    trigger: str
    feet: int
    what: str
    release: Callable
    held: str | None = None


def ready(game, c, trigger, feet, build):
    """Take the Ready action: `c` readies a response for when the creature `trigger` moves to
    within `feet` ft of it. `build()` prepares the response and returns (what, release, held);
    it runs only once the action is known to be free, so a refused response costs nothing."""
    cb = game.combat
    # SRD[GLOSS.ready#2] the Ready action is taken on your turn, and it is that turn's action
    if cb is None:
        raise Refusal(f"{c.name} can Ready only on their turn in combat", page=186, rule="GLOSS.ready#2")
    cb.require_action(c, "Ready")
    # SRD[GLOSS.ready#3] the trigger is a perceivable circumstance: a creature that is here
    try:
        who = game.get(trigger)
    except Refusal as e:
        raise Refusal(
            f"The trigger needs a creature that is here: {e.reason}", page=186, rule="GLOSS.ready#3"
        ) from e
    if who is c or not isinstance(feet, int) or feet < 0:
        raise Refusal(
            "The trigger is another creature moving to within a distance of you",
            page=186,
            rule="GLOSS.ready#3",
        )
    what, release, held = build()
    cb.spend(c, "action", "Ready")
    cb.readied[c.id] = Readied(who.id, feet, what, release, held)
    if held:
        c.notes["on_concentration_end"] = lambda g: _held_spell_dissipates(g, c)
    # SRD[GLOSS.ready#1] nothing happens now: the response waits for the trigger
    game.log.player(
        "ready",
        f"{c.name} readies {what} for when {who.name} moves to within {feet} ft",
        page=186,
        rule="GLOSS.ready#1",
    )


def readied_attack(game, c, target, weapon=None):
    """An attack readied as the response (GLOSS.ready#4); see `ready` for the return value."""
    kw = {"weapon": weapon} if c.is_pc() else {"attack_name": weapon}

    def release(g):
        attack(g, c, target, reaction=True, **kw)

    return f"an attack on {target.name}", release, None


def readied_move(game, c, to):
    """A move readied as the response (GLOSS.ready#4); see `ready` for the return value."""
    dest = tuple(to)

    def check():
        # SRD[GLOSS.ready#4] R-20: a move of up to your Speed, checked when you ready it
        feet = dist_points(c.position, dest)
        if feet > c.speed():
            raise Refusal(
                f"A readied move goes up to {c.name}'s Speed of {c.speed()} ft, not {feet} ft",
                page=187,
                rule="GLOSS.ready#4",
                ruling="R-20",
            )

    check()

    def release(g):
        check()
        # SRD[GLOSS.ready#4] the readied move is the Reaction's, outside the turn's budget
        move(g, c, to=dest, reaction=True)

    return f"a move to {dest}", release, None


def _readied_triggers(game, mover, start):
    """After `mover` has moved from `start`, each creature whose readied trigger that was may
    take its Reaction right after it (GLOSS.ready#5)."""
    cb = game.combat
    if cb is None or mover.dead:
        return
    for rid, rec in list(cb.readied.items()):
        readier = game.creatures.get(rid)
        if rec.trigger != mover.id or readier is None or readier is mover or cb.readied.get(rid) is not rec:
            continue
        # SRD[GLOSS.ready#3] only the chosen circumstance: this creature moving to within the distance
        here = readier.position
        if not dist_points(here, start) > rec.feet >= dist_points(here, mover.position):
            continue
        if not cb.has_reaction(readier):
            game.log.player(
                "ready",
                f"{readier.name} can't take the readied {rec.what} (no Reaction available)",
                page=186,
                rule="GLOSS.ready#2",
            )
            continue
        # SRD[GLOSS.ready#5] take the Reaction right after the trigger finishes, or ignore the trigger
        if not game.decide(
            readier,
            "readied",
            [True, False],
            default=True,
            prompt=f"{mover.name} is within {rec.feet} ft of {readier.name}: take the readied {rec.what}?",
        ):
            # R-18: an ignored trigger keeps the readied response and the Reaction
            game.log.player(
                "ready",
                f"{readier.name} ignores the trigger and keeps {rec.what} readied",
                page=187,
                rule="GLOSS.ready#5",
                ruling="R-18",
            )
            continue
        cb.spend(readier, "reaction")
        del cb.readied[rid]
        game.log.player(
            "ready",
            f"{readier.name} takes the readied {rec.what} with their Reaction",
            page=187,
            rule="GLOSS.ready#5",
        )
        try:
            rec.release(game)
        except Refusal as e:
            # nothing was taken: the Reaction and the readied response stay for a later trigger
            # (a held spell's release is checked before its Concentration ends, so it stays held)
            cb.reaction_used.discard(rid)
            cb.readied[rid] = rec
            game.log.player(
                "ready",
                f"{readier.name} can't take the readied {rec.what}: {e.reason}",
                page=187,
                rule="GLOSS.ready#5",
            )


def _held_spell_dissipates(game, c):
    cb = game.combat
    rec = cb.readied.pop(c.id, None) if cb is not None else None
    if rec is None:
        return
    # SRD[GLOSS.ready#9] broken Concentration: the held spell dissipates without taking effect
    game.log.player(
        "ready",
        f"{c.name}'s held {rec.what} dissipates without taking effect",
        page=187,
        rule="GLOSS.ready#9",
    )


def _readied_lapses(game, c, why="the start of their next turn"):
    rec = game.combat.readied.pop(c.id, None)
    if rec is None:
        return
    # SRD[GLOSS.ready#2] the readied Reaction lasts until the start of your next turn
    game.log.player("ready", f"{c.name}'s readied {rec.what} lapses ({why})", page=186, rule="GLOSS.ready#2")
    if rec.held and c.concentrating == rec.held:
        # SRD[GLOSS.ready#8] R-19: the Concentration holding the spell ends with it; the slot stays spent
        c.notes.pop("on_concentration_end", None)
        game.end_concentration(c, f"the held spell is lost at {why}")
        game.log.player(
            "ready",
            f"{c.name}'s held {rec.what} dissipates without taking effect",
            page=187,
            rule="GLOSS.ready#8",
            ruling="R-19",
        )


# ---------------------------------------------------------------------------
# Attacks
# ---------------------------------------------------------------------------
@dataclass
class AttackResult:
    roll: D20Roll | None
    hit: bool
    crit: bool
    damage: int = 0
    target: object = None
    notes: list = field(default_factory=list)


def _weapon_item(attacker, weapon):
    if weapon is None:
        return None
    if hasattr(weapon, "weapon"):
        return weapon
    it = attacker.inventory.find(weapon) if getattr(attacker, "inventory", None) else None
    if it is None:
        raise Refusal(f"{attacker.name} has no {weapon}")
    return it


def attack(
    game,
    attacker,
    target,
    weapon=None,
    attack_name=None,
    thrown=False,
    two_handed=False,
    light_extra=False,
    nick=False,
    opportunity=False,
    reaction=False,
    unarmed=False,
    adv=(),
    dis=(),
    distance=None,
    ability=None,
    savage=None,
    knock_out=None,
    ignore_range=False,
):
    """Resolve one attack roll. `weapon`: PC weapon item/name; `attack_name`: monster attack.
    `reaction`: the attack is made with a Reaction the caller has spent (a readied attack)."""
    cb = game.combat
    if not attacker.can_act():
        raise Refusal(f"{attacker.name} can't attack right now")
    if target.dead:
        raise Refusal(f"{target.name} is already dead")
    _charm_check(game, attacker, target)
    cover = game.cover_between(attacker, target)
    if cover == "total":
        raise Refusal(
            f"{target.name} is behind Total Cover and can't be targeted directly",
            page=15,
            rule="PLAY.combat.cover",
        )
    dist = distance if distance is not None else attacker.distance_to(target)
    is_pc = attacker.is_pc()
    item = None
    matk = None
    if is_pc and not unarmed:
        item = (
            _weapon_item(attacker, weapon)
            if weapon is not None
            else (attacker.wielded[0] if attacker.wielded else None)
        )
        if item is None:
            unarmed = True
    if not is_pc and not unarmed:
        matk = attacker.attack_named(attack_name)
    # --- melee or ranged? ---
    if unarmed:
        wd = None
        melee, ranged = True, False
        reach = attacker.reach
    elif item is not None:
        wd = item.weapon
        if wd is None:
            raise Refusal(f"{item.display} isn't a weapon")
        ranged = wd["kind"] == "ranged" or thrown
        melee = not ranged
        reach = attacker.reach + (5 if "reach" in wd["props"] else 0)
        if thrown and "thrown" not in wd["props"]:
            raise Refusal(
                f"{item.display} doesn't have the Thrown property (it would be an improvised weapon)",
                page=90,
                rule="EQUIP.weapons.properties.thrown",
            )
    else:
        wd = WEAPONS.get(matk.get("weapon") or "")
        ranged = matk["kind"] == "ranged" or (matk["kind"] == "both" and dist > matk["reach"])
        melee = not ranged
        reach = matk["reach"]
    # --- range ---
    ctx = Ctx(
        "attack",
        attacker,
        target=target,
        melee=melee,
        ranged=ranged,
        weapon=item,
        distance=dist,
        ability=None,
    )
    adv, dis = list(adv), list(dis)
    auto_miss = None
    rng = None
    if ranged:
        rng = (wd["range"] if wd and wd.get("range") else (matk["range"] if matk else None)) or (20, 60)
        if matk and matk.get("range"):
            rng = matk["range"]
        if dist > rng[1] and not ignore_range:
            raise Refusal(
                f"{target.name} is {dist} ft away, beyond the long range of {rng[1]} ft",
                page=90,
                rule="EQUIP.weapons.properties.range",
            )
        if dist > rng[0]:
            if game.scene.underwater:
                auto_miss = "underwater: target beyond the weapon's normal range"
            else:
                dis.append(f"beyond normal range ({rng[0]} ft)")
        elif game.scene.underwater:
            dis.append("ranged attack underwater (p.16)")
        for e in game.creatures.values():
            if (
                e.team not in (attacker.team, "neutral")
                and not e.dead
                and e is not attacker
                and dist_points(e.position, attacker.position) <= 5
                and not e.has("incapacitated")
                and can_see(e, attacker)
            ):
                dis.append(f"ranged attack with {e.name} within 5 ft")
                break
        if item is not None and "ammunition" in wd["props"]:
            ammo = attacker.inventory.find(wd["ammo"])
            if ammo is None or ammo.qty <= 0:
                raise Refusal(
                    f"{attacker.name} has no {wd['ammo']} for the {item.display}",
                    page=89,
                    rule="EQUIP.weapons.properties.ammunition",
                )
    else:
        if dist > reach and not ignore_range:
            raise Refusal(
                f"{target.name} is {dist} ft away, beyond {attacker.name}'s reach of {reach} ft",
                page=15,
                rule="PLAY.combat.melee-attacks",
            )
        if game.scene.underwater and attacker.speed("swim") == 0:
            dtype = wd["dtype"] if wd else (matk["dtype"] if matk else "bludgeoning")
            if dtype != "piercing":
                dis.append("melee weapon attack underwater without a Swim Speed (p.16)")
    # --- action economy ---
    if cb is not None:
        # SRD[MONSTER.goblins.goblin-warrior#18] SRD[MONSTER.goblins.goblin-warrior#21] the attack
        # is spent only once its reach or range allows it: a refused attack costs nothing
        _spend_attack(game, attacker, item, light_extra, nick, opportunity or reaction)
    # heavy weapons (p.89): Str/Dex below 13
    if is_pc and wd and "heavy" in wd["props"]:
        if melee and attacker.score("str") < 13:
            dis.append(f"Heavy weapon with Strength {attacker.score('str')} < 13")
        if ranged and not thrown and attacker.score("dex") < 13:
            dis.append(f"Heavy weapon with Dexterity {attacker.score('dex')} < 13")
    # unseen attackers / targets (p.14)
    if not can_see(attacker, target):
        dis.append(f"{attacker.name} can't see {target.name}")
    if not can_see(target, attacker):
        adv.append(f"{target.name} can't see {attacker.name}")
    # Pack Tactics
    if "pack tactics" in attacker.traits:
        for ally in game.allies_of(attacker):
            if ally.distance_to(target) <= 5 and not ally.has("incapacitated"):
                adv.append(f"Pack Tactics ({ally.name} is next to {target.name})")
                break
    # Sanctuary (p.159)
    target = _sanctuary(game, attacker, target)
    if target is None:
        return AttackResult(None, False, False)
    acc = attacker.gather(ctx)
    # --- build the roll ---
    roll = D20Roll(
        "attack",
        f"attack on {target.name}"
        + (f" with {item.display}" if item else f" ({matk['name']})" if matk else " (Unarmed Strike)"),
        attacker.name,
    )
    mods, abil = _attack_mods(attacker, item, matk, unarmed, ranged, thrown, ability)
    roll.mods = mods + acc.mods
    roll.adv = acc.adv + adv
    roll.dis = acc.dis + dis
    crit_on = 20
    if is_pc and attacker.has_feature("improved critical") and (item is not None or unarmed):
        crit_on = 19
    roll.crit_on = crit_on
    acc.remove_consumed()
    ac_parts = target.ac_parts() + game.cover_bonus(attacker, target, "AC")
    roll.target = sum(v for v, _ in ac_parts)
    roll_d20_test(
        game,
        attacker,
        roll,
        bonus_dice=acc.bonus_dice,
        page="14-15",
        rule="PLAY.combat.making-an-attack",
        rulings=acc.rulings,
    )
    _reveal_attacker(game, attacker)
    # Redirect Attack (Goblin Boss): swap with an ally who becomes the target
    target, roll = _redirect(game, attacker, target, roll, cover)
    hit = bool(roll.success) and auto_miss is None
    if auto_miss:
        game.log.player(
            "attack",
            f"The attack automatically misses ({auto_miss})",
            page=16,
            rule="PLAY.combat.underwater-combat",
        )
    crit = hit and roll.crit
    if hit and not crit and acc.auto_crit:
        crit = True
        game.log.player(
            "attack", f"Critical Hit: {acc.auto_crit[0]}", page="186/191", rule="GLOSS.critical-hit"
        )
    # Shield spell reaction: +5 AC including against the triggering attack
    if hit and not crit and _shield_reaction(game, target, roll):
        hit = roll.total >= roll.target
        if not hit:
            game.log.player(
                "attack",
                f"The attack now misses {target.name} (AC {roll.target})",
                page=161,
                rule="SPELL.shield",
            )
    res = AttackResult(roll, hit, crit, target=target)
    _after_attack_roll(game, attacker, target, roll)
    if hit:
        dmg = deal_attack_damage(
            game,
            attacker,
            target,
            item,
            matk,
            unarmed,
            crit,
            roll,
            abil,
            light_extra,
            two_handed,
            melee,
            ranged,
            thrown,
            savage,
            knock_out,
        )
        res.damage = dmg
        if item is not None and attacker.has_mastery(item) and not target.dead:
            _mastery_on_hit(game, attacker, target, item, abil, dmg)
        if (
            matk
            and matk.get("on_hit") == "prone_if_medium"
            and not target.dead
            and size_index(target.size) <= size_index("medium")
        ):
            target.add_condition("prone", f"{attacker.name}'s Bite")
        if crit and is_pc and attacker.has_feature("remarkable athlete"):
            attacker.add_effect(
                Flag(
                    "remarkable athlete move",
                    "Remarkable Athlete: move half Speed without provoking Opportunity Attacks",
                    ends=[("end", attacker.id)],
                )
            )
            game.log.player(
                "feature",
                f"{attacker.name} may move up to {attacker.speed() // 2} ft without provoking "
                f"Opportunity Attacks (Remarkable Athlete)",
                page=49,
                rule="CLASS.fighter.fighter-subclass-champion.level-3-remarkable-athlete",
            )
    else:
        if item is not None and attacker.has_mastery(item) and item.weapon["mastery"] == "graze":
            m = attacker.mod(abil)
            if m > 0:
                game.log.player(
                    "mastery",
                    f"Graze: {target.name} takes {m} damage despite the miss",
                    page=90,
                    rule="EQUIP.weapons.mastery-properties.graze",
                )
                target.take_damage(
                    m,
                    item.weapon["dtype"],
                    attacker=attacker,
                    source="Graze",
                    rule="EQUIP.weapons.mastery-properties.graze",
                )
    _consume_ammo(game, attacker, item, ranged, thrown)
    return res


def _charm_check(game, attacker, target):
    for e in attacker.effects:
        if e.condition == "charmed" and e.caster_id == target.id:
            raise Refusal(
                f"{attacker.name} is Charmed by {target.name} and can't attack it",
                page=178,
                rule="GLOSS.charmed",
            )


def _spend_attack(game, attacker, item, light_extra, nick, with_reaction):
    cb = game.combat
    if with_reaction:  # an Opportunity Attack or a readied attack: the Reaction pays for it
        return
    t = cb.turn
    if not cb.is_turn(attacker):
        # SRD[PLAY.combat.the-order-of-combat]: outside a Reaction, a combatant attacks on its own turn
        raise Refusal(f"It isn't {attacker.name}'s turn", page=13, rule="PLAY.combat.the-order-of-combat")
    if light_extra:
        # Light property (p.89): extra attack with a different Light weapon after the Attack action
        if not t.attack_action_taken:
            raise Refusal(
                "The Light extra attack requires taking the Attack action with a Light weapon first",
                page=89,
                rule="EQUIP.weapons.properties.light",
            )
        first = t.notes.get("light_weapon")
        if item is None or "light" not in item.weapon["props"] or first is None:
            raise Refusal(
                "The extra attack must be made with a Light weapon after attacking with a Light weapon",
                page=89,
                rule="EQUIP.weapons.properties.light",
            )
        if item.uid == first:
            raise Refusal(
                "The extra attack must use a different Light weapon",
                page=89,
                rule="EQUIP.weapons.properties.light",
            )
        if t.light_attack_done:
            raise Refusal(
                "You can make only one Light extra attack per turn",
                page=89,
                rule="EQUIP.weapons.properties.light",
            )
        use_nick = nick or (
            attacker.is_pc() and attacker.has_mastery(item) and item.weapon["mastery"] == "nick"
        )
        if use_nick and attacker.has_mastery(item) and item.weapon["mastery"] == "nick" and not t.nick_used:
            t.nick_used = True
            game.log.player(
                "mastery",
                "Nick: the extra Light attack is part of the Attack action; the Bonus Action stays free",
                page=90,
                rule="EQUIP.weapons.mastery-properties.nick",
            )
        else:
            cb.spend(attacker, "bonus", "Light weapon extra attack")
        t.light_attack_done = True
        return
    if t.attacks_left > 0:
        t.attacks_left -= 1
    else:
        cb.spend(attacker, "action", "Attack")
        t.attack_action_taken = True
        t.attacks_left = 0  # one attack per Attack action at levels 1-3 (no Extra Attack)
    if item is not None and "light" in item.weapon["props"]:
        t.notes["light_weapon"] = item.uid
    # equip/draw as part of the attack (p.177)
    if item is not None and attacker.is_pc() and item not in attacker.wielded:
        if not t.attack_equip_used:
            t.attack_equip_used = True
            attacker.wielded.append(item)
            game.log.player(
                "equip",
                f"{attacker.name} draws the {item.display} as part of the attack",
                page=177,
                rule="GLOSS.attack",
            )
        else:
            cb.spend(attacker, "free", f"draw {item.display}")
            attacker.wielded.append(item)
    if item is not None and "loading" in item.weapon["props"]:
        key = "action"
        if key in t.loading_fired:
            raise Refusal(
                "Loading: only one piece of ammunition per action, Bonus Action or Reaction",
                page=90,
                rule="EQUIP.weapons.properties.loading",
            )
        t.loading_fired.add(key)


def _attack_mods(attacker, item, matk, unarmed, ranged, thrown, ability):
    if not attacker.is_pc():
        if unarmed:
            return [(attacker.mod("str") + attacker.pb, "Unarmed Strike")], "str"
        return [(matk["bonus"], f"{matk['name']} (stat block)")], None
    if unarmed:
        return [(attacker.mod("str"), "Str"), (attacker.pb, "PB")], "str"
    wd = item.weapon
    if ability:
        abil = ability
    elif "finesse" in wd["props"]:
        abil = "dex" if attacker.mod("dex") >= attacker.mod("str") else "str"
    elif wd["kind"] == "ranged":
        abil = "dex"
    else:
        abil = "str"  # melee, including thrown melee weapons (p.90 Thrown)
    mods = [(attacker.mod(abil), abil.title())]
    if attacker.proficient_with(item):
        mods.append((attacker.pb, "PB"))
    if item.magic_bonus:
        mods.append((item.magic_bonus, f"{item.display} magic bonus"))
    if attacker.fighting_style == "archery" and wd["kind"] == "ranged":
        mods.append((2, "Archery"))
    return mods, abil


def _reveal_attacker(game, attacker):
    """Making an attack roll ends hiding (p.183)."""
    for e in list(attacker.effects):
        if e.condition == "invisible" and e.source.startswith("Hide"):
            attacker.remove_effect(e, "attack roll gives away the hiding place")
            attacker.hidden_total = None


def _after_attack_roll(game, attacker, target, roll):
    for e in list(attacker.effects):
        e.on_attack_roll(game, roll, None)


def _sanctuary(game, attacker, target):
    for e in list(target.effects):
        if getattr(e, "name", "") == "Sanctuary":
            caster = game.creatures.get(e.caster_id)
            dc = caster.spell_dc() if caster is not None and hasattr(caster, "spell_dc") else 13
            r = attacker.save(
                "wis",
                dc,
                label=f"Wisdom save vs Sanctuary on {target.name}",
                page=159,
                rule="SPELL.sanctuary",
            )
            if not r.success:
                others = [
                    c
                    for c in game.enemies_of(attacker)
                    if c is not target and attacker.distance_to(c) <= attacker.reach
                ]
                pick = game.decide(
                    attacker,
                    "sanctuary_retarget",
                    [None] + [c.id for c in others],
                    default=None,
                    prompt=f"{attacker.name} can't attack {target.name} (Sanctuary): choose a new "
                    f"target or lose the attack",
                )
                if pick:
                    game.log.player(
                        "spell",
                        f"{attacker.name} turns to attack {game.get(pick).name} instead",
                        page=159,
                        rule="SPELL.sanctuary",
                    )
                    return game.get(pick)
                game.log.player(
                    "spell", f"{attacker.name} loses the attack (Sanctuary)", page=159, rule="SPELL.sanctuary"
                )
                if game.combat and game.combat.is_turn(attacker):
                    pass
                return None
    return target


def _redirect(game, attacker, target, roll, cover):
    if "redirect attack" not in target.traits or game.combat is None or not game.combat.has_reaction(target):
        return target, roll
    if not can_see(target, attacker):
        return target, roll
    allies = [
        a for a in game.allies_of(target) if target.distance_to(a) <= 5 and a.size in ("small", "medium")
    ]
    if not allies:
        return target, roll
    pick = game.decide(
        target,
        "redirect_attack",
        [None] + [a.id for a in allies],
        default=allies[0].id,
        prompt=f"{target.name}: use Redirect Attack?",
    )
    if not pick:
        return target, roll
    ally = game.get(pick)
    game.combat.spend(target, "reaction")
    target.position, ally.position = ally.position, target.position
    game.log.player(
        "reaction",
        f"{target.name} uses Redirect Attack: swaps places with {ally.name}, who becomes the target",
        page=290,
        rule="MONSTER.goblins.goblin-boss",
    )
    ac_parts = ally.ac_parts()
    roll.target = sum(v for v, _ in ac_parts)
    roll.label = roll.label.replace(target.name, ally.name)
    game.log.player(
        "attack",
        f"The attack roll of {roll.total} is now against {ally.name} (AC {roll.target}) → "
        + ("hit" if roll.success else "miss"),
        page=290,
        rule="MONSTER.goblins.goblin-boss",
    )
    return ally, roll


def _shield_reaction(game, target, roll) -> bool:
    from . import spells

    return spells.offer_shield(game, target, roll)


def _consume_ammo(game, attacker, item, ranged, thrown):
    if item is None or not attacker.is_pc():
        return
    wd = item.weapon
    if ranged and "ammunition" in wd["props"]:
        attacker.inventory.remove(wd["ammo"], 1)
        if game.combat:
            k = (attacker.id, wd["ammo"])
            game.combat.ammo_spent[k] = game.combat.ammo_spent.get(k, 0) + 1
        else:
            attacker.notes["ammo_spent"] = attacker.notes.get("ammo_spent", {})
            attacker.notes["ammo_spent"][wd["ammo"]] = attacker.notes["ammo_spent"].get(wd["ammo"], 0) + 1
    if thrown:
        if item in attacker.wielded:
            attacker.wielded.remove(item)
        attacker.inventory.remove(item, 1)
        game.scene.objects.setdefault(f"thrown {item.name}", {"items": []})["items"].append(item.name)


def recover_ammunition(game, pc, ammo="arrows", used=None):
    """p.89: spend 1 minute after a fight to recover half the ammunition (round down)."""
    spent = used if used is not None else pc.notes.get("ammo_spent", {}).get(ammo, 0)
    back = spent // 2
    if back:
        pc.inventory.add(ammo, back)
    pc.notes.get("ammo_spent", {}).pop(ammo, None)
    game.advance(60, f"{pc.name} recovers ammunition")
    game.log.player(
        "ammo",
        f"{pc.name} recovers {back} of {spent} {ammo}",
        page=89,
        rule="EQUIP.weapons.properties.ammunition",
    )
    return back


# ---------------------------------------------------------------------------
# Damage from attacks
# ---------------------------------------------------------------------------
def roll_damage_dice(
    game, attacker, expr: str, crit: bool, gwf=False, savage=None, label=""
) -> tuple[int, list]:
    """Roll damage dice (doubled on a Critical Hit). Returns (dice total, dice list)."""
    n, s, m = parse_expr(expr)
    if crit:
        n *= 2
    rolls = game.dice.roll_many(n, s)
    if savage:
        again = game.dice.roll_many(n, s)
        choice = game.decide(
            attacker,
            "savage_attacker",
            [rolls, again],
            default=again if sum(again) > sum(rolls) else rolls,
            prompt=f"Savage Attacker: use {rolls} or {again}?",
        )
        if isinstance(choice, int):
            choice = (
                [rolls, again][choice] if choice in (0, 1) else (again if sum(again) == choice else rolls)
            )
        game.log.player(
            "feat",
            f"Savage Attacker: rolled {rolls} and {again}; uses {choice}",
            page=87,
            rule="FEAT.feat-descriptions.origin-feats.savage-attacker",
        )
        rolls = list(choice)
    if gwf:
        new = [3 if r in (1, 2) else r for r in rolls]
        if new != rolls:
            game.log.player(
                "feat",
                f"Great Weapon Fighting: {rolls} → {new}",
                page=88,
                rule="FEAT.feat-descriptions.fighting-style-feats.great-weapon-fighting",
            )
        rolls = new
    rolls = inspiration_reroll(game, attacker, rolls, s)
    return sum(rolls) + m, rolls


def deal_attack_damage(
    game,
    attacker,
    target,
    item,
    matk,
    unarmed,
    crit,
    roll,
    abil,
    light_extra,
    two_handed,
    melee,
    ranged,
    thrown,
    savage,
    knock_out,
):
    cb = game.combat
    parts = []
    is_pc = attacker.is_pc()
    if unarmed:
        dtype = "bludgeoning"
        total = 1 + attacker.mod("str")
        parts.append(f"1 + Str {attacker.mod('str')}")
    elif item is not None:
        wd = item.weapon
        dtype = wd["dtype"]
        expr = wd["damage"]
        hands_two = two_handed or "two-handed" in wd["props"]
        if two_handed:
            if "versatile" not in wd["props"] and "two-handed" not in wd["props"]:
                raise Refusal(f"{item.display} can't be wielded two-handed for extra damage")
            if "versatile" in wd["props"]:
                expr = wd["versatile"]
            if getattr(attacker, "shield", None) is not None:
                raise Refusal(f"{attacker.name} needs a free hand (a Shield is strapped on) to use two hands")
        use_savage = False
        if (
            is_pc
            and attacker.has_feat("savage attacker")
            and cb is not None
            and not cb.turn.savage_used
            and cb.is_turn(attacker)
        ):
            want = (
                savage
                if savage is not None
                else game.decide(
                    attacker,
                    "use_savage_attacker",
                    [True, False],
                    default=True,
                    prompt="Use Savage Attacker (once per turn)?",
                )
            )
            if want:
                use_savage = True
                cb.turn.savage_used = True
        elif is_pc and attacker.has_feat("savage attacker") and cb is None and savage:
            use_savage = True
        gwf = (
            is_pc
            and attacker.fighting_style == "great weapon fighting"
            and melee
            and hands_two
            and ({"two-handed", "versatile"} & wd["props"])
        )
        if "-" in expr or expr.isdigit():
            dice_total, dice = int(expr), []
        else:
            dice_total, dice = roll_damage_dice(game, attacker, expr, crit, gwf=bool(gwf), savage=use_savage)
        total = dice_total
        parts.append(f"{expr}{'x2' if crit else ''}={dice}")
        mod = attacker.mod(abil)
        add_mod = True
        if light_extra and mod > 0 and not attacker.has_feat("two-weapon fighting"):
            add_mod = False
            parts.append("no ability modifier (Light extra attack)")
        if add_mod:
            total += mod
            parts.append(f"{fmt_mod(mod)} {abil.title()}")
        if item.magic_bonus:
            total += item.magic_bonus
            parts.append(f"+{item.magic_bonus} magic")
    elif game.fixed_monster_damage and not crit:
        # p.189: the GM uses either the static number or the dice, never both
        from .dice import average

        dtype = matk["dtype"]
        total = average(matk["damage"])
        parts.append(f"fixed {total} ({matk['damage']})")
        # SRD[MONSTER.goblins.goblin-warrior#20]: the Advantage rider has its own static number
        if matk.get("adv_extra") and roll.mode == "advantage":
            x = average(matk["adv_extra"])
            total += x
            parts.append(f"+fixed {x} ({matk['adv_extra']}, attack had Advantage)")
    else:
        dtype = matk["dtype"]
        dice_total, dice = roll_damage_dice(game, attacker, matk["damage"], crit)
        total = dice_total
        parts.append(f"{matk['damage']}{' (crit dice x2)' if crit else ''}: {dice}")
        # SRD[MONSTER.goblins.goblin-warrior#20]
        if matk.get("adv_extra") and roll.mode == "advantage":
            x, xd = roll_damage_dice(game, None, matk["adv_extra"], crit)
            total += x
            parts.append(f"+{matk['adv_extra']}={xd} (attack had Advantage)")
    total = max(0, total)
    # Sneak Attack (p.61-62)
    sneak = 0
    if is_pc and attacker.has_feature("sneak attack") and item is not None:
        sneak = _sneak_attack(game, attacker, target, item, roll, crit)
        if sneak:
            total += sneak
            parts.append(f"+{sneak} Sneak Attack")
    game.log.player(
        "damage_roll",
        f"{attacker.name} deals {total} {dtype.title()} damage"
        + (" (CRITICAL)" if crit else "")
        + f": {'; '.join(parts)}",
        page=16,
        rule="PLAY.damage-and-healing.damage-rolls",
    )
    ko = knock_out
    if ko is None:
        ko = None
    dealt = target.take_damage(
        total,
        dtype,
        attacker=attacker,
        crit=crit,
        melee=melee,
        source=f"{attacker.name}'s attack",
        within5=attacker.distance_to(target) <= 5,
    )
    # extra damage instances (Cultist necrotic, Priest radiant)
    if matk:
        for expr, dt in matk.get("extra", []):
            if not target.dead:
                if expr.isdigit():
                    x = int(expr)
                else:
                    x, _ = roll_damage_dice(game, None, expr, crit)
                target.take_damage(x, dt, attacker=attacker, crit=crit, melee=melee, source=f"{matk['name']}")
    # poison coating (p.197-198)
    if item is not None and item.props.get("coating") and dtype in ("piercing", "slashing") and dealt > 0:
        from .hazards import trigger_coating

        trigger_coating(game, attacker, target, item)
    _post_damage_hooks(game, attacker, target, dealt)
    return dealt


def _post_damage_hooks(game, attacker, target, dealt):
    """Effects that end when their owner deals damage (Invisibility, Sanctuary)."""
    if dealt <= 0:
        return
    for e in list(attacker.effects):
        if getattr(e, "ends_on_dealing_damage", False):
            attacker.remove_effect(e, f"{attacker.name} dealt damage")


def _sneak_attack(game, rogue, target, item, roll, crit) -> int:
    cb = game.combat
    wd = item.weapon
    if cb is not None and cb.turn.sneak_attack_used and cb.is_turn(rogue):
        return 0
    if not ("finesse" in wd["props"] or wd["kind"] == "ranged"):
        game.log.player(
            "sneak",
            "No Sneak Attack: the weapon isn't Finesse or Ranged",
            page=61,
            rule="CLASS.rogue.level-1-sneak-attack",
        )
        return 0
    ok = roll.mode == "advantage"
    why = "Advantage"
    if not ok and roll.mode != "disadvantage":
        for ally in game.allies_of(rogue):
            if ally.distance_to(target) <= 5 and not ally.has("incapacitated"):
                ok = True
                why = f"{ally.name} is within 5 ft of {target.name}"
                break
    if not ok:
        game.log.player(
            "sneak",
            "No Sneak Attack (no Advantage, and no able ally next to the target without Disadvantage)",
            page=61,
            rule="CLASS.rogue.level-1-sneak-attack",
        )
        return 0
    from .features import sneak_attack_dice

    n = sneak_attack_dice(rogue)
    total, dice = roll_damage_dice(game, rogue, f"{n}d6", crit)
    if cb is not None:
        cb.turn.sneak_attack_used = True
        rogue.notes["sneak_used_turn"] = (cb.round, cb.index)
    game.log.player(
        "sneak",
        f"Sneak Attack ({why}): {n}d6{'x2' if crit else ''} = {dice}",
        page=61,
        rule="CLASS.rogue.level-1-sneak-attack",
    )
    return total


def _mastery_on_hit(game, attacker, target, item, abil, dmg):
    m = item.weapon["mastery"]
    cb = game.combat
    if m == "sap":
        target.add_effect(
            AdvNext(f"Sap ({attacker.name})", kinds=("attack",), mode="dis", ends=[("start", attacker.id)])
        )
        game.log.player(
            "mastery",
            f"Sap: {target.name} has Disadvantage on its next attack roll before the start of "
            f"{attacker.name}'s next turn",
            page=90,
            rule="EQUIP.weapons.mastery-properties.sap",
        )
    elif m == "vex" and dmg > 0:
        eff = AdvNext(f"Vex ({item.display})", kinds=("attack",), target=target, ends=[("end", attacker.id)])
        if cb is not None and cb.is_turn(attacker):
            eff.data["skip"] = {("end", attacker.id): 1}  # expires at the end of the *next* turn
        attacker.add_effect(eff)
        game.log.player(
            "mastery",
            f"Vex: {attacker.name} has Advantage on the next attack roll against {target.name} "
            f"before the end of their next turn",
            page=90,
            rule="EQUIP.weapons.mastery-properties.vex",
        )
    elif m == "slow" and dmg > 0:
        existing = [e for e in target.effects if isinstance(e, SpeedPenalty) and e.group == "Slow"]
        target.add_effect(SpeedPenalty("Slow", 10, group="Slow", ends=[("start", attacker.id)]))
        game.log.player(
            "mastery",
            f"Slow: {target.name}'s Speed drops by 10 ft until the start of {attacker.name}'s "
            f"next turn" + (" (doesn't stack past 10 ft)" if existing else ""),
            page=90,
            rule="EQUIP.weapons.mastery-properties.slow",
        )
    elif m == "push":
        if size_index(target.size) <= size_index("large") and game.decide(
            attacker, "push", [True, False], default=True, prompt="Push the target 10 ft?"
        ):
            move(game, target, away_from=attacker, feet=10, forced=True)
    elif m == "topple":
        dc = 8 + attacker.mod(abil) + attacker.pb
        if game.decide(attacker, "topple", [True, False], default=True, prompt="Topple: force a Con save?"):
            r = target.save(
                "con",
                dc,
                label=f"Con save vs Topple (DC {dc})",
                page=90,
                rule="EQUIP.weapons.mastery-properties.topple",
            )
            if not r.success:
                target.add_condition("prone", "Topple")
    elif m == "cleave":
        game.log.player(
            "mastery",
            "Cleave: a melee attack against a second creature within 5 ft of the first is "
            "available (once per turn)",
            page=90,
            rule="EQUIP.weapons.mastery-properties.cleave",
        )
        if cb:
            cb.turn.notes["cleave_available"] = target.id


def _mounted_fall_check(game, creature):
    mount_id = creature.notes.get("rider")
    if mount_id is not None:
        rider = game.creatures.get(mount_id)
        if rider is not None:
            from .mounted import fall_off_check

            fall_off_check(game, rider, "mount knocked Prone")
    if creature.notes.get("mount"):
        from .mounted import fall_off_check

        fall_off_check(game, creature, "knocked Prone while mounted")


# ---------------------------------------------------------------------------
# Unarmed Strike: Grapple and Shove (p.190)
# ---------------------------------------------------------------------------
def hands_free(c) -> int:
    if not c.is_pc():
        return 2
    used = 0
    if c.shield is not None:
        used += 1
    for w in c.wielded:
        used += 2 if (w.weapon and "two-handed" in w.weapon["props"]) else 1
    used += sum(1 for e in c.effects if e.name == "grappling")
    return max(0, 2 - used)


def grapple(game, attacker, target):
    if size_index(target.size) - size_index(attacker.size) > 1:
        raise Refusal(
            f"{target.name} is more than one size larger than {attacker.name}; it can't be grappled",
            page=190,
            rule="GLOSS.unarmed-strike",
        )
    if hands_free(attacker) < 1:
        raise Refusal(f"{attacker.name} needs a free hand to grapple", page=182, rule="GLOSS.grappling")
    if attacker.distance_to(target) > 5:
        raise Refusal(f"{target.name} is out of reach (5 ft)")
    if game.combat is not None:
        _spend_attack(game, attacker, None, False, False, False)
    dc = 8 + attacker.mod("str") + attacker.pb
    ab = _save_choice(target)
    r = target.save(
        ab,
        dc,
        label=f"{'Strength' if ab == 'str' else 'Dexterity'} save vs grapple (DC {dc})",
        avoid={"grappled"},
        page=190,
        rule="GLOSS.unarmed-strike",
    )
    if not r.success:
        target.add_condition(
            "grappled", f"grappled by {attacker.name}", caster=attacker, grappler=attacker.id, escape_dc=dc
        )
        attacker.add_effect(Flag("grappling", f"grappling {target.name}", target=target.id))
        return True
    return False


def _save_choice(target) -> str:
    """The target picks Str or Dex, whichever is better (its choice)."""
    s, d = target.save_bonus_total("str"), target.save_bonus_total("dex")
    return "str" if s > d else "dex"


def shove(game, attacker, target, effect="prone"):
    if size_index(target.size) - size_index(attacker.size) > 1:
        raise Refusal(
            f"{target.name} is more than one size larger than {attacker.name}; it can't be shoved",
            page=190,
            rule="GLOSS.unarmed-strike",
        )
    if attacker.distance_to(target) > 5:
        raise Refusal(f"{target.name} is out of reach (5 ft)")
    if game.combat is not None:
        _spend_attack(game, attacker, None, False, False, False)
    dc = 8 + attacker.mod("str") + attacker.pb
    ab = _save_choice(target)
    r = target.save(
        ab,
        dc,
        label=f"{'Strength' if ab == 'str' else 'Dexterity'} save vs shove (DC {dc})",
        page=190,
        rule="GLOSS.unarmed-strike",
    )
    if r.success:
        return False
    if effect == "prone":
        target.add_condition("prone", f"shoved by {attacker.name}")
    else:
        move(game, target, away_from=attacker, feet=5, forced=True)
    return True


def escape_grapple(game, c, skill=None):
    eff = next(iter(grapples_on(c)), None)
    if eff is None:
        raise Refusal(f"{c.name} isn't Grappled")
    if game.combat is not None:
        game.combat.spend(c, "action", "escape grapple")
    skill = skill or (
        "athletics" if c.skill_total("athletics") > c.skill_total("acrobatics") else "acrobatics"
    )
    dc = eff.data.get("escape_dc", 10)
    r = c.check(
        skill,
        dc=dc,
        avoid={"grappled"},
        label=f"{skill.title()} check to escape the grapple (DC {dc})",
        page=182,
        rule="GLOSS.grappling",
    )
    if r.success:
        release_grapple(game, c)
    return r


def release_grapple(game, target, reason="escaped"):
    for e in grapples_on(target):
        grappler = game.creatures.get(e.data.get("grappler"))
        target.remove_effect(e, reason)
        if grappler:
            for f in list(grappler.effects):
                if f.name == "grappling" and f.data.get("target") == target.id:
                    grappler.effects.remove(f)


# ---------------------------------------------------------------------------
# Object interactions and position changes
# ---------------------------------------------------------------------------
def interact(game, actor, what: str):
    """One free object interaction per turn; more need the Utilize action (p.13)."""
    cb = game.combat
    if cb is None or not cb.is_turn(actor):
        game.log.player("interact", f"{actor.name}: {what}", page=13, rule="PLAY.combat.the-order-of-combat")
        return "free"
    if not cb.turn.free_interaction:
        cb.turn.free_interaction = True
        game.log.player(
            "interact",
            f"{actor.name}: {what} (free object interaction)",
            page=13,
            rule="PLAY.combat.the-order-of-combat",
        )
        return "free"
    cb.spend(actor, "action", f"Utilize ({what})")
    game.log.player("interact", f"{actor.name}: {what} (Utilize action)", page=13, rule="GLOSS.utilize")
    return "utilize"


def drop_prone(game, c):
    if c.speed() == 0:
        raise Refusal(
            f"{c.name} can't drop Prone while their Speed is 0",
            page=14,
            rule="PLAY.combat.movement-and-position",
        )
    c.add_condition("prone", "dropped prone")
    game.log.player(
        "move",
        f"{c.name} drops Prone (no movement spent)",
        page=14,
        rule="PLAY.combat.movement-and-position",
    )


def stand_up(game, c):
    # SRD[GLOSS.prone#2]: righting yourself ends the condition, so there is nothing to end without it
    if not c.has("prone"):
        raise Refusal(f"{c.name} isn't Prone, so has nothing to right", page=186, rule="GLOSS.prone#2")
    # SRD[GLOSS.prone#3]
    if c.speed() == 0:
        raise Refusal(f"{c.name} can't right themselves with Speed 0", page=186, rule="GLOSS.prone#3")
    # SRD[GLOSS.prone#2]
    cost = c.speed() // 2
    cb = game.combat
    if cb is not None:
        cb.spend_movement(c, cost, "Standing up", page=186, rule="GLOSS.prone#2", ruling="R-22")
    c.remove_condition("prone", reason=f"stood up for {cost} ft of movement")
    return cost
