"""SRD rule tests for Playing the Game (SRD 5.2.1 p.5-19)."""

import pytest

from dungdra import combat as C
from dungdra import spells as S
from dungdra.api import Session
from tests.support.helpers import mon, pc
from tests.support.srd import assert_refused_cleanly

COVER = "PLAY.combat.cover"

GOBLIN_AC = 15  # Goblin Warrior stat block

NO_CREATURE_COVER = (
    "T-new: a creature between attacker and target gives no Half Cover; "
    "cover comes only from scene.cover/cover_all"
)
NO_COVER_TRACE = (
    "T-new: the Half/Three-Quarters Cover bonus is applied but no event carries rule=PLAY.combat.cover"
)


def set_turn(game, c):
    cb = game.combat
    if cb.current is not None:
        C._expire(game, "end", cb.current)
    cb.index = next(i for i, (cid, _) in enumerate(cb.order) if cid == c.id)
    C.start_turn(game)


def in_combat(game, mover, *others):
    """Start combat and give `mover` the turn. Initiative dice are forced so every roll is used."""
    game.dice.force_str("d20=[" + ",".join(["20"] + ["1"] * len(others)) + "]")
    C.roll_initiative(game, [mover, *others])
    set_turn(game, mover)


def shoot(game, attacker, target, d20=10):
    game.dice.force_str(f"d20=[{d20}]")
    return C.attack(game, attacker, target, weapon="shortbow")


def lidda_and_goblin(game, dist=30):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (dist, 0))
    gob.base_max_hp = gob.hp = 500
    return lidda, gob


def mialee_burns(game, gob_cover=None, d20=9, pair=None):
    """MIALEE casts Burning Hands (DC 13) at a Goblin Warrior (Dex save +2) 5 ft away.
    `gob_cover` is cover against everyone; `pair` is (attacker id, degree) for one-sided cover.
    Damage is forced to 3d6 = 12; returns the goblin."""
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 50
    if gob_cover:
        game.scene.cover_all[gob.id] = gob_cover
    if pair:
        who, degree = pair
        game.scene.cover[(who.id if who != "caster" else m.id, gob.id)] = degree
    game.dice.force_str(f"d6=[3,4,5]; d20=[{d20}]")
    S.cast(game, m, "burning hands", [m, gob])
    return m, gob


