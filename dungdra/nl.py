"""Natural-language interface: turns what the player says into structured
commands (api.Session.execute). Rule-based, so it works offline; an optional
LLM front end (llm.py) can produce the same commands from freer prose.

The parser never decides numbers: it only picks the command and its targets.
"""
from __future__ import annotations

import re

from .data.classes import CLASSES
from .data.equipment import ARMOR, GAMING_SETS, PACKS, TOOLS, WEAPONS, canonical
from .data.origins import ALIGNMENTS, BACKGROUNDS, FIGHTING_STYLES, SPECIES, STANDARD_LANGUAGES
from .data.spells import SPELLS
from .rules import ABILITIES, SKILLS, norm

ABILITY_WORDS = {"str": "str", "strength": "str", "dex": "dex", "dexterity": "dex", "con": "con",
                 "constitution": "con", "int": "int", "intelligence": "int", "wis": "wis", "wisdom": "wis",
                 "cha": "cha", "charisma": "cha"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "twenty": 20, "thirty": 30}


def _num(s):
    s = s.lower()
    return NUMBER_WORDS.get(s) or int(s)


# ---------------------------------------------------------------------------
# character creation
# ---------------------------------------------------------------------------
def parse_creation(text: str, builder=None) -> dict:
    """Extract character-creation choices from free text."""
    t = " " + norm(text).replace(",", " , ").replace(".", " . ") + " "
    out: dict = {}
    have = builder.c if builder is not None else {}
    langctx = bool(re.search(r"\b(speaks?|languages?|tongues?)\b", t))
    cls = next((c for c in CLASSES if re.search(rf"\b{c}\b", t)), None)
    if cls:
        out["cls"] = cls
    for sp in ("high elf", "wood elf", "drow"):
        if sp in t:
            out["species"] = "elf"
            out["lineage"] = sp
    if "species" not in out and not langctx and ("species" not in have or re.search(r"\b(species|race)\b", t)):
        for sp in SPECIES:
            if re.search(rf"\b{sp}(s|ves)?\b", t) or (sp == "elf" and re.search(r"\belven\b", t)):
                out["species"] = sp
    for bg in BACKGROUNDS:
        if re.search(rf"\b(ex-?\s?)?{bg}\b", t) and ("background" not in have or "background" in t):
            out["background"] = bg
    if cls and "cls" in have and cls != have["cls"] and not re.search(r"\bclass\b", t):
        del out["cls"]
    if "standard array" in t or "standard" in t and "array" in t:
        out["ability_method"] = "standard"
    elif "point buy" in t or "point cost" in t:
        out["ability_method"] = "point"
    elif re.search(r"\broll(ed)? (for )?(the )?(scores|stats|abilities)\b", t) or "random generation" in t:
        out["ability_method"] = "random"
    scores = {}
    for m in re.finditer(r"\b(str|dex|con|int|wis|cha|strength|dexterity|constitution|intelligence|wisdom|charisma)"
                         r"\s*(?:of\s*|=\s*|:\s*)?(\d{1,2})\b", t):
        scores[ABILITY_WORDS[m.group(1)]] = int(m.group(2))
    if len(scores) == 6:
        out["scores"] = scores
    bonus = {}
    for m in re.finditer(r"\+\s*([12])\s*(?:in|to|on)?\s*(str|dex|con|int|wis|cha|strength|dexterity|constitution|"
                         r"intelligence|wisdom|charisma)\b", t):
        bonus[ABILITY_WORDS[m.group(2)]] = int(m.group(1))
    if bonus:
        out["background_bonus"] = bonus
    elif re.search(r"\+1 (to|in) (all|each) (three|of them)", t) and out.get("background"):
        out["background_bonus"] = {a: 1 for a in BACKGROUNDS[out["background"]]["abilities"]}
    for fs in FIGHTING_STYLES:
        if re.search(rf"\b{fs}\b(\s+(fighting\s+)?style)?", t) and ("style" in t or fs in ("great weapon fighting",
                                                                                          "two-weapon fighting")):
            out["fighting_style"] = fs
    for al in sorted(ALIGNMENTS, key=len, reverse=True):
        if re.search(rf"\b{al}\b", t) and "alignment" not in out:
            if al == "neutral" and re.search(r"\bneutral (good|evil)\b|\b(lawful|chaotic) neutral\b", t):
                continue
            out["alignment"] = al
    m = re.search(r"\b(?:named|name is|call (?:him|her|them|me)|called)\s+([a-z][a-z'-]+)", t)
    if m:
        out["name"] = m.group(1).upper() if len(m.group(1)) <= 8 else m.group(1).title()
    langs = [l for l in STANDARD_LANGUAGES if re.search(rf"\b{l}\b", t)]
    if len(langs) >= 2 and ("speak" in t or "language" in t):
        out["languages"] = langs[:2]
        if len(langs) >= 3 and (builder and builder.c.get("cls") == "rogue" or out.get("cls") == "rogue"):
            out["rogue_language"] = langs[2]
    # skills
    sk_m = re.search(r"\bskills?\s*(?::|are|in)?\s*([a-z ,]+?)(?:\.|;|$| and mastery| mastery)", t)
    if sk_m:
        found = [s for s in SKILLS if re.search(rf"\b{s}\b", sk_m.group(1))]
        if found:
            out["class_skills"] = found
    ex = re.search(r"\bexpertise\s*(?:in|:)?\s*([a-z ,]+?)(?:\.|;|$)", t)
    if ex:
        out["expertise"] = [s for s in SKILLS if re.search(rf"\b{s}\b", ex.group(1))]
    ma = re.search(r"\bmaster(?:y|ies)\s*(?:with|:|in|of)?\s*([a-z ,']+?)(?:\.|;|$)", t)
    if ma:
        out["masteries"] = [w for w in WEAPONS if re.search(rf"\b{w}s?\b", ma.group(1))]
    for gs in GAMING_SETS:
        base = gs.replace(" set", "")
        if re.search(rf"\b{base}\b", t) and ("gaming" in t or "set" in t or base == "dice"):
            out["gaming_set"] = gs
    ks = re.search(r"\bkeen senses\s*(?::|in|with)?\s*(insight|perception|survival)\b", t)
    if ks:
        out["keen_senses"] = ks.group(1)
    sf = re.search(r"\bskillful\s*(?::|in|with)?\s*([a-z ]+?)(?:\.|,|;|$)", t)
    if sf:
        s = next((s for s in SKILLS if s in sf.group(1)), None)
        if s:
            out["skillful"] = s
    for order in ("protector", "thaumaturge"):
        if order in t:
            out["divine_order"] = order
    if re.search(r"\bsmall\b", t):
        out["size"] = "small"
    elif re.search(r"\bmedium\b", t):
        out["size"] = "medium"
    ct = re.search(r"\bcantrips?\s*(?::|are)?\s*([a-z ,']+?)(?:\.|;|$)", t)
    if ct:
        out["cantrips"] = [s for s in SPELLS if SPELLS[s]["level"] == 0 and s in ct.group(1)]
    pr = re.search(r"\bprepare[sd]?\s*(?::)?\s*([a-z ,']+?)(?:\.|;|$)", t)
    if pr:
        out["prepared"] = [s for s in SPELLS if SPELLS[s]["level"] > 0 and s in pr.group(1)]
    sb = re.search(r"\bspellbook\s*(?::|has|with)?\s*([a-z ,']+?)(?:\.|;|$)", t)
    if sb:
        out["spellbook"] = [s for s in SPELLS if SPELLS[s]["level"] == 1 and s in sb.group(1)]
    op = re.search(r"(?<!background )\b(?:class )?(?:equipment )?(?:package|option)\s+([abc])\b", t)
    if op:
        out["class_equipment"] = op.group(1).upper()
    bo = re.search(r"\bbackground (?:equipment|package|option)\s+([ab])\b", t)
    if bo:
        out["bg_equipment"] = bo.group(1).upper()
    # Magic Initiate / Skilled feat choices
    mi = re.search(r"\bmagic initiate\b(.*)", t)
    if mi:
        body = mi.group(1)
        lst = next((l for l in ("cleric", "wizard", "druid") if l in body), None)
        ab = next((ABILITY_WORDS[w] for w in ("intelligence", "wisdom", "charisma") if w in body), None)
        cants = [s_ for s_ in SPELLS if SPELLS[s_]["level"] == 0 and s_ in body]
        lvl1 = [s_ for s_ in SPELLS if SPELLS[s_]["level"] == 1 and s_ in body]
        spec = {"name": "magic initiate", "list": lst, "ability": ab, "cantrips": cants, "spell": lvl1[0] if lvl1 else ""}
        key = "versatile" if "versatile" in t else "bg_feat"
        out[key] = spec
    sk2 = re.search(r"\bskilled\b(?:\s+(?:in|with|:))?\s*([a-z ,']+)", t)
    if sk2 and "magic initiate" not in t:
        body = sk2.group(1)
        ch = [s_ for s_ in SKILLS if re.search(rf"\b{s_}\b", body)]
        ch += [x for x in TOOLS if x in body or x.replace("'", "") in body]
        out["versatile" if ("versatile" in t or (builder and builder.c.get("species") == "human")) else "bg_feat"] = \
            {"name": "skilled", "choices": ch}
    la = re.search(r"\blineage\b.*\b(intelligence|wisdom|charisma)\b", t)
    if la:
        out["lineage_ability"] = ABILITY_WORDS[la.group(1)]
    if re.search(r"\b(instead|replac|different tool|learns?)\b", t):
        tools = [x for x in TOOLS if (x in t or x.replace("'", "") in t) and x != "thieves' tools"]
        if tools:
            out["replacement_tool"] = tools[0]
    if "species" not in out and ("versatile" in out or "bg_feat" in out):
        pass
    # gear wishes: armor, shields, weapons mentioned
    gear = []
    spell_context = re.search(r"\b(spellbook|prepare|cantrips?|magic initiate|spells?)\b", t)
    for name in list(ARMOR) + ["shield"] + list(WEAPONS) + list(PACKS):
        short = name.replace(" armor", "") if name.endswith(" armor") and name not in ("leather armor",) else name
        m = re.search(rf"\b(\d+|one|two|three|four|five|six|eight|ten)?\s*{re.escape(short)}s?\b", t)
        if m and not (name == "glaive" and "mastery" in t and not re.search(r"\bbuy\b", t)):
            q = _num(m.group(1)) if m.group(1) else 1
            gear.append((name, q))
    if gear and not spell_context and ("mastery" not in t or re.search(r"\b(buy|gear|equipment|carry|wield|wear)\b", t)):
        out["_gear"] = gear
    return out


