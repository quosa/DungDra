"""Unit tests for dungdra.spells: casting logs the rule of the spell cast."""

import json
from pathlib import Path

import pytest

from dungdra.combat import roll_initiative
from dungdra.data.equipment import GP
from dungdra.data.spells import SPELLS, Restriction, spell_rule
from dungdra.rules import Refusal
from dungdra.spells import Casting, _affected_targets, _material, _save_for_half, cast, is_creature
from tests.support.helpers import mon, pc

UNITS = {json.loads(line)["id"] for line in Path("docs/srd/units.jsonl").read_text().splitlines()}


def test_every_spell_names_its_srd_unit():
    assert {n: spell_rule(n) for n in SPELLS if spell_rule(n) not in UNITS} == {}


def test_spell_rule_slugs_the_name():
    assert spell_rule("cure wounds") == "SPELL.cure-wounds"
    assert spell_rule("tasha's hideous laughter") == "SPELL.tashas-hideous-laughter"


def test_a_cast_logs_the_spells_rule(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    game.dice.force_str("d20=[15]")
    cast(game, mialee, "fire bolt", targets=[gob])
    assert game.log.last("cast").rule == "SPELL.fire-bolt"
    assert game.log.last("attack").rule == "SPELL.casting-spells.effects.attack-rolls"


def test_an_out_of_range_spell_is_refused_under_the_range_rule(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (500, 0))
    with pytest.raises(Refusal) as exc:
        cast(game, mialee, "fire bolt", targets=[gob])
    assert exc.value.rule == "SPELL.casting-spells.range"


def test_a_target_behind_total_cover_is_refused_under_the_clear_path_clause(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    game.scene.cover_all[gob.id] = "total"
    with pytest.raises(Refusal) as exc:
        cast(game, mialee, "fire bolt", targets=[gob])
    assert (exc.value.rule, exc.value.page) == ("SPELL.casting-spells.effects.targets#2", 106)


def _jozan_holding_his_mace(game):
    jozan = pc(game, "JOZAN", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    assert jozan.wielded
    return jozan, brom


def _drop(c, name):
    while (it := c.inventory.find(name)) is not None:
        c.inventory.remove(it, it.qty)


def test_a_bless_refused_for_its_material_keeps_the_weapon_in_hand(game):
    jozan, brom = _jozan_holding_his_mace(game)
    _drop(jozan, "holy symbol")
    held = list(jozan.wielded)
    with pytest.raises(Refusal) as exc:
        cast(game, jozan, "bless", [brom])
    assert exc.value.rule == "SPELL.casting-spells.components.material-m"
    assert jozan.wielded == held
    assert game.log.last("interact") is None


def test_a_costed_component_is_checked_against_the_spells_own_item(game):
    jozan, _ = _jozan_holding_his_mace(game)
    _drop(jozan, "holy symbol")
    sd = dict(
        SPELLS["bless"], material="a spyglass worth 1,000+ GP", material_item="spyglass", material_cost=1000
    )
    with pytest.raises(Refusal, match="spyglass"):
        _material(jozan, "bless", sd, None)
    jozan.inventory.add("holy symbol")
    with pytest.raises(Refusal):  # a holy symbol doesn't stand in for another spell's component
        _material(jozan, "bless", sd, None)
    jozan.inventory.add("spyglass")
    _material(jozan, "bless", sd, None)


def test_a_costed_component_worth_less_than_its_price_is_refused(game):
    jozan, brom = _jozan_holding_his_mace(game)
    _drop(jozan, "holy symbol")
    jozan.inventory.add("holy symbol", cost=4 * GP)
    with pytest.raises(Refusal) as exc:
        cast(game, jozan, "bless", [brom])
    assert exc.value.rule == "SPELL.casting-spells.components.material-m"
    jozan.inventory.add("holy symbol", cost=5 * GP)
    cast(game, jozan, "bless", [brom])
    assert brom.find_effects("Bless")


def test_bless_names_its_holy_symbol_and_price():
    assert SPELLS["bless"]["material_item"] == "holy symbol"
    assert SPELLS["bless"]["material_cost"] == 5


def test_a_somatic_hand_is_freed_only_once_the_cast_goes_ahead(game):
    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))  # mace and shield: no free hand
    with pytest.raises(Refusal):
        cast(game, jozan, "cure wounds", [pc(game, "LIDDA", (500, 0))])  # out of range
    assert len(jozan.wielded) == 2
    cast(game, jozan, "cure wounds", [brom])
    assert len(jozan.wielded) == 1
    assert game.log.last("interact").rule == "SPELL.casting-spells.components.somatic-s"


def test_bless_with_a_holy_symbol_needs_no_free_hand(game):
    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))
    cast(game, jozan, "bless", [brom])
    assert len(jozan.wielded) == 2  # the Holy Symbol is the focus: the M hand also does the S
    assert brom.find_effects("Bless")


