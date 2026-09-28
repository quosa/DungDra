"""Character creation (SRD p.19-23): a validating, step-by-step builder.

Every required choice must be made before the sheet can be finalized; the
builder reports which ones are still missing so the game can ask for them.
"""
from __future__ import annotations

from .character import Character
from .data.classes import CLASSES, OUT_OF_SCOPE_CLASSES
from .data.equipment import (AMMO_BUNDLE, ARMOR, GAMING_SETS, GEAR, PACKS, TOOLS, WEAPONS, canonical,
                             item_cost)
from .data.origins import (BACKGROUNDS, FIGHTING_STYLES, ORIGIN_FEATS, OUT_OF_SCOPE_SPECIES, POINT_COST,
                           RARE_LANGUAGES, SPECIES, STANDARD_ARRAY, STANDARD_LANGUAGES, ALIGNMENTS)
from .data.spells import CLASS_LISTS, SPELLS
from .features import grant_features
from .items import fmt_cp
from .rules import ABILITIES, SKILLS, OutOfScope, Refusal, norm

MAGIC_INITIATE_LISTS = ("cleric", "wizard", "druid")


class CharacterBuilder:
    def __init__(self, game=None):
        self.game = game
        self.c: dict = {}
        self.log: list[str] = []

    # ------------------------------------------------------------------
    def set(self, key: str, value):
        fn = getattr(self, f"_set_{key}", None)
        if fn is None:
            raise Refusal(f"Unknown creation step {key!r}")
        fn(value)
        return self

    def update(self, **kw):
        order = ["name", "cls", "species", "lineage", "size", "background", "ability_method", "scores",
                 "background_bonus"]
        for k in order:
            if k in kw:
                self.set(k, kw.pop(k))
        for k, v in kw.items():
            self.set(k, v)
        return self

    # --- basic identity ---
    def _set_name(self, v):
        self.c["name"] = str(v).strip()

    def _set_cls(self, v):
        v = norm(v)
        if v in OUT_OF_SCOPE_CLASSES:
            raise OutOfScope(f"The {v.title()} class is out of scope; choose Fighter, Rogue, Cleric or Wizard.")
        if v not in CLASSES:
            raise Refusal(f"Unknown class {v!r}")
        self.c["cls"] = v

    def _set_species(self, v):
        v = norm(v)
        for lin, sp in (("high elf", "elf"), ("wood elf", "elf"), ("drow", "elf")):
            if v == lin:
                self.c["lineage"] = lin
                v = sp
        if v.endswith("s"):
            v = v[:-1]
        if v in OUT_OF_SCOPE_SPECIES:
            raise OutOfScope(f"{v.title()} is out of scope; choose Human, Dwarf, Elf or Halfling.")
        if v not in SPECIES:
            raise Refusal(f"Unknown species {v!r}")
        self.c["species"] = v

    def _set_lineage(self, v):
        v = norm(v)
        if v in ("high", "wood"):
            v += " elf"
        if v not in SPECIES["elf"]["lineages"]:
            raise Refusal(f"Unknown elven lineage {v!r}")
        self.c["lineage"] = v

    def _set_lineage_ability(self, v):
        v = _ab(v)
        if v not in ("int", "wis", "cha"):
            raise Refusal("The lineage spellcasting ability must be Intelligence, Wisdom or Charisma")
        self.c["lineage_ability"] = v

    def _set_size(self, v):
        v = norm(v)
        sp = self.c.get("species")
        allowed = SPECIES[sp]["size"] if sp else ["small", "medium"]
        if v not in allowed:
            raise Refusal(f"A {sp} can't be {v}")
        self.c["size"] = v

    def _set_background(self, v):
        v = norm(v)
        if v not in BACKGROUNDS:
            raise Refusal(f"Unknown background {v!r}; choose Acolyte, Criminal, Sage or Soldier")
        self.c["background"] = v

    def _set_alignment(self, v):
        v = norm(v)
        if v == "true neutral":
            v = "neutral"
        if v not in ALIGNMENTS:
            raise Refusal(f"Unknown alignment {v!r}")
        self.c["alignment"] = v

    # --- ability scores (p.21) ---
    def _set_ability_method(self, v):
        v = norm(v)
        if v.startswith("standard"):
            v = "standard"
        elif v.startswith("point"):
            v = "point"
        elif v.startswith("random") or v.startswith("roll"):
            v = "random"
        else:
            raise Refusal("Ability method must be Standard Array, Point Cost or Random Generation")
        self.c["ability_method"] = v

    def roll_scores(self, dice) -> list[int]:
        """Random Generation: 4d6 drop the lowest, six times."""
        out = []
        for _ in range(6):
            r = dice.roll_many(4, 6)
            out.append(sum(sorted(r)[1:]))
        self.c["ability_method"] = "random"
        self.c["rolled"] = out
        return out

    def _set_scores(self, v: dict):
        v = {_ab(k): int(s) for k, s in v.items()}
        if set(v) != set(ABILITIES):
            raise Refusal("Assign a score to each of the six abilities")
        method = self.c.get("ability_method", "standard")
        vals = sorted(v.values())
        if method == "standard":
            if vals != sorted(STANDARD_ARRAY):
                raise Refusal(f"The Standard Array is 15, 14, 13, 12, 10, 8 — each used exactly once "
                              f"(got {sorted(v.values(), reverse=True)})")
        elif method == "point":
            if any(s < 8 or s > 15 for s in vals):
                raise Refusal("Point Cost scores must be between 8 and 15")
            cost = sum(POINT_COST[s] for s in vals)
            if cost > 27:
                raise Refusal(f"That build costs {cost} points; the budget is 27")
        elif method == "random":
            rolled = sorted(self.c.get("rolled", []))
            if rolled and vals != rolled:
                raise Refusal(f"Assign the rolled scores {rolled}")
        self.c["scores"] = v

    def _set_background_bonus(self, v: dict):
        v = {_ab(k): int(n) for k, n in v.items() if int(n)}
        bg = self.c.get("background")
        if not bg:
            raise Refusal("Choose a background before adjusting ability scores")
        allowed = BACKGROUNDS[bg]["abilities"]
        bad = [k for k in v if k not in allowed]
        if bad:
            raise Refusal(f"A {bg.title()} may only increase {', '.join(a.title() for a in allowed)}")
        if sorted(v.values()) not in ([1, 2], [1, 1, 1]):
            raise Refusal("Increase one score by 2 and a different one by 1, or all three by 1")
        self.c["background_bonus"] = v

    # --- choices ---
    def _set_languages(self, v):
        langs = [norm(x) for x in v]
        langs = [x for x in langs if x != "common"]
        for x in langs:
            if x in RARE_LANGUAGES:
                raise Refusal(f"{x.title()} is a rare language; it can't be picked without a feature that grants it")
            if x not in STANDARD_LANGUAGES:
                raise Refusal(f"Unknown language {x!r}")
        if len(langs) != 2 or len(set(langs)) != 2:
            raise Refusal("Choose two different standard languages (plus Common)")
        self.c["languages"] = langs

    def _set_rogue_language(self, v):
        x = norm(v)
        if x in RARE_LANGUAGES or x not in STANDARD_LANGUAGES:
            raise Refusal("Choose a standard language")
        self.c["rogue_language"] = x

    def _set_class_skills(self, v):
        cls = self._need("cls")
        cd = CLASSES[cls]
        skills = [norm(x) for x in v]
        for s in skills:
            if s not in cd["skill_choices"]:
                raise Refusal(f"{s.title()} isn't on the {cls.title()} skill list")
        if len(skills) != cd["skill_count"] or len(set(skills)) != len(skills):
            raise Refusal(f"Choose {cd['skill_count']} different skills")
        bg = self.c.get("background")
        if bg:
            dup = set(skills) & set(BACKGROUNDS[bg]["skills"])
            if dup:
                raise Refusal(f"You already have {', '.join(dup)} from your background; choose another skill")
        self.c["class_skills"] = skills

    def _set_keen_senses(self, v):
        v = norm(v)
        if v not in SPECIES["elf"]["keen_senses"]:
            raise Refusal("Keen Senses: choose Insight, Perception or Survival")
        self.c["keen_senses"] = v

    def _set_skillful(self, v):
        v = norm(v)
        if v not in SKILLS:
            raise Refusal(f"Unknown skill {v!r}")
        self.c["skillful"] = v

    def _set_fighting_style(self, v):
        v = norm(v)
        if v not in FIGHTING_STYLES:
            raise Refusal(f"Fighting Style must be one of {', '.join(FIGHTING_STYLES)}")
        self.c["fighting_style"] = v

    def _set_masteries(self, v):
        cls = self._need("cls")
        n = CLASSES[cls].get("mastery_count", 0)
        ws = [canonical(x) for x in v]
        for w in ws:
            if w not in WEAPONS:
                raise Refusal(f"{w!r} isn't a weapon")
            if cls == "rogue":
                wd = WEAPONS[w]
                if wd["category"] == "martial" and not ({"finesse", "light"} & wd["props"]):
                    raise Refusal(f"A Rogue can only master weapons they are proficient with ({w} isn't)")
        if len(ws) != n or len(set(ws)) != n:
            raise Refusal(f"Choose {n} different kinds of weapons for Weapon Mastery")
        self.c["masteries"] = ws

    def _set_expertise(self, v):
        sk = [norm(x) for x in v]
        if len(sk) != 2 or len(set(sk)) != 2:
            raise Refusal("Choose two skill proficiencies for Expertise")
        self.c["expertise"] = sk

    def _set_divine_order(self, v):
        v = norm(v)
        if v not in ("protector", "thaumaturge"):
            raise Refusal("Divine Order: Protector or Thaumaturge")
        self.c["divine_order"] = v

    def _set_cantrips(self, v):
        cls = self._need("cls")
        cs = [norm(x) for x in v]
        for s in cs:
            if s not in SPELLS:
                raise OutOfScope(f"{s.title()} is out of scope")
            if SPELLS[s]["level"] != 0 or s not in CLASS_LISTS[cls]:
                raise Refusal(f"{s.title()} isn't a {cls.title()} cantrip")
        self.c["cantrips"] = cs

    def _set_prepared(self, v):
        self.c["prepared"] = [norm(x) for x in v]

    def _set_spellbook(self, v):
        sb = [norm(x) for x in v]
        for s in sb:
            if s not in SPELLS:
                raise OutOfScope(f"{s.title()} is out of scope")
            if s not in CLASS_LISTS["wizard"] or SPELLS[s]["level"] != 1:
                raise Refusal(f"{s.title()} isn't a level 1 Wizard spell")
        if len(sb) != 6 or len(set(sb)) != 6:
            raise Refusal("A new spellbook holds six level 1 Wizard spells")
        self.c["spellbook"] = sb

    def _feat_choice(self, spec):
        """Validate sub-choices of an Origin feat. spec: {'name':..., ...}"""
        name = norm(spec["name"])
        if name not in ORIGIN_FEATS:
            raise Refusal(f"{name.title()} isn't an Origin feat in scope")
        out = {"name": name}
        if name == "magic initiate":
            lst = norm(spec.get("list", ""))
            if lst not in MAGIC_INITIATE_LISTS:
                raise Refusal("Magic Initiate: choose the Cleric, Druid or Wizard list")
            ab = _ab(spec.get("ability", ""))
            if ab not in ("int", "wis", "cha"):
                raise Refusal("Magic Initiate ability must be Intelligence, Wisdom or Charisma")
            cantrips = [norm(x) for x in spec.get("cantrips", [])]
            spell = norm(spec.get("spell", ""))
            for c in cantrips:
                if c not in SPELLS or SPELLS[c]["level"] != 0 or lst not in SPELLS[c]["lists"]:
                    raise Refusal(f"{c.title()} isn't a {lst.title()} cantrip in scope")
            if len(cantrips) != 2:
                raise Refusal("Magic Initiate grants two cantrips")
            if spell not in SPELLS or SPELLS[spell]["level"] != 1 or lst not in SPELLS[spell]["lists"]:
                raise Refusal(f"{spell.title()} isn't a level 1 {lst.title()} spell in scope")
            out.update(list=lst, ability=ab, cantrips=cantrips, spell=spell)
        elif name == "skilled":
            ch = [norm(x) for x in spec.get("choices", [])]
            if len(ch) != 3:
                raise Refusal("Skilled grants three skills or tools")
            for x in ch:
                if x not in SKILLS and canonical(x) not in TOOLS:
                    raise Refusal(f"{x!r} is neither a skill nor a tool")
            out["choices"] = [x if x in SKILLS else canonical(x) for x in ch]
        return out

    def _set_bg_feat(self, spec):
        bg = self._need("background")
        want, lst = BACKGROUNDS[bg]["feat"]
        spec = dict(spec)
        spec.setdefault("name", want)
        if lst:
            spec.setdefault("list", lst)
            if norm(spec["list"]) != lst:
                raise Refusal(f"The {bg.title()} background grants Magic Initiate ({lst.title()})")
        self.c["bg_feat"] = self._feat_choice(spec)

    def _set_versatile(self, spec):
        if isinstance(spec, str):
            spec = {"name": spec}
        self.c["versatile"] = self._feat_choice(spec)

    def _set_gaming_set(self, v):
        v = canonical(v)
        if v not in GAMING_SETS:
            raise Refusal(f"Choose a gaming set: {', '.join(GAMING_SETS)}")
        self.c["gaming_set"] = v

    def _set_replacement_tool(self, v):
        v = canonical(v)
        if v not in TOOLS:
            raise Refusal(f"{v!r} isn't a tool")
        self.c["replacement_tool"] = v

    def _set_class_equipment(self, v):
        v = str(v).upper().replace("OPTION", "").strip()
        cls = self._need("cls")
        eq = CLASSES[cls]["equipment"]
        if v not in ("A", "B", "C") or (v != "C" and f"{v}_gp" not in eq) or (v == "C" and "C_gp" not in eq):
            raise Refusal(f"{cls.title()} starting equipment options: "
                          f"{', '.join(k[0] for k in eq if k.endswith('_gp'))}")
        self.c["class_equipment"] = v

    def _set_bg_equipment(self, v):
        v = str(v).upper().replace("OPTION", "").strip()
        if v not in ("A", "B"):
            raise Refusal("Background equipment: option A (package) or B (50 GP)")
        self.c["bg_equipment"] = v

    def _set_purchases(self, items):
        """Buy equipment at list price with gold-only starting options (p.20)."""
        budget = self.starting_gold_cp()
        total = 0
        bought = []
        for entry in items:
            name, qty = (entry, 1) if isinstance(entry, str) else entry
            n = canonical(name)
            cost = item_cost(n)
            if cost is None:
                raise Refusal(f"{name!r} isn't on the equipment lists")
            price = cost * qty
            if n in AMMO_BUNDLE:
                price = round(cost * qty)
            if total + price > budget:
                raise Refusal(f"Can't afford {qty} × {n.title()} ({fmt_cp(int(price))}); "
                              f"{fmt_cp(int(budget - total))} left")
            total += price
            bought.append((n, qty))
        self.c["purchases"] = bought
        self.c["purchase_total"] = int(total)

    def starting_gold_cp(self) -> int:
        cls = self.c.get("cls")
        opt = self.c.get("class_equipment")
        gp = 0
        if cls and opt:
            gp += CLASSES[cls]["equipment"][f"{opt}_gp"]
        return gp * 100

    # ------------------------------------------------------------------
    def _need(self, k):
        if k not in self.c:
            raise Refusal(f"Choose your {k.replace('_', ' ')} first")
        return self.c[k]

    def duplicate_tools(self) -> list[str]:
        cls, bg = self.c.get("cls"), self.c.get("background")
        if not cls or not bg:
            return []
        bg_tool = BACKGROUNDS[bg]["tool"]
        if bg_tool == "@gaming set":
            bg_tool = self.c.get("gaming_set")
        dup = [t for t in CLASSES[cls]["tools"] if t == bg_tool]
        for f in (self.c.get("versatile"), self.c.get("bg_feat")):
            if f and f["name"] == "skilled":
                have = set(CLASSES[cls]["tools"]) | {bg_tool}
                dup += [x for x in f["choices"] if x in have]
        return dup

    def missing(self) -> list[tuple[str, str]]:
        c = self.c
        out = []

        def need(k, q):
            if k not in c:
                out.append((k, q))

        need("name", "What is your character's name?")
        need("cls", "Which class: Fighter, Rogue, Cleric or Wizard?")
        need("species", "Which species: Human, Dwarf, Elf or Halfling?")
        need("background", "Which background: Acolyte, Criminal, Sage or Soldier?")
        need("scores", "Assign ability scores (Standard Array 15, 14, 13, 12, 10, 8; Point Cost; or Random).")
        need("background_bonus", "Which background abilities get +2/+1 (or +1/+1/+1)?")
        need("alignment", "What is your alignment?")
        need("languages", f"Choose two standard languages: {', '.join(l.title() for l in STANDARD_LANGUAGES)}.")
        cls, sp, bg = c.get("cls"), c.get("species"), c.get("background")
        if cls:
            cd = CLASSES[cls]
            need("class_skills", f"Choose {cd['skill_count']} {cls.title()} skills from "
                                 f"{', '.join(s.title() for s in cd['skill_choices'])}.")
            need("class_equipment", "Starting equipment: option " +
                 " / ".join(k[0] for k in cd["equipment"] if k.endswith("_gp")) + "?")
            if cls == "fighter":
                need("fighting_style", "Choose a Fighting Style (Defense is recommended).")
            if cls in ("fighter", "rogue"):
                need("masteries", f"Choose {cd['mastery_count']} weapons for Weapon Mastery.")
            if cls == "rogue":
                need("expertise", "Choose two skills for Expertise.")
                need("rogue_language", "Thieves' Cant: choose one more standard language.")
            if cls == "cleric":
                need("divine_order", "Divine Order: Protector or Thaumaturge?")
            if cd.get("spellcasting"):
                need("cantrips", f"Choose {CLASSES[cls]['spellcasting']['cantrips'][1] + (1 if c.get('divine_order') == 'thaumaturge' else 0)} cantrips.")
                need("prepared", "Choose 4 level 1 spells to prepare.")
            if cls == "wizard":
                need("spellbook", "Choose six level 1 Wizard spells for your spellbook.")
        if sp == "elf":
            need("lineage", "Which elven lineage: Drow, High Elf or Wood Elf?")
            need("lineage_ability", "Spellcasting ability for your lineage spells (Int, Wis or Cha)?")
            need("keen_senses", "Keen Senses: Insight, Perception or Survival?")
        if sp == "human":
            need("size", "Human size: Small or Medium?")
            need("skillful", "Skillful: choose one skill proficiency.")
            need("versatile", "Versatile: choose an Origin feat (Skilled is recommended).")
        if bg:
            need("bg_equipment", "Background equipment: package (A) or 50 GP (B)?")
            feat, lst = BACKGROUNDS[bg]["feat"]
            if feat in ("magic initiate", "skilled"):
                need("bg_feat", f"{feat.title()}: make your choices.")
            if BACKGROUNDS[bg]["tool"] == "@gaming set":
                need("gaming_set", "Soldier: choose a kind of gaming set.")
        if self.duplicate_tools() and "replacement_tool" not in c:
            out.append(("replacement_tool", f"You'd gain {', '.join(self.duplicate_tools())} twice; "
                        "choose a different tool proficiency instead (ruling R-01)."))
        return out

    # ------------------------------------------------------------------
    def build(self, game=None) -> Character:
        g = game or self.game
        miss = self.missing()
        if miss:
            raise Refusal("The character sheet can't be finalized yet. Still needed: "
                          + "; ".join(q for _, q in miss))
        c = self.c
        cls, spn, bgn = c["cls"], c["species"], c["background"]
        cd, sp, bg = CLASSES[cls], SPECIES[spn], BACKGROUNDS[bgn]
        pc = Character(c["name"], cls)
        if g:
            g.add(pc, team="party")
        notes = []
        # abilities
        scores = dict(c["scores"])
        pc.base_scores = dict(scores)
        for ab, n in c["background_bonus"].items():
            new = scores[ab] + n
            if new > 20:
                notes.append(f"{ab.title()} increase capped at 20")
                new = 20
            scores[ab] = new
        pc.abilities = scores
        pc.species, pc.background, pc.alignment = spn, bgn, c["alignment"]
        # species
        pc.size = c.get("size", sp["size"][0])
        pc.speeds = {"walk": sp["speed"]}
        pc.traits |= set(sp["traits"])
        pc.resist |= set(sp.get("resist", []))
        if sp.get("darkvision"):
            pc.senses["darkvision"] = sp["darkvision"]
        if spn == "elf":
            lin = sp["lineages"][c["lineage"]]
            pc.lineage = c["lineage"]
            pc.notes["lineage_ability"] = c["lineage_ability"]
            if lin.get("darkvision"):
                pc.senses["darkvision"] = lin["darkvision"]
            if lin.get("speed"):
                pc.speeds["walk"] = lin["speed"]
            if lin["cantrip"] in SPELLS:
                pc.cantrips.append((lin["cantrip"], c["lineage_ability"], f"{c['lineage'].title()} lineage"))
            else:
                pc.notes.setdefault("out_of_scope_cantrips", []).append(lin["cantrip"])
            pc.skills[c["keen_senses"]] = 1
        if spn == "human":
            pc.skills[c["skillful"]] = 1
        # class basics
        pc.save_profs = set(cd["saves"])
        for s in bg["skills"] + c["class_skills"]:
            pc.skills[s] = 1
        tools = list(cd["tools"])
        bg_tool = bg["tool"] if bg["tool"] != "@gaming set" else c["gaming_set"]
        dup = self.duplicate_tools()
        if bg_tool not in tools:
            tools.append(bg_tool)
        if dup:
            tools.append(c["replacement_tool"])
            if g:
                g.log.player("ruling", f"{pc.name} would gain {', '.join(dup)} proficiency twice; takes "
                             f"{c['replacement_tool'].title()} instead", ruling="R-01")
        pc.tools = set(tools)
        pc.hp = pc.base_max_hp = cd["hp1"] + pc.mod("con") + (1 if "dwarven toughness" in pc.traits else 0)
        # feats
        for f in (c.get("bg_feat") or {"name": bg["feat"][0]}, c.get("versatile")):
            if not f:
                continue
            pc.feats.append(f)
            if f["name"] == "skilled":
                for x in f["choices"]:
                    if x in SKILLS:
                        pc.skills[x] = max(1, pc.skills.get(x, 0))
                    else:
                        pc.tools.add(x)
            if f["name"] == "magic initiate":
                src = f"Magic Initiate ({f['list'].title()})"
                for ct in f["cantrips"]:
                    pc.cantrips.append((ct, f["ability"], src))
                pc.always_prepared[f["spell"]] = (f["ability"], src)
                pc.free_casts[f["spell"]] = {"available": True, "ability": f["ability"], "source": src}
        pc.fighting_style = c.get("fighting_style")
        pc.weapon_masteries = list(c.get("masteries", []))
        for s in c.get("expertise", []):
            if s not in pc.skills:
                raise Refusal(f"Expertise requires proficiency in {s.title()}")
            pc.skills[s] = 2
        if c.get("divine_order") == "protector":
            pc.weapon_profs.add("martial")
            pc.armor_training.add("heavy")
        pc.divine_order = c.get("divine_order")
        # languages
        pc.languages = ["common"] + c["languages"]
        if cls == "rogue":
            pc.languages += ["thieves' cant", c["rogue_language"]]
        # features
        grant_features(pc, 1)
        # spells
        if cd.get("spellcasting"):
            n = pc.cantrip_limit()
            if len(c["cantrips"]) != n:
                raise Refusal(f"Choose exactly {n} {cls.title()} cantrips")
            for ct in c["cantrips"]:
                pc.cantrips.append((ct, pc.spell_ability, cls.title()))
            if cls == "wizard":
                pc.spellbook = list(c["spellbook"])
            prepare_spells(pc, c["prepared"], at_creation=True)
        # equipment
        self._equip(pc, g, notes)
        if g:
            g.log.player("create", f"{pc.name} is created: {spn.title()} {cls.title()} 1 ({bgn.title()})"
                         + (f"; {'; '.join(notes)}" if notes else ""), page="19-23")
        return pc

    def _equip(self, pc, g, notes):
        c = self.c
        cd, bg = CLASSES[pc.cls], BACKGROUNDS[pc.background]
        opt = c["class_equipment"]
        eq = cd["equipment"]
        if opt in eq and isinstance(eq.get(opt), list):
            for n, q in eq[opt]:
                pc.inventory.add(n, q)
        pc.purse.add(gp=eq[f"{opt}_gp"])
        if c.get("purchases"):
            for n, q in c["purchases"]:
                pc.inventory.add(n, q)
            pc.purse.pay(c["purchase_total"])
            notes.append(f"bought {', '.join(f'{q} {n}' for n, q in c['purchases'])} for {fmt_cp(c['purchase_total'])}")
        if c["bg_equipment"] == "A":
            for n, q in bg["equipment"]["A"]:
                pc.inventory.add(c["gaming_set"] if n == "@gaming set" else n, q)
            pc.purse.add(gp=bg["equipment"]["A_gp"])
        else:
            pc.purse.add(gp=bg["equipment"]["B_gp"])
        auto_equip(pc)


