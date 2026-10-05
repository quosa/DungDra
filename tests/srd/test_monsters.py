"""SRD rule tests for Monsters A–Z (SRD 5.2.1 p.258+): stat blocks tested by their effect."""

import pytest

from dungdra import actions
from dungdra import class_actions as CA
from dungdra import combat as C
from dungdra import spells as S
from dungdra.api import Session
from dungdra.encounters import award_xp
from tests.support.helpers import mon, pc
from tests.support.srd import assert_refused_cleanly

GW = "MONSTER.goblins.goblin-warrior"


def set_turn(game, c):
    cb = game.combat
    if cb.current is not None:
        C._expire(game, "end", cb.current)
    cb.index = next(i for i, (cid, _) in enumerate(cb.order) if cid == c.id)
    C.start_turn(game)


def in_combat(game, mover, *others):
    """Start combat and give `mover` the turn. Initiative dice are forced so every roll is used
    (the creatures must be of different kinds: identical monsters share one roll)."""
    game.dice.force_str("d20=[" + ",".join(["20"] + ["1"] * len(others)) + "]")
    C.roll_initiative(game, [mover, *others])
    set_turn(game, mover)


def goblin_vs_brom(game, gob_pos=(5, 0)):
    """BROM at the origin (HP raised so damage never drops him) and a Goblin Warrior."""
    b = pc(game, "BROM", (0, 0))
    b.hp = b.base_max_hp = 100
    gob = mon(game, "goblin warrior", gob_pos, name="Gob")
    return b, gob


def assert_save_and_check(game, gob, ability, mod, save):
    """A save and a plain ability check of the goblin with a forced 10 total 10 + bonus."""
    game.dice.force_str("d20=[10]")
    assert gob.save(ability, 30).total == 10 + save
    game.dice.force_str("d20=[10]")
    assert gob.check(ability=ability, dc=30).total == 10 + mod


def assert_save_threshold(game, gob, ability, save):
    """The save meets a DC equal to its total and fails one point higher."""
    game.dice.force_str("d20=[10,10]")
    assert gob.save(ability, 10 + save).success
    assert not gob.save(ability, 11 + save).success


# ---------------------------------------------------------------- #1 Small Fey (Goblinoid), Chaotic Neutral
@pytest.mark.srd(GW, clause=f"{GW}#1", kind="positive")
def test_goblin_warrior_is_a_small_fey_goblinoid_that_can_grapple_a_medium_creature(game):
    b, gob = goblin_vs_brom(game)
    assert (gob.size, gob.ctype) == ("small", "fey") and "goblinoid" in gob.type_tags
    assert gob.data["alignment"] == "chaotic neutral"
    game.dice.force_str("d20=[1]")
    assert C.grapple(game, gob, b)  # Medium is one size larger than Small
    assert b.has("grappled")


