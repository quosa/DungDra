"""Spellcasting (SRD p.104-106) and the 32 subset spells (p.107-175)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .d20 import D20Roll, roll_d20_test
from .data.spells import SPELLS, spell_level
from .effects import ACBonus, AdvNext, Condition, Ctx, Effect, SpeedPenalty, can_see
from .geometry import dist_points
from .rules import DAY, HOUR, MINUTE, ROUND, OutOfScope, Refusal, div, norm, size_index

FOCUS_FOR = {"cleric": ["holy symbol"], "wizard": ["arcane focus", "spellbook", "quarterstaff"]}


@dataclass
class Casting:
    spell: str
    caster: object
    level: int                   # level the spell is cast at (0 for cantrips)
    ability: str | None
    dc: int
    attack: int
    slot: int | None = None
    ritual: bool = False
    source: str = ""
    item: object = None
    results: dict = field(default_factory=dict)

    @property
    def data(self):
        return SPELLS[self.spell]


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def cast(game, caster, spell: str, targets=None, slot: int | None = None, ritual=False, free=False,
         item=None, scroll=False, point=None, option=None, charges=None, **kw):
    """Cast a spell. targets: creature(s)/object names; slot: slot level to expend."""
    spell = norm(spell)
    if spell not in SPELLS:
        if spell_level(spell) is not None:
            raise OutOfScope(f"{spell.title()} is out of scope for this game")
        raise OutOfScope(f"{spell.title()} isn't a spell in scope")
    sd = SPELLS[spell]
    targets = _as_list(game, targets)
    g = game
    if caster.dead or caster.has("incapacitated"):
        raise Refusal(f"{caster.name} can't cast spells right now")
    # --- how is it cast? -----------------------------------------------------
    ability, dc, atk, source = None, 13, 5, ""
    use_slot = None
    if item is not None:                        # wand or scroll
        ability, dc, atk, source = _item_casting(game, caster, spell, item, scroll, charges)
        level = sd["level"] if not charges else sd["level"] + charges - 1
        if scroll:
            level = sd["level"]
    else:
        way = _way(caster, spell, ritual, free, slot)
        ability = way["ability"]
        source = way["source"]
        dc, atk = caster.spell_dc(ability), caster.spell_attack_bonus(ability)
        level = sd["level"]
        if ritual:
            if not sd["ritual"]:
                raise Refusal(f"{spell.title()} doesn't have the Ritual tag")
            if slot is not None and slot != sd["level"]:
                raise Refusal("A Ritual doesn't expend a spell slot, so it can't be cast at a higher level", page=187)
        elif sd["level"] > 0 and not way.get("free"):
            use_slot = slot or sd["level"]
            if use_slot < sd["level"]:
                raise Refusal(f"{spell.title()} needs a slot of level {sd['level']} or higher")
            if caster.slots_left(use_slot) <= 0:
                raise Refusal(f"{caster.name} has no level {use_slot} spell slots left", page=104)
            level = use_slot
        elif way.get("free"):
            if slot is not None:
                raise Refusal("The free casting is at the spell's base level; use a slot to cast it higher")
    # --- restrictions ----------------------------------------------------------
    if getattr(caster, "armor", None) is not None and not caster.trained_in(caster.armor_category()):
        raise Refusal(f"{caster.name} lacks training with {caster.armor.display} and can't cast spells in it",
                      page=104)
    _components(game, caster, spell, sd, scroll or item is not None)
    cb = game.combat
    if cb is not None and cb.is_turn(caster) and use_slot and cb.turn.slot_spell_cast:
        raise Refusal("Only one spell slot can be expended to cast a spell on a turn", page=105)
    if ritual and cb is not None:
        raise Refusal("A Ritual takes 10 minutes longer than normal; it can't be completed in the middle of combat "
                      "(you'd have to take the Magic action every turn while keeping Concentration)", page=105)
    # targets behind Total Cover can't be targeted (p.106)
    for t in ([] if sd.get("area") else targets):
        if hasattr(t, "id") and t is not caster and game.cover_between(caster, t) == "total":
            raise Refusal(f"{t.name} is behind Total Cover and can't be targeted", page=106)
    _range_check(game, caster, spell, sd, targets)
    # --- action economy ----------------------------------------------------------
    time = sd["time"]
    if cb is not None:
        if time == "action":
            cb.spend(caster, "action", "Magic")
        elif time == "bonus action":
            cb.spend(caster, "bonus", f"cast {spell.title()}")
        elif time == "reaction":
            cb.spend(caster, "reaction")
    # --- pay ---------------------------------------------------------------------
    if use_slot:
        caster.slots_used[use_slot] = caster.slots_used.get(use_slot, 0) + 1
        if cb is not None and cb.is_turn(caster):
            cb.turn.slot_spell_cast = True
    if item is None and not ritual and sd["level"] > 0 and not use_slot:
        caster.free_casts[spell]["available"] = False
    if sd["level"] > 0 and game.rest is not None:
        game.rest["interrupted"] = f"{caster.name} cast {spell.title()}"
    # casting a spell reveals a hidden caster (V) and ends Invisibility / Sanctuary on the caster
    _on_cast_side_effects(game, caster, sd)
    c = Casting(spell, caster, level, ability, dc, atk, use_slot, ritual, source, item)
    how = ("as a Ritual (+10 minutes, no slot)" if ritual else f"with a level {use_slot} slot" if use_slot
           else f"from {item.display}" if item is not None else "(no slot)")
    g.log.player("cast", f"{caster.name} casts {spell.title()}" + (f" at level {level}" if level > sd["level"] else "")
                 + f" {how}" + (f" [{source}]" if source else ""), page=sd["page"], spell=spell, level=level)
    if ritual:
        game.advance(10 * MINUTE + (ROUND if time == "action" else 0), f"ritual casting of {spell.title()}")
    if sd["concentration"]:
        game.start_concentration(caster, spell.title())
    fn = IMPL.get(spell)
    if fn is None:
        raise OutOfScope(f"{spell.title()} has no implementation")
    fn(game, c, targets, point=point, option=option, **kw)
    if item is not None and scroll:
        caster.inventory.remove(item, 1)
        g.log.player("item", f"The Spell Scroll crumbles to dust", page=244)
    return c


def _as_list(game, targets):
    if targets is None:
        return []
    if not isinstance(targets, (list, tuple)):
        targets = [targets]
    out = []
    for t in targets:
        if isinstance(t, str):
            try:
                out.append(game.get(t))
            except Refusal:
                out.append(t)
        else:
            out.append(t)
    return out


def _way(caster, spell, ritual, free, slot):
    if not caster.is_pc():
        return _monster_way(caster, spell)
    sd = SPELLS[spell]
    if ritual and caster.cls == "wizard" and spell in caster.spellbook and caster.has_feature("ritual adept"):
        return {"ability": caster.spell_ability, "source": "Ritual Adept (from the spellbook)"}
    ways = caster.castable(spell)
    if not ways:
        where = "prepared" if sd["level"] else "known"
        raise Refusal(f"{caster.name} doesn't have {spell.title()} {where}", page=104)
    if ritual:
        w = next((w for w in ways if w["slot"]), None)
        if w is None:
            raise Refusal(f"To cast {spell.title()} as a Ritual, {caster.name} must have it prepared", page=104)
        return w
    if sd["level"] == 0:
        return ways[0]
    free_way = next((w for w in ways if w.get("free")), None)
    slot_way = next((w for w in ways if w["slot"]), None)
    if free and free_way:
        if not caster.free_casts[spell]["available"]:
            raise Refusal(f"The free casting of {spell.title()} recharges only on a Long Rest", page=87)
        return free_way
    if free and not free_way:
        raise Refusal(f"{caster.name} has no free casting of {spell.title()}")
    if slot_way is None:
        # an always-prepared feature spell (e.g. Magic Initiate) can also be cast with any slot
        if free_way:
            return {"ability": free_way["ability"], "source": free_way["source"], "slot": True}
        raise Refusal(f"{caster.name} can't cast {spell.title()}")
    # Magic Initiate spells always use the feat's ability, even with a slot
    if free_way:
        return {"ability": free_way["ability"], "source": free_way["source"], "slot": True}
    return slot_way


def _monster_way(caster, spell):
    if "divine aid" in caster.traits and spell in ("bless", "healing word", "sanctuary"):
        if caster.uses.get("divine aid", 0) <= 0:
            raise Refusal(f"{caster.name} has used Divine Aid today")
        caster.uses["divine aid"] -= 1
        return {"ability": "wis", "source": "Divine Aid", "free": True, "monster": True}
    raise Refusal(f"{caster.name} can't cast {spell.title()} (not in its stat block)")


def _item_casting(game, caster, spell, item, scroll, charges):
    if scroll:
        from .magic_items import scroll_casting
        return scroll_casting(game, caster, spell, item)
    from .magic_items import wand_casting
    return wand_casting(game, caster, spell, item, charges)


def _components(game, caster, spell, sd, from_item):
    comp = sd["components"]
    if "V" in comp:
        if caster.notes.get("gagged"):
            raise Refusal(f"{caster.name} is gagged and can't provide the Verbal component", page=105)
        if game.scene.silence:
            raise Refusal(f"{caster.name} is in an area of magical Silence; Verbal components are impossible",
                          page=105)
    if not caster.is_pc() or from_item:
        return
    from .combat import hands_free
    focus = _held_focus(caster)
    if "S" in comp and hands_free(caster) < 1 and not ("M" in comp and focus):
        _free_a_hand(game, caster)
    if "M" in comp:
        if sd["material_cost"]:
            # a costed component must be the real thing (Bless: a Holy Symbol worth 5+ GP)
            if caster.inventory.find("holy symbol") is None:
                raise Refusal(f"{spell.title()} needs {sd['material']}", page=105)
            return
        if caster.inventory.find("component pouch") or focus or caster.inventory.find("holy symbol") \
                and "holy symbol" in FOCUS_FOR.get(caster.cls, []):
            return
        raise Refusal(f"{caster.name} needs {sd['material']}, a Component Pouch or a Spellcasting Focus", page=105)


def _free_a_hand(game, caster):
    """Somatic components need a hand (p.105). A held weapon can be stowed with the free object
    interaction; hands that are otherwise full can't cast."""
    if caster.notes.get("hands_full") or not caster.wielded:
        raise Refusal(f"{caster.name} needs a free hand for the Somatic component", page=105)
    cb = game.combat
    w = caster.wielded[-1]
    if cb is not None and cb.is_turn(caster):
        if cb.turn.free_interaction:
            raise Refusal(f"{caster.name} needs a free hand for the Somatic component and has already used the "
                          f"free object interaction this turn", page=105)
        cb.turn.free_interaction = True
    caster.wielded.remove(w)
    game.log.player("interact", f"{caster.name} stows the {w.display} to free a hand for the spell's gestures",
                    page=13)