def apply_creation(session, text) -> dict:
    """Update the builder from text; resolve gear wishes into packages or gold + purchases."""
    from .creation import CharacterBuilder
    b = session.builder or CharacterBuilder(session.game)
    session.builder = b
    fields = parse_creation(text, b)
    gear = fields.pop("_gear", None)
    errors = []
    order = ["name", "cls", "species", "lineage", "size", "background", "ability_method", "scores",
             "background_bonus"]
    for k in order + [k for k in fields if k not in order]:
        if k in fields:
            try:
                b.set(k, fields[k])
            except Exception as e:  # noqa: BLE001  report every problem to the player
                errors.append(getattr(e, "reason", str(e)))
    notes = []
    if gear and b.c.get("cls"):
        notes += _resolve_gear(b, gear, errors)
    return {"set": {k: v for k, v in fields.items()}, "errors": errors, "notes": notes,
            "missing": b.missing()}


def _resolve_gear(b, gear, errors):
    from .data.classes import CLASSES as CL
    cls = b.c["cls"]
    eq = CL[cls]["equipment"]
    wanted = {n for n, _ in gear}
    for opt in ("A", "B"):
        pkg = eq.get(opt)
        if isinstance(pkg, list) and wanted <= {n for n, _ in pkg}:
            b.set("class_equipment", opt)
            return [f"Your {cls.title()} starting package {opt} includes that gear."]
    if "C_gp" in eq or ("B_gp" in eq and not isinstance(eq.get("B"), list)):
        opt = "C" if "C_gp" in eq else "B"
        b.set("class_equipment", opt)
        prior = list(b.c.get("purchases", []))
        want = prior + [(n, q) for n, q in gear if n not in {p for p, _ in prior}]
        try:
            b.set("purchases", want)
        except Exception as e:  # noqa: BLE001
            errors.append(getattr(e, "reason", str(e)))
            return []
        from .items import fmt_cp
        return [f"No {cls.title()} package matches, so you take option {opt} "
                f"({eq[opt + '_gp']} GP) and buy at list price: "
                + ", ".join(f"{q} {n}" for n, q in want) + f" for {fmt_cp(b.c['purchase_total'])}"
                f" ({fmt_cp(b.starting_gold_cp() - b.c['purchase_total'])} left)."]
    errors.append(f"No {cls.title()} package includes that gear")
    return []


