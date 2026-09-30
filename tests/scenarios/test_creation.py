"""CC, ORIG and the proficiency-dependent CORE scenarios."""
import pytest

from dungdra import Game, Refusal, OutOfScope
from dungdra.creation import CharacterBuilder
from dungdra.fixtures import FIXTURES, make, party
from dungdra import actions


@pytest.fixture
def pcs(game):
    return {pc.name: pc for pc in party(game)}


# ---- §4 oracle values -----------------------------------------------------
def test_brom_oracle(pcs):
    b = pcs["BROM"]
    assert (b.hp, b.ac(), b.speed(), b.senses["darkvision"]) == (13, 19, 30, 120)
    assert b.initiative_bonus() == 2
    assert b.save_bonus_total("str") == 5 and b.save_bonus_total("con") == 4
    assert b.skill_total("athletics") == 5 and b.passive() == 12
    assert b.purse.gp == 35
    assert b.abilities == {"str": 17, "dex": 14, "con": 14, "int": 8, "wis": 10, "cha": 12}


def test_lidda_oracle(pcs):
    l = pcs["LIDDA"]
    assert (l.hp, l.ac(), l.size, l.speed()) == (10, 14, "small", 30)
    assert l.initiative_bonus() == 5
    assert l.skill_total("stealth") == 7 and l.skill_total("sleight of hand") == 7
    assert l.passive() == 12
    assert l.capacity() == (180, 360)


def test_mialee_oracle(pcs):
    m = pcs["MIALEE"]
    assert (m.hp, m.ac(), m.speed(), m.senses["darkvision"]) == (8, 11, 30, 60)
    assert m.spell_dc() == 13 and m.spell_attack_bonus() == 5
    assert m.slots_max() == {1: 2}
    assert m.save_bonus_total("int") == 5 and m.save_bonus_total("wis") == 4
    assert m.passive() == 14


def test_jozan_oracle(pcs):
    j = pcs["JOZAN"]
    assert (j.hp, j.ac(), j.speed()) == (9, 14, 30)
    assert j.spell_dc() == 13 and j.spell_attack_bonus() == 5
    assert j.save_bonus_total("wis") == 5 and j.save_bonus_total("cha") == 3
    assert j.skill_total("medicine") == 5 and j.passive() == 15
    assert j.slots_max() == {1: 2}


# ---- CC-01 · builder side: missing choices, purchases --------------------
def test_cc01_gold_option_purchases_and_missing(game):
    b = CharacterBuilder(game)
    b.update(name="BROM", cls="fighter", species="dwarf", background="soldier",
             scores=FIXTURES["BROM"]["scores"], background_bonus={"str": 2, "con": 1})
    missing = {k for k, _ in b.missing()}
    assert {"languages", "class_skills", "masteries", "gaming_set"} <= missing
    with pytest.raises(Refusal):
        b.build()
    b.set("class_equipment", "C")
    with pytest.raises(Refusal):   # exceeds 155 GP
        b.set("purchases", [("plate armor", 1)])
    fx = dict(FIXTURES["BROM"])
    b2 = CharacterBuilder(game).update(**fx)
    brom = b2.build()
    assert brom.purse.gp == 35


# ---- CC-02 · ability scores ----------------------------------------------
def test_cc02_random_generation(game):
    b = CharacterBuilder(game)
    game.dice.force_str("d6=[6,5,1,3]")
    scores = b.roll_scores(game.dice)
    assert scores[0] == 14


def test_cc02_point_cost(game):
    b = CharacterBuilder(game).set("ability_method", "point buy")
    b.set("scores", {"str": 15, "dex": 15, "con": 13, "int": 8, "wis": 8, "cha": 8})  # 23 points: fine
    with pytest.raises(Refusal, match="27"):
        b.set("scores", {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 9})
    with pytest.raises(Refusal, match="between 8 and 15"):
        b.set("scores", {"str": 16, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8})


def test_cc02_standard_array_twice_rejected(game):
    b = CharacterBuilder(game).set("ability_method", "standard")
    with pytest.raises(Refusal):
        b.set("scores", {"str": 15, "dex": 15, "con": 13, "int": 12, "wis": 10, "cha": 8})