@pytest.mark.srd(GW, clause=f"{GW}#1", kind="negative")
def test_hold_person_does_nothing_to_a_goblin_warrior_which_isnt_humanoid(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.award_xp(900)
    jozan.prepared.append("hold person")
    gob = mon(game, "goblin warrior", (20, 0))
    rolled = len(game.dice.history)
    S.cast(game, jozan, "hold person", [gob])
    assert not gob.has("paralyzed") and len(game.dice.history) == rolled
    assert jozan.slots_left(2) == 1


@pytest.mark.srd(GW, clause=f"{GW}#1", kind="boundary")
def test_a_small_goblin_cant_grapple_a_large_ogre(game):
    gob = mon(game, "goblin warrior", (0, 0), name="Gob")
    ogre = mon(game, "ogre", (5, 0))
    assert_refused_cleanly(game, C.grapple, game, gob, ogre, match="size")


# ---------------------------------------------------------------- #2 AC 15
@pytest.mark.srd(GW, clause=f"{GW}#2", kind="positive")
def test_an_attack_total_of_15_hits_the_goblin(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[10]; d8=[3]")
    r = C.attack(game, b, gob, weapon="longsword")
    assert r.roll.total == 15 and r.roll.target == 15 and r.hit


@pytest.mark.srd(GW, clause=f"{GW}#2", kind="boundary")
def test_an_attack_total_of_14_misses_the_goblin(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[9]")
    r = C.attack(game, b, gob, weapon="longsword")
    assert r.roll.total == 14 and not r.hit and gob.hp == 10


# ---------------------------------------------------------------- #3 Initiative +2 (12)
@pytest.mark.srd(GW, clause=f"{GW}#3", kind="positive")
def test_goblin_initiative_roll_adds_2(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[10]")
    r = C.initiative_roll(game, gob)
    assert r.total == 12


@pytest.mark.srd(GW, clause=f"{GW}#3", kind="boundary")
def test_goblin_rolling_11_for_initiative_takes_its_place_at_13_in_the_order(game):
    gob = mon(game, "goblin warrior", (5, 0), name="Gob")
    bandit = mon(game, "bandit", (10, 0))
    ogre = mon(game, "ogre", (15, 0))
    game.dice.force_str("d20=[11,12,12]")  # goblin 13; bandit and ogre roll 12 + their bonuses
    C.roll_initiative(game, [gob, bandit, ogre])
    order = dict(game.combat.order)
    assert order[gob.id] == 13
    assert [cid for cid, _ in game.combat.order].index(gob.id) == sorted(order.values(), reverse=True).index(
        13
    )


# ---------------------------------------------------------------- #4 HP 10 (3d6)
@pytest.mark.srd(GW, clause=f"{GW}#4", kind="positive")
def test_goblin_has_10_hit_points_and_rolled_hp_uses_3d6(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.hp == gob.max_hp == 10
    game.dice.force_str("d6=[6,6,6]")
    gob.roll_hp(game.dice)
    assert gob.hp == gob.max_hp == 18


@pytest.mark.srd(GW, clause=f"{GW}#4", kind="negative")
def test_a_goblin_added_with_rolled_hp_rolls_3d6(game):
    game.dice.force_str("d6=[1,2,3]")
    gob = mon(game, "goblin warrior", (5, 0), hp="roll")
    assert gob.hp == gob.max_hp == 6


@pytest.mark.srd(GW, clause=f"{GW}#4", kind="boundary")
def test_9_damage_leaves_the_goblin_at_1_hp_and_10_kills_it(game):
    gob = mon(game, "goblin warrior", (5, 0))
    gob.take_damage(9, "slashing")
    assert gob.hp == 1 and not gob.dead
    gob2 = mon(game, "goblin warrior", (10, 0), name="Gob 2")
    gob2.take_damage(10, "slashing")
    assert gob2.hp == 0 and gob2.dead


# ---------------------------------------------------------------- #5 Speed 30 ft.
@pytest.mark.srd(GW, clause=f"{GW}#5", kind="positive")
def test_goblin_moves_30_feet_on_its_turn(game):
    b, gob = goblin_vs_brom(game, gob_pos=(50, 0))
    in_combat(game, gob, b)
    assert gob.speed() == 30
    C.move(game, gob, to=(50, 30))
    assert gob.position == (50, 30) and game.combat.turn.movement_left == 0


@pytest.mark.srd(GW, clause=f"{GW}#5", kind="boundary")
def test_goblin_cant_move_35_feet(game):
    b, gob = goblin_vs_brom(game, gob_pos=(50, 0))
    in_combat(game, gob, b)
    assert_refused_cleanly(game, C.move, game, gob, to=(50, 35))


@pytest.mark.srd(GW, clause=f"{GW}#5", kind="negative")
def test_goblin_has_no_fly_speed(game):
    b, gob = goblin_vs_brom(game, gob_pos=(50, 0))
    in_combat(game, gob, b)
    assert gob.speed("fly") == 0
    assert_refused_cleanly(game, C.move, game, gob, to=(50, 10), mode="fly")


# ---------------------------------------------------------------- #6–#11 ability scores and saves
@pytest.mark.srd(GW, clause=f"{GW}#6", kind="positive")
def test_goblin_strength_8_gives_minus_1_to_checks_and_saves(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.score("str") == 8 and gob.mod("str") == -1
    assert_save_and_check(game, gob, "str", -1, -1)


@pytest.mark.srd(GW, clause=f"{GW}#6", kind="boundary")
def test_goblin_strength_save_meets_dc_9_on_a_10_and_fails_dc_10(game):
    assert_save_threshold(game, mon(game, "goblin warrior", (5, 0)), "str", -1)


@pytest.mark.srd(GW, clause=f"{GW}#7", kind="positive")
def test_goblin_dexterity_15_gives_plus_2_to_checks_and_saves(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.score("dex") == 15 and gob.mod("dex") == 2
    assert_save_and_check(game, gob, "dex", 2, 2)


@pytest.mark.srd(GW, clause=f"{GW}#7", kind="boundary")
def test_goblin_dexterity_save_meets_dc_12_on_a_10_and_fails_dc_13(game):
    assert_save_threshold(game, mon(game, "goblin warrior", (5, 0)), "dex", 2)


@pytest.mark.srd(GW, clause=f"{GW}#8", kind="positive")
def test_goblin_constitution_10_gives_plus_0_to_checks_and_saves(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.score("con") == 10 and gob.mod("con") == 0
    assert_save_and_check(game, gob, "con", 0, 0)


@pytest.mark.srd(GW, clause=f"{GW}#8", kind="boundary")
def test_goblin_constitution_save_meets_dc_10_on_a_10_and_fails_dc_11(game):
    assert_save_threshold(game, mon(game, "goblin warrior", (5, 0)), "con", 0)


@pytest.mark.srd(GW, clause=f"{GW}#9", kind="positive")
def test_goblin_intelligence_10_gives_plus_0_to_checks_and_saves(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.score("int") == 10 and gob.mod("int") == 0
    assert_save_and_check(game, gob, "int", 0, 0)


@pytest.mark.srd(GW, clause=f"{GW}#9", kind="boundary")
def test_goblin_intelligence_save_meets_dc_10_on_a_10_and_fails_dc_11(game):
    assert_save_threshold(game, mon(game, "goblin warrior", (5, 0)), "int", 0)


@pytest.mark.srd(GW, clause=f"{GW}#10", kind="positive")
def test_goblin_wisdom_8_gives_minus_1_to_checks_and_saves(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.score("wis") == 8 and gob.mod("wis") == -1
    assert_save_and_check(game, gob, "wis", -1, -1)


@pytest.mark.srd(GW, clause=f"{GW}#10", kind="boundary")
def test_goblin_wisdom_save_meets_dc_9_on_a_10_and_fails_dc_10(game):
    assert_save_threshold(game, mon(game, "goblin warrior", (5, 0)), "wis", -1)


@pytest.mark.srd(GW, clause=f"{GW}#11", kind="positive")
def test_goblin_charisma_8_gives_minus_1_to_checks_and_saves(game):
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.score("cha") == 8 and gob.mod("cha") == -1
    assert_save_and_check(game, gob, "cha", -1, -1)


@pytest.mark.srd(GW, clause=f"{GW}#11", kind="boundary")
def test_goblin_charisma_save_meets_dc_9_on_a_10_and_fails_dc_10(game):
    assert_save_threshold(game, mon(game, "goblin warrior", (5, 0)), "cha", -1)


# ---------------------------------------------------------------- #12 Skills Stealth +6
@pytest.mark.srd(GW, clause=f"{GW}#12", kind="positive")
def test_goblin_stealth_check_adds_6(game):
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[10]")
    assert gob.check("stealth", dc=30).total == 16


@pytest.mark.srd(GW, clause=f"{GW}#12", kind="negative")
def test_the_stealth_bonus_doesnt_apply_to_other_dexterity_checks(game):
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[10,10]")
    assert gob.check("sleight of hand", dc=30).total == 12
    assert gob.check("acrobatics", dc=30).total == 12


@pytest.mark.srd(GW, clause=f"{GW}#12", kind="boundary")
def test_goblin_hides_on_a_9_against_dc_15_and_fails_on_an_8(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    game.dice.force_str("d20=[8]")
    r = actions.hide(game, gob, cover="total")
    assert r.total == 14 and not gob.has("invisible")
    game.dice.force_str("d20=[9]")
    r = actions.hide(game, gob, cover="total")
    assert r.total == 15 and gob.has("invisible")


# ---------------------------------------------------------------- #13 Gear
@pytest.mark.srd(GW, clause=f"{GW}#13", kind="positive")
def test_goblin_attacks_with_the_scimitar_and_shortbow_from_its_gear(game):
    b, gob = goblin_vs_brom(game)
    assert {"leather armor", "scimitar", "shield", "shortbow"} == set(gob.data["gear"])
    game.dice.force_str("d20=[2,2]")
    assert C.attack(game, gob, b, attack_name="scimitar").roll is not None
    gob.position = (30, 0)
    assert C.attack(game, gob, b, attack_name="shortbow").roll is not None


@pytest.mark.srd(GW, clause=f"{GW}#13", kind="positive", ruling="R-25")
def test_goblin_shortbow_attack_needs_no_tracked_arrows(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    in_combat(game, gob, b)
    game.dice.force_str("d20=[15]; d6=[3]")
    r = C.attack(game, gob, b, attack_name="shortbow")
    assert r.roll.total == 19 and r.hit and r.damage == 5


@pytest.mark.srd(GW, clause=f"{GW}#13", kind="negative")
def test_goblin_cant_attack_with_a_weapon_not_in_its_stat_block(game):
    b, gob = goblin_vs_brom(game)
    in_combat(game, gob, b)
    assert_refused_cleanly(game, C.attack, game, gob, b, attack_name="longsword")


# ---------------------------------------------------------------- #14 Darkvision 60 ft.
@pytest.mark.srd(GW, clause=f"{GW}#14", kind="positive")
def test_goblin_sees_a_creature_60_feet_away_in_darkness(game):
    li = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (60, 0), name="Gob")
    game.scene.light = "dark"
    assert game.can_see(gob, li)
    game.dice.force_str("d20=[2,2]")
    r = C.attack(game, gob, li, attack_name="shortbow")
    assert not any("can't see" in s and s.startswith("Gob") for s in r.roll.dis)


@pytest.mark.srd(GW, clause=f"{GW}#14", kind="boundary")
def test_goblin_cant_see_a_creature_65_feet_away_in_darkness(game):
    li = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (65, 0), name="Gob")
    game.scene.light = "dark"
    assert not game.can_see(gob, li)
    game.dice.force_str("d20=[2]")  # LIDDA can't see the goblin either: Advantage and Disadvantage cancel
    r = C.attack(game, gob, li, attack_name="shortbow")
    assert any("Gob can't see LIDDA" in s for s in r.roll.dis)


@pytest.mark.srd(GW, clause=f"{GW}#14", kind="negative")
def test_darkvision_doesnt_let_the_goblin_see_an_invisible_creature(game):
    li = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0), name="Gob")
    game.scene.light = "dark"
    li.add_condition("invisible", "test")
    assert not game.can_see(gob, li)


# ---------------------------------------------------------------- #15 Passive Perception 9
@pytest.mark.srd(GW, clause=f"{GW}#15", kind="positive")
def test_goblin_passive_perception_9_finds_a_hide_total_of_9(game):
    li = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    assert gob.passive("perception") == 9
    li.hidden_total = 9
    assert actions.notices(game, gob, li)


@pytest.mark.srd(GW, clause=f"{GW}#15", kind="boundary")
def test_goblin_passive_perception_9_misses_a_hide_total_of_10(game):
    li = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    li.hidden_total = 10
    assert not actions.notices(game, gob, li)
    assert li.hidden_total == 10


@pytest.mark.srd(GW, clause=f"{GW}#15", kind="negative")
def test_a_poisoned_goblins_passive_perception_drops_to_4(game):
    gob = mon(game, "goblin warrior", (30, 0))
    gob.add_condition("poisoned", "test")
    assert gob.passive("perception") == 4


# ---------------------------------------------------------------- #16 Languages Common, Goblin
@pytest.mark.srd(GW, clause=f"{GW}#16", kind="positive")
def test_goblin_speaks_common_and_goblin(game):
    gob = mon(game, "goblin warrior", (30, 0))
    assert set(gob.languages) == {"common", "goblin"}


# ---------------------------------------------------------------- #17 CR 1/4 (XP 50; PB +2)
@pytest.mark.srd(GW, clause=f"{GW}#17", kind="positive")
def test_defeating_a_goblin_warrior_is_worth_50_xp(game):
    b = pc(game, "BROM", (0, 0))
    li = pc(game, "LIDDA", (0, 5))
    gob = mon(game, "goblin warrior", (5, 0))
    assert gob.cr == 0.25 and gob.pb == 2
    assert award_xp(game, [gob], [b]) == 50
    assert award_xp(game, [gob], [b, li]) == 25


@pytest.mark.srd(GW, clause=f"{GW}#17", kind="boundary")
def test_goblin_grapple_dc_is_9_from_str_minus_1_and_pb_2(game):
    b, gob = goblin_vs_brom(game)
    bonus = b.save_bonus_total("str") if b.score("str") >= b.score("dex") else b.save_bonus_total("dex")
    game.dice.force_str(f"d20=[{9 - bonus}]")
    assert not C.grapple(game, gob, b)  # a save total of 9 meets DC 9
    assert "DC 9" in game.log.last("save").text
    game.dice.force_str(f"d20=[{8 - bonus}]")
    assert C.grapple(game, gob, b) and b.has("grappled")


# ---------------------------------------------------------------- #18 Scimitar +4, reach 5 ft.
@pytest.mark.srd(GW, clause=f"{GW}#18", kind="positive")
def test_scimitar_attack_adds_4_and_hits_at_equal_ac(game):
    b, gob = goblin_vs_brom(game)
    ac = b.ac()
    game.dice.force_str(f"d20=[{ac - 4}]; d6=[1]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.roll.total == ac and r.hit


@pytest.mark.srd(GW, clause=f"{GW}#18", kind="negative")
def test_scimitar_attack_isnt_strength_based(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[10]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.roll.total != 10 - 1 + 2 and r.roll.total == 14


@pytest.mark.srd(GW, clause=f"{GW}#18", kind="boundary")
def test_scimitar_cant_reach_a_target_10_feet_away(game):
    b, gob = goblin_vs_brom(game, gob_pos=(10, 0))
    in_combat(game, gob, b)
    assert_refused_cleanly(game, C.attack, game, gob, b, attack_name="scimitar", match="reach")


@pytest.mark.srd(GW, clause=f"{GW}#18", kind="abuse")
def test_goblin_gets_one_scimitar_attack_per_action(game):
    b, gob = goblin_vs_brom(game)
    in_combat(game, gob, b)
    game.dice.force_str("d20=[2]")
    C.attack(game, gob, b, attack_name="scimitar")
    assert_refused_cleanly(game, C.attack, game, gob, b, attack_name="scimitar")


@pytest.mark.srd(GW, clause=f"{GW}#18", kind="abuse")
def test_goblin_scimitar_attack_through_the_session_out_of_reach_is_refused(game):
    b, gob = goblin_vs_brom(game, gob_pos=(10, 0))
    in_combat(game, gob, b)
    s = Session(game)
    s.auto_gm = False
    assert_refused_cleanly(
        game, s.execute, {"cmd": "attack", "actor": gob.id, "target": b.id, "weapon": "scimitar"}
    )


# ---------------------------------------------------------------- #19 Hit: 5 (1d6 + 2) Slashing
@pytest.mark.srd(GW, clause=f"{GW}#19", kind="positive")
def test_scimitar_hit_deals_1d6_plus_2_slashing(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[19]; d6=[3]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.hit and r.damage == 5 and b.hp == 95
    assert "Slashing" in game.log.last("damage_roll").text


@pytest.mark.srd(GW, clause=f"{GW}#19", kind="negative")
def test_scimitar_critical_hit_doubles_the_d6_not_the_2(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[20]; d6=[1,1]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.crit and r.damage == 4


@pytest.mark.srd(GW, clause=f"{GW}#19", kind="boundary")
def test_scimitar_static_damage_is_5(game):
    b, gob = goblin_vs_brom(game)
    game.fixed_monster_damage = True
    game.dice.force_str("d20=[19]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.damage == 5


# ---------------------------------------------------------------- #20 +1d4 Slashing with Advantage
@pytest.mark.srd(GW, clause=f"{GW}#20", kind="positive")
def test_scimitar_with_advantage_adds_1d4_slashing(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[3,19]; d6=[1]; d4=[2]")
    r = C.attack(game, gob, b, attack_name="scimitar", adv=["test"])
    assert r.roll.mode == "advantage" and r.damage == 1 + 2 + 2


@pytest.mark.srd(GW, clause=f"{GW}#20", kind="negative")
def test_scimitar_without_advantage_adds_no_1d4(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[19]; d6=[1]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.damage == 3


@pytest.mark.srd(GW, clause=f"{GW}#20", kind="negative")
def test_scimitar_with_disadvantage_adds_no_1d4(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[19,19]; d6=[1]")
    r = C.attack(game, gob, b, attack_name="scimitar", dis=["test"])
    assert r.roll.mode == "disadvantage" and r.damage == 3


@pytest.mark.srd(GW, clause=f"{GW}#20", kind="boundary", ruling="R-23")
def test_scimitar_with_cancelled_advantage_adds_no_1d4(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[19]; d6=[1]")
    r = C.attack(game, gob, b, attack_name="scimitar", adv=["test"], dis=["test"])
    assert r.roll.mode == "normal" and r.damage == 3


@pytest.mark.srd(GW, clause=f"{GW}#20", kind="positive", ruling="R-24")
def test_scimitar_critical_hit_with_advantage_doubles_the_1d4_too(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[20,5]; d6=[1,1]; d4=[1,1]")
    r = C.attack(game, gob, b, attack_name="scimitar", adv=["test"])
    assert r.crit and r.damage == 1 + 1 + 2 + 1 + 1


@pytest.mark.srd(GW, clause=f"{GW}#20", kind="positive")
@pytest.mark.xfail(
    strict=True,
    reason="T-72: with static monster damage the Advantage rider's static 2 is dropped; "
    "the hit deals 5, not 7",
)
def test_scimitar_static_damage_with_advantage_is_7(game):
    b, gob = goblin_vs_brom(game)
    game.fixed_monster_damage = True
    game.dice.force_str("d20=[3,19]")
    r = C.attack(game, gob, b, attack_name="scimitar", adv=["test"])
    assert r.damage == 5 + 2


@pytest.mark.srd(GW, clause=f"{GW}#20", kind="positive")
def test_an_unseen_goblins_scimitar_attack_has_advantage_and_adds_1d4(game):
    b, gob = goblin_vs_brom(game)
    gob.add_condition("invisible", "test")
    b.senses.pop("darkvision", None)
    game.dice.force_str("d20=[3,19]; d6=[1]; d4=[4]")
    r = C.attack(game, gob, b, attack_name="scimitar")
    assert r.roll.mode == "advantage" and r.damage == 1 + 2 + 4


# ---------------------------------------------------------------- #21 Shortbow +4, range 80/320
@pytest.mark.srd(GW, clause=f"{GW}#21", kind="positive")
def test_shortbow_at_80_feet_adds_4_with_no_range_disadvantage(game):
    b, gob = goblin_vs_brom(game, gob_pos=(80, 0))
    game.dice.force_str("d20=[2]")
    r = C.attack(game, gob, b, attack_name="shortbow")
    assert r.roll.total == 6 and r.roll.mode == "normal"


@pytest.mark.srd(GW, clause=f"{GW}#21", kind="boundary")
def test_shortbow_at_85_feet_has_long_range_disadvantage(game):
    b, gob = goblin_vs_brom(game, gob_pos=(85, 0))
    game.dice.force_str("d20=[2,2]")
    r = C.attack(game, gob, b, attack_name="shortbow")
    assert r.roll.mode == "disadvantage" and any("normal range" in s for s in r.roll.dis)


@pytest.mark.srd(GW, clause=f"{GW}#21", kind="boundary")
def test_shortbow_reaches_320_feet_but_not_325(game):
    b, gob = goblin_vs_brom(game, gob_pos=(320, 0))
    in_combat(game, gob, b)
    game.dice.force_str("d20=[2,2]")
    assert C.attack(game, gob, b, attack_name="shortbow").roll.mode == "disadvantage"
    game.combat.turn.actions_used = 0
    gob.position = (325, 0)
    assert_refused_cleanly(game, C.attack, game, gob, b, attack_name="shortbow", match="long range")


@pytest.mark.srd(GW, clause=f"{GW}#21", kind="negative")
def test_shortbow_fired_next_to_an_enemy_has_disadvantage(game):
    b, gob = goblin_vs_brom(game)
    game.dice.force_str("d20=[2,2]")
    r = C.attack(game, gob, b, attack_name="shortbow")
    assert any("within 5 ft" in s for s in r.roll.dis)


# ---------------------------------------------------------------- #22 Hit: 5 (1d6 + 2) Piercing
@pytest.mark.srd(GW, clause=f"{GW}#22", kind="positive")
def test_shortbow_hit_deals_1d6_plus_2_piercing(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    game.dice.force_str("d20=[19]; d6=[4]")
    r = C.attack(game, gob, b, attack_name="shortbow")
    assert r.damage == 6 and "Piercing" in game.log.last("damage_roll").text


@pytest.mark.srd(GW, clause=f"{GW}#22", kind="negative")
def test_shortbow_critical_hit_doubles_the_d6_not_the_2(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    game.dice.force_str("d20=[20]; d6=[6,6]")
    r = C.attack(game, gob, b, attack_name="shortbow")
    assert r.crit and r.damage == 14


@pytest.mark.srd(GW, clause=f"{GW}#22", kind="boundary")
def test_shortbow_minimum_damage_is_3(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    game.dice.force_str("d20=[19]; d6=[1]")
    assert C.attack(game, gob, b, attack_name="shortbow").damage == 3


# ---------------------------------------------------------------- #23 +1d4 Piercing with Advantage
@pytest.mark.srd(GW, clause=f"{GW}#23", kind="positive")
def test_shortbow_with_advantage_adds_1d4_piercing(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    game.dice.force_str("d20=[3,19]; d6=[1]; d4=[3]")
    r = C.attack(game, gob, b, attack_name="shortbow", adv=["test"])
    assert r.damage == 1 + 2 + 3


@pytest.mark.srd(GW, clause=f"{GW}#23", kind="negative")
def test_shortbow_without_advantage_adds_no_1d4(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    game.dice.force_str("d20=[19]; d6=[1]")
    assert C.attack(game, gob, b, attack_name="shortbow").damage == 3


@pytest.mark.srd(GW, clause=f"{GW}#23", kind="boundary", ruling="R-23")
def test_shortbow_advantage_cancelled_by_long_range_adds_no_1d4(game):
    b, gob = goblin_vs_brom(game, gob_pos=(100, 0))
    game.dice.force_str("d20=[19]; d6=[1]")
    r = C.attack(game, gob, b, attack_name="shortbow", adv=["test"])
    assert r.roll.mode == "normal" and r.damage == 3


# ---------------------------------------------------------------- #24 Nimble Escape
@pytest.mark.srd(GW, clause=f"{GW}#24", kind="positive")
def test_nimble_escape_disengages_as_a_bonus_action_and_leaves_the_action(game):
    b, gob = goblin_vs_brom(game)
    in_combat(game, gob, b)
    CA.nimble_escape(game, gob, "disengage")
    t = game.combat.turn
    assert t.bonus_used and t.actions_used == 0
    C.move(game, gob, to=(30, 0))
    assert game.combat.has_reaction(b) and b.hp == 100
    game.dice.force_str("d20=[2]")
    C.attack(game, gob, b, attack_name="shortbow")
    assert t.actions_used == 1


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="positive")
def test_nimble_escape_hides_as_a_bonus_action(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    in_combat(game, gob, b)
    game.dice.force_str("d20=[9]")
    CA.nimble_escape(game, gob, "hide", cover="three-quarters")
    assert gob.has("invisible") and gob.hidden_total == 15
    assert game.combat.turn.bonus_used and game.combat.turn.actions_used == 0


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="negative")
def test_without_nimble_escape_the_goblin_moving_away_provokes(game):
    b, gob = goblin_vs_brom(game)
    in_combat(game, gob, b)
    game.answer("opportunity_attack", True)
    game.dice.force_str("d20=[2]")
    C.move(game, gob, to=(30, 0))
    assert not game.combat.has_reaction(b)


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="negative")
def test_nimble_escape_hide_needs_cover_or_heavy_obscurement(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    in_combat(game, gob, b)
    assert_refused_cleanly(game, CA.nimble_escape, game, gob, "hide", match="plain view")


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="boundary")
def test_nimble_escape_hide_fails_on_a_stealth_total_of_14_and_spends_the_bonus_action(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    in_combat(game, gob, b)
    game.dice.force_str("d20=[8]")
    r = CA.nimble_escape(game, gob, "hide", cover="three-quarters")
    assert r.total == 14 and not gob.has("invisible") and game.combat.turn.bonus_used


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="abuse")
def test_nimble_escape_only_once_per_turn(game):
    b, gob = goblin_vs_brom(game, gob_pos=(30, 0))
    in_combat(game, gob, b)
    CA.nimble_escape(game, gob, "disengage")
    assert_refused_cleanly(
        game, CA.nimble_escape, game, gob, "hide", cover="three-quarters", match="Bonus Action"
    )


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="abuse")
@pytest.mark.xfail(
    strict=True,
    reason="T-73: a Bonus Action taken out of turn is refused (\"It isn't Gob's turn\") "
    "without citing a page",
)
def test_nimble_escape_out_of_turn_is_refused(game):
    b, gob = goblin_vs_brom(game)
    in_combat(game, b, gob)
    assert_refused_cleanly(game, CA.nimble_escape, game, gob, "disengage")


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="abuse")
def test_nimble_escape_while_incapacitated_is_refused(game):
    b, gob = goblin_vs_brom(game)
    in_combat(game, gob, b)
    gob.add_condition("incapacitated", "test")
    assert_refused_cleanly(game, CA.nimble_escape, game, gob, "disengage")


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="abuse")
@pytest.mark.xfail(
    strict=True,
    reason="T-74: Nimble Escape for a creature without the trait is refused without citing a page",
)
def test_a_bandit_has_no_nimble_escape(game):
    b = pc(game, "BROM", (0, 0))
    bandit = mon(game, "bandit", (5, 0))
    in_combat(game, bandit, b)
    assert_refused_cleanly(game, CA.nimble_escape, game, bandit, "disengage")


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="abuse")
@pytest.mark.xfail(
    strict=True,
    reason="T-75: the disengage command takes bonus=True from anyone; a bandit without Nimble Escape "
    "Disengages as a Bonus Action",
)
def test_a_bandit_cant_disengage_as_a_bonus_action_through_the_session(game):
    b = pc(game, "BROM", (0, 0))
    bandit = mon(game, "bandit", (5, 0))
    in_combat(game, bandit, b)
    s = Session(game)
    s.auto_gm = False
    assert_refused_cleanly(game, s.execute, {"cmd": "disengage", "actor": bandit.id, "bonus": True})