# ---------------------------------------------------------------------------
# gameplay
# ---------------------------------------------------------------------------
VERB_ATTACK = r"\b(attacks?|hits?|strikes?|stabs?|slashes?|swings?|shoots?|fires?|throws?|punch(es)?|smashes?)\b"


def find_actor(session, t: str, default=True):
    g = session.game
    hits = []
    for c in g.pcs():
        m = re.search(rf"\b{re.escape(norm(c.name))}\b", t)
        if m:
            hits.append((m.start(), c))
    if hits:
        return min(hits, key=lambda h: h[0])[1]
    if not default:
        return None
    try:
        return session._c(None)
    except Exception:  # noqa: BLE001
        return None


def find_creatures(session, t: str, exclude=None, enemies_first=True):
    g = session.game
    found = []
    cands = sorted(g.creatures.values(), key=lambda c: -len(c.name))
    taken = t
    for c in cands:
        if c is exclude or c.dead:
            continue
        n = norm(c.name)
        if re.search(rf"\b{re.escape(n)}\b", taken):
            found.append(c)
            taken = taken.replace(n, " ")
    if not found:
        # generic words: "the goblin", "the ogre" -> first living enemy whose name contains it
        for c in cands:
            if c is exclude or c.dead or c.team != "enemy":
                continue
            key = getattr(c, "key", "")
            words = set(norm(c.name).split()) | set(key.split())
            for w in words:
                if len(w) > 3 and re.search(rf"\b{re.escape(w)}s?\b", t):
                    found.append(c)
                    break
            if found:
                break
    return found


