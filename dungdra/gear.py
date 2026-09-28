"""Equipment handling: armor don/doff, carrying, trade, lifestyle, crafting
(SRD p.89-103, 178)."""
from __future__ import annotations

from .data.equipment import (ARMOR, DON_DOFF, GP, LIFESTYLE, TOOLS, WEAPONS, canonical, item_cost)
from .items import Item, fmt_cp, make_change, sale_price
from .rules import DAY, HOUR, Refusal, div, div_up, norm


# -- armor -------------------------------------------------------------------------
def don_armor(game, pc, name: str):
    it = pc.inventory.find(name)
    if it is None:
        raise Refusal(f"{pc.name} doesn't have {name}")
    if it.kind == "shield":
        return equip_shield(game, pc, it)
    if it.kind != "armor":
        raise Refusal(f"{it.display} isn't armor")
    if pc.armor is not None:
        raise Refusal(f"{pc.name} is already wearing {pc.armor.display}; a creature can wear only one suit "
                      f"of armor at a time", page=92)
    cat = it.armor["category"]
    if game.combat is not None:
        raise Refusal(f"Donning {cat} armor takes {DON_DOFF[cat][0] // 60} minutes; not possible mid-combat",
                      page=92)
    pc.armor = it
    if pc.notes.pop("mage_armor", None):
        for e in list(pc.effects):
            if e.source.startswith("Mage Armor"):
                pc.remove_effect(e, "donned armor")
    game.advance(DON_DOFF[cat][0], f"{pc.name} dons {it.display}")
    warn = []
    if not pc.trained_in(cat):
        warn.append(f"untrained: Disadvantage on Str/Dex D20 Tests and can't cast spells")
    if it.armor["str"] and pc.score("str") < it.armor["str"]:
        warn.append(f"Str {pc.score('str')} < {it.armor['str']}: Speed −10 ft")
    game.log.player("equip", f"{pc.name} dons {it.display} (AC {pc.ac()})" + (f" — {'; '.join(warn)}" if warn else ""),
                    page=92)
    return it


def doff_armor(game, pc):
    if pc.armor is None:
        raise Refusal(f"{pc.name} isn't wearing armor")
    cat = pc.armor.armor["category"]
    if game.combat is not None:
        raise Refusal(f"Doffing {cat} armor takes {DON_DOFF[cat][1] // 60} minutes; not possible mid-combat",
                      page=92)
    it = pc.armor
    pc.armor = None
    game.advance(DON_DOFF[cat][1], f"{pc.name} doffs {it.display}")
    game.log.player("equip", f"{pc.name} removes {it.display} (AC {pc.ac()})", page=92)


def equip_shield(game, pc, it=None):
    it = it or pc.inventory.find("shield")
    if it is None:
        raise Refusal(f"{pc.name} has no Shield")
    if pc.shield is not None:
        raise Refusal(f"{pc.name} can wield only one Shield at a time", page=92)
    if game.combat is not None:
        game.combat.spend(pc, "action", "Utilize (don Shield)")
    pc.shield = it
    note = "" if pc.trained_in("shield") else " — untrained: no AC bonus"
    game.log.player("equip", f"{pc.name} takes up the Shield (Utilize action){note} (AC {pc.ac()})", page=92)


def unequip_shield(game, pc):
    if pc.shield is None:
        raise Refusal(f"{pc.name} isn't holding a Shield")
    if game.combat is not None:
        game.combat.spend(pc, "action", "Utilize (doff Shield)")
    pc.shield = None
    game.log.player("equip", f"{pc.name} sets the Shield aside (AC {pc.ac()})", page=92)


# -- carrying (p.178) ----------------------------------------------------------------
def pick_up(game, pc, name: str, qty: int = 1, weight: float | None = None, **props):
    """Add an item to a PC's load; refused if it would exceed carrying capacity."""
    it = Item(name, qty, **props)
    if weight is not None:
        it.props["weight"] = weight / qty
    carry, _ = pc.capacity()
    new = pc.load() + it.weight()
    if new > carry:
        raise Refusal(f"{pc.name} can't carry that: {new:g} lb exceeds carrying capacity {carry:g} lb", page=178)
    pc.inventory.add(it)
    game.log.player("inventory", f"{pc.name} picks up {it}", page=178)
    return it


def drag(game, pc, weight: float):
    _, maxdrag = pc.capacity()
    if weight > maxdrag:
        raise Refusal(f"{weight:g} lb exceeds {pc.name}'s drag/lift/push limit of {maxdrag:g} lb", page=178)
    pc.notes["dragging"] = weight
    game.log.player("inventory", f"{pc.name} drags {weight:g} lb; Speed is at most 5 ft while doing so "
                    f"(now {pc.speed()} ft)", page=178)


def stop_dragging(game, pc):
    pc.notes.pop("dragging", None)


# -- trade (p.89) ----------------------------------------------------------------------
def buy(game, pc, name: str, qty: int = 1):
    n = canonical(name)
    c = item_cost(n)
    if c is None:
        raise Refusal(f"{name!r} isn't for sale here")
    price = int(round(c * qty))
    pc.purse.pay(price)
    pc.inventory.add(n, qty)
    game.log.player("trade", f"{pc.name} buys {qty} × {n.title()} for {fmt_cp(price)} (left: {pc.purse})", page=89)


