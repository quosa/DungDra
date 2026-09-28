"""Class and species features granted at each level (levels 1-3)."""
from __future__ import annotations

from .data.classes import CLASSES, LIFE_DOMAIN_SPELLS, SCHOLAR_SKILLS, SUBCLASS_NAMES
from .data.origins import SPECIES
from .data.spells import CLASS_LISTS, OTHER_EVOCATION, OTHER_WIZARD_SPELLS, SPELLS, spell_level
from .rules import Refusal


def grant_features(pc, level: int):
    cd = CLASSES[pc.cls]
    for f in cd["features"].get(level, []):
        if f not in pc.features:
            pc.features.append(f)
    if pc.subclass:
        for f in cd["subclasses"][pc.subclass].get(level, []):
            if f not in pc.features:
                pc.features.append(f)
    refresh_resources(pc)


def refresh_resources(pc):
    lvl = pc.level
    if pc.cls == "fighter":
        pc.add_resource("second wind", CLASSES["fighter"]["second_wind"], short=1)
        if lvl >= 2:
            pc.add_resource("action surge", 1, short="all")
    if pc.cls == "cleric" and lvl >= 2:
        pc.add_resource("channel divinity", CLASSES["cleric"]["channel_divinity"][lvl], short=1)
    if pc.cls == "wizard":
        pc.add_resource("arcane recovery", 1, short=0)
    if "stonecunning" in pc.traits:
        pc.add_resource("stonecunning", pc.pb)


def sneak_attack_dice(pc) -> int:
    return CLASSES["rogue"]["sneak_attack"][pc.level] if pc.cls == "rogue" else 0


def on_level_up(pc):
    g = pc.game
    lvl = pc.level
    new = list(CLASSES[pc.cls]["features"].get(lvl, []))
    grant_features(pc, lvl)
    if lvl == 3 and pc.subclass is None:
        opts = [SUBCLASS_NAMES[pc.cls]]
        choice = g.decide(pc, "subclass", opts, default=opts[0],
                          prompt=f"{pc.name} reached level 3: choose a {pc.cls.title()} subclass {opts}")
        choose_subclass(pc, choice)
        new += CLASSES[pc.cls]["subclasses"][pc.subclass].get(3, [])
    if g and new:
        g.log.player("features", f"{pc.name} gains: {', '.join(f.title() for f in new)}",
                     page=CLASSES[pc.cls]["page"])
    # Fighting Style may be swapped whenever you gain a Fighter level (p.47)
    if pc.cls == "fighter" and g:
        swap = g.decide(pc, "fighting_style_swap", [None, "archery", "defense", "great weapon fighting",
                                                   "two-weapon fighting"], default=None,
                        prompt=f"{pc.name} may replace the {pc.fighting_style} Fighting Style feat")
        if swap and swap != pc.fighting_style:
            old = pc.fighting_style
            pc.fighting_style = swap
            g.log.player("feat", f"{pc.name} replaces {old.title()} with {swap.title()}", page=47)
    # Wizard: two new spellbook spells per level (p.78); Scholar at 2
    if pc.cls == "wizard":
        max_lvl = max(pc.slots_max())
        options = [s for s in CLASS_LISTS["wizard"] if 1 <= SPELLS[s]["level"] <= max_lvl and s not in pc.spellbook]
        options += [s for l in range(1, max_lvl + 1) for s in OTHER_WIZARD_SPELLS[l] if s not in pc.spellbook]
        picks = g.decide(pc, "spellbook_add", options, default=options[:2],
                         prompt=f"{pc.name}: add two Wizard spells to the spellbook") if g else options[:2]
        for p in picks[:2]:
            lv = spell_level(p)
            if lv is None or lv > max_lvl or lv < 1:
                raise Refusal(f"{p.title()} isn't a Wizard spell of a level {pc.name} has slots for")
        add_to_spellbook(pc, picks[:2], "level advancement")
        if lvl == 2:
            opts = [s for s in SCHOLAR_SKILLS if s in pc.skills]
            if opts:
                sk = g.decide(pc, "scholar", opts, default=opts[0],
                              prompt=f"{pc.name}: choose a skill for Scholar (Expertise) {opts}") if g else opts[0]
                if sk not in opts:
                    raise Refusal(f"Scholar must be one of {opts} that you are proficient in")
                pc.scholar_skill = sk
                pc.skills[sk] = 2
                if g:
                    g.log.player("features", f"{pc.name} gains Expertise in {sk.title()} (Scholar)", page=78)
    # Species: Elf lineage spell at character level 3 (p.84)
    if pc.lineage and lvl >= 3:
        lin = SPECIES["elf"]["lineages"][pc.lineage]
        sp = lin["spells"].get(3)
        if sp and sp in SPELLS and sp not in pc.always_prepared:
            ab = pc.notes.get("lineage_ability", "int")
            pc.always_prepared[sp] = (ab, f"{pc.lineage.title()} lineage")
            pc.free_casts[sp] = {"available": True, "ability": ab, "source": f"{pc.lineage.title()} lineage"}
    if "stonecunning" in pc.traits:
        pc.add_resource("stonecunning", pc.pb)
    if g and pc.cdata.get("spellcasting"):
        g.log.player("spells", f"{pc.name} can now prepare {pc.prepared_limit()} spells; slots "
                     + ", ".join(f"level {l}: {m}" for l, m in pc.slots_max().items()), page=pc.cdata["page"])