def auto_equip(pc):
    """Wear the best armor the character is trained in, hold a Shield if trained."""
    armors = [it for it in pc.inventory if it.kind == "armor"]
    trained = [a for a in armors if pc.trained_in(a.armor["category"])]
    if trained:
        pc.armor = max(trained, key=lambda a: a.armor["base"] + a.magic_bonus)
    sh = pc.inventory.find("shield")
    if sh and pc.trained_in("shield"):
        pc.shield = sh
    weapons = [it for it in pc.inventory if it.kind == "weapon"]
    if weapons:
        main = max(weapons, key=lambda w: (pc.proficient_with(w), "two-handed" not in w.weapon["props"] or not pc.shield,
                                           w.weapon["kind"] == "melee", w.weapon["cost"]))
        pc.wielded = [main]


def prepare_spells(pc, spells, at_creation=False):
    """Prepare level 1+ spells (p.37, p.78). Only allowed at creation or after a Long Rest."""
    g = pc.game
    spells = [norm(s) for s in spells]
    counted = [s for s in spells if s not in pc.always_prepared]
    limit = pc.prepared_limit()
    if len(counted) > limit:
        raise Refusal(f"{pc.name} can prepare only {limit} spells at level {pc.level}")
    max_lvl = max(pc.slots_max()) if pc.slots_max() else 0
    for s in counted:
        if s not in SPELLS:
            raise OutOfScope(f"{s.title()} is out of scope")
        if SPELLS[s]["level"] == 0:
            raise Refusal(f"{s.title()} is a cantrip")
        if SPELLS[s]["level"] > max_lvl:
            raise Refusal(f"{s.title()} is level {SPELLS[s]['level']}; {pc.name} has no slots of that level")
        if pc.cls == "wizard" and s not in pc.spellbook:
            raise Refusal(f"{s.title()} isn't in {pc.name}'s spellbook")
        if pc.cls == "cleric" and s not in CLASS_LISTS["cleric"]:
            raise Refusal(f"{s.title()} isn't a Cleric spell")
    if not at_creation and g:
        last = pc.long_rest_finished_at
        if not pc.notes.get("may_change_prepared"):
            raise Refusal("Prepared spells can be changed only after finishing a Long Rest")
    pc.prepared = counted
    if g:
        g.log.player("prepare", f"{pc.name} prepares {', '.join(s.title() for s in counted)}",
                     page=pc.cdata["page"])


def _ab(v) -> str:
    v = norm(v)
    for a in ABILITIES:
        if v.startswith(a):
            return a
    raise Refusal(f"Unknown ability {v!r}")