def _held_focus(caster):
    for f in FOCUS_FOR.get(caster.cls, []):
        it = caster.inventory.find(f)
        if it is not None:
            return it
    return None


def _range_check(game, caster, spell, sd, targets):
    rng = sd["range"]
    for t in targets:
        if not hasattr(t, "position"):
            continue
        d = caster.distance_to(t)
        if rng == "touch":
            if d > caster.reach:
                raise Refusal(f"{t.name} is {d} ft away; {spell.title()} requires touch", page=105)
        elif isinstance(rng, int):
            limit = rng
            if spell == "spare the dying":
                limit = rng * (2 if caster_level(caster) >= 5 else 1)
            if d > limit:
                raise Refusal(f"{t.name} is {d} ft away, beyond {spell.title()}'s range of {limit} ft", page=105)


def _on_cast_side_effects(game, caster, sd):
    if "V" in sd["components"] and caster.hidden_total is not None:
        from .actions import end_hiding
        end_hiding(game, caster, "cast a spell with a Verbal component")
    for e in list(caster.effects):
        if getattr(e, "ends_on_cast", False):
            caster.remove_effect(e, f"{caster.name} cast a spell")


def caster_level(c) -> int:
    return getattr(c, "level", None) or max(1, int(getattr(c, "cr", 1)))