def add_to_spellbook(pc, spells, how=""):
    for s in spells:
        if s not in pc.spellbook:
            pc.spellbook.append(s)
    if pc.game and spells:
        oos = [s for s in spells if s not in SPELLS]
        pc.game.log.player("spellbook", f"{pc.name} adds {', '.join(s.title() for s in spells)} to the spellbook"
                           + (f" ({how})" if how else "")
                           + (f"; note: {', '.join(s.title() for s in oos)} can't be cast in this game "
                              f"(out of scope)" if oos else ""), page=78)


def choose_subclass(pc, name: str):
    name = name.lower()
    want = SUBCLASS_NAMES[pc.cls]
    if name != want:
        from .rules import OutOfScope
        raise OutOfScope(f"Only the {want.title()} subclass is in scope for {pc.cls.title()}s")
    pc.subclass = name
    grant_features(pc, 3)
    g = pc.game
    if name == "champion":
        pass
    elif name == "thief":
        pc.speeds["climb"] = pc.speeds["walk"]           # Second-Story Work: Climber
    elif name == "life domain":
        for s in LIFE_DOMAIN_SPELLS[3]:
            pc.always_prepared[s] = ("wis", "Life Domain")
            if s in pc.prepared:
                pc.prepared.remove(s)                   # domain spells don't count against the limit
    elif name == "evoker":
        opts = [s for s in CLASS_LISTS["wizard"] if SPELLS[s]["school"] == "evocation"
                and 1 <= SPELLS[s]["level"] <= 2 and s not in pc.spellbook]
        opts += [s for s in OTHER_EVOCATION if s not in pc.spellbook]
        picks = g.decide(pc, "evocation_savant", opts, default=opts[:2],
                         prompt=f"{pc.name}: Evocation Savant — choose two Evocation spells (level 2 or lower)") \
            if g else opts[:2]
        for p in picks[:2]:
            if (p in SPELLS and (SPELLS[p]["school"] != "evocation" or SPELLS[p]["level"] > 2)) or \
                    (p not in SPELLS and p not in OTHER_EVOCATION):
                raise Refusal("Evocation Savant spells must be Evocation spells of level 2 or lower")
        add_to_spellbook(pc, picks[:2], "Evocation Savant")
    if g:
        g.log.player("subclass", f"{pc.name} becomes a {name.title()}", page=pc.cdata["page"])