# ---------------- #1 · obstacles make a target harder to harm ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#1", kind="positive")
def test_cover_makes_a_hit_harder(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    r = shoot(game, lidda, gob, d20=11)
    # 11 + Dex 3 + PB 2 = 16: would hit AC 15, misses AC 17
    assert r.roll.total == 16 and r.roll.target == GOBLIN_AC + 2
    assert not r.hit


@pytest.mark.srd(COVER, clause=f"{COVER}#1", kind="negative")
def test_no_cover_no_bonus(game):
    lidda, gob = lidda_and_goblin(game)
    r = shoot(game, lidda, gob, d20=10)
    assert r.roll.target == GOBLIN_AC and r.hit
    assert not any("Cover" in label for _, label in r.roll.mods)


@pytest.mark.srd(COVER, clause=f"{COVER}#1", kind="positive")
@pytest.mark.xfail(strict=True, reason="T-15: an applied cover bonus is not traced to rule=PLAY.combat.cover")
def test_applied_cover_bonus_is_traced_to_the_rule(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    shoot(game, lidda, gob)
    game.log.assert_applied(rule=COVER)


# ---------------- #2 · three degrees, each a different benefit ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#2", kind="positive")
@pytest.mark.parametrize("degree,bonus", [("half", 2), ("three-quarters", 5)])
def test_each_degree_gives_its_own_ac_bonus(game, degree, bonus):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = degree
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC + bonus


@pytest.mark.srd(COVER, clause=f"{COVER}#2", kind="negative")
def test_total_cover_is_not_a_bigger_ac_bonus(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "total"
    # Total Cover isn't a bigger AC bonus: the attack can't be made at all
    assert_refused_cleanly(game, C.attack, game, lidda, gob, weapon="shortbow", match="Total Cover")


# ---------------- #3 · only from the opposite side ----------------


@pytest.mark.srd(COVER, clause=f"{COVER}#3", kind="negative")
def test_cover_from_one_attacker_doesnt_protect_against_another(game):
    lidda, gob = lidda_and_goblin(game)
    other = pc(game, "LIDDA", (30, 30))
    game.scene.cover[(lidda.id, gob.id)] = "three-quarters"
    assert shoot(game, other, gob).roll.target == GOBLIN_AC


@pytest.mark.srd(COVER, clause=f"{COVER}#3", kind="negative", ruling="P-7")
def test_cover_is_not_symmetric(game):
    """The goblin is behind the wall from LIDDA's side; LIDDA isn't behind it from the goblin's."""
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    lidda_ac = sum(v for v, _ in lidda.ac_parts())
    game.dice.force_str("d20=[10]; d6=[1]")
    r = C.attack(game, gob, lidda, attack_name="Shortbow")
    assert r.roll.target == lidda_ac


@pytest.mark.srd(COVER, clause=f"{COVER}#3", kind="negative")
def test_dex_save_cover_only_against_effect_from_the_far_side(game):
    brom = pc(game, "BROM", (0, 30))
    _, gob = mialee_burns(game, pair=(brom, "half"), d20=9)
    save = game.log.last("save")
    assert "Cover" not in save.text and "→ failure" in save.text
    assert gob.hp == 50 - 12


@pytest.mark.srd(COVER, clause=f"{COVER}#3", kind="negative")
def test_total_cover_from_another_side_doesnt_stop_the_attack(game):
    lidda, gob = lidda_and_goblin(game)
    brom = pc(game, "BROM", (30, 30))
    game.scene.cover[(brom.id, gob.id)] = "total"
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC


# ---------------- #4 · only the most protective degree ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#4", kind="positive")
def test_creature_half_and_tree_three_quarters_give_three_quarters(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "three-quarters"
    game.scene.cover_all[gob.id] = "half"
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC + 5


@pytest.mark.srd(COVER, clause=f"{COVER}#4", kind="negative")
def test_two_half_covers_dont_add_up(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    game.scene.cover_all[gob.id] = "half"
    r = shoot(game, lidda, gob)
    assert r.roll.target == GOBLIN_AC + 2


@pytest.mark.srd(COVER, clause=f"{COVER}#4", kind="positive")
def test_total_beats_lesser_cover(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    game.scene.cover_all[gob.id] = "total"
    assert_refused_cleanly(game, C.attack, game, lidda, gob, weapon="shortbow", match="Total Cover")


@pytest.mark.srd(COVER, clause=f"{COVER}#4", kind="negative")
def test_spell_attack_cover_doesnt_stack(game):
    m = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    gob.base_max_hp = gob.hp = 500
    game.scene.cover[(m.id, gob.id)] = "half"
    game.scene.cover_all[gob.id] = "three-quarters"
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "fire bolt", gob)
    atk = game.log.last("attack")
    assert f"AC {GOBLIN_AC + 5}" in atk.text, atk.text


@pytest.mark.srd(COVER, clause=f"{COVER}#4", kind="negative")
def test_dex_save_cover_doesnt_stack(game):
    # 6 + 2 + best(+2, +5) = 13 succeeds against DC 13; +2 and +5 summed would show 15
    _, gob = mialee_burns(game, gob_cover="half", pair=("caster", "three-quarters"), d20=6)
    save = game.log.last("save")
    assert "→ success" in save.text and "= 13" in save.text, save.text
    assert gob.hp == 50 - 6


# ---------------- #5 · Half Cover: +2 to AC and Dex saves ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#5", kind="boundary")
def test_half_cover_ac_is_exactly_two(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    # 10 + 5 = 15 meets AC 15 but not AC 17; 12 + 5 = 17 meets AC 17
    r = shoot(game, lidda, gob, d20=10)
    assert r.roll.target == 17 and not r.hit
    r = shoot(game, lidda, gob, d20=12)
    assert r.roll.total == 17 and r.hit


@pytest.mark.srd(COVER, clause=f"{COVER}#5", kind="positive")
def test_half_cover_adds_two_to_dex_save(game):
    # 9 + Dex 2 = 11 fails DC 13; with +2 it's 13 and succeeds
    _, gob = mialee_burns(game, gob_cover="half", d20=9)
    save = game.log.last("save")
    assert "Half Cover" in save.text and "→ success" in save.text, save.text
    assert gob.hp == 50 - 6


@pytest.mark.srd(COVER, clause=f"{COVER}#5", kind="negative")
def test_no_cover_dex_save_fails(game):
    _, gob = mialee_burns(game, d20=9)
    assert "→ failure" in game.log.last("save").text
    assert gob.hp == 50 - 12


@pytest.mark.srd(COVER, clause=f"{COVER}#5", kind="negative")
def test_cover_doesnt_help_other_saves(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("thunderwave")
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 50
    game.scene.cover_all[gob.id] = "half"
    game.dice.force_str("d8=[1,1]; d20=[10]")
    S.cast(game, m, "thunderwave", [gob])
    save = game.log.last("save")
    assert "Con" in save.text and "Cover" not in save.text, save.text


@pytest.mark.srd(COVER, clause=f"{COVER}#5", kind="positive")
def test_half_cover_on_a_spell_attack(game):
    m = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    gob.base_max_hp = gob.hp = 500
    game.scene.cover_all[gob.id] = "half"
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "fire bolt", gob)
    assert f"AC {GOBLIN_AC + 2}" in game.log.last("attack").text


@pytest.mark.srd(COVER, clause=f"{COVER}#5", kind="positive")
def test_half_cover_on_a_melee_attack(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 500
    game.scene.cover[(brom.id, gob.id)] = "half"
    game.dice.force_str("d20=[1]")
    assert C.attack(game, brom, gob).roll.target == GOBLIN_AC + 2


# ---------------- #6 · offered by another creature ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#6", kind="positive")
@pytest.mark.xfail(strict=True, reason="T-16: a creature between attacker and target gives no Half Cover")
def test_creature_in_the_way_gives_half_cover(game):
    lidda, gob = lidda_and_goblin(game, dist=30)
    mon(game, "goblin warrior", (15, 0), name="Screen")  # same size as the target, right in the line
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC + 2


@pytest.mark.srd(COVER, clause=f"{COVER}#6", kind="positive")
@pytest.mark.xfail(strict=True, reason="T-16: a creature between attacker and target gives no Half Cover")
def test_ally_in_the_way_gives_half_cover_to_the_enemy(game):
    lidda, gob = lidda_and_goblin(game, dist=30)
    pc(game, "BROM", (15, 0))
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC + 2


@pytest.mark.srd(COVER, clause=f"{COVER}#6", kind="negative")
def test_creature_off_the_line_gives_no_cover(game):
    lidda, gob = lidda_and_goblin(game, dist=30)
    mon(game, "goblin warrior", (15, 30), name="Bystander")
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC


@pytest.mark.srd(COVER, clause=f"{COVER}#6", kind="negative")
def test_creature_behind_the_target_gives_no_cover(game):
    lidda, gob = lidda_and_goblin(game, dist=30)
    mon(game, "goblin warrior", (45, 0), name="Behind")
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC


@pytest.mark.srd(COVER, clause=f"{COVER}#6", kind="boundary", ruling="R-09")
def test_creature_and_object_give_only_half(game):
    """A creature never gives more than Half Cover; with an object giving Half too, still +2."""
    lidda, gob = lidda_and_goblin(game, dist=30)
    mon(game, "goblin warrior", (15, 0), name="Screen")
    game.scene.cover[(lidda.id, gob.id)] = "half"
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC + 2


# ---------------- #7 · Three-Quarters Cover: +5 to AC and Dex saves ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#7", kind="boundary")
def test_three_quarters_ac_is_exactly_five(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover[(lidda.id, gob.id)] = "three-quarters"
    r = shoot(game, lidda, gob, d20=14)  # 19 < 20
    assert r.roll.target == 20 and not r.hit
    r = shoot(game, lidda, gob, d20=15)  # 20 meets 20
    assert r.hit


@pytest.mark.srd(COVER, clause=f"{COVER}#7", kind="positive")
def test_three_quarters_adds_five_to_dex_save(game):
    # 6 + 2 = 8 fails; + 5 = 13 meets DC 13
    _, gob = mialee_burns(game, gob_cover="three-quarters", d20=6)
    save = game.log.last("save")
    assert "Three-Quarters Cover" in save.text and "→ success" in save.text, save.text
    assert gob.hp == 50 - 6


@pytest.mark.srd(COVER, clause=f"{COVER}#7", kind="boundary")
def test_three_quarters_dex_save_one_short(game):
    # 5 + 2 + 5 = 12 fails DC 13
    _, gob = mialee_burns(game, gob_cover="three-quarters", d20=5)
    assert "→ failure" in game.log.last("save").text
    assert gob.hp == 50 - 12


# ---------------- #8 · offered by an object covering three-quarters ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#8", kind="negative", ruling="R-09")
@pytest.mark.xfail(strict=True, reason="T-16: a creature between attacker and target gives no Half Cover")
def test_creature_alone_never_gives_three_quarters(game):
    lidda, gob = lidda_and_goblin(game, dist=30)
    mon(game, "goblin warrior", (10, 0), name="Screen 1")
    mon(game, "goblin warrior", (20, 0), name="Screen 2")
    # two creatures in the way: Half Cover (+2), never Three-Quarters (+5)
    assert shoot(game, lidda, gob).roll.target == GOBLIN_AC + 2


# ---------------- #9 · Total Cover: can't be targeted directly ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="positive")
def test_total_cover_refuses_weapon_attack(game):
    lidda, gob = lidda_and_goblin(game)
    game.scene.cover_all[gob.id] = "total"
    e = assert_refused_cleanly(game, C.attack, game, lidda, gob, weapon="shortbow", match="Total Cover")
    assert e.page == 15


@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="positive")
def test_total_cover_refuses_single_target_spell(game):
    m = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    game.scene.cover[(m.id, gob.id)] = "total"
    assert_refused_cleanly(game, S.cast, game, m, "magic missile", gob, match="Total Cover")
    assert m.slots_left(1) == 2


@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="positive")
def test_sacred_flame_still_cant_target_total_cover(game):
    j = pc(game, "JOZAN", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    game.scene.cover_all[gob.id] = "total"
    assert_refused_cleanly(game, S.cast, game, j, "sacred flame", gob, match="Total Cover")


@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="negative", ruling="R-10")
def test_total_cover_doesnt_refuse_an_area_spell(game):
    """'Directly': an area spell isn't refused because one creature in the area has Total Cover.
    Whether the area reaches it is the area-of-effect rule's call (blocked lines need Total Cover)."""
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g1 = mon(game, "goblin warrior", (5, 0), name="G1")
    g1.base_max_hp = g1.hp = 50
    g2 = mon(game, "goblin warrior", (10, 0), name="G2")
    game.scene.cover_all[g2.id] = "total"
    game.dice.force_str("d6=[3,4,5]; d20=[1]")
    S.cast(game, m, "burning hands", [m, g1, g2])
    assert g1.hp == 50 - 12 and g2.hp == g2.max_hp
    assert m.slots_left(1) == 1
    game.log.assert_applied(rule="GLOSS.area-of-effect")


@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="positive")
def test_total_cover_refused_through_the_session(game):
    lidda, gob = lidda_and_goblin(game)
    in_combat(game, lidda, gob)
    game.scene.cover_all[gob.id] = "total"
    s = Session(game)
    s.auto_gm = False
    out = assert_refused_cleanly(
        game,
        s.execute,
        {"cmd": "attack", "actor": lidda.id, "target": gob.id, "weapon": "shortbow"},
        match="Total Cover",
    )
    assert out["ok"] is False


@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="abuse")
def test_refused_total_cover_attack_keeps_the_attack_action(game):
    lidda, gob = lidda_and_goblin(game)
    in_combat(game, lidda, gob)
    other = mon(game, "goblin warrior", (30, 10), name="Open")
    other.base_max_hp = other.hp = 500
    game.scene.cover_all[gob.id] = "total"
    s = Session(game)
    s.auto_gm = False
    assert_refused_cleanly(
        game, s.execute, {"cmd": "attack", "actor": lidda.id, "target": gob.id, "weapon": "shortbow"}
    )
    game.dice.force_str("d20=[10]; d6=[1]")
    out = s.execute({"cmd": "attack", "actor": lidda.id, "target": other.id, "weapon": "shortbow"})
    assert out["ok"], out
    assert game.log.last("attack").text.startswith("LIDDA"), out


@pytest.mark.srd(COVER, clause=f"{COVER}#9", kind="abuse")
def test_total_cover_target_cant_be_slipped_into_a_multi_target_spell(game):
    m = pc(game, "MIALEE", (0, 0))
    g1 = mon(game, "goblin warrior", (30, 0), name="G1")
    g2 = mon(game, "goblin warrior", (30, 10), name="G2")
    game.scene.cover_all[g2.id] = "total"
    assert_refused_cleanly(game, S.cast, game, m, "magic missile", [g1, g2], match="Total Cover")


# ---------------- #10 · offered by an object covering the whole target ----------------
@pytest.mark.srd(COVER, clause=f"{COVER}#10", kind="negative", ruling="R-09")
def test_creature_in_the_way_never_gives_total_cover(game):
    lidda, gob = lidda_and_goblin(game, dist=30)
    mon(game, "goblin warrior", (15, 0), name="Screen")
    r = shoot(game, lidda, gob)  # the attack can be made: a creature never gives Total Cover
    assert r.roll.target < 20