def cantrip_dice(c, n: int = 1) -> int:
    lvl = caster_level(c)
    return n * (1 + (lvl >= 5) + (lvl >= 11) + (lvl >= 17))


# ---------------------------------------------------------------------------
# shared resolution helpers
# ---------------------------------------------------------------------------
def spell_attack(game, c: Casting, target, melee=False, dist=None):
    caster = c.caster
    dist = dist if dist is not None else caster.distance_to(target)
    ctx = Ctx("attack", caster, target=target, melee=melee, ranged=not melee, spell=c.spell, distance=dist)
    acc = caster.gather(ctx)
    roll = D20Roll("attack", f"spell attack ({c.spell.title()}) on {target.name}", caster.name)
    roll.mods = [(c.attack, "spell attack bonus")] + acc.mods
    roll.adv, roll.dis = list(acc.adv), list(acc.dis)
    if not melee:
        for e in game.creatures.values():
            if e.team not in (caster.team, "neutral") and not e.dead and dist_points(e.position, caster.position) <= 5 \
                    and not e.has("incapacitated") and can_see(e, caster):
                roll.dis.append(f"ranged attack with {e.name} within 5 ft")
                break
    if not can_see(caster, target):
        roll.dis.append(f"{caster.name} can't see {target.name}")
    if not can_see(target, caster):
        roll.adv.append(f"{target.name} can't see {caster.name}")
    for e in acc.consumed:
        if e.owner is not None:
            e.owner.remove_effect(e)
    parts = target.ac_parts()
    cover = game.cover_between(caster, target)
    if cover in ("half", "three-quarters"):
        parts.append((2 if cover == "half" else 5, f"{cover.title()} Cover"))
    roll.target = sum(v for v, _ in parts)
    roll_d20_test(game, caster, roll, bonus_dice=acc.bonus_dice, page=106)
    from .combat import _reveal_attacker, _sanctuary
    _reveal_attacker(game, caster)
    for e in list(caster.effects):
        e.on_attack_roll(game, roll, None)
    hit = bool(roll.success)
    crit = hit and roll.crit
    if hit and not crit and acc.auto_crit:
        crit = True
    if hit and not crit and offer_shield(game, target, roll):
        hit = roll.total >= roll.target
    return roll, hit, crit


def spell_save(game, c: Casting, target, ability, ignore_cover=False, avoid=(), label=None):
    bonus = []
    if ability == "dex" and not ignore_cover:
        cover = game.cover_between(c.caster, target)
        if cover in ("half", "three-quarters"):
            bonus.append((2 if cover == "half" else 5, f"{cover.title()} Cover"))
    return target.save(ability, c.dc, bonus=bonus, avoid=avoid, source=c.caster,
                       label=label or f"{ability.title()} save vs {c.spell.title()} (DC {c.dc})", page=c.data["page"])


def roll_dice(game, expr, crit=False, actor=None):
    from .combat import roll_damage_dice
    return roll_damage_dice(game, actor, expr, crit)


def deal(game, c, target, amount, dtype, crit=False):
    if amount <= 0:
        return 0
    dealt = target.take_damage(amount, dtype, attacker=c.caster, crit=crit, source=c.spell.title())
    from .combat import _post_damage_hooks
    _post_damage_hooks(game, c.caster, target, dealt)
    return dealt


def potent(c) -> bool:
    return c.data["level"] == 0 and c.caster.is_pc() and c.caster.has_feature("potent cantrip")


def disciple_bonus(c) -> int:
    """Disciple of Life (p.40): +2 + slot level when a slot-cast spell restores HP."""
    if c.slot and c.caster.is_pc() and c.caster.has_feature("disciple of life"):
        return 2 + c.slot
    return 0


def heal(game, c, target, dice_expr, extra_label=""):
    total, rolls = roll_dice(game, dice_expr, actor=c.caster)
    mod = c.caster.mod(c.ability) if c.ability else 0
    bonus = disciple_bonus(c)
    amount = total + mod + bonus
    game.log.player("spell", f"{c.spell.title()} heals {dice_expr}={rolls} + {mod} ({c.ability.title()})"
                    + (f" + {bonus} Disciple of Life" if bonus else "") + f" = {amount}", page=c.data["page"])
    return target.heal(amount, c.spell.title(), page=c.data["page"])