def find_weapon(actor, t):
    if not hasattr(actor, "inventory"):
        return None
    for it in sorted(actor.inventory, key=lambda i: -i.magic_bonus):
        if it.kind == "weapon" and re.search(rf"\b{re.escape(it.base)}s?\b", t):
            return it.display if it.props.get("title") else it.base
    return None


def find_spell(t):
    for s in sorted(SPELLS, key=len, reverse=True):
        if s in t:
            return s
    return None


def parse(session, text: str) -> list[dict] | dict:
    """Return a list of commands, or {'say': ...} for things that need no engine call."""
    t = norm(text).rstrip(" .!?")
    g = session.game
    if re.search(r"\b(new character|create a character|make a character)\b", t):
        from .creation import CharacterBuilder
        session.builder = CharacterBuilder(g)
    if session.builder is not None:
        if re.search(r"\b(done|finish|finalize|that's all|that is all)\b", t) and session.builder is not None:
            return [{"cmd": "finish_character"}]
        return {"create": text}
    actor = find_actor(session, t)
    aid = actor.id if actor else None
    if re.fullmatch(r"(end( my)? turn|done|pass|next|end)", t) or re.search(r"\bends? (his|her|their|my) turn\b", t):
        return [{"cmd": "end_turn"}]
    if not re.search(r"\bcasts?\b", t):
        sec = None
        if re.search(r"\b(inventory|inventories|equipment|gear|belongings|what (do|does) \w+ (carry|have)|items)\b", t):
            sec = "all"
        if re.search(r"\b(spells?|spell list|spell slots|slots|cantrips)\b", t) and len(t.split()) <= 5:
            sec = "spells"
        if re.search(r"\bpotions?\b", t) and len(t.split()) <= 5 and not re.search(r"\b(drinks?|gives?|administers?)\b", t):
            sec = "potions"
        if re.search(r"^(show |list )?(\w+'?s? )?weapons\b|\bweapons$", t):
            sec = "weapons"
        if sec:
            who = find_actor(session, t, default=False)
            return [{"cmd": "inventory", "actor": who.id if who else None,
                     "section": None if sec == "all" else sec}]
    if re.search(r"\b(status|how are we|hp\b)", t):
        return [{"cmd": "status"}]
    if re.search(r"\b(sheet|character sheet)\b", t):
        return [{"cmd": "sheet", "actor": aid}]
    if re.fullmatch(r"(look|look around|where are we|describe)", t):
        return [{"cmd": "look"}]
    m = re.search(r"\b(?:go|goes|head|heads|travel|travels|walk|walks|set off|proceed|return)\s+(?:back\s+)?(?:on\s+)?(?:to|towards?|for|into)\s+(?:the\s+)?(.+)$", t)
    if m and g.combat is None and session.adventure is not None:
        return [{"cmd": "go", "where": m.group(1)}]
    if (m or re.search(r"\b(continue|go on|press on|move on|onward|leave|travel)\b", t)) and g.combat is not None:
        return {"say": _combat_help(session, "You can't travel on while a fight is going on. Defeat, drive off "
                                             "or escape the enemies first.")}
    if re.search(r"\b(continue|go on|press on|move on|onward|next scene|go (north|east|west|south|inside|in|deeper))\b",
                 t) and g.combat is None:
        return [{"cmd": "go"}]
    if re.search(r"\bresume\b.*\brest\b|\bback to (sleep|rest)\b", t):
        return [{"cmd": "resume_rest"}]
    if re.search(r"\bshort rest\b", t):
        return [{"cmd": "short_rest"}]
    if re.search(r"\blong rest\b|\bsleep for the night\b|\bmake camp\b", t):
        return [{"cmd": "long_rest"}]
    m = re.search(r"\btravel(?:s)?\s+(\d+(?:\.\d+)?)\s*miles?", t)
    if m:
        pace = next((p for p in ("fast", "normal", "slow") if p in t), "normal")
        terrain = next((x for x in ("forest", "grassland", "hill", "mountain", "swamp", "urban", "desert", "coastal",
                                    "arctic", "underdark") if x in t), "forest")
        return [{"cmd": "travel", "miles": float(m.group(1)), "pace": pace, "terrain": terrain,
                 "road": bool(re.search(r"\broad\b", t))}]
    if re.search(r"\bsecond wind\b", t):
        return [{"cmd": "second_wind", "actor": aid}]
    if re.search(r"\baction surge\b", t):
        return [{"cmd": "action_surge", "actor": aid}]
    if re.search(r"\bsteady aim\b", t):
        cmds = [{"cmd": "steady_aim", "actor": aid}]
        rest = re.sub(r".*steady aim( and| then)?", "", t)
        if re.search(VERB_ATTACK, rest):
            cmds += parse(session, f"{actor.name} {rest}") if actor else []
        return cmds
    if re.search(r"\bcunning action\b", t):
        what = next((w for w in ("dash", "disengage", "hide") if w in t), "dash")
        return [{"cmd": "cunning_action", "what": what, "actor": aid}]
    if re.search(r"\bdisengages?\b", t):
        return [{"cmd": "disengage", "actor": aid, "bonus": "bonus" in t}]
    if re.search(r"\bdash(es)?\b", t):
        return [{"cmd": "dash", "actor": aid, "bonus": "bonus" in t}]
    if re.search(r"\bdodges?\b", t):
        return [{"cmd": "dodge", "actor": aid}]
    if re.search(r"\blights? a torch\b", t):
        return [{"cmd": "light_torch", "actor": aid}]
    if re.search(r"\b(drinks?|quaffs?)\b.*\bpotion\b", t):
        return [{"cmd": "drink", "actor": aid}]
    m = re.search(r"\b(gives?|administers?|feeds?)\b.*\bpotion\b", t)
    if m:
        tg = find_creatures(session, t, exclude=actor)
        return [{"cmd": "drink", "actor": aid, "target": tg[0].id if tg else None}]
    if re.search(r"\b(healer'?s kit)\b", t):
        tg = find_creatures(session, t, exclude=actor)
        return [{"cmd": "stabilize", "actor": aid, "target": tg[0].id, "kit": True}]
    if re.search(r"\bstabili[sz]es?\b|\bfirst aid\b", t):
        tg = find_creatures(session, t, exclude=actor)
        return [{"cmd": "stabilize", "actor": aid, "target": tg[0].id}]
    if re.search(r"\bhides?\b", t):
        cover = "total" if "total cover" in t else "three-quarters"
        return [{"cmd": "hide", "actor": aid, "cover": cover}]
    if re.search(r"\bgrapples?\b", t):
        tg = find_creatures(session, t, exclude=actor)
        return [{"cmd": "grapple", "actor": aid, "target": tg[0].id}]
    if re.search(r"\bshoves?\b", t):
        tg = find_creatures(session, t, exclude=actor)
        return [{"cmd": "shove", "actor": aid, "target": tg[0].id, "effect": "push" if "push" in t or "away" in t else "prone"}]
    if re.search(r"\b(stands? up|gets? up)\b", t):
        return [{"cmd": "stand", "actor": aid}]
    if re.search(r"\bturn undead\b", t):
        return [{"cmd": "turn_undead", "actor": aid}]
    if re.search(r"\bdivine spark\b", t):
        tg = find_creatures(session, t, exclude=actor)
        mode = "harm" if re.search(r"\b(harm|damage|smite|blast)\b", t) else "heal"
        return [{"cmd": "divine_spark", "actor": aid, "target": tg[0].id, "mode": mode}]
    if re.search(r"\b(pick|picks|open|opens) the lock\b|\blockpick", t):
        return [{"cmd": "use_tool", "actor": aid, "task": "pick a lock"}]
    if re.search(r"\bdisarms?\b", t):
        trap = _find_trap(session, t)
        return [{"cmd": "trap", "action": "disarm", "trap": trap, "actor": aid}]
    if re.search(r"\b(wedges?|jams?)\b|\bspikes? (into|under|in)\b", t) and not re.search(r"\b(buys?|sells?)\b", t):
        trap = _find_trap(session, t)
        return [{"cmd": "trap", "action": "spike", "trap": trap, "actor": aid}]
    if re.search(r"\b(examin|inspect|stud|check|search|look)\w*\b", t) and \
            re.search(r"\b(traps?|lock|chest|floor|flagstones|walls?|needle|pit)\b", t):
        trap = _find_trap(session, t)
        if trap:
            return [{"cmd": "trap", "action": "detect", "trap": trap, "actor": aid}]
    spell = find_spell(t)
    if spell and re.search(r"\bcasts?\b|\buses?\b", t):
        rest = re.sub(rf"\b{re.escape(spell)}\b", " ", t)
        if actor is not None:
            rest = re.sub(rf"\b{re.escape(norm(actor.name))}\b", " ", rest, count=1)
        tg = find_creatures(session, rest, exclude=None)
        if not tg and actor is not None and re.search(r"\b(himself|herself|themself|themselves|myself|self)\b", t):
            tg = [actor]
        cmd = {"cmd": "cast", "spell": spell, "actor": aid, "targets": [c.id for c in tg] or None}
        m = re.search(r"\blevel (\d) (spell )?slot\b|\bat level (\d)\b", t)
        if m:
            cmd["slot"] = int(m.group(1) or m.group(3))
        if "ritual" in t:
            cmd["ritual"] = True
        if re.search(r"\b(free|magic initiate|without a slot)\b", t):
            cmd["free"] = True
        if "scroll" in t:
            cmd["item"] = "spell scroll"
        if "wand" in t:
            cmd["item"] = "wand of magic missiles"
            m = re.search(r"\b(\d|one|two|three|four) charges?\b", t)
            cmd["charges"] = _num(m.group(1)) if m else 1
        for w in ("approach", "drop", "flee", "grovel", "halt"):
            if re.search(rf"\b{w}\b", t):
                cmd["option"] = w
        return [cmd]
    if re.search(r"\bhelps?\b", t):
        tg = find_creatures(session, t, exclude=actor)
        if tg and tg[0].team == "enemy":
            return [{"cmd": "help", "actor": aid, "enemy": tg[0].id}]
        skill = next((s for s in SKILLS if s in t), None)
        tool = next((x for x in TOOLS if x in t), None)
        return [{"cmd": "help", "actor": aid, "ally": tg[0].id if tg else None, "skill": skill, "tool": tool}]
    if re.search(r"\b(search(es)?|reads?|looks? for|listens?|insight)\b", t):
        skill = next((s for s in ("insight", "medicine", "survival", "perception") if s in t), None)
        if skill is None:
            skill = "insight" if re.search(r"\b(body language|lying|motives?|reads?)\b", t) else "perception"
        tg = find_creatures(session, t, exclude=actor)
        return [{"cmd": "search", "actor": aid, "skill": skill, "target": tg[0].id if tg else None, "what": text}]
    if re.search(r"\b(recalls?|remembers?|study|studies|lore)\b", t):
        ctype = None
        tg = find_creatures(session, t, exclude=actor)
        if tg:
            ctype = tg[0].ctype
        else:
            for w, ct in (("goblin", "fey"), ("ogre", "giant"), ("wolf", "beast"), ("skeleton", "undead"),
                          ("zombie", "undead"), ("kobold", "dragon"), ("bandit", "humanoid"), ("rat", "beast")):
                if w in t:
                    ctype = ct
        skill = next((s for s in ("arcana", "history", "investigation", "nature", "religion") if s in t), None)
        return [{"cmd": "study", "actor": aid, "skill": skill if not ctype else None, "creature_type": ctype,
                 "topic": text}]
    if re.search(r"\b(persuades?|asks?|convinces?|intimidates?|threatens?|deceives?|lies to|urges?)\b", t):
        tg = find_creatures(session, t, exclude=actor)
        approach = "intimidate" if re.search(r"intimidat|threat", t) else "deceive" if re.search(r"deceiv|lie", t) \
            else "persuade"
        return [{"cmd": "influence", "actor": aid, "npc": tg[0].id if tg else None, "request": text,
                 "disposition": "hesitant", "approach": approach}]
    m = re.search(r"\bmoves?\s+(\d+)\s*(?:ft|feet)?\s*(toward|towards|to|away from)?\s*", t)
    if m or re.search(r"\b(approach(es)?|charges?|closes? in on|runs? (to|toward))\b", t):
        tg = find_creatures(session, t, exclude=actor)
        cmd = {"cmd": "move", "actor": aid}
        if m:
            cmd["feet"] = int(m.group(1))
        if tg:
            key = "away_from" if m and m.group(2) == "away from" else "toward"
            cmd[key] = tg[0].id
        if "climb" in t:
            cmd["mode"] = "climb"
        cmds = [cmd]
        if re.search(VERB_ATTACK, t):
            att = _attack_cmd(session, actor, t)
            if att:
                cmds.append(att)
        return cmds
    if re.search(VERB_ATTACK, t) or re.search(r"\battack", t):
        att = _attack_cmd(session, actor, t)
        if att:
            return [att]
    if re.search(r"\b(open|opens) the chest\b|\b(take|takes|grab|grabs|collect) the (treasure|loot)\b|\bloot\b", t):
        return [{"cmd": "loot"}]
    m = re.search(r"\b(modest|comfortable|wealthy|aristocratic|poor|squalid|wretched)\b.*?(\d+)\s*days?", t)
    if m and re.search(r"\b(live|lives|lifestyle|stay)\b", t):
        return [{"cmd": "lifestyle", "level": m.group(1), "days": int(m.group(2))}]
    m = re.search(r"\bcrafts?\s+(?:a|an|the)?\s*([a-z' ]+?)(?:\s+with.*)?$", t)
    if m:
        return [{"cmd": "craft", "actor": aid, "item": canonical(m.group(1).strip())}]
    m = re.search(r"\b(attunes?|identif(?:y|ies))\b.*?\b(?:the |a )?(cloak of protection|wand of magic missiles|bag of holding|[a-z +1]+)$", t)
    if m:
        item = re.sub(r"^(to |with )?(the |a |an |his |her |their )?", "", m.group(2).strip())
        return [{"cmd": "attune" if m.group(1).startswith("attun") else "identify", "actor": aid, "item": item}]
    if re.search(r"\bcop(y|ies)\b.*\bscroll\b", t):
        return [{"cmd": "copy_scroll", "actor": aid}]
    m = re.search(r"\bprepares?\s+(.*)", t)
    if m:
        spells = [sp for sp in SPELLS if SPELLS[sp]["level"] > 0 and sp in m.group(1)]
        return [{"cmd": "prepare", "actor": aid, "spells": spells}]
    m = re.search(r"\bwait(?:s)?\s+(?:for\s+)?(\d+)\s*hours?", t)
    if m:
        return [{"cmd": "wait", "hours": int(m.group(1))}]
    if re.search(r"\b(end of (the )?day|we eat|eat (our )?rations|make camp and eat)\b", t):
        return [{"cmd": "end_day"}]
    m = re.search(r"\bloses?\s+(?:a|an|one|(\d+))?\s*(ration|rations|torch|arrows?)\b", t)
    if m:
        return [{"cmd": "lose_item", "actor": aid, "item": canonical(m.group(2)), "qty": int(m.group(1) or 1)}]
    if re.search(r"\bbuys?\b", t):
        m = re.search(r"\bbuys?\s+(\d+|a|an|one|two|three|four|five|ten)?\s*([a-z' ]+)", t)
        qty = 1 if not m.group(1) or m.group(1) in ("a", "an") else _num(m.group(1))
        return [{"cmd": "buy", "actor": aid, "item": canonical(m.group(2).strip()), "qty": qty}]
    if re.search(r"\bsells?\b", t):
        m = re.search(r"\bsells?\s+(?:the |a |an |his |her |their )?([a-z' +1]+)", t)
        return [{"cmd": "sell", "actor": aid, "item": m.group(1).strip()}]
    if g.combat is not None:
        return {"say": _combat_help(session, "I didn't catch that.")}
    return {"say": "I didn't catch that. Try e.g. 'continue', 'go to the watchtower', 'inventory', 'BROM inventory', "
                   "'MIALEE spells', 'short rest', 'status', or 'help' for more."}


