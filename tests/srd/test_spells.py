"""SRD rule tests for Spells › Spell Descriptions (SRD 5.2.1 p.107+)."""

import pytest

from dungdra import combat as C
from dungdra import spells as S
from dungdra.api import Session
from tests.support.helpers import mon, pc
from tests.support.srd import assert_refused_cleanly

BLESS = "SPELL.bless"

GOBLIN_AC = 15  # Goblin Warrior stat block


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


def bless_mods(roll):
    return [(v, s) for v, s in roll.mods if s.startswith("Bless")]


def party(game):
    """JOZAN (cleric) at the origin with BROM, LIDDA and MIALEE within 30 feet."""
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (5, 0))
    li = pc(game, "LIDDA", (10, 0))
    m = pc(game, "MIALEE", (15, 0))
    return j, b, li, m


def level3(c):
    c.award_xp(900)  # level 3: four level 1 slots, two level 2 slots
    return c


# ---------------------------------------------------------------- #1 Level 1 Enchantment (Cleric, Paladin)
@pytest.mark.srd(BLESS, clause=f"{BLESS}#1", kind="positive")
def test_bless_is_a_level_1_cleric_spell_cast_with_a_level_1_slot(game):
    j, b, _, _ = party(game)
    assert j.slots_left(1) == 2
    S.cast(game, j, "bless", [b])
    assert j.slots_left(1) == 1
    assert S.SPELLS["bless"]["level"] == 1 and S.SPELLS["bless"]["school"] == "enchantment"
    assert {"cleric", "paladin"} <= set(S.SPELLS["bless"]["lists"])


@pytest.mark.srd(BLESS, clause=f"{BLESS}#1", kind="abuse")
def test_bless_needs_a_slot_when_none_are_left(game):
    j, b, _, _ = party(game)
    j.slots_used = {1: 2}
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="no level 1")


# ---------------------------------------------------------------- #2 Casting Time: Action
@pytest.mark.srd(BLESS, clause=f"{BLESS}#2", kind="positive")
def test_casting_bless_takes_the_action(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (60, 0))
    in_combat(game, j, gob)
    assert game.combat.turn.actions_used == 0
    S.cast(game, j, "bless", [b])
    assert game.combat.turn.actions_used == 1
    assert b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#2", kind="negative")
def test_bless_cant_be_cast_after_the_action_is_spent(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (60, 0))
    in_combat(game, j, gob)
    game.combat.spend(j, "action", "Dodge")
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b])
    assert not b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#2", kind="abuse")
def test_bless_through_the_session_when_the_action_is_spent_is_refused(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (60, 0))
    in_combat(game, j, gob)
    game.combat.spend(j, "action", "Dodge")
    s = Session(game)
    assert_refused_cleanly(
        game, s.execute, {"cmd": "cast", "spell": "bless", "actor": j.id, "targets": [b.id]}
    )


# ---------------------------------------------------------------- #3 Range: 30 feet
@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="boundary")
def test_bless_reaches_a_creature_exactly_30_feet_away(game):
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (30, 0))
    S.cast(game, j, "bless", [b])
    assert b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="boundary")
def test_bless_cant_reach_a_creature_35_feet_away(game):
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (35, 0))
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="range")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="abuse")
def test_one_out_of_range_target_refuses_the_whole_casting(game):
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (5, 0))
    li = pc(game, "LIDDA", (40, 0))
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b, li], match="range")
    assert not b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="positive", ruling="R-14")
def test_a_target_that_moves_beyond_30_feet_stays_blessed(game):
    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b])
    b.position = (120, 0)
    game.dice.force_str("d20=[10]; d4=[2]")
    r = b.save("wis", 10)
    assert bless_mods(r) == [(2, "Bless (1d4=[2])")]


@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="abuse")
def test_out_of_range_through_the_session_is_refused(game):
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (35, 0))
    s = Session(game)
    assert_refused_cleanly(
        game, s.execute, {"cmd": "cast", "spell": "bless", "actor": j.id, "targets": [b.id]}
    )


