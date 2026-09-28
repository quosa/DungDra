"""The 7 subset magic items (SRD p.102-103, 204-253): identification,
attunement, potions, Spell Scrolls, Wand of Magic Missiles, +1 gear,
Cloak of Protection, Bag of Holding."""
from __future__ import annotations

from .data.spells import SPELLS, CLASS_LISTS
from .effects import ACBonus, SaveBonus
from .items import Item
from .rules import DAY, HOUR, Refusal, norm

SCROLL_DC = {0: (13, 5), 1: (13, 5), 2: (13, 5)}
MAGIC_ITEMS = {
    "potion of healing": {"kind": "potion", "attunement": False},
    "spell scroll": {"kind": "scroll", "attunement": False},
    "wand of magic missiles": {"kind": "wand", "attunement": False, "charges": 7},
    "cloak of protection": {"kind": "wondrous", "attunement": True, "slot": "cloak"},
    "bag of holding": {"kind": "wondrous", "attunement": False, "weight": 5},
    "weapon +1": {"kind": "weapon", "attunement": False},
    "armor +1": {"kind": "armor", "attunement": False},
}


def make(name: str, base: str | None = None, spell: str | None = None, identified=False) -> Item:
    n = norm(name)
    if n in ("potion of healing",):
        return Item("potion of healing", 1, magic=True, identified=identified, kind="potion")
    if n.startswith("spell scroll") or n.startswith("scroll of"):
        sp = norm(spell or n.replace("scroll of", "").replace("spell scroll", "").strip(" ()"))
        if sp not in SPELLS:
            from .rules import OutOfScope
            raise OutOfScope(f"A scroll of {sp} is out of scope")
        return Item("spell scroll", 1, magic=True, spell=sp, title=f"Spell Scroll ({sp.title()})", identified=True,
                    kind="scroll", weight=0)
    if n == "wand of magic missiles":
        return Item(n, 1, magic=True, charges=7, max_charges=7, identified=identified, kind="wand", weight=1,
                    title="Wand of Magic Missiles")
    if n == "cloak of protection":
        return Item(n, 1, magic=True, attunement=True, identified=identified, kind="wondrous", weight=1,
                    title="Cloak of Protection", slot="cloak")
    if n == "bag of holding":
        return Item(n, 1, magic=True, identified=identified, kind="wondrous", weight=5, contents=[],
                    title="Bag of Holding")
    if n.startswith("+1") or n.endswith("+1"):
        b = base or n.replace("+1", "").strip()
        return Item(b, 1, base=b, magic=True, bonus=1, identified=identified, title=f"+1 {b.title()}")
    from .rules import OutOfScope
    raise OutOfScope(f"The magic item {name!r} is out of scope")


# -- potions (p.204, p.99) --------------------------------------------------------------
def drink_potion(game, user, target=None, potion="potion of healing"):
    target = target or user
    it = user.inventory.find(potion)
    if it is None:
        raise Refusal(f"{user.name} has no {potion}")
    if target is not user and user.distance_to(target) > 5:
        raise Refusal("You can administer a potion only to a creature within 5 feet", page=99)
    if game.combat is not None:
        game.combat.spend(user, "bonus", "potion")
    user.inventory.remove(it, 1)
    total, rolls, _ = game.dice.roll_expr("2d4+2")
    who = "drinks" if target is user else f"administers to {target.name}"
    game.log.player("item", f"{user.name} {who} a Potion of Healing (Bonus Action): 2d4+2 = {rolls}+2", page=99)
    return target.heal(total, "Potion of Healing", page=99)


def taste(game, c, item):
    item.props["identified"] = True
    game.log.player("item", f"{c.name} tastes the potion and learns what it does: {item.display}", page=102)


# -- identify & attune (p.102-103) -------------------------------------------------------
def short_rest_focus(game, pc, focus):
    """focus: ('identify'|'attune'|'end_attunement', item)"""
    what, item = focus
    if what == "identify":
        item.props["identified"] = True
        game.log.player("item", f"{pc.name} studies the {item.display} during the Short Rest and learns its "
                        f"properties", page=102)
    elif what == "attune":
        attune(game, pc, item)
    elif what == "end_attunement":
        end_attunement(game, pc, item)