def test_a_material_component_without_pouch_or_focus_is_refused(game):
    mialee = pc(game, "MIALEE", (0, 0))
    cast(game, mialee, "mage armor", [mialee])  # spellbook and quarterstaff are her focus
    assert mialee.find_effects("Mage Armor")
    _drop(mialee, "spellbook")
    _drop(mialee, "quarterstaff")
    with pytest.raises(Refusal, match="Component Pouch") as exc:
        cast(game, mialee, "mage armor", [mialee])
    assert exc.value.rule == "SPELL.casting-spells.components.material-m"


def test_no_weapon_is_stowed_once_the_free_interaction_is_spent(game):
    from dungdra import combat

    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))
    game.dice.force_str("d20=[20,1]")
    combat.roll_initiative(game, [jozan, brom])
    assert game.combat.is_turn(jozan)
    game.combat.turn.free_interaction = True
    with pytest.raises(Refusal, match="free object interaction"):
        cast(game, jozan, "cure wounds", [brom])
    assert len(jozan.wielded) == 2
    assert game.combat.turn.actions_used == 0


def _bless_party(game):
    return [pc(game, n, (5 * i, 0)) for i, n in enumerate(("JOZAN", "BROM", "LIDDA", "MIALEE"))]


def test_too_many_bless_targets_are_refused_before_anything_is_spent(game):
    jozan, *others = party = _bless_party(game)
    with pytest.raises(Refusal, match="up to 3 creatures") as exc:
        cast(game, jozan, "bless", party)
    assert (exc.value.rule, exc.value.page) == ("SPELL.bless#6", 113)
    assert jozan.slots_left(1) == 2 and jozan.concentrating is None
    assert not any(c.find_effects("Bless") for c in party)
    assert game.log.last("cast") is None


def test_naming_a_creature_more_than_once_still_counts_against_the_cap(game):
    jozan, brom, _, _ = _bless_party(game)
    with pytest.raises(Refusal, match="up to 3 creatures"):
        cast(game, jozan, "bless", [brom] * 4)
    assert jozan.slots_left(1) == 2


def test_a_higher_slot_raises_the_cap_and_cites_the_upcast_clause(game):
    jozan, *_ = party = _bless_party(game)
    jozan.award_xp(900)  # level 3: level 2 slots
    gob = mon(game, "goblin warrior", (20, 0))
    with pytest.raises(Refusal, match="up to 4 creatures") as exc:
        cast(game, jozan, "bless", [*party, gob], slot=2)
    assert exc.value.rule == "SPELL.bless#8"
    assert jozan.slots_left(2) == 2
    cast(game, jozan, "bless", party, slot=2)
    assert all(c.find_effects("Bless") for c in party)


def test_an_object_among_bless_targets_is_refused_before_anything_is_spent(game):
    jozan, brom, _, _ = _bless_party(game)
    game.scene.objects["door"] = {}
    with pytest.raises(Refusal, match="'door' isn't one") as exc:
        cast(game, jozan, "bless", [brom, "door"])
    assert (exc.value.rule, exc.value.page) == ("SPELL.bless#6", 113)
    assert jozan.slots_left(1) == 2 and jozan.concentrating is None
    assert not brom.find_effects("Bless")
    assert game.log.last("cast") is None


@pytest.mark.parametrize(
    "spell", ["command", "hold person", "aid", "invisibility", "cure wounds", "guiding bolt", "sanctuary"]
)
def test_each_creature_only_spell_refuses_a_non_creature_target_under_its_own_rule(game, spell):
    from dungdra.spells import _target_kind

    with pytest.raises(Refusal, match="targets creatures") as exc:
        _target_kind(spell, SPELLS[spell], ["door"])
    assert (exc.value.rule, exc.value.page) == (spell_rule(spell), SPELLS[spell]["page"])


def test_is_creature_tells_a_creature_from_an_object_name_or_point(game):
    assert is_creature(pc(game, "MIALEE"))
    assert is_creature(mon(game, "goblin warrior"))
    assert not is_creature("door")
    assert not is_creature({"web": True})
    assert not is_creature((10, 5))