def sell(game, pc, name: str, qty: int = 1):
    it = pc.inventory.find(name)
    if it is None:
        raise Refusal(f"{pc.name} doesn't have {name}")
    if it is pc.armor or it is pc.shield:
        raise Refusal(f"Take off {it.display} before selling it")
    price = sale_price(it.base) * qty
    if it.props.get("sell_value") is not None:
        price = it.props["sell_value"] * qty
    pc.inventory.remove(it, qty)
    if it in pc.wielded:
        pc.wielded.remove(it)
    pc.purse.add(price)
    game.log.player("trade", f"{pc.name} sells {qty} × {it.display} for {fmt_cp(price)} (half price)", page=89)
    return price


def pay_with(game, pc, cost_cp: int, coin_cp: int):
    ch = make_change(coin_cp, cost_cp)
    game.log.player("trade", f"{pc.name} pays {fmt_cp(cost_cp)} with {fmt_cp(coin_cp)}; change "
                    f"{ch['gp']} GP {ch['sp']} SP" + (f" {ch['cp']} CP" if ch['cp'] else ""), page=89)
    return ch


# -- lifestyle (p.101) --------------------------------------------------------------------
def live(game, pcs, lifestyle: str, days: int):
    lifestyle = norm(lifestyle)
    if lifestyle not in LIFESTYLE:
        raise Refusal(f"Lifestyles: {', '.join(LIFESTYLE)}")
    per = LIFESTYLE[lifestyle] * days
    for pc in pcs:
        if pc.purse.total_cp() < per:
            raise Refusal(f"{pc.name} can't afford {days} days of {lifestyle.title()} living ({fmt_cp(per)})")
    for pc in pcs:
        pc.purse.pay(per)
        game.log.player("lifestyle", f"{pc.name} pays {fmt_cp(per)} for {days} days of {lifestyle.title()} living",
                        page=101)
    game.advance(days * DAY, f"{days} days of {lifestyle.title()} living")


# -- crafting (p.103) ---------------------------------------------------------------------
def tool_for(item: str) -> list[str]:
    n = canonical(item)
    out = []
    w = WEAPONS.get(n)
    a = ARMOR.get(n)
    for t, d in TOOLS.items():
        for entry in d.get("craft", []):
            if entry == n:
                out.append(t)
            elif entry == "@ranged_except_pistol_musket_sling" and w and w["kind"] == "ranged" \
                    and n not in ("pistol", "musket", "sling"):
                out.append(t)
            elif entry == "@melee_except_club_greatclub_quarterstaff_whip" and w and w["kind"] == "melee" \
                    and n not in ("club", "greatclub", "quarterstaff", "whip"):
                out.append(t)
            elif entry == "@medium_except_hide" and a and a["category"] == "medium" and n != "hide armor":
                out.append(t)
            elif entry == "@heavy" and a and a["category"] == "heavy":
                out.append(t)
    return out


def craft_plan(item: str, helpers: int = 0) -> dict:
    n = canonical(item)
    cost = item_cost(n)
    if cost is None:
        raise Refusal(f"{item!r} has no listed price to craft from")
    gp = cost // GP if cost % GP == 0 else cost / GP
    materials = div(cost, 2)                      # half cost, round down (in CP)
    materials = (materials // GP) * GP if cost >= GP else materials
    days = div_up(int(-(-cost // GP)), 10) if cost >= GP else 1
    work_days = days / (1 + helpers)
    return {"item": n, "materials_cp": materials, "days": days, "work_days": work_days}


def craft(game, pc, item: str, helpers=()):
    n = canonical(item)
    tools = tool_for(n)
    if not tools:
        raise Refusal(f"No tool in scope can craft {n.title()}")
    tool = next((t for t in tools if pc.has_tool_prof(t)), None)
    if tool is None:
        raise Refusal(f"{pc.name} needs proficiency with {' or '.join(t.title() for t in tools)} to craft "
                      f"{n.title()}", page=103)
    if pc.inventory.find(tool) is None:
        pc.notes.setdefault("borrowed_tools", []).append(tool)
    for h in helpers:
        if not h.has_tool_prof(tool):
            raise Refusal(f"{h.name} can't help: helpers must also be proficient with {tool.title()}", page=103)
    plan = craft_plan(n, len(helpers))
    pc.purse.pay(plan["materials_cp"])
    hours = int(plan["work_days"] * 8)
    game.log.player("craft", f"{pc.name} crafts a {n.title()} with {tool.title()}: raw materials "
                    f"{fmt_cp(plan['materials_cp'])}, {plan['days']} day(s) of work"
                    + (f" split among {1 + len(helpers)} crafters ({plan['work_days']:g} days)" if helpers else ""),
                    page=103)
    game.advance(int(-(-plan["work_days"] // 1)) * DAY, f"crafting {n.title()}")
    pc.inventory.add(n, 1)
    return plan