def offer_shield(game, target, roll, trigger="attack") -> bool:
    """Shield (p.161): Reaction when hit by an attack roll; +5 AC including against that attack."""
    if not target.is_pc() or "shield" not in [s for s in target.all_known_spells()]:
        return False
    if target.slots_left(1) <= 0 and not any(target.slots_left(l) > 0 for l in (2, 3)):
        return False
    if game.combat is not None and not game.combat.has_reaction(target):
        return False
    if target.has("incapacitated"):
        return False
    if trigger == "magic missile":
        want = game.decide(target, "shield", [True, False], default=True,
                           prompt=f"REACTION: {target.name} is targeted by Magic Missile. Cast Shield (no damage from "
                                  f"Magic Missile, +5 AC until your next turn)?")
        if want:
            cast(game, target, "shield")
        return bool(want)
    new_ac = roll.target + 5
    want = game.decide(target, "shield", [True, False], default=roll.total < new_ac,
                       prompt=f"REACTION: {target.name} is hit (attack total {roll.total} vs AC {roll.target}). "
                              f"Cast Shield for +5 AC (AC {new_ac}), including against this attack?")
    if not want:
        return False
    cast(game, target, "shield")
    roll.target = new_ac
    return True


# ---------------------------------------------------------------------------
# spell effects
# ---------------------------------------------------------------------------
class Bless(Effect):
    name = "Bless"

    def d20(self, ctx, acc):
        if ctx.kind in ("attack", "save"):
            first = next(e for e in self.owner.effects if isinstance(e, Bless))
            if first is self:                     # same spell twice doesn't combine (p.106)
                acc.dice("1d4", "Bless")


class Guidance(Effect):
    name = "Guidance"

    def __init__(self, skill, **kw):
        super().__init__(f"Guidance ({skill.title()})", **kw)
        self.skill = skill

    def d20(self, ctx, acc):
        if ctx.kind == "check" and ctx.skill == self.skill:
            first = next(e for e in self.owner.effects if isinstance(e, Guidance))
            if first is self:
                acc.dice("1d4", "Guidance")


class ShieldSpell(ACBonus):
    name = "Shield"

    def damage_traits(self, owner, dtype):
        return False, False, False


class Sanctuary(Effect):
    name = "Sanctuary"
    ends_on_cast = True
    ends_on_dealing_damage = True

    def on_attack_roll(self, game, roll, ctx):
        self.owner.remove_effect(self, f"{self.owner.name} made an attack roll")


class InvisibilitySpell(Effect):
    name = "Invisibility (spell)"
    ends_on_cast = True
    ends_on_dealing_damage = True

    def on_attack_roll(self, game, roll, ctx):
        self.owner.remove_effect(self, f"{self.owner.name} made an attack roll")
        self.owner.remove_condition("invisible", source="Invisibility")

    def on_removed(self, game):
        if self.owner is not None:
            for e in list(self.owner.effects):
                if e.condition == "invisible" and e.source == "Invisibility":
                    self.owner.effects.remove(e)


class RepeatSave(Condition):
    """A spell-imposed condition with a repeat save at the end of the target's turns (Hold Person)."""

    def __init__(self, name, ability, dc, spell, **kw):
        super().__init__(name, **kw)
        self.ability, self.dc, self.spell = ability, dc, spell

    def on_turn_end(self, game):
        o = self.owner
        r = o.save(self.ability, self.dc, label=f"{self.ability.title()} save to end {self.spell} (DC {self.dc})")
        if r.success:
            o.remove_effect(self, f"succeeded on the save against {self.spell}")


class SleepEffect(Condition):
    """Sleep (p.163): Incapacitated until the end of its next turn, then a second save or Unconscious."""

    def __init__(self, dc, stage="incapacitated", **kw):
        super().__init__(stage, source=f"Sleep", **kw)
        self.dc = dc
        self.stage = stage

    def on_turn_end(self, game):
        o = self.owner
        if self.stage != "incapacitated":
            return
        r = o.save("wis", self.dc, label=f"Wisdom save vs Sleep, second save (DC {self.dc})", page=163)
        o.effects.remove(self)
        if not r.success:
            u = SleepEffect(self.dc, "unconscious", caster=self.caster_id, concentration=True, until=self.until)
            o.add_effect(u)
            game.log.player("condition", f"{o.name} falls Unconscious (Sleep)", page=163)
            game.on_incapacitated(o)
        else:
            game.log.player("spell", f"{o.name} shakes off the Sleep spell", page=163)

    def on_damaged(self, game, amount, dtype, attacker=None, crit=False):
        self.owner.remove_effect(self, "took damage (Sleep ends)")

    def on_removed(self, game):
        o = self.owner
        if o is not None and self.stage == "unconscious" and not o.has("prone"):
            o.add_condition("prone", "was Unconscious")


class TurnedEffect(Condition):
    ends_if_caster_incapacitated = True

    def on_damaged(self, game, amount, dtype, attacker=None, crit=False):
        o = self.owner
        for e in list(o.effects):
            if isinstance(e, TurnedEffect):
                o.remove_effect(e, "took damage (Turn Undead ends)")


class CommandEffect(Effect):
    name = "Command"

    def __init__(self, word, caster, **kw):
        super().__init__(f"Command: {word.title()}", caster=caster, **kw)
        self.word = word

    def on_turn_start(self, game):
        apply_command(game, self.owner, self.word, game.creatures.get(self.caster_id))
        self.owner.remove_effect(self)