@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="negative")
def test_bless_range_is_measured_from_the_caster_not_from_another_target(game):
    # LIDDA is 10 ft from BROM but 40 ft from JOZAN: range runs from the caster only
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (30, 0))
    li = pc(game, "LIDDA", (40, 0))
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b, li], match="range")
    assert not b.find_effects("Bless") and not li.find_effects("Bless")


# ---------------------------------------------------------------- #4 Components: V, S, M (Holy Symbol 5+ GP)
def drop_holy_symbol(j, free_hands=True):
    if free_hands:
        j.wielded = []  # the Somatic hand isn't what these tests are about
    for it in list(j.inventory):
        if it.name == "holy symbol":
            j.inventory.remove(it, it.qty)


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="positive")
def test_bless_with_a_holy_symbol_works(game):
    j, b, _, _ = party(game)
    assert j.inventory.find("holy symbol") is not None
    S.cast(game, j, "bless", [b])
    assert b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="negative")
def test_bless_without_a_holy_symbol_is_refused(game):
    j, b, _, _ = party(game)
    drop_holy_symbol(j)
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="boundary")
def test_a_component_pouch_doesnt_replace_the_costed_holy_symbol(game):
    j, b, _, _ = party(game)
    drop_holy_symbol(j)
    j.inventory.add("component pouch")
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="abuse")
def test_holy_water_isnt_the_material_component(game):
    # the 2014 component was holy water; 2024 needs the Holy Symbol
    j, b, _, _ = party(game)
    drop_holy_symbol(j)
    j.inventory.add("holy water")
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="abuse")
def test_a_refused_bless_doesnt_stow_the_casters_weapon(game):
    j, b, _, _ = party(game)
    drop_holy_symbol(j, free_hands=False)
    assert j.wielded
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="negative")
def test_bless_cant_be_cast_while_gagged(game):
    j, b, _, _ = party(game)
    j.notes["gagged"] = True
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Verbal")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="negative")
def test_bless_cant_be_cast_in_magical_silence(game):
    j, b, _, _ = party(game)
    game.scene.silence = True
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Silence")


def holy_symbol_worth(j, gp, qty=1):
    """Replace JOZAN's Holy Symbol with one worth `gp` GP (a `cost` in CP)."""
    drop_holy_symbol(j)
    return j.inventory.add("holy symbol", qty, cost=gp * 100)


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="boundary")
def test_a_holy_symbol_worth_exactly_5_gp_is_enough(game):
    j, b, _, _ = party(game)
    holy_symbol_worth(j, 5)
    S.cast(game, j, "bless", [b])
    assert b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="boundary")
def test_a_holy_symbol_worth_4_gp_isnt_enough(game):
    j, b, _, _ = party(game)
    holy_symbol_worth(j, 4)
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")
    assert not b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="positive")
def test_a_holy_symbol_worth_more_than_5_gp_works(game):
    j, b, _, _ = party(game)
    holy_symbol_worth(j, 25)
    S.cast(game, j, "bless", [b])
    assert b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="positive")
def test_bless_doesnt_consume_the_holy_symbol(game):
    # the component has a cost but the spell doesn't say it consumes it
    j, b, li, _ = party(game)
    level3(j)
    holy_symbol_worth(j, 5)
    assert j.inventory.count("holy symbol") == 1
    S.cast(game, j, "bless", [b])
    assert j.inventory.count("holy symbol") == 1
    S.cast(game, j, "bless", [li])
    assert li.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="abuse")
def test_cheap_holy_symbols_dont_add_up_to_5_gp(game):
    j, b, _, _ = party(game)
    holy_symbol_worth(j, 3, qty=2)
    j.inventory.add("holy symbol", 1, cost=300)
    assert j.inventory.count("holy symbol") == 3  # 9 GP in all, but none is worth 5 GP
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="abuse")
def test_a_component_pouch_doesnt_top_up_a_cheap_holy_symbol(game):
    j, b, _, _ = party(game)
    holy_symbol_worth(j, 4)
    j.inventory.add("component pouch")
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b], match="Holy Symbol")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#4", kind="abuse")
def test_a_cheap_holy_symbol_through_the_session_is_refused(game):
    j, b, _, _ = party(game)
    holy_symbol_worth(j, 4)
    s = Session(game)
    assert_refused_cleanly(
        game, s.execute, {"cmd": "cast", "spell": "bless", "actor": j.id, "targets": [b.id]}
    )


