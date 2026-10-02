"""Unit tests for dungdra.spells: casting logs the rule of the spell cast."""

import json
from pathlib import Path

import pytest

from dungdra.data.equipment import GP
from dungdra.data.spells import SPELLS, spell_rule
from dungdra.rules import Refusal
from dungdra.spells import Casting, _material, _save_for_half, cast
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