def apply_command(game, target, word, caster):
    word = word.lower()
    if word == "grovel":
        target.add_condition("prone", "Command: Grovel")
        game.log.player("spell", f"{target.name} grovels (Prone) and ends its turn", page=116)
        if game.combat is not None and game.combat.is_turn(target):
            game.combat.turn.actions_used = game.combat.turn.actions
            game.combat.turn.bonus_used = True
            game.combat.turn.movement_left = 0
            target.notes["turn_ended"] = True
    elif word == "drop":
        if getattr(target, "wielded", None):
            target.wielded = []
        game.log.player("spell", f"{target.name} drops what it holds and ends its turn", page=116)
    elif word == "halt":
        game.log.player("spell", f"{target.name} doesn't move and takes no action or Bonus Action", page=116)
        if game.combat is not None and game.combat.is_turn(target):
            game.combat.turn.actions_used = game.combat.turn.actions
            game.combat.turn.bonus_used = True
            game.combat.turn.movement_left = 0
    else:
        game.log.player("spell", f"{target.name} obeys the command '{word.title()}' on its turn", page=116)


class AidEffect(Effect):
    name = "Aid"

    def __init__(self, amount, **kw):
        super().__init__(f"Aid (+{amount})", **kw)
        self.amount = amount

    def on_removed(self, game):
        o = self.owner
        if o is not None:
            o.max_hp_bonus -= self.amount
            o.hp = min(o.hp, o.max_hp)


class MageArmorEffect(Effect):
    name = "Mage Armor"

    def on_removed(self, game):
        if self.owner is not None:
            self.owner.notes.pop("mage_armor", None)


class SpiritualWeaponEffect(Effect):
    name = "Spiritual Weapon"


# ---------------------------------------------------------------------------
# implementations
# ---------------------------------------------------------------------------
def _fire_bolt(game, c, targets, **kw):
    t = targets[0]
    if isinstance(t, str):
        obj = game.scene.objects.get(t)
        if obj is None:
            raise Refusal(f"No target {t!r}")
        game.log.player("spell", f"The Fire Bolt strikes the {t}", page=132)
        if obj.get("flammable") and not obj.get("worn"):
            obj["burning"] = True
            game.log.player("spell", f"The {t} starts burning", page=132)
        return
    roll, hit, crit = spell_attack(game, c, t)
    n = cantrip_dice(c.caster)
    if hit:
        total, rolls = roll_dice(game, f"{n}d10", crit, c.caster)
        deal(game, c, t, total, "fire", crit)
    elif potent(c):
        total, rolls = roll_dice(game, f"{n}d10", False, c.caster)
        game.log.player("spell", f"Potent Cantrip: the miss still deals half damage ({total}//2)", page=82)
        deal(game, c, t, div(total, 2), "fire")


def _ray_of_frost(game, c, targets, **kw):
    t = targets[0]
    roll, hit, crit = spell_attack(game, c, t)
    n = cantrip_dice(c.caster)
    if hit:
        total, _ = roll_dice(game, f"{n}d8", crit, c.caster)
        deal(game, c, t, total, "cold", crit)
        if not t.dead:
            t.add_effect(SpeedPenalty("Ray of Frost", 10, ends=[("start", c.caster.id)]))
            game.log.player("spell", f"{t.name}'s Speed drops by 10 ft until the start of {c.caster.name}'s next turn",
                            page=157)
    elif potent(c):
        total, _ = roll_dice(game, f"{n}d8", False, c.caster)
        game.log.player("spell", "Potent Cantrip: half damage on the miss, no Speed reduction", page=82)
        deal(game, c, t, div(total, 2), "cold")


def _sacred_flame(game, c, targets, **kw):
    t = targets[0]
    if not can_see(c.caster, t):
        raise Refusal(f"{c.caster.name} must see the target of Sacred Flame")
    r = spell_save(game, c, t, "dex", ignore_cover=True)
    n = cantrip_dice(c.caster)
    if not r.success:
        total, _ = roll_dice(game, f"{n}d8", False, c.caster)
        deal(game, c, t, total, "radiant")
    elif potent(c):
        total, _ = roll_dice(game, f"{n}d8", False, c.caster)
        deal(game, c, t, div(total, 2), "radiant")


def _guidance(game, c, targets, option=None, **kw):
    t = targets[0] if targets else c.caster
    skill = norm(option or "perception")
    t.add_effect(Guidance(skill, caster=c.caster, concentration=True, until=game.clock + MINUTE))
    game.log.player("spell", f"{t.name} adds 1d4 to {skill.title()} checks while Guidance lasts", page=138)


def _light(game, c, targets, **kw):
    name = targets[0] if targets and isinstance(targets[0], str) else "glowing object"
    for obj in game.scene.objects.values():
        if obj.get("light_spell") == c.caster.id:
            obj.pop("light", None)
            obj.pop("light_spell", None)
    game.scene.objects.setdefault(name, {})
    game.scene.objects[name].update(light=[20, 20], light_spell=c.caster.id, position=c.caster.position,
                                    until=game.clock + HOUR)
    game.log.player("spell", f"The {name} sheds Bright Light 20 ft and Dim Light 20 ft more for 1 hour", page=144)


def _flavor(text):
    def fn(game, c, targets, option=None, **kw):
        game.log.player("spell", text.format(caster=c.caster.name, option=option or ""), page=c.data["page"])
        if c.spell == "thaumaturgy" and option and "boom" in option.lower():
            c.caster.add_effect(AdvNext("Thaumaturgy (Booming Voice)", kinds=("check",), skill="intimidation",
                                        until=game.clock + MINUTE))
    return fn


def _spare_the_dying(game, c, targets, **kw):
    t = targets[0]
    if t.dead or t.hp > 0:
        raise Refusal("Spare the Dying targets a creature with 0 Hit Points that isn't dead", page=163)
    from .damage import make_stable
    make_stable(game, t, f"Spare the Dying from {c.caster.name}")