def _combat_help(session, lead: str) -> str:
    """A combat-aware hint: whose turn it is, what they can do, and which enemies are about."""
    g = session.game
    cb = g.combat
    cur = cb.current
    foes = [e for e in g.creatures.values() if e.team == "enemy" and not e.dead and not e.notes.get("fled")]
    seen = [e for e in foes if cur is not None and g.can_see(cur, e)]
    hidden = [e for e in foes if e not in seen]
    lines = [lead]
    if cur is not None and cur.team == "party" and cur.is_pc():
        from .turnhelp import turn_summary
        hint, _ = turn_summary(g, cur)
        lines.append(f"It's {cur.name}'s turn ({hint}).")
        n = cur.name
        ex = seen[0].name if seen else (foes[0].name if foes else "the goblin")
        lines.append(f"Try: '{n} attacks {ex}', '{n} casts <spell> at {ex}', '{n} moves 30 feet toward {ex}', "
                     f"'{n} searches for hidden enemies', '{n} dodges', 'end turn'.")
    if seen:
        lines.append("Enemies you can see: " + ", ".join(f"{e.name} ({cur.distance_to(e)} ft)" if cur else e.name
                                                      for e in seen))
    if hidden:
        lines.append(f"{len(hidden)} more hidden enemy(ies) somewhere nearby.")
    lines.append("Type 'status' for the initiative order, or 'help' for more examples.")
    return "\n".join(lines)