def attune(game, pc, item):
    if not item.props.get("attunement"):
        raise Refusal(f"{item.display} doesn't require Attunement")
    if item in pc.attuned:
        raise Refusal(f"{pc.name} is already attuned to it")
    if item.props.get("identified_on") == game.clock:
        pass
    if any(a.name == item.name for a in pc.attuned):
        raise Refusal(f"{pc.name} can't attune to more than one copy of {item.display}", page=102)
    limit = 3
    if len(pc.attuned) >= limit:
        raise Refusal(f"{pc.name} is already attuned to {limit} magic items; end one Attunement first", page=102)
    pc.attuned.append(item)
    item.props["attuned_to"] = pc.id
    _apply_item(game, pc, item)
    game.log.player("item", f"{pc.name} attunes to the {item.display}", page=102)


def end_attunement(game, pc, item, reason="voluntarily, over a Short Rest"):
    if item not in pc.attuned:
        raise Refusal(f"{pc.name} isn't attuned to {item.display}")
    pc.attuned.remove(item)
    item.props.pop("attuned_to", None)
    for e in list(pc.effects):
        if e.data.get("item") == item.uid:
            pc.effects.remove(e)
    game.log.player("item", f"{pc.name}'s Attunement to the {item.display} ends ({reason})", page=103)


def wear(game, pc, item):
    slot = item.props.get("slot")
    if slot:
        for other in pc.inventory:
            if other is not item and other.props.get("slot") == slot and other.props.get("worn"):
                raise Refusal(f"{pc.name} can't wear more than one {slot}", page=103)
    item.props["worn"] = True
    if item in pc.attuned:
        _apply_item(game, pc, item)
    game.log.player("item", f"{pc.name} puts on the {item.display}", page=103)


def _apply_item(game, pc, item):
    if item.name == "cloak of protection" and item.props.get("worn", True):
        if not any(e.data.get("item") == item.uid for e in pc.effects):
            pc.add_effect(ACBonus("Cloak of Protection", 1, item=item.uid))
            pc.add_effect(SaveBonus("Cloak of Protection", 1, item=item.uid))


def check_distance_attunements(game, pc, away_hours: dict):
    """Attunement ends if the item has been more than 100 ft away for at least 24 hours."""
    for item in list(pc.attuned):
        if away_hours.get(item.uid, 0) >= 24:
            end_attunement(game, pc, item, "more than 100 ft away for 24 hours")


# -- Spell Scroll (p.244) ------------------------------------------------------------------
def scroll_casting(game, caster, spell, item):
    sp = item.props.get("spell")
    if sp != spell:
        raise Refusal(f"That scroll holds {sp.title()}, not {spell.title()}")
    cls = getattr(caster, "cls", None)
    lists = [cls] if cls else []
    if not any(spell in CLASS_LISTS.get(l, []) for l in lists):
        raise Refusal(f"The scroll is unintelligible to {caster.name}: {spell.title()} isn't on their spell list",
                      page=244)
    lvl = SPELLS[spell]["level"]
    max_lvl = max(caster.slots_max()) if caster.slots_max() else 0
    if lvl > max_lvl:
        dc = 10 + lvl
        r = caster.check(ability=caster.spell_ability, dc=dc,
                         label=f"{caster.spell_ability.title()} check to cast {spell.title()} from a scroll (DC {dc})",
                         page=244)
        if not r.success:
            caster.inventory.remove(item, 1)
            game.log.player("item", f"The spell vanishes from the scroll with no other effect", page=244)
            raise Refusal(f"{caster.name} fails to cast {spell.title()} from the scroll; it's lost")
    dc, atk = SCROLL_DC[lvl]
    return caster.spell_ability, dc, atk, "Spell Scroll"


