"""Player-facing inventory, weapon and spell listings."""
from __future__ import annotations

from .data.spells import SPELLS
from .rules import fmt_mod


def _weapon_line(pc, it):
    w = it.weapon
    if "finesse" in w["props"]:
        ab = "dex" if pc.mod("dex") >= pc.mod("str") else "str"
    else:
        ab = "dex" if w["kind"] == "ranged" else "str"
    bonus = pc.mod(ab) + (pc.pb if pc.proficient_with(it) else 0) + it.magic_bonus
    if pc.fighting_style == "archery" and w["kind"] == "ranged":
        bonus += 2
    dmg_mod = pc.mod(ab) + it.magic_bonus
    dmg = f"{w['damage']}{fmt_mod(dmg_mod) if dmg_mod else ''}"
    if w.get("versatile"):
        dmg += f" ({w['versatile']}{fmt_mod(dmg_mod) if dmg_mod else ''} two-handed)"
    extra = []
    if w.get("range"):
        extra.append(f"range {w['range'][0]}/{w['range'][1]}")
    if w["kind"] == "ranged" and "ammunition" in w["props"]:
        extra.append(f"{pc.inventory.count(w['ammo'])} {w['ammo']}")
    if pc.has_mastery(it):
        extra.append(f"mastery: {w['mastery'].title()}")
    held = " [in hand]" if it in pc.wielded else ""
    qty = f" x{it.qty}" if it.qty > 1 else ""
    return (f"  {it.display}{qty}{held}: {fmt_mod(bonus)} to hit, {dmg} {w['dtype'].title()}"
            + (f" ({', '.join(extra)})" if extra else ""))


def inventory_text(pc, section=None) -> str:
    lines = [f"== {pc.name} ({pc.hp}/{pc.max_hp} HP, AC {pc.ac()}) =="]
    want = lambda s: section in (None, s)
    if want("equipment") or want("weapons"):
        worn = []
        if pc.armor:
            worn.append(pc.armor.display)
        if pc.shield:
            worn.append("Shield")
        worn += [i.display for i in pc.attuned]
        lines.append("Wearing: " + (", ".join(worn) or "no armor"))
        weapons = [i for i in pc.inventory if i.kind == "weapon"]
        if weapons:
            lines.append("Weapons:")
            lines += [_weapon_line(pc, i) for i in weapons]
    if want("equipment") or want("potions"):
        magic = [i for i in pc.inventory if i.magical and i.kind != "weapon" and i is not pc.armor]
        if magic:
            lines.append("Potions & magic items:")
            for i in magic:
                note = []
                if "charges" in i.props:
                    note.append(f"{i.props['charges']}/{i.props.get('max_charges', '?')} charges")
                if i.props.get("attunement"):
                    note.append("attuned" if i in pc.attuned else "requires attunement")
                lines.append(f"  {i.display}" + (f" x{i.qty}" if i.qty > 1 else "")
                             + (f" ({', '.join(note)})" if note else ""))
        elif section == "potions":
            lines.append("No potions or magic items.")
    if want("equipment"):
        other = [i for i in pc.inventory if i.kind not in ("weapon", "armor", "shield") and not i.magical
                 and not i.props.get("in_bag")]
        if other:
            lines.append("Gear: " + ", ".join(str(i) for i in other))
        lines.append(f"Coins: {pc.purse}   Load: {pc.load():g}/{pc.capacity()[0]:g} lb")
    if want("spells") or (section is None):
        known = pc.all_known_spells()
        if known:
            if pc.slots_max():
                lines.append("Spell slots: " + ", ".join(f"level {l}: {pc.slots_left(l)}/{m}"
                                                       for l, m in pc.slots_max().items()))
            if pc.spell_ability:
                lines.append(f"Spell save DC {pc.spell_dc()}, spell attack {fmt_mod(pc.spell_attack_bonus())}")
            cants = [c[0].title() for c in pc.cantrips]
            lines.append("Cantrips: " + ", ".join(cants))
            lvl = [s for s in known if SPELLS.get(s, {}).get("level", 0) > 0]
            if lvl:
                parts = []
                for s in sorted(lvl, key=lambda x: (SPELLS[x]["level"], x)):
                    tag = f"L{SPELLS[s]['level']}"
                    if s in pc.free_casts:
                        tag += ", free cast " + ("ready" if pc.free_casts[s]["available"] else "used")
                    if SPELLS[s]["time"] != "action":
                        tag += f", {SPELLS[s]['time']}"
                    parts.append(f"{s.title()} ({tag})")
                lines.append("Spells: " + ", ".join(parts))
            if pc.spellbook:
                lines.append("Spellbook: " + ", ".join(s.title() for s in pc.spellbook))
        elif section == "spells":
            lines.append(f"{pc.name} doesn't cast spells.")
    if section is None and pc.resources:
        lines.append("Features: " + ", ".join(f"{k.title()} {v['max'] - v['used']}/{v['max']}"
                                              for k, v in pc.resources.items()))
    return "\n".join(lines)