# ---------------------------------------------------------------- #5 Duration: Concentration, up to 1 minute
@pytest.mark.srd(BLESS, clause=f"{BLESS}#5", kind="positive")
def test_bless_is_a_concentration_spell(game):
    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b])
    assert j.concentrating == "Bless"


@pytest.mark.srd(BLESS, clause=f"{BLESS}#5", kind="boundary")
def test_bless_lasts_up_to_one_minute(game):
    j, b, li, _ = party(game)
    S.cast(game, j, "bless", [b, li])
    game.advance(54)
    assert b.find_effects("Bless") and li.find_effects("Bless")
    game.advance(6)
    assert not b.find_effects("Bless") and not li.find_effects("Bless")
    assert j.concentrating is None


@pytest.mark.srd(BLESS, clause=f"{BLESS}#5", kind="negative")
def test_losing_concentration_ends_bless_on_every_target(game):
    j, b, li, _ = party(game)
    S.cast(game, j, "bless", [j, b, li])
    j.add_condition("incapacitated")
    assert j.concentrating is None
    assert not any(c.find_effects("Bless") for c in (j, b, li))
    game.dice.force_str("d20=[10]")
    r = b.save("wis", 10)
    assert bless_mods(r) == []


@pytest.mark.srd(BLESS, clause=f"{BLESS}#5", kind="abuse")
def test_a_second_concentration_spell_ends_bless(game):
    j, b, _, _ = party(game)
    j.prepared.append("shield of faith")
    S.cast(game, j, "bless", [b])
    S.cast(game, j, "shield of faith", b)
    assert j.concentrating == "Shield Of Faith"
    assert not b.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#5", kind="abuse")
def test_recasting_bless_on_new_targets_ends_the_first_casting(game):
    j, b, li, _ = party(game)
    S.cast(game, j, "bless", [b])
    S.cast(game, j, "bless", [li])
    assert li.find_effects("Bless") and not b.find_effects("Bless")


# ---------------------------------------------------------------- #6 up to three creatures within range
@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="positive")
def test_bless_blesses_three_creatures(game):
    j, b, li, m = party(game)
    S.cast(game, j, "bless", [b, li, m])
    assert all(c.find_effects("Bless") for c in (b, li, m))
    assert not j.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="positive", ruling="R-13")
def test_the_caster_can_bless_themself(game):
    j, b, li, _ = party(game)
    S.cast(game, j, "bless", [j, b, li])
    assert all(c.find_effects("Bless") for c in (j, b, li))


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="negative")
def test_only_the_chosen_creatures_are_blessed(game):
    j, b, li, m = party(game)
    gob = mon(game, "goblin warrior", (20, 0))
    S.cast(game, j, "bless", [b])
    assert b.find_effects("Bless")
    assert not any(c.find_effects("Bless") for c in (j, li, m, gob))


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="positive")
def test_bless_can_target_a_monster(game):
    # "creatures": any creature, not only allies
    j = pc(game, "JOZAN", (0, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    S.cast(game, j, "bless", [gob])
    assert gob.find_effects("Bless")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="boundary")
def test_four_targets_with_a_level_1_slot_is_refused_cleanly(game):
    j, b, li, m = party(game)
    assert_refused_cleanly(game, S.cast, game, j, "bless", [j, b, li, m], match="up to 3")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="abuse")
def test_four_targets_through_the_session_costs_nothing(game):
    j, b, li, m = party(game)
    s = Session(game)
    assert_refused_cleanly(
        game,
        s.execute,
        {"cmd": "cast", "spell": "bless", "actor": j.id, "targets": [j.id, b.id, li.id, m.id]},
    )


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="abuse")
def test_naming_a_target_twice_gives_only_one_d4(game):
    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b, b])
    game.dice.force_str("d20=[10]; d4=[3]")
    r = b.save("wis", 10)
    assert bless_mods(r) == [(3, "Bless (1d4=[3])")]


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="abuse")
def test_bless_cant_target_an_object(game):
    j, b, _, _ = party(game)
    game.scene.objects["door"] = {}
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b, "door"])