def _bless(game, c, targets, **kw):
    n = 3 + (c.level - 1)
    if len(targets) > n:
        raise Refusal(f"Bless at level {c.level} targets up to {n} creatures")
    for t in targets:
        t.add_effect(Bless(f"Bless ({c.caster.name})", caster=c.caster, concentration=True,
                           until=game.clock + MINUTE))
    game.log.player("spell", f"Blessed: {', '.join(t.name for t in targets)} (+1d4 to attack rolls and saves)",
                    page=113)


def _area_targets(game, c, targets, shape, size):
    """Creatures named by the caller as inside the area; drop anyone behind Total Cover from the origin
    and the caster (the point of origin of a Cone/Cube from self isn't included)."""
    out = []
    for t in targets:
        if t is c.caster:
            continue
        if game.cover_between(c.caster, t) == "total":
            game.log.player("spell", f"{t.name} is behind Total Cover and isn't affected", page=177)
            continue
        if c.caster.distance_to(t) > size:
            game.log.player("spell", f"{t.name} is outside the {size}-ft {shape}", page=177)
            continue
        out.append(t)
    return out


def _save_for_half(game, c, targets, ability, dice, dtype, on_fail=None):
    total, rolls = roll_dice(game, dice, False, c.caster)
    game.log.player("spell", f"{c.spell.title()} damage rolled once for all targets: {dice}={rolls} = {total}",
                    page=16)
    for t in targets:
        r = spell_save(game, c, t, ability)
        dmg = div(total, 2) if r.success else total
        deal(game, c, t, dmg, dtype)
        if not r.success and on_fail and not t.dead:
            on_fail(t)
    return total


def _burning_hands(game, c, targets, **kw):
    ts = _area_targets(game, c, targets, "Cone", 15)
    _save_for_half(game, c, ts, "dex", f"{3 + c.level - 1}d6", "fire")
    for name, obj in game.scene.objects.items():
        if obj.get("flammable") and obj.get("in_cone") and not obj.get("worn"):
            obj["burning"] = True
            game.log.player("spell", f"The {name} catches fire", page=114)


def _thunderwave(game, c, targets, **kw):
    ts = _area_targets(game, c, targets, "Cube", 15)

    def push(t):
        from .combat import move
        move(game, t, away_from=c.caster, feet=10, forced=True)
    _save_for_half(game, c, ts, "con", f"{2 + c.level - 1}d8", "thunder", on_fail=push)
    game.log.player("spell", "A thunderous boom is audible within 300 feet", page=168)


def _command(game, c, targets, option="grovel", **kw):
    n = 1 + (c.level - 1)
    if len(targets) > n:
        raise Refusal(f"Command at level {c.level} affects up to {n} creatures")
    word = norm(option or "grovel")
    if word not in ("approach", "drop", "flee", "grovel", "halt"):
        raise Refusal("Command words: Approach, Drop, Flee, Grovel or Halt")
    for t in targets:
        r = spell_save(game, c, t, "wis")
        if not r.success:
            if game.combat is not None and not game.combat.is_turn(t):
                t.add_effect(CommandEffect(word, c.caster))
                game.log.player("spell", f"{t.name} must follow the command '{word.title()}' on its next turn",
                                page=116)
            else:
                apply_command(game, t, word, c.caster)


def _cure_wounds(game, c, targets, **kw):
    t = targets[0]
    heal(game, c, t, f"{2 * c.level}d8")


def _healing_word(game, c, targets, **kw):
    t = targets[0]
    if not can_see(c.caster, t):
        raise Refusal(f"{c.caster.name} must see the target of Healing Word")
    heal(game, c, t, f"{2 * c.level}d4")


def _detect_magic(game, c, targets, **kw):
    found = []
    for cr in game.creatures.values():
        if cr.distance_to(c.caster) <= 30:
            for it in getattr(cr, "inventory", []):
                if it.magical:
                    found.append(f"{it.display} ({cr.name})")
    for name, obj in game.scene.objects.items():
        if obj.get("magic"):
            found.append(name)
    c.caster.add_effect(Effect("Detect Magic", caster=c.caster, concentration=True, until=game.clock + 10 * MINUTE))
    game.log.player("spell", f"{c.caster.name} senses magic: " + (", ".join(found) if found else "nothing within 30 ft"),
                    page=125)


def _guiding_bolt(game, c, targets, **kw):
    t = targets[0]
    roll, hit, crit = spell_attack(game, c, t)
    if hit:
        total, _ = roll_dice(game, f"{4 + c.level - 1}d6", crit, c.caster)
        deal(game, c, t, total, "radiant", crit)
        if not t.dead:
            eff = GuidedTarget(f"Guiding Bolt ({c.caster.name})", ends=[("end", c.caster.id)])
            if game.combat is not None and game.combat.is_turn(c.caster):
                eff.data["skip"] = {("end", c.caster.id): 1}
            t.add_effect(eff)


class GuidedTarget(Effect):
    name = "Guiding Bolt"

    def as_target(self, ctx, acc):
        if ctx.kind == "attack":
            acc.advantage(self.source)
            acc.consumed.append(self)


def _mage_armor(game, c, targets, **kw):
    t = targets[0] if targets else c.caster
    if getattr(t, "armor", None) is not None:
        raise Refusal(f"{t.name} is wearing armor; Mage Armor needs a creature not wearing armor", page=145)
    t.notes["mage_armor"] = True
    t.add_effect(MageArmorEffect("Mage Armor", caster=c.caster, until=game.clock + 8 * HOUR))
    game.log.player("spell", f"{t.name}'s base AC becomes 13 + Dex (AC {t.ac()}) for 8 hours", page=145)