def copy_scroll(game, wizard, item):
    """Copy a Wizard spell from a scroll (p.78, 244): level you can prepare; 2 h and 50 GP per level;
    Int (Arcana) DC 10 + level; the scroll is destroyed either way (p.244)."""
    sp = item.props.get("spell")
    if wizard.cls != "wizard" or sp not in CLASS_LISTS["wizard"]:
        raise Refusal("Only a Wizard can copy a Wizard spell into a spellbook")
    lvl = SPELLS[sp]["level"]
    max_lvl = max(wizard.slots_max())
    if lvl > max_lvl:
        raise Refusal(f"{sp.title()} is level {lvl}; {wizard.name} can only copy spells of a level they can prepare "
                      f"(up to {max_lvl})", page=78)
    if sp in wizard.spellbook:
        raise Refusal(f"{sp.title()} is already in the spellbook")
    cost = 50 * lvl * 100
    wizard.purse.pay(cost)
    game.advance(2 * lvl * HOUR, f"{wizard.name} copies {sp.title()} into the spellbook")
    r = wizard.check("arcana", dc=10 + lvl, label=f"Intelligence (Arcana) check to copy {sp.title()} (DC {10 + lvl})",
                     page=244)
    wizard.inventory.remove(item, 1)
    if r.success:
        wizard.spellbook.append(sp)
        game.log.player("spellbook", f"{wizard.name} copies {sp.title()} into the spellbook (50 GP × {lvl}, "
                        f"{2 * lvl} hours); the scroll is destroyed", page=78)
    else:
        game.log.player("spellbook", f"The copying fails; the scroll is destroyed", page=244)
    return r.success


# -- Wand of Magic Missiles (p.251) --------------------------------------------------------
def wand_casting(game, caster, spell, item, charges):
    if item.name != "wand of magic missiles" or spell != "magic missile":
        raise Refusal("That item can't cast that spell")
    charges = charges or 1
    if charges > 3:
        raise Refusal("You can expend no more than 3 charges from the Wand of Magic Missiles", page=251)
    if item.props["charges"] < charges:
        raise Refusal(f"The wand has only {item.props['charges']} charges")
    item.props["charges"] -= charges
    game.log.player("item", f"{caster.name} expends {charges} charge(s) from the Wand of Magic Missiles "
                    f"({item.props['charges']} left); no spell slot is used", page=251)
    if item.props["charges"] == 0:
        r = game.dice.roll(20)
        game.log.player("item", f"The wand's last charge is spent: d20={r}", page=251)
        if r == 1:
            item.props["destroyed"] = True
            caster.inventory.remove(item, 1)
            game.log.player("item", "The wand crumbles into ashes and is destroyed", page=251)
    return None, 13, 5, "Wand of Magic Missiles"


def dawn(game):
    """Items that recharge at dawn."""
    for c in game.creatures.values():
        for it in getattr(c, "inventory", []):
            if it.name == "wand of magic missiles" and not it.props.get("destroyed"):
                r = game.dice.roll(6)
                before = it.props["charges"]
                it.props["charges"] = min(it.props["max_charges"], before + r + 1)
                game.log.player("item", f"At dawn the Wand of Magic Missiles regains 1d6+1 = {r + 1} charges "
                                f"({before} → {it.props['charges']})", page=251)


# -- Bag of Holding (p.212) -----------------------------------------------------------------
def bag_put(game, pc, bag, name, qty=1):
    it = pc.inventory.find(name)
    if it is None:
        raise Refusal(f"{pc.name} has no {name}")
    w = it.unit_weight() * qty
    inside = sum(x.weight() for x in pc.inventory if x.props.get("in_bag") == bag.uid)
    if inside + w > 500:
        raise Refusal("The Bag of Holding holds at most 500 pounds", page=212)
    if qty < it.qty:
        pc.inventory.remove(it, qty)
        it = pc.inventory.add(Item(it.name, qty, in_bag=bag.uid))
    else:
        it.props["in_bag"] = bag.uid
    game.log.player("item", f"{pc.name} puts {qty} × {it.display} in the Bag of Holding", page=212)


def bag_take(game, pc, bag, name):
    it = next((x for x in pc.inventory if x.props.get("in_bag") == bag.uid and (x.name == name or name in x.display.lower())), None)
    if it is None:
        raise Refusal(f"There's no {name} in the bag")
    if game.combat is not None:
        game.combat.spend(pc, "action", "Utilize (retrieve from Bag of Holding)")
    it.props.pop("in_bag")
    game.log.player("item", f"{pc.name} takes the {it.display} out of the Bag of Holding (Utilize action)", page=212)
    return it