def test_a_spell_that_can_target_an_object_accepts_one(game):
    from dungdra.spells import _target_kind

    assert SPELLS["fire bolt"]["targets"] is None  # "a creature or an object" (p.132)
    _target_kind("fire bolt", SPELLS["fire bolt"], ["door"])


def test_an_object_only_spell_refuses_a_creature_and_accepts_an_object(game):
    from dungdra.spells import _target_kind

    _, brom = _jozan_holding_his_mace(game)
    with pytest.raises(Refusal, match=f"Light targets an object, and {brom.name} is a creature") as exc:
        _target_kind("light", SPELLS["light"], [brom])
    assert (exc.value.rule, exc.value.page) == ("SPELL.casting-spells.effects.targets#1", 106)
    _target_kind("light", SPELLS["light"], ["lantern"])


def test_a_refused_light_on_a_creature_lights_nothing(game):
    jozan, brom = _jozan_holding_his_mace(game)
    with pytest.raises(Refusal, match="targets an object"):
        cast(game, jozan, "light", [brom])
    assert not any(o.get("light_spell") for o in game.scene.objects.values())
    assert game.log.last("cast") is None


def test_every_capped_spell_is_creature_only():
    assert [n for n, sd in SPELLS.items() if "max_targets" in sd and sd["targets"] != "creature"] == []


def test_an_uncapped_creature_only_spell_refuses_an_object_before_anything_is_spent(game):
    jozan, brom = _jozan_holding_his_mace(game)
    jozan.wielded.append(jozan.inventory.find("shield"))  # a cast that went ahead would stow the mace
    game.scene.objects["door"] = {}
    assert "max_targets" not in SPELLS["cure wounds"]
    with pytest.raises(Refusal, match="Cure Wounds targets creatures, and 'door' isn't one") as exc:
        cast(game, jozan, "cure wounds", ["door"])
    assert (exc.value.rule, exc.value.page) == ("SPELL.cure-wounds", 121)
    assert jozan.slots_left(1) == 2 and len(jozan.wielded) == 2
    assert game.log.last("cast") is None
    cast(game, jozan, "cure wounds", [brom])  # a creature is still a valid target
    assert game.log.last("cast").rule == "SPELL.cure-wounds"


@pytest.mark.parametrize(
    "spell, level, cap",
    [("command", 1, 1), ("command", 3, 3), ("hold person", 2, 1), ("hold person", 4, 3), ("aid", 4, 3)],
)
def test_each_capped_spell_refuses_one_target_over_its_cap_under_its_own_rule(game, spell, level, cap):
    from dungdra.spells import _target_cap

    gobs = [mon(game, "goblin warrior", (5 * i, 0)) for i in range(cap + 1)]
    _target_cap(spell, SPELLS[spell], level, gobs[:cap])
    with pytest.raises(Refusal, match=f"up to {cap} creature") as exc:
        _target_cap(spell, SPELLS[spell], level, gobs)
    assert (exc.value.rule, exc.value.page) == (spell_rule(spell), SPELLS[spell]["page"])


def _goblins_in_a_line(game):
    mialee = pc(game, "MIALEE", (0, 0))
    front = mon(game, "goblin warrior", (5, 0), name="Front")
    back = mon(game, "goblin warrior", (10, 0), name="Back")  # Front stands in the line
    c = Casting("burning hands", mialee, level=1, ability="int", dc=13, attack=5)
    return c, front, back


def test_every_target_saves_before_any_target_takes_damage(game):
    c, front, back = _goblins_in_a_line(game)
    game.dice.force_str("d6=[3,4,5]; d20=[9]; d20=[9]")
    assert _save_for_half(game, c, [front, back], "dex", "3d6", "fire") == 12
    # Front fails (9+2) and dies, yet Back saved first, with Front's Half Cover (9+2+2)
    assert front.dead and back.hp == 10 - 6
    kinds = [e.kind for e in game.log.events if e.kind in ("save", "damage", "death")]
    assert kinds == ["save", "save", "damage", "death", "damage"]
    assert [e.rule for e in game.log.of_kind("cover")] == ["PLAY.combat.cover#5"]


def test_a_creature_dead_before_the_effect_gives_no_cover(game):
    c, front, back = _goblins_in_a_line(game)
    front.hp = 0
    front.dead = True
    game.dice.force_str("d6=[3,4,5]; d20=[9]")
    _save_for_half(game, c, [back], "dex", "3d6", "fire")
    assert back.dead and not game.log.of_kind("cover")