def _attack_cmd(session, actor, t):
    if actor is None:
        return None
    tg = find_creatures(session, t, exclude=actor)
    tg = [c for c in tg if c.team != actor.team] or tg
    if not tg:
        return None
    w = find_weapon(actor, t)
    cmd = {"cmd": "attack", "actor": actor.id, "target": tg[0].id}
    if w:
        cmd["weapon"] = w
    if re.search(r"\bthrows?\b", t):
        cmd["thrown"] = True
    if re.search(r"\b(two hands|two-handed|both hands)\b", t):
        cmd["two_handed"] = True
    if re.search(r"\b(off-hand|offhand|bonus action|extra attack|second weapon|nick)\b", t):
        cmd["light_extra"] = True
    if re.search(r"\b(punch(es)?|unarmed|kicks?|headbutts?)\b", t):
        cmd["unarmed"] = True
    return cmd


def _find_trap(session, t):
    from .traps import Trap
    for name, obj in session.game.scene.objects.items():
        tr = obj.get("trap")
        if tr is not None and not tr.disabled and (tr.name in t or tr.kind in t or
                                                   ("lock" in t and tr.kind == "poisoned needle") or
                                                   ("chest" in t and tr.kind == "poisoned needle") or
                                                   ("floor" in t and "pit" in tr.kind)):
            return name
    for name, obj in session.game.scene.objects.items():
        if obj.get("trap") is not None and not obj["trap"].disabled:
            return name
    return None