def test_cc02_background_adjustments(game):
    b = CharacterBuilder(game).set("background", "soldier")
    with pytest.raises(Refusal, match="Strength, Dexterity, Constitution|Str"):
        b.set("background_bonus", {"wis": 2, "str": 1})
    b.set("background_bonus", {"str": 1, "dex": 1, "con": 1})   # accepted
    # (f) capped at 20 — use Random Generation with an 19
    fx = dict(FIXTURES["BROM"])
    fx.update(ability_method="random")
    b2 = CharacterBuilder(game)
    b2.c["rolled"] = [19, 14, 13, 12, 10, 8]
    fx["scores"] = {"str": 19, "dex": 14, "con": 13, "int": 8, "wis": 10, "cha": 12}
    pc = b2.update(**fx).build()
    assert pc.abilities["str"] == 20


# ---- CC-03 · levels 1-3 and the cap ----------------------------------------
def test_cc03_advancement(pcs, game):
    expected = {"BROM": (13, 22, 31), "LIDDA": (10, 17, 24), "MIALEE": (8, 14, 20), "JOZAN": (9, 15, 21)}
    for name, (h1, h2, h3) in expected.items():
        pc = pcs[name]
        assert pc.max_hp == h1
        pc.award_xp(300)
        assert pc.level == 2 and pc.max_hp == h2 and pc.pb == 2
        pc.award_xp(600)
        assert pc.level == 3 and pc.max_hp == h3 and pc.pb == 2
    b, l, m, j = (pcs[n] for n in ("BROM", "LIDDA", "MIALEE", "JOZAN"))
    assert {"action surge", "tactical mind"} <= set(b.features)
    assert "cunning action" in l.features and "channel divinity" in j.features and "scholar" in m.features
    assert b.subclass == "champion" and l.subclass == "thief" and j.subclass == "life domain" and m.subclass == "evoker"
    assert any("subclass" in e.text for e in game.log.of_kind("offer"))
    # Wizard: 6 + 2 (L2) + 2 (L3) + 2 Evocation Savant
    assert len(m.spellbook) == 12
    b.award_xp(1800)
    assert b.xp == 2700 and b.level == 3
    assert "out of scope" in game.log.last("scope").text


def test_cc03_wizard_level2_adds_two(game):
    m = make(game, "MIALEE")
    m.award_xp(300)
    assert len(m.spellbook) == 8


# ---- CC-04 · languages -----------------------------------------------------
def test_cc04_languages(pcs, game):
    for pc in pcs.values():
        assert pc.languages[0] == "common" and len(pc.languages) >= 3
    assert "thieves' cant" in pcs["LIDDA"].languages and len(pcs["LIDDA"].languages) == 5
    with pytest.raises(Refusal, match="rare"):
        CharacterBuilder(game).set("languages", ["abyssal", "elvish"])


# ---- ORIG-01 · species traits ------------------------------------------------
def test_orig01_species(pcs):
    b, l, m, j = (pcs[n] for n in ("BROM", "LIDDA", "MIALEE", "JOZAN"))
    assert b.speed() in (30,) and b.senses["darkvision"] == 120 and "poison" in b.resist
    assert {"stonecunning", "dwarven resilience", "dwarven toughness"} <= b.traits
    assert b.resources["stonecunning"]["max"] == 2
    assert m.senses["darkvision"] == 60 and {"fey ancestry", "trance", "keen senses"} <= m.traits
    assert l.size == "small" and {"brave", "halfling nimbleness", "luck", "naturally stealthy"} <= l.traits
    assert {"resourceful", "skillful", "versatile"} <= j.traits and len(j.feats) == 2


def test_orig01_elf_lineage_spell_at_3(game):
    m = make(game, "MIALEE")
    m.award_xp(900)
    assert "detect magic" in m.always_prepared and m.free_casts["detect magic"]["available"]


def test_orig01_saves_advantage(pcs, game):
    b = pcs["BROM"]
    game.dice.force_str("d20=[3,15]")
    r = b.save("con", 11, avoid={"poisoned"})
    assert r.mode == "advantage" and r.chosen == 15
    game.dice.force_str("d20=[5]")
    r = b.save("con", 11)
    assert r.mode == "normal" and r.dice == [5]


