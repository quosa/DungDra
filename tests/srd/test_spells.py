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


@pytest.mark.srd(BLESS, clause=f"{BLESS}#1", kind="negative")
def test_a_wizard_cant_cast_bless(game):
    j, b, _, m = party(game)
    assert "wizard" not in S.SPELLS["bless"]["lists"]
    assert_refused_cleanly(game, S.cast, game, m, "bless", [b])


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


@pytest.mark.srd(BLESS, clause=f"{BLESS}#3", kind="positive", ruling="P-10")
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


@pytest.mark.xfail(
    strict=True,
    reason="T-20: casting a V,S,M spell without its material component first stows the held weapon "
    "(free object interaction, log entry), then refuses",
)
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


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="positive", ruling="P-9")
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


@pytest.mark.xfail(
    strict=True,
    reason="T-21: Bless's target cap is checked inside _bless, after the slot is spent and Concentration "
    "starts; the refusal also cites no page",
)
@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="boundary")
def test_four_targets_with_a_level_1_slot_is_refused_cleanly(game):
    j, b, li, m = party(game)
    assert_refused_cleanly(game, S.cast, game, j, "bless", [j, b, li, m], match="up to 3")


@pytest.mark.srd(BLESS, clause=f"{BLESS}#6", kind="boundary")
def test_four_targets_with_a_level_1_slot_blesses_nobody(game):
    j, b, li, m = party(game)
    with pytest.raises(S.Refusal):
        S.cast(game, j, "bless", [j, b, li, m])
    assert not any(c.find_effects("Bless") for c in (j, b, li, m))


@pytest.mark.xfail(
    strict=True,
    reason="T-21: Bless's target cap is checked inside _bless, after the slot is spent and Concentration "
    "starts; the refusal also cites no page",
)
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


@pytest.mark.xfail(
    strict=True, reason="T-22: Bless accepts a non-creature target and crashes instead of refusing it"
)
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


@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive", ruling="P-9")
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


@pytest.mark.xfail(
    strict=True,
    reason="T-23: death_save doesn't gather effects, so Bless adds no 1d4 to a Death Saving Throw",
)
@pytest.mark.srd(BLESS, clause=f"{BLESS}#7", kind="positive", ruling="P-8")
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


# ---------------------------------------------------------------- #8 one additional creature per slot level above 1
@pytest.mark.srd(BLESS, clause=f"{BLESS}#8", kind="positive")
def test_a_level_2_slot_blesses_four_creatures(game):
    j, b, li, m = party(game)
    level3(j)
    S.cast(game, j, "bless", [j, b, li, m], slot=2)
    assert all(c.find_effects("Bless") for c in (j, b, li, m))
    assert j.slots_left(2) == 1 and j.slots_left(1) == 4


@pytest.mark.xfail(
    strict=True,
    reason="T-21: Bless's target cap is checked inside _bless, after the slot is spent and Concentration "
    "starts; the refusal also cites no page",
)
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