def _magic_missile(game, c, targets, option=None, **kw):
    darts = 3 + (c.level - 1)
    if not targets:
        raise Refusal("Choose targets for the darts")
    # distribute: option may be a list of counts per target
    counts = option if isinstance(option, (list, tuple)) else None
    if counts is None:
        counts = [darts // len(targets) + (1 if i < darts % len(targets) else 0) for i in range(len(targets))]
    if sum(counts) != darts:
        raise Refusal(f"Magic Missile at level {c.level} creates {darts} darts")
    game.log.player("spell", f"{darts} darts of magical force strike automatically", page=146)
    for t, n in zip(targets, counts):
        # Shield: the target may react when targeted
        if t.is_pc() and not t.find_effects(cls=ShieldSpell):
            offer_shield(game, t, None, trigger="magic missile")
        if t.find_effects(cls=ShieldSpell):
            game.log.player("spell", f"{t.name}'s Shield absorbs the darts: no damage from Magic Missile", page=161)
            continue
        total = 0
        for _ in range(n):
            r = game.dice.roll(4)
            total += r + 1
        deal(game, c, t, total, "force")


def _sanctuary(game, c, targets, **kw):
    t = targets[0]
    t.add_effect(Sanctuary(f"Sanctuary ({c.caster.name})", caster=c.caster, until=game.clock + MINUTE))
    game.log.player("spell", f"{t.name} is warded by Sanctuary", page=159)


def _shield(game, c, targets, **kw):
    t = c.caster
    eff = ShieldSpell("Shield", 5, ends=[("start", t.id)])
    t.add_effect(eff)
    game.log.player("spell", f"{t.name} raises Shield: +5 AC until the start of their next turn (AC {t.ac()})",
                    page=161)


def _shield_of_faith(game, c, targets, **kw):
    t = targets[0] if targets else c.caster
    t.add_effect(ACBonus("Shield of Faith", 2, caster=c.caster, concentration=True, until=game.clock + 10 * MINUTE))
    game.log.player("spell", f"{t.name} gains +2 AC (Shield of Faith)", page=161)


def _sleep(game, c, targets, **kw):
    for t in targets:
        if "trance" in t.traits or "exhaustion" in t.cond_immune or t.notes.get("doesnt_sleep"):
            game.log.player("save", f"{t.name} automatically succeeds on the save against Sleep "
                            f"({'doesn’t sleep' if 'trance' in t.traits or t.notes.get('doesnt_sleep') else 'Immune to Exhaustion'})",
                            page=163)
            continue
        r = spell_save(game, c, t, "wis")
        if not r.success:
            e = SleepEffect(c.dc, caster=c.caster, concentration=True, until=game.clock + MINUTE)
            e.ends = []
            t.add_effect(e)
            game.log.player("condition", f"{t.name} has the Incapacitated condition until the end of its next turn "
                            f"(Sleep)", page=163)
            game.on_incapacitated(t)


def shake_awake(game, helper, target):
    if helper.distance_to(target) > 5:
        raise Refusal("You must be within 5 ft to shake someone awake")
    if game.combat is not None:
        game.combat.spend(helper, "action", "shake awake")
    for e in list(target.effects):
        if isinstance(e, SleepEffect):
            target.remove_effect(e, f"shaken awake by {helper.name}")


def _aid(game, c, targets, **kw):
    if len(targets) > 3:
        raise Refusal("Aid targets up to three creatures")
    amount = 5 * (1 + (c.level - 2))
    for t in targets:
        for e in list(t.effects):
            if isinstance(e, AidEffect):
                t.remove_effect(e)
        t.max_hp_bonus += amount
        t.hp += amount
        t.add_effect(AidEffect(amount, caster=c.caster, until=game.clock + 8 * HOUR))
        game.log.player("spell", f"{t.name}'s HP maximum and current HP increase by {amount} for 8 hours "
                        f"({t.hp}/{t.max_hp})", page=107)


def _hold_person(game, c, targets, **kw):
    n = 1 + (c.level - 2)
    if len(targets) > n:
        raise Refusal(f"Hold Person at level {c.level} targets up to {n} Humanoids")
    for t in targets:
        if t.ctype != "humanoid":
            # p.106 invalid target: slot spent; the target appears to succeed
            game.log.player("save", f"{t.name} succeeds on its Wisdom saving throw against Hold Person", page=106)
            game.log.gm("invalid_target", f"{t.name} is a {t.ctype.title()}, not a Humanoid: invalid target for Hold "
                        f"Person; the slot is spent and it only appears to save", page=106)
            continue
        r = spell_save(game, c, t, "wis", avoid={"paralyzed"})
        if not r.success:
            e = RepeatSave("paralyzed", "wis", c.dc, "Hold Person", source="Hold Person", caster=c.caster,
                           concentration=True, until=game.clock + MINUTE)
            t.add_effect(e)
            game.log.player("condition", f"{t.name} has the Paralyzed condition (Hold Person)", page=141)
            game.on_incapacitated(t)


def _invisibility(game, c, targets, **kw):
    n = 1 + (c.level - 2)
    if len(targets) > n:
        raise Refusal(f"Invisibility at level {c.level} targets up to {n} creatures")
    for t in targets:
        t.add_effect(InvisibilitySpell("Invisibility", caster=c.caster, concentration=True,
                                       until=game.clock + HOUR))
        t.add_condition("invisible", "Invisibility", caster=c.caster, concentration=True, until=game.clock + HOUR)


def _lesser_restoration(game, c, targets, option=None, **kw):
    t = targets[0]
    cond = norm(option) if option else next((x for x in ("poisoned", "paralyzed", "blinded", "deafened")
                                            if t.has(x)), None)
    if cond not in ("blinded", "deafened", "paralyzed", "poisoned"):
        raise Refusal("Lesser Restoration ends Blinded, Deafened, Paralyzed or Poisoned")
    for e in list(t.effects):
        if e.condition == cond:
            t.remove_effect(e, "Lesser Restoration")


def _misty_step(game, c, targets, point=None, **kw):
    if point is None:
        raise Refusal("Choose an unoccupied space within 30 ft that you can see")
    if dist_points(c.caster.position, point) > 30:
        raise Refusal("Misty Step teleports up to 30 feet")
    from .combat import move
    move(game, c.caster, to=point, teleport=True)


def _scorching_ray(game, c, targets, **kw):
    rays = 3 + (c.level - 2)
    if len(targets) == 0:
        raise Refusal("Choose targets for the rays")
    seq = targets if len(targets) == rays else [targets[i % len(targets)] for i in range(rays)]
    for t in seq:
        if t.dead:
            continue
        roll, hit, crit = spell_attack(game, c, t)
        if hit:
            total, _ = roll_dice(game, "2d6", crit, c.caster)
            deal(game, c, t, total, "fire", crit)


def _spiritual_weapon(game, c, targets, point=None, **kw):
    caster = c.caster
    pos = point or (targets[0].position if targets else caster.position)
    caster.add_effect(SpiritualWeaponEffect("Spiritual Weapon", caster=caster, concentration=True,
                                            until=game.clock + MINUTE, position=pos, level=c.level))
    game.log.player("spell", "A spectral weapon appears (Concentration, up to 1 minute)", page=165)
    if targets:
        spiritual_weapon_attack(game, caster, targets[0], first=True)


def spiritual_weapon_attack(game, caster, target, first=False):
    eff = next((e for e in caster.effects if isinstance(e, SpiritualWeaponEffect)), None)
    if eff is None:
        raise Refusal(f"{caster.name} has no Spiritual Weapon")
    if not first and game.combat is not None:
        game.combat.spend(caster, "bonus", "Spiritual Weapon")
        eff.data["position"] = target.position
    level = eff.data.get("level", 2)
    c = Casting("spiritual weapon", caster, level, caster.spell_ability, caster.spell_dc(), caster.spell_attack_bonus())
    roll, hit, crit = spell_attack(game, c, target, melee=True, dist=5)
    if hit:
        total, rolls = roll_dice(game, f"{1 + level - 2}d8", crit, caster)
        deal(game, c, target, total + caster.mod(caster.spell_ability), "force", crit)
    return hit


def _web(game, c, targets, point=None, option=None, **kw):
    anchored = option != "unanchored"
    name = f"web ({c.caster.name})"
    game.scene.objects[name] = {"web": True, "dc": c.dc, "concentration": c.caster.id, "flammable": True,
                                "anchored": anchored, "difficult": True, "lightly_obscured": True,
                                "caught": [t.id for t in targets if hasattr(t, "id")]}
    game.log.player("spell", "Sticky webbing fills a 20-foot Cube: Difficult Terrain and Lightly Obscured", page=174)
    for t in targets:
        web_save(game, t, name)


def web_save(game, t, web_name):
    web = game.scene.objects[web_name]
    r = t.save("dex", web["dc"], label=f"Dexterity save vs Web (DC {web['dc']})", page=174)
    if not r.success:
        t.add_condition("restrained", "Web", concentration=True, caster=web["concentration"], web=web_name)
    return r


def break_web(game, t):
    eff = next((e for e in t.effects if e.condition == "restrained" and e.source == "Web"), None)
    if eff is None:
        raise Refusal(f"{t.name} isn't caught in a web")
    if game.combat is not None:
        game.combat.spend(t, "action", "break free of the web")
    web = game.scene.objects[eff.data["web"]]
    r = t.check("athletics", ability="str", dc=web["dc"], label=f"Strength (Athletics) check to break free "
                f"(DC {web['dc']})", page=174)
    if r.success:
        t.remove_effect(eff, "broke free")
    return r


def burn_web(game, web_name, creatures_in_fire=()):
    web = game.scene.objects.get(web_name)
    if web is None:
        raise Refusal("No such web")
    game.log.player("spell", "Fire burns away a 5-foot Cube of web in 1 round", page=174)
    for t in creatures_in_fire:
        total, rolls = roll_dice(game, "2d4")
        t.take_damage(total, "fire", source="burning web")
        for e in list(t.effects):
            if e.condition == "restrained" and e.source == "Web":
                t.remove_effect(e, "the web burned away")


IMPL = {
    "fire bolt": _fire_bolt, "ray of frost": _ray_of_frost, "sacred flame": _sacred_flame, "guidance": _guidance,
    "light": _light, "mage hand": _flavor("A spectral hand appears near {caster}"),
    "minor illusion": _flavor("{caster} creates an illusion {option}"),
    "prestidigitation": _flavor("{caster} creates a minor magical effect {option}"),
    "thaumaturgy": _flavor("{caster} manifests a minor wonder {option}"),
    "spare the dying": _spare_the_dying, "bless": _bless, "burning hands": _burning_hands, "command": _command,
    "cure wounds": _cure_wounds, "detect magic": _detect_magic, "guiding bolt": _guiding_bolt,
    "healing word": _healing_word, "mage armor": _mage_armor, "magic missile": _magic_missile,
    "sanctuary": _sanctuary, "shield": _shield, "shield of faith": _shield_of_faith, "sleep": _sleep,
    "thunderwave": _thunderwave, "aid": _aid, "hold person": _hold_person, "invisibility": _invisibility,
    "lesser restoration": _lesser_restoration, "misty step": _misty_step, "scorching ray": _scorching_ray,
    "spiritual weapon": _spiritual_weapon, "web": _web,
}