# ---------------------------------------------------------------- #7 adds 1d4 to attack rolls and saves
@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive")
def test_bless_adds_1d4_to_an_attack_roll(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (10, 0))
    gob.base_max_hp = gob.hp = 500
    S.cast(game, j, "bless", [b])
    b.position = (gob.position[0] - 5, 0)
    # BROM's longsword: +5. A 7 alone totals 12 and misses AC 15; the d4's 3 makes it 15, a hit
    game.dice.force_str("d20=[7]; d4=[3]; d8=[4]")
    r = C.attack(game, b, gob, weapon="longsword")
    assert bless_mods(r.roll) == [(3, "Bless (1d4=[3])")]
    assert r.roll.total == GOBLIN_AC and r.hit


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive")
def test_bless_adds_1d4_to_a_saving_throw_automatically(game):
    # 2024 "adds": no prompt, no game.answer needed
    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[8]; d4=[2]")
    r = b.save("wis", 10)
    assert bless_mods(r) == [(2, "Bless (1d4=[2])")]
    assert r.total == 10 and r.success


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive", ruling="R-13")
def test_bless_adds_1d4_to_the_casters_concentration_save(game):
    j, b, _, _ = party(game)
    j.base_max_hp = j.hp = 40
    S.cast(game, j, "bless", [j, b])
    # DC 10; JOZAN's Con save is +1 (no proficiency): 7 + 1 = 8 fails, + d4 2 = 10 holds
    game.dice.force_str("d20=[7]; d4=[2]")
    j.take_damage(6, "slashing")
    r = game.log.last("save")
    assert "Bless" in r.text
    assert j.concentrating == "Bless"


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive", ruling="R-12")
def test_bless_adds_1d4_to_a_death_saving_throw(game):
    from dungdra.damage import death_save

    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b])
    b.hp = 0
    # 8 fails a Death Saving Throw on its own; the d4's 2 makes it 10, a success
    game.dice.force_str("d20=[8]; d4=[2]")
    r = death_save(game, b)
    assert bless_mods(r) == [(2, "Bless (1d4=[2])")]
    assert b.death_saves == {"success": 1, "failure": 0}


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="negative")
def test_bless_adds_nothing_to_an_ability_check(game):
    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[10]")
    r = b.check("athletics", dc=10)
    assert bless_mods(r) == []


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="negative")
def test_bless_adds_nothing_to_initiative(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (60, 0))
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[10, 5, 1]")
    C.roll_initiative(game, [b, j, gob])
    init = [e for e in game.log.of_kind("initiative") if "BROM" in e.text]
    assert init and all("Bless" not in e.text for e in init)


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="negative")
def test_a_creature_that_wasnt_targeted_gets_no_d4(game):
    j, b, li, _ = party(game)
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[10]")
    r = li.save("dex", 10)
    assert bless_mods(r) == []


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="negative")
def test_no_d4_after_the_spell_ends(game):
    j, b, _, _ = party(game)
    S.cast(game, j, "bless", [b])
    game.advance(60)
    game.dice.force_str("d20=[10]")
    r = b.save("wis", 10)
    assert bless_mods(r) == []


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="boundary")
def test_bless_adds_one_d4_to_an_attack_with_advantage(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 500
    b.position = (0, 5)
    gob.add_condition("prone")  # melee attack within 5 feet: Advantage
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[4, 9]; d4=[1]; d8=[4]")
    r = C.attack(game, b, gob, weapon="longsword")
    assert r.roll.mode == "advantage"
    assert bless_mods(r.roll) == [(1, "Bless (1d4=[1])")]


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive", ruling="R-13")
def test_bless_adds_1d4_to_a_spell_attack_roll(game):
    # a spell attack is an attack roll: Guiding Bolt from a blessed caster gets the d4
    j = pc(game, "JOZAN", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    gob.base_max_hp = gob.hp = 500
    S.cast(game, j, "bless", [j])
    d20 = GOBLIN_AC - j.spell_attack_bonus() - 3  # misses by 3 alone; the d4's 3 makes it a hit
    start = len(game.log.events)
    game.dice.force_str(f"d20=[{d20}]; d4=[3]; d6=[1,1,1,1]")
    S.cast(game, j, "guiding bolt", gob)
    attack = [e for e in game.log.since(start) if "Guiding Bolt" in e.text and "Bless" in e.text]
    assert attack, "the spell attack roll shows the Bless d4"
    assert gob.hp == 500 - 4


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="negative")
def test_bless_adds_nothing_to_a_damage_roll(game):
    j, b, _, _ = party(game)
    gob = mon(game, "goblin warrior", (10, 0))
    gob.base_max_hp = gob.hp = 500
    S.cast(game, j, "bless", [b])
    b.position = (gob.position[0] - 5, 0)
    rolled = len(game.dice.history)
    game.dice.force_str("d20=[15]; d4=[1]; d8=[4]")
    r = C.attack(game, b, gob, weapon="longsword")
    assert r.hit and bless_mods(r.roll) == [(1, "Bless (1d4=[1])")]
    d4s = [v for sides, v, _ in game.dice.history[rolled:] if sides == 4]
    assert d4s == [1], "only the attack roll gets a d4"


# ---------------------------------------------------- #8 one additional creature per slot level above 1
@pytest.mark.srd(BLESS, clause=f"{BLESS}#8", kind="positive")
def test_a_level_2_slot_blesses_four_creatures(game):
    j, b, li, m = party(game)
    level3(j)
    S.cast(game, j, "bless", [j, b, li, m], slot=2)
    assert all(c.find_effects("Bless") for c in (j, b, li, m))
    assert j.slots_left(2) == 1 and j.slots_left(1) == 4


@pytest.mark.srd(BLESS, clause=f"{BLESS}#8", kind="abuse")
def test_upcasting_bless_without_a_level_2_slot_is_refused(game):
    # a level 1 cleric has no level 2 slot to buy the fourth target with
    j, b, li, m = party(game)
    assert j.slots_left(2) == 0
    assert_refused_cleanly(game, S.cast, game, j, "bless", [j, b, li, m], slot=2)
    assert not any(c.find_effects("Bless") for c in (j, b, li, m))


@pytest.mark.srd(BLESS, clause=f"{BLESS}#8", kind="boundary")
def test_five_targets_with_a_level_2_slot_is_refused_cleanly(game):
    j, b, li, m = party(game)
    level3(j)
    gob = mon(game, "goblin warrior", (20, 0))
    assert_refused_cleanly(game, S.cast, game, j, "bless", [j, b, li, m, gob], slot=2, match="up to 4")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#8", kind="negative")
def test_a_level_2_slot_doesnt_raise_the_d4(game):
    j, b, _, _ = party(game)
    level3(j)
    S.cast(game, j, "bless", [b], slot=2)
    game.dice.force_str("d20=[10]; d4=[4]")
    r = b.save("wis", 10)
    assert bless_mods(r) == [(4, "Bless (1d4=[4])")]


# ==================================================================================================
# SPELL.casting-spells.effects.targets (p.106): Targets
# ==================================================================================================
TARGETS = "SPELL.casting-spells.effects.targets"


def hold_person_caster(game, pos=(0, 0)):
    """JOZAN at level 3 (two level 2 slots) with Hold Person prepared."""
    j = level3(pc(game, "JOZAN", pos))
    j.prepared.append("hold person")
    return j


def player_text_since(game, start):
    return " ".join(e.text for e in game.log.since(start) if e.visibility == "player")


def unbeatable_dc(c):
    """Raise the caster's spellcasting ability so no d20 save can reach the DC (2024: a natural
    20 isn't an automatic success on a saving throw), so a target that rolls at all fails."""
    c.abilities[c.spell_ability] = 40
    return c.spell_dc()


# ---------------------------------------------------------------- #1 the description says what it targets
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#1", kind="positive")
def test_light_targets_the_object_its_description_names(game):
    j = pc(game, "JOZAN", (0, 0))
    game.scene.objects["torch"] = {"position": (5, 0)}
    S.cast(game, j, "light", ["torch"])
    assert game.scene.objects["torch"]["light"] == [20, 20]


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#1", kind="negative")
def test_ray_of_frost_cant_target_an_object(game):
    m = pc(game, "MIALEE", (0, 0))
    game.scene.objects["crate"] = {}
    assert_refused_cleanly(game, S.cast, game, m, "ray of frost", ["crate"])


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#1", kind="abuse")
def test_light_cant_target_a_creature(game):
    m = pc(game, "MIALEE", (0, 0))
    b = pc(game, "BROM", (5, 0))
    assert_refused_cleanly(game, S.cast, game, m, "light", [b])


# ---------------------------------------------------------------- #2 clear path: not behind Total Cover


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#2", kind="positive")
def test_total_cover_refusal_through_the_session(game):
    j = pc(game, "JOZAN", (0, 0))
    bandit = mon(game, "bandit", (20, 0))
    game.scene.cover_all[bandit.id] = "total"
    s = Session(game)
    assert_refused_cleanly(
        game, s.execute, {"cmd": "cast", "spell": "guiding bolt", "actor": j.id, "targets": [bandit.id]}
    )


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#2", kind="negative")
def test_three_quarters_cover_doesnt_stop_targeting(game):
    j = pc(game, "JOZAN", (0, 0))
    bandit = mon(game, "bandit", (20, 0))
    game.scene.cover_all[bandit.id] = "three-quarters"
    game.dice.force_str("d20=[1]")
    S.cast(game, j, "guiding bolt", bandit)
    assert j.slots_left(1) == 1
    assert bandit.hp == bandit.max_hp


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#2", kind="negative")
def test_a_creature_in_the_line_doesnt_stop_targeting(game):
    j = pc(game, "JOZAN", (0, 0))
    mon(game, "goblin warrior", (10, 0), name="G1")  # Half Cover only (R-09)
    bandit = mon(game, "bandit", (20, 0))
    game.dice.force_str("d20=[1]")
    S.cast(game, j, "guiding bolt", bandit)
    assert j.slots_left(1) == 1


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#2", kind="abuse")
def test_a_creature_behind_total_cover_cant_be_one_of_several_bless_targets(game):
    j, b, li, _ = party(game)
    game.scene.cover_all[li.id] = "total"
    assert_refused_cleanly(game, S.cast, game, j, "bless", [b, li], match="Total Cover")
    assert not b.find_effects("Bless")


# ---------------------------------------------------------------- #3 targeting yourself
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#3", kind="positive")
def test_cure_wounds_can_target_the_caster(game):
    j = pc(game, "JOZAN", (0, 0))
    j.hp = 1
    game.dice.force_str("d8=[4,5]")
    S.cast(game, j, "cure wounds", [j])
    assert j.hp == min(j.max_hp, 1 + 9 + j.mod("wis"))


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#3", kind="positive")
def test_healing_word_on_yourself_through_the_session(game):
    j = pc(game, "JOZAN", (0, 0))
    j.hp = 1
    game.dice.force_str("d4=[2,3]")
    out = Session(game).execute({"cmd": "cast", "spell": "healing word", "actor": j.id, "targets": [j.id]})
    assert out.get("ok") is not False, out
    assert j.hp >= 1 + 5


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#3", kind="positive")
def test_mage_armor_can_target_the_caster(game):
    m = pc(game, "MIALEE", (0, 0))
    S.cast(game, m, "mage armor", [m])
    assert m.notes.get("mage_armor") and m.ac() == 13 + m.mod("dex")


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#3", kind="positive")
def test_magic_missile_darts_can_go_to_the_caster(game):
    # "one or more creatures of your choice": the caster may be one of them
    m = pc(game, "MIALEE", (0, 0))
    m.base_max_hp = m.hp = 30
    game.answer("shield", False, who=m)  # MIALEE doesn't Shield herself against her own darts
    game.dice.force_str("d4=[1,1,1]")
    S.cast(game, m, "magic missile", [m])
    assert m.hp == 30 - 3 * (1 + 1)


# ------------------------------------------------------------ #4 the area determines what the spell targets
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#4", kind="positive", ruling="R-16")
def test_burning_hands_hits_a_creature_in_the_cone_that_wasnt_named(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    near = mon(game, "goblin warrior", (5, 0), name="NEAR")
    named = mon(game, "goblin warrior", (10, 0), name="NAMED")
    near.base_max_hp = near.hp = named.base_max_hp = named.hp = 30
    # aimed due east: both goblins are in the 15-ft Cone; both fail their saves
    game.dice.force_str("d6=[2,2,2]; d20=[1,1]")
    S.cast(game, m, "burning hands", [named], point=(15, 0))
    assert named.hp == 30 - 6
    assert near.hp == 30 - 6


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#4", kind="negative")
def test_a_named_creature_outside_the_cone_isnt_affected(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    far = mon(game, "goblin warrior", (30, 0), name="FAR")
    game.dice.force_str("d6=[2,2,2]")
    S.cast(game, m, "burning hands", [far])
    assert far.hp == 10
    assert not game.log.of_kind("save")


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#4", kind="abuse", ruling="R-16")
def test_one_cone_cant_reach_both_sides_of_the_caster(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    east = mon(game, "goblin warrior", (5, 0), name="EAST")
    west = mon(game, "goblin warrior", (-5, 0), name="WEST")
    east.hp = west.hp = 30
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    S.cast(game, m, "burning hands", [east, west])
    assert [east.hp < 30, west.hp < 30].count(True) == 1


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#4", kind="abuse", ruling="R-16")
def test_sleep_doesnt_reach_a_creature_outside_its_sphere(game):
    m = pc(game, "MIALEE", (0, 0))
    g = mon(game, "goblin warrior", (10, 0), name="G")
    start = len(game.log.events)
    S.cast(game, m, "sleep", [g], point=(60, 0))
    assert not [e for e in game.log.since(start) if e.kind == "save"]
    assert not g.has("incapacitated")


# ---------------------------------------------------------------- #5 area shapes
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#5", kind="positive")
def test_area_spells_name_one_of_the_area_shapes(game):
    shapes = {"cone", "cube", "cylinder", "emanation", "line", "sphere"}
    assert S.SPELLS["burning hands"]["area"] == ("cone", 15)
    assert S.SPELLS["thunderwave"]["area"] == ("cube", 15)
    assert S.SPELLS["sleep"]["area"] == ("sphere", 5)
    assert S.SPELLS["web"]["area"] == ("cube", 20)
    assert all(sd["area"][0] in shapes for sd in S.SPELLS.values() if sd.get("area"))


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#5", kind="negative")
def test_single_target_spells_have_no_area(game):
    for spell in ("guiding bolt", "hold person", "cure wounds", "fire bolt", "magic missile"):
        assert not S.SPELLS[spell].get("area"), spell


# ---------------------------------------------------------------- #8 invalid target: nothing happens
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#8", kind="positive", ruling="R-15")
def test_hold_person_does_nothing_to_a_wolf_that_couldnt_have_saved(game):
    # a DC no d20 save can reach: had the Wolf been affected at all, it would be Paralyzed
    j = hold_person_caster(game)
    assert unbeatable_dc(j) > 20 + 1  # the Wolf's Wis save is +1
    wolf = mon(game, "wolf", (20, 0))
    rolled = len(game.dice.history)
    S.cast(game, j, "hold person", wolf)
    assert not wolf.has("paralyzed")
    assert wolf.hp == wolf.max_hp and not wolf.conditions()
    assert len(game.dice.history) == rolled


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#8", kind="abuse", ruling="R-15")
def test_hold_person_on_a_wolf_through_the_session_spends_the_slot_and_does_nothing(game):
    j = hold_person_caster(game)
    unbeatable_dc(j)
    wolf = mon(game, "wolf", (20, 0))
    out = Session(game).execute({"cmd": "cast", "spell": "hold person", "actor": j.id, "targets": [wolf.id]})
    assert out.get("ok") is not False, out
    assert j.slots_left(2) == 1
    assert not wolf.has("paralyzed")


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#8", kind="negative")
def test_hold_person_paralyzes_a_humanoid_that_fails(game):
    j = hold_person_caster(game)
    bandit = mon(game, "bandit", (20, 0))
    game.dice.force_str("d20=[2]")
    S.cast(game, j, "hold person", bandit)
    assert bandit.has("paralyzed")


# ---------------------------------------------------------------- #9 the slot is still expended
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#9", kind="positive")
def test_the_slot_is_spent_on_an_invalid_target(game):
    j = hold_person_caster(game)
    wolf = mon(game, "wolf", (20, 0))
    assert j.slots_left(2) == 2
    S.cast(game, j, "hold person", wolf)
    assert j.slots_left(2) == 1


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#9", kind="negative")
def test_a_target_out_of_range_is_refused_before_the_slot_is_spent(game):
    # the slot is spent when the spell is cast; a target the caster can't choose stops the casting
    j = hold_person_caster(game)
    wolf = mon(game, "wolf", (65, 0))
    assert_refused_cleanly(game, S.cast, game, j, "hold person", wolf, match="range")
    assert j.slots_left(2) == 2


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#9", kind="abuse")
def test_mage_armor_on_an_armored_creature_isnt_a_half_refusal(game):
    m = pc(game, "MIALEE", (0, 0))
    b = pc(game, "BROM", (5, 0))
    ac = b.ac()
    try:
        assert_refused_cleanly(game, S.cast, game, m, "mage armor", [b])
    except AssertionError:
        # not refused: then it was cast at an invalid target and nothing happened to BROM
        assert m.slots_left(1) == 1
        assert b.ac() == ac and not b.notes.get("mage_armor")


# ---------------------------------------------------------------- #10 appears to succeed on the save
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#10", kind="positive")
def test_an_invalid_target_appears_to_succeed_without_rolling(game):
    j = hold_person_caster(game)
    wolf = mon(game, "wolf", (20, 0))
    rolled = len(game.dice.history)
    start = len(game.log.events)
    S.cast(game, j, "hold person", wolf)
    assert len(game.dice.history) == rolled, "the invalid target didn't attempt a save"
    saves = [e for e in game.log.since(start) if e.kind == "save" and e.visibility == "player"]
    assert saves and "succeeds" in saves[-1].text


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#10", kind="abuse")
def test_an_invalid_target_gives_the_player_no_hint(game):
    # probing a creature's type by casting at it: the player sees only a successful save
    j = hold_person_caster(game)
    wolf = mon(game, "wolf", (20, 0))
    start = len(game.log.events)
    S.cast(game, j, "hold person", wolf)
    seen = player_text_since(game, start).lower()
    for hint in ("invalid", "humanoid", "beast", "immune", "no effect", "nothing"):
        assert hint not in seen, hint


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#10", kind="negative")
def test_a_valid_target_really_rolls_its_save(game):
    j = hold_person_caster(game)
    bandit = mon(game, "bandit", (20, 0))
    rolled = len(game.dice.history)
    game.dice.force_str("d20=[19]")
    S.cast(game, j, "hold person", bandit)
    assert not bandit.has("paralyzed")
    assert len(game.dice.history) == rolled + 1


# ---------------------------------------------------------------- #11 otherwise: the spell did nothing
@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#11", kind="positive", ruling="R-15")
def test_mage_armor_on_an_armored_creature_visibly_does_nothing(game):
    m = pc(game, "MIALEE", (0, 0))
    b = pc(game, "BROM", (5, 0))
    ac = b.ac()
    start = len(game.log.events)
    S.cast(game, m, "mage armor", [b])
    assert m.slots_left(1) == 1
    assert b.ac() == ac and not b.notes.get("mage_armor")
    told = [e for e in game.log.since(start) if e.visibility == "player" and e.applies(TARGETS)]
    assert told, "the caster perceives that the spell did nothing to the target"


@pytest.mark.srd(TARGETS, clause=f"{TARGETS}#11", kind="negative")
def test_a_save_spell_on_an_invalid_target_doesnt_say_it_did_nothing(game):
    j = hold_person_caster(game)
    wolf = mon(game, "wolf", (20, 0))
    start = len(game.log.events)
    S.cast(game, j, "hold person", wolf)
    player = [e for e in game.log.since(start) if e.visibility == "player"]
    assert all(e.kind == "save" for e in player if e.applies(TARGETS))