# ---- ORIG-04 · background packages -----------------------------------------
def test_orig04_background_packages(game):
    fx = dict(FIXTURES["JOZAN"], name="ACO", bg_equipment="B")
    pc = CharacterBuilder(game).update(**fx).build()
    assert {"insight", "religion"} <= set(pc.skills) and "calligrapher's supplies" in pc.tools
    assert any(f["name"] == "magic initiate" and f["list"] == "cleric" for f in pc.feats)
    assert pc.purse.gp == 7 + 50
    fx = dict(FIXTURES["LIDDA"], name="CRIM", class_equipment="B")
    pc = CharacterBuilder(game).update(**fx).build()
    for item, n in [("dagger", 2), ("thieves' tools", 1), ("crowbar", 1), ("pouch", 2), ("traveler's clothes", 1)]:
        assert pc.inventory.count(item) == n
    assert pc.purse.gp == 100 + 16
    assert {"sleight of hand", "stealth"} <= set(pc.skills) and pc.has_feat("alert")
    with pytest.raises(Refusal):
        CharacterBuilder(game).update(background="criminal", background_bonus={"str": 2, "dex": 1})


def test_r01_logged(game):
    make(game, "LIDDA")
    assert "R-01" in game.log.rulings()


def test_subset_guard(game):
    with pytest.raises(OutOfScope):
        CharacterBuilder(game).set("cls", "bard")
    with pytest.raises(OutOfScope):
        CharacterBuilder(game).set("species", "tiefling")


# ---- CORE-03 · checks, Expertise, tools ------------------------------------
def test_core03_checks(pcs, game):
    b, l, m = pcs["BROM"], pcs["LIDDA"], pcs["MIALEE"]
    game.dice.force_str("d20=[10]")
    assert b.check("athletics").total == 15
    game.dice.force_str("d20=[10]")
    assert l.check("stealth").total == 17
    game.dice.force_str("d20=[10]")
    assert m.check("athletics").total == 9
    game.dice.force_str("d20=[10,4]")
    r = actions.use_tool(game, l, "pick a lock", dc=15)
    assert r.mode == "advantage" and r.total == 17
    assert sum(1 for _, s in r.mods if "PB" in s) == 1
    l.inventory.remove("thieves' tools", l.inventory.count("thieves' tools"))
    with pytest.raises(Refusal):
        actions.use_tool(game, l, "pick a lock", dc=15)


# ---- CORE-04 · Passive Perception ---------------------------------------------
def test_core04_passive(pcs):
    vals = {n: pcs[n].passive() for n in pcs}
    assert vals == {"BROM": 12, "LIDDA": 12, "MIALEE": 14, "JOZAN": 15}
    assert [n for n, v in vals.items() if v >= 13] == ["MIALEE", "JOZAN"]
    assert pcs["MIALEE"].passive(tags={"dim_light"}) == 9


# ---- CORE-05 · saves ------------------------------------------------------------
def test_core05_brom_saves(pcs):
    b = pcs["BROM"]
    assert b.save_bonus_total("con") == 4 and b.save_bonus_total("wis") == 0


# ---- CORE-06 · Help (checks) ---------------------------------------------------
def test_core06_help_checks(pcs, game):
    b, l = pcs["BROM"], pcs["LIDDA"]
    actions.help_check(game, b, l, skill="athletics")
    game.dice.force_str("d20=[4,17]")
    r = l.check("athletics")
    assert r.mode == "advantage"
    game.dice.force_str("d20=[4]")
    assert l.check("athletics").mode == "normal"        # used up
    with pytest.raises(Refusal, match="proficient"):
        actions.help_check(game, b, l, tool="thieves' tools")


def test_core06_help_attack_range(pcs, game):
    from dungdra.creature import Creature
    j = pcs["JOZAN"]
    gob = game.add(Creature("Goblin", team="enemy"), position=(10, 0))
    j.position = (0, 0)
    with pytest.raises(Refusal):
        actions.help_attack(game, j, gob)
    gob.position = (5, 0)
    actions.help_attack(game, j, gob)
    assert gob.effects