def test_on_fail_runs_only_for_a_living_target_that_failed(game):
    c, front, back = _goblins_in_a_line(game)
    hit = []
    game.dice.force_str("d6=[1,1,1]; d20=[9]; d20=[20]")
    _save_for_half(game, c, [front, back], "dex", "3d6", "fire", on_fail=hit.append)
    assert hit == [front] and front.hp == 10 - 3 and back.hp == 10 - 1


def test_mage_armor_on_an_armored_creature_spends_the_slot_and_says_it_did_nothing(game):
    mialee = pc(game, "MIALEE", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    ac = brom.ac()
    start = len(game.log.events)
    cast(game, mialee, "mage armor", [brom])
    assert mialee.slots_left(1) == 1
    assert brom.ac() == ac and not brom.notes.get("mage_armor")
    new = game.log.since(start)
    told = [e for e in new if e.kind == "spell" and e.visibility == "player"]
    assert told[-1].text == "Mage Armor does nothing to BROM"
    assert (told[-1].rule, told[-1].ruling, told[-1].page) == (
        "SPELL.casting-spells.effects.targets#11",
        "R-15",
        "106",
    )
    why = [e for e in new if e.kind == "invalid_target"]
    assert len(why) == 1 and why[0].visibility == "gm" and "wearing armor" in why[0].text
    assert (why[0].rule, why[0].ruling) == ("SPELL.casting-spells.effects.targets#8", "R-15")


def test_hold_person_on_a_non_humanoid_appears_to_save_under_r15(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.award_xp(900)  # level 3: two level 2 slots
    jozan.prepared.append("hold person")
    wolf = mon(game, "wolf", (20, 0))
    start = len(game.log.events)
    rolled = len(game.dice.history)
    cast(game, jozan, "hold person", [wolf])
    assert jozan.slots_left(2) == 1 and len(game.dice.history) == rolled
    assert not wolf.has("paralyzed")
    new = game.log.since(start)
    saves = [e for e in new if e.kind == "save" and e.visibility == "player"]
    assert saves[-1].text == "Wolf succeeds on its Wisdom saving throw against Hold Person"
    assert (saves[-1].rule, saves[-1].ruling) == ("SPELL.casting-spells.effects.targets#10", "R-15")
    assert not [e for e in new if e.kind == "spell" and "does nothing" in e.text]
    assert [e.visibility for e in new if e.kind == "invalid_target"] == ["gm"]


def test_a_spell_restriction_routes_failing_targets_to_r15_and_keeps_the_rest(game):
    wolf = mon(game, "wolf", (20, 0))
    brom = pc(game, "BROM", (5, 0))
    sd = {
        "restrict": Restriction(lambda t: t.ctype == "humanoid", lambda t: f"{t.name} is no Humanoid", "wis")
    }
    start = len(game.log.events)
    assert _affected_targets(game, "hold person", sd, [wolf, brom, "a rock"]) == [brom, "a rock"]
    new = game.log.since(start)
    assert [e.text for e in new if e.kind == "save"] == [
        "Wolf succeeds on its Wisdom saving throw against Hold Person"
    ]
    assert [e.text for e in new if e.kind == "invalid_target"] == [
        "Wolf is no Humanoid: invalid target for Hold Person; the slot is spent and nothing happens to it"
    ]


def test_a_restriction_without_a_save_says_the_spell_did_nothing(game):
    brom = pc(game, "BROM", (5, 0))
    sd = {"restrict": Restriction(lambda t: False, lambda t: "never")}
    start = len(game.log.events)
    assert _affected_targets(game, "mage armor", sd, [brom]) == []
    new = game.log.since(start)
    assert [e.text for e in new if e.kind == "spell"] == ["Mage Armor does nothing to BROM"]
    assert not [e for e in new if e.kind == "save"]


def test_an_unrestricted_spell_affects_every_target(game):
    brom = pc(game, "BROM", (5, 0))
    start = len(game.log.events)
    assert _affected_targets(game, "bless", {"restrict": None}, [brom]) == [brom]
    assert game.log.since(start) == []


def test_mage_armor_with_no_target_named_wards_the_caster(game):
    mialee = pc(game, "MIALEE", (0, 0))
    cast(game, mialee, "mage armor")
    assert mialee.notes.get("mage_armor") and mialee.find_effects("Mage Armor")


def test_self_defaulting_spells_say_so_in_their_data():
    assert {n for n, sd in SPELLS.items() if sd["default_self"]} >= {
        "mage armor",
        "guidance",
        "shield of faith",
    }


def test_guidance_and_shield_of_faith_with_no_target_named_affect_the_caster(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.prepared.append("shield of faith")
    cast(game, jozan, "guidance")
    assert jozan.find_effects("Guidance")
    cast(game, jozan, "shield of faith")
    assert jozan.find_effects("Shield of Faith")


def test_a_named_target_overrides_the_self_default(game):
    jozan = pc(game, "JOZAN", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    cast(game, jozan, "guidance", [brom])
    assert brom.find_effects("Guidance") and not jozan.find_effects("Guidance")


def test_restricted_spells_carry_the_restriction_in_their_data():
    restricted = {n for n, sd in SPELLS.items() if sd["restrict"] is not None}
    assert restricted >= {"mage armor", "hold person"}
    assert SPELLS["hold person"]["restrict"].save == "wis"
    assert SPELLS["mage armor"]["restrict"].save is None


def test_a_cone_aimed_at_the_first_named_creature_skips_one_behind_the_caster(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    east = mon(game, "goblin warrior", (5, 0), name="EAST")
    west = mon(game, "goblin warrior", (-5, 0), name="WEST")
    east.hp = west.hp = 30
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    cast(game, m, "burning hands", [west, east])
    assert west.hp == 24 and east.hp == 30
    game.log.assert_applied(rule="SPELL.casting-spells.effects.targets#4")


def test_sleep_at_a_point_only_reaches_creatures_in_its_sphere(game):
    m = pc(game, "MIALEE", (0, 0))
    near = mon(game, "goblin warrior", (35, 0), name="NEAR")
    far = mon(game, "goblin warrior", (10, 0), name="FAR")
    game.dice.force_str("d20=[1]")
    cast(game, m, "sleep", [near, far], point=(40, 0))
    assert near.has("incapacitated") and not far.has("incapacitated")
    assert len([e for e in game.log.events if e.kind == "save"]) == 1
    game.log.assert_applied(rule="SPELL.casting-spells.effects.targets#4")


def test_sleep_without_a_point_takes_the_named_creatures_as_inside(game):
    m = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[1]")
    cast(game, m, "sleep", [gob])
    assert gob.has("incapacitated")


def test_a_cone_aimed_at_a_point_follows_the_point(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    east = mon(game, "goblin warrior", (5, 0), name="EAST")
    west = mon(game, "goblin warrior", (-5, 0), name="WEST")
    east.hp = west.hp = 30
    game.dice.force_str("d6=[2,2,2]; d20=[1]")
    cast(game, m, "burning hands", [east, west], point=(-15, 0))
    assert west.hp == 24 and east.hp == 30


# ---------------- readied spells ----------------
def _in_combat(game, name, gob_pos=(30, 0)):
    caster = pc(game, name, (0, 0))
    gob = mon(game, "goblin warrior", gob_pos)
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [caster, gob])
    return caster, gob


def test_a_bonus_action_spell_cant_be_readied_and_spends_nothing(game):
    jozan, _ = _in_combat(game, "JOZAN")
    with pytest.raises(Refusal, match="casting time") as exc:
        cast(game, jozan, "healing word", [jozan], ready=True)
    assert (exc.value.page, exc.value.rule) == (187, "GLOSS.ready#7")
    assert jozan.slots_left(1) == 2 and not game.combat.turn.bonus_used


def test_a_readied_spell_pays_its_slot_but_not_the_action_and_holds_its_energy(game):
    mialee, gob = _in_combat(game, "MIALEE")
    c = cast(game, mialee, "magic missile", [gob], ready=True)
    assert mialee.slots_left(1) == 1
    assert game.combat.turn.actions_used == 0  # the Ready action pays for it
    assert mialee.concentrating == c.held == "Magic Missile (readied)"
    assert gob.hp == 10
    assert game.log.last("ready").ruling == "R-17"


def test_releasing_a_held_spell_ends_the_holding_and_takes_effect(game):
    mialee, gob = _in_combat(game, "MIALEE")
    c = cast(game, mialee, "magic missile", [gob], ready=True)
    game.dice.force_str("d4=[1,1,1]")
    c.release(game)
    assert gob.hp == 4
    assert not mialee.concentrating
    assert mialee.slots_left(1) == 1


def test_a_release_out_of_range_is_refused_before_the_holding_concentration_ends(game):
    mialee, gob = _in_combat(game, "MIALEE")
    c = cast(game, mialee, "magic missile", [gob], ready=True)
    gob.position = (200, 0)
    with pytest.raises(Refusal) as exc:
        c.release(game)
    assert exc.value.rule == "SPELL.casting-spells.range"
    assert mialee.concentrating == c.held
    assert gob.hp == 10


def test_a_release_the_spells_own_text_refuses_leaves_the_spell_held(game):
    jozan, gob = _in_combat(game, "JOZAN", gob_pos=(5, 0))
    gob.hp = 0
    c = cast(game, jozan, "spare the dying", [gob], ready=True)
    gob.hp = 3  # healed before the trigger: no longer a creature at 0 Hit Points
    with pytest.raises(Refusal) as exc:
        c.release(game)
    assert exc.value.rule == "SPELL.spare-the-dying"
    assert jozan.concentrating == c.held


def test_a_spells_own_refusal_comes_before_its_slot_is_spent(game):
    mialee, gob = _in_combat(game, "MIALEE")
    with pytest.raises(Refusal, match="creates 3 darts"):
        cast(game, mialee, "magic missile", [gob], option=[1, 1])
    assert mialee.slots_left(1) == 2
    assert game.combat.turn.actions_used == 0


def test_fire_bolt_at_a_missing_object_is_refused_before_the_cast_and_burns_one_that_is_there(game):
    mialee = pc(game, "MIALEE", (0, 0))
    with pytest.raises(Refusal, match="No target 'crate'"):
        cast(game, mialee, "fire bolt", ["crate"])
    assert game.log.last("cast") is None
    game.scene.objects["crate"] = {"flammable": True}
    cast(game, mialee, "fire bolt", ["crate"])
    assert game.scene.objects["crate"]["burning"]


def test_a_target_the_caster_cant_see_is_refused_before_the_slot(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    gob.add_condition("invisible")
    with pytest.raises(Refusal, match="can't be seen") as exc:
        cast(game, mialee, "magic missile", [gob])
    assert exc.value.rule == "SPELL.magic-missile"
    assert mialee.slots_left(1) == 2


def _casting(spell, caster, level):
    return Casting(spell, caster, level, "wis", 13, 5, None, False, "", None)


def test_a_command_word_is_checked_and_a_bad_one_refused(game):
    from dungdra.spells import CHECKS, IMPL

    jozan = pc(game, "JOZAN", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    with pytest.raises(Refusal, match="Command words"):
        CHECKS["command"](game, jozan, 1, [gob], None, "dance")
    game.dice.force_str("d20=[1]")
    IMPL["command"](game, _casting("command", jozan, 1), [gob], option="halt")
    assert "doesn't move" in str(game.log.last("spell"))


def test_lesser_restoration_refuses_a_condition_it_doesnt_end_and_ends_one_it_does(game):
    from dungdra.spells import CHECKS, IMPL

    jozan = pc(game, "JOZAN", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    brom.add_condition("poisoned")
    with pytest.raises(Refusal, match="ends Blinded, Deafened, Paralyzed or Poisoned"):
        CHECKS["lesser restoration"](game, jozan, 2, [brom], None, "charmed")
    CHECKS["lesser restoration"](game, jozan, 2, [brom], None, None)
    IMPL["lesser restoration"](game, _casting("lesser restoration", jozan, 2), [brom])
    assert not brom.has("poisoned")


@pytest.mark.parametrize(
    ("point", "match"), [(None, "Choose an unoccupied space"), ((40, 0), "up to 30 feet")]
)
def test_misty_step_refuses_a_missing_or_far_point(game, point, match):
    from dungdra.spells import CHECKS

    mialee = pc(game, "MIALEE", (0, 0))
    with pytest.raises(Refusal, match=match):
        CHECKS["misty step"](game, mialee, 2, [], point, None)
    CHECKS["misty step"](game, mialee, 2, [], (30, 0), None)


def test_scorching_ray_needs_a_target(game):
    from dungdra.spells import CHECKS

    with pytest.raises(Refusal, match="Choose targets for the rays"):
        CHECKS["scorching ray"](game, pc(game, "MIALEE", (0, 0)), 2, [], None, None)


def test_releasing_a_concentration_spell_concentrates_on_the_spell_itself(game):
    jozan, _ = _in_combat(game, "JOZAN")
    c = cast(game, jozan, "bless", [jozan], ready=True)
    assert "readied" in jozan.concentrating
    c.release(game)
    assert jozan.concentrating == "Bless"
