"""Unit tests for dungdra.combat: moving while dragging a creature."""

import pytest

from dungdra.combat import (
    MOVE_MODES,
    attack,
    end_combat,
    end_turn,
    escape_grapple,
    move,
    readied_attack,
    readied_move,
    ready,
    release_grapple,
    roll_initiative,
    stand_up,
)
from dungdra.effects import Condition, Flag, SpeedPenalty, grapplers_of
from dungdra.events import GM
from dungdra.mounted import mount
from dungdra.rules import Refusal
from dungdra.spells import cast
from tests.support.helpers import mon, pc
from tests.unit.helpers import grappled_by


def test_drag_refused_when_target_isnt_grappled(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    with pytest.raises(Refusal) as exc:
        move(game, brom, to=(-10, 0), drag=gob)
    assert exc.value.page == 182
    assert brom.position == (0, 0)
    assert gob.position == (5, 0)


def test_drag_refused_when_someone_else_is_the_grappler(game):
    brom = pc(game, "BROM", (0, 0))
    lidda = pc(game, "LIDDA", (5, 5))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    with pytest.raises(Refusal):
        move(game, lidda, to=(15, 5), drag=gob)
    assert lidda.position == (5, 5)
    assert gob.position == (5, 0)


def test_grappler_drags_its_grappled_target_along(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(-10, 0), drag=gob)
    assert brom.position == (-10, 0)
    assert gob.position == (-5, 0)


def test_grappler_carries_its_target_while_flying_at_extra_cost(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["fly"] = 30
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    cost = move(game, brom, to=(-10, 0), mode="fly", drag=gob)
    assert cost == 20
    assert gob.position == (-5, 0)


def test_flying_refused_without_a_fly_speed(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    with pytest.raises(Refusal) as exc:
        move(game, brom, to=(-10, 0), mode="fly", drag=gob)
    assert exc.value.page == 182
    assert brom.position == (0, 0)
    assert gob.position == (5, 0)


def test_grappler_carries_its_target_while_climbing_with_a_climb_speed(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["climb"] = 30
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    cost = move(game, brom, to=(-10, 0), mode="climb", drag=gob)
    assert cost == 20
    assert gob.position == (-5, 0)


def test_dragging_logs_the_movable_clause(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(-10, 0), drag=gob)
    [ev] = game.log.applied("GLOSS.grappled#4")
    assert ev.kind == "move" and ev.ruling is None


def test_a_tiny_grappler_dragging_a_tiny_creature_logs_ruling_r05(game):
    gob = mon(game, "goblin warrior", (0, 0))
    gob.size = "tiny"
    rat = mon(game, "giant rat", (5, 0))
    rat.size = "tiny"
    grappled_by(rat, gob)
    assert move(game, gob, to=(-10, 0), drag=rat) == 10
    game.log.assert_applied("GLOSS.grappled#4", ruling="R-05")


def test_dragging_a_creature_two_sizes_smaller_needs_no_ruling(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    rat.size = "tiny"
    grappled_by(rat, brom)
    assert move(game, brom, to=(-10, 0), drag=rat) == 10
    assert game.log.applied("GLOSS.grappled#4") and not game.log.applied(ruling="R-05")


def test_walking_logs_movement_without_a_grapple_rule(game):
    brom = pc(game, "BROM", (0, 0))
    move(game, brom, to=(-10, 0))
    assert game.log.last("move").rule == "PLAY.combat.movement-and-position"
    assert not game.log.applied("GLOSS.grappled")


def test_a_grappled_climber_is_refused_under_ruling_r07(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    grappled_by(rat, brom)
    with pytest.raises(Refusal) as exc:
        move(game, rat, to=(5, 10), mode="climb")
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.grappled#1", "R-07")


def test_a_grappled_walker_is_refused_by_the_rule_alone(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    with pytest.raises(Refusal) as exc:
        move(game, gob, to=(5, 10))
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.grappled#1", None)


def test_speed_zero_without_a_grapple_cites_speed(game):
    gob = mon(game, "goblin warrior", (5, 0))
    gob.speeds["walk"] = 0
    with pytest.raises(Refusal) as exc:
        move(game, gob, to=(5, 10))
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.speed", None)


def test_an_attack_by_a_creature_with_two_grapplers_logs_r06(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (0, 5))
    grappled_by(brom, gob)
    grappled_by(brom, bandit)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]")
    attack(game, brom, gob, weapon="longsword")
    [ev] = game.log.assert_applied("GLOSS.grappled#2", ruling="R-06")
    assert ev.visibility == GM
    assert game.log.last("attack").rule == "PLAY.combat.making-an-attack"


def test_a_grappler_walking_away_without_dragging_ends_the_grapple(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(-5, 0))
    assert grapplers_of(gob) == set()


def test_a_grappler_staying_within_5_feet_keeps_the_grapple(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    move(game, brom, to=(5, 5))
    assert grapplers_of(gob) == {brom.id}


def test_a_grappled_creature_moved_out_of_reach_is_freed_of_that_grappler_only(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    bandit = mon(game, "bandit", (10, 0))
    grappled_by(gob, brom)
    grappled_by(gob, bandit)
    move(game, gob, to=(15, 0), teleport=True)
    assert grapplers_of(gob) == {bandit.id}


def test_release_grapple_ends_the_condition_and_the_grapplers_flag(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    grappled_by(gob, brom)
    brom.add_effect(Flag("grappling", f"grappling {gob.name}", target=gob.id))
    release_grapple(game, gob)
    assert grapplers_of(gob) == set()
    assert not any(f.name == "grappling" for f in brom.effects)


def test_escape_grapple_refused_when_not_grappled(game):
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("restrained", "net", escape_dc=10)
    with pytest.raises(Refusal):
        escape_grapple(game, gob)
    assert gob.has("restrained")


def test_escape_grapple_checks_against_the_grapples_escape_dc(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("restrained", "net", escape_dc=30)
    gob.add_effect(Condition("grappled", "grappled", grappler=brom.id, escape_dc=15))
    game.dice.force_str("d20=[20]")
    r = escape_grapple(game, gob, skill="acrobatics")
    assert r.target == 15 and r.success
    assert grapplers_of(gob) == set()


def test_climbing_without_a_climb_speed_costs_an_extra_foot(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds.pop("climb", None)
    assert move(game, brom, to=(10, 0), mode="climb") == 20
    assert "climbing" in game.log.last("move").text


def test_swimming_without_a_swim_speed_in_difficult_terrain_costs_two_extra_feet(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds.pop("swim", None)
    assert move(game, brom, to=(10, 0), mode="swim", difficult=True) == 30
    assert "Difficult Terrain" not in game.log.last("move").text


def test_swimming_with_a_swim_speed_costs_no_extra(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["swim"] = 30
    assert move(game, brom, to=(10, 0), mode="swim") == 10
    assert "Swim Speed" in game.log.last("move").text


def test_a_climb_speed_reduced_to_0_falls_back_to_climbing_by_walking(game):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds["climb"] = 10
    brom.add_effect(SpeedPenalty("Ray of Frost", 10))
    assert move(game, brom, to=(10, 0), mode="climb") == 20
    assert "climbing" in game.log.last("move").text


def test_a_grappled_flyer_is_refused_for_speed_0_not_for_lacking_a_fly_speed(game):
    brom = pc(game, "BROM", (0, 0))
    rat = mon(game, "giant rat", (5, 0))
    rat.speeds["fly"] = 30
    grappled_by(rat, brom)
    with pytest.raises(Refusal) as exc:
        move(game, rat, to=(5, 10), mode="fly")
    assert (exc.value.rule, exc.value.ruling) == ("GLOSS.grappled#1", "R-07")
    assert rat.position == (5, 0)


@pytest.mark.parametrize("mode", ["climb", "swim", "fly"])
def test_a_prone_creature_is_refused_any_movement_but_crawling(game, mode):
    brom = pc(game, "BROM", (0, 0))
    brom.speeds[mode] = 30
    brom.add_effect(Condition("prone", "prone"))
    with pytest.raises(Refusal) as exc:
        move(game, brom, to=(10, 0), mode=mode)
    assert exc.value.page == 186
    assert exc.value.rule == "GLOSS.prone#1"
    assert brom.position == (0, 0)


def test_a_prone_creature_still_crawls_at_double_cost(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(Condition("prone", "prone"))
    assert move(game, brom, to=(10, 0), mode="crawl") == 20
    assert brom.position == (10, 0)


def test_a_prone_creature_walking_crawls_at_double_cost(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(Condition("prone", "prone"))
    assert move(game, brom, to=(10, 0), mode="walk") == 20
    assert brom.position == (10, 0)


def test_only_the_crawl_entry_of_the_move_modes_table_is_crawling():
    assert [name for name, spec in MOVE_MODES.items() if spec.crawling] == ["crawl"]


def test_crawling_costs_double_without_being_prone_and_walking_does_not(game):
    brom = pc(game, "BROM", (0, 0))
    assert move(game, brom, to=(10, 0), mode="crawl") == 20
    assert move(game, brom, to=(20, 0), mode="walk") == 10
    assert brom.position == (20, 0)


def test_a_prone_creature_is_refused_a_mode_outside_the_move_modes_table(game):
    brom = pc(game, "BROM", (0, 0))
    brom.add_effect(Condition("prone", "prone"))
    with pytest.raises(Refusal) as exc:
        move(game, brom, to=(10, 0), mode="burrow")
    assert (exc.value.page, exc.value.rule) == (186, "GLOSS.prone#1")
    assert brom.position == (0, 0)


def test_stand_up_refused_when_not_prone_cites_the_page(game):
    gob = mon(game, "goblin warrior", (0, 0))
    with pytest.raises(Refusal) as exc:
        stand_up(game, gob)
    assert (exc.value.page, exc.value.rule) == (186, "GLOSS.prone#2")
    assert not gob.has("prone")


def test_stand_up_refused_at_speed_zero(game):
    gob = mon(game, "goblin warrior", (0, 0))
    gob.add_condition("prone", "knocked down")
    gob.speeds["walk"] = 0
    with pytest.raises(Refusal) as exc:
        stand_up(game, gob)
    assert (exc.value.page, exc.value.rule) == (186, "GLOSS.prone#3")
    assert gob.has("prone")


def test_stand_up_ends_prone_for_half_speed(game):
    gob = mon(game, "goblin warrior", (0, 0))
    gob.add_condition("prone", "knocked down")
    assert stand_up(game, gob) == gob.speed() // 2
    assert not gob.has("prone")


def test_stand_up_refused_off_turn_in_combat(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [gob, brom])
    assert game.combat.is_turn(gob)
    brom.add_condition("prone", "knocked down")
    with pytest.raises(Refusal, match="own turn") as exc:
        stand_up(game, brom)
    assert (exc.value.page, exc.value.rule) == (186, "GLOSS.prone#2")
    assert brom.has("prone")
    assert game.combat.turn.movement_left == gob.speed()


def test_stand_up_on_own_turn_spends_half_speed(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [gob, brom])
    gob.add_condition("prone", "knocked down")
    assert stand_up(game, gob) == 15
    assert not gob.has("prone")
    assert game.combat.turn.movement_left == 15


def _goblin_turn(game):
    gob = mon(game, "goblin warrior", (0, 0))
    brom = pc(game, "BROM", (40, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [gob, brom])
    assert game.combat.is_turn(gob)
    return gob, brom


def test_spend_movement_decrements_the_turn_budget(game):
    gob, _ = _goblin_turn(game)
    assert game.combat.spend_movement(gob, 10, "Climbing", page=14, rule="X#1") is True
    assert game.combat.turn.movement_left == gob.speed() - 10


def test_spend_movement_refuses_more_than_is_left_without_spending(game):
    gob, _ = _goblin_turn(game)
    game.combat.turn.movement_left = 5
    with pytest.raises(Refusal, match="costs 10 ft.*5 ft left") as exc:
        game.combat.spend_movement(gob, 10, "Standing up", page=186, rule="GLOSS.prone#2", ruling="R-22")
    assert (exc.value.page, exc.value.rule, exc.value.ruling) == (186, "GLOSS.prone#2", "R-22")
    assert game.combat.turn.movement_left == 5


def test_spend_movement_refuses_off_turn_by_default(game):
    gob, brom = _goblin_turn(game)
    with pytest.raises(Refusal, match="own turn") as exc:
        game.combat.spend_movement(brom, 5, "Standing up", page=186, rule="GLOSS.prone#2")
    assert (exc.value.page, exc.value.rule) == (186, "GLOSS.prone#2")
    assert game.combat.turn.movement_left == gob.speed()


def test_spend_movement_off_turn_free_leaves_the_budget_alone(game):
    gob, brom = _goblin_turn(game)
    assert game.combat.spend_movement(brom, 500, "Moving", page=14, rule="X#1", free_off_turn=True) is False
    assert game.combat.turn.movement_left == gob.speed()


def test_move_off_turn_is_refused_and_changes_nothing(game):
    gob, brom = _goblin_turn(game)
    start = tuple(brom.position)
    with pytest.raises(Refusal, match="own turn") as exc:
        move(game, brom, to=(30, 0))
    assert (exc.value.page, exc.value.rule) == (14, "PLAY.combat.movement-and-position")
    assert tuple(brom.position) == start
    assert (game.combat.turn.movement_left, game.combat.turn.moved) == (gob.speed(), 0)


def _mounted_turn(game, controlled):
    jozan = pc(game, "JOZAN", (0, 0))
    horse = mon(game, "riding horse", (5, 0))
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [jozan, horse])
    mount(game, jozan, horse, controlled=controlled)
    assert game.combat.is_turn(jozan)
    return jozan, horse


def test_controlled_mount_moves_on_its_riders_turn_outside_the_riders_budget(game):
    jozan, horse = _mounted_turn(game, controlled=True)
    left = game.combat.turn.movement_left
    move(game, horse, to=(-30, 0))
    assert horse.position == (-30, 0)
    assert (game.combat.turn.movement_left, game.combat.turn.moved) == (left, 0)


def test_independent_mount_cant_move_on_its_riders_turn(game):
    jozan, horse = _mounted_turn(game, controlled=False)
    with pytest.raises(Refusal, match="own turn") as exc:
        move(game, horse, to=(-30, 0))
    assert (exc.value.page, exc.value.rule) == (14, "PLAY.combat.movement-and-position")
    assert horse.position == (5, 0) and jozan.position == (5, 0)


def test_readied_move_released_off_turn_moves_the_readier(game):
    gob, brom = _goblin_turn(game)
    end_turn(game)
    ready(game, brom, gob, 10, lambda: readied_move(game, brom, (60, 0)))
    end_turn(game)
    assert game.combat.is_turn(gob)
    move(game, gob, to=(30, 0))
    assert brom.position == (60, 0)
    assert game.combat.turn.movement_left == 0


def test_reaction_move_off_turn_is_not_drawn_from_the_current_turn(game):
    gob, brom = _goblin_turn(game)
    move(game, brom, to=(30, 0), reaction=True)
    assert brom.position == (30, 0)
    assert (game.combat.turn.movement_left, game.combat.turn.moved) == (gob.speed(), 0)


def test_move_refused_over_budget_names_the_cost_and_changes_nothing(game):
    gob, _ = _goblin_turn(game)
    with pytest.raises(Refusal, match="costs 35 ft") as exc:
        move(game, gob, to=(-35, 0))
    assert (exc.value.page, exc.value.rule) == (14, "PLAY.combat.movement-and-position")
    assert gob.position == (0, 0)
    assert game.combat.turn.movement_left == gob.speed()


# ---------------- the Ready action ----------------
def _brom_vs_goblins(game, *positions):
    brom = pc(game, "BROM", (0, 0))
    gobs = [mon(game, "goblin warrior", p, name=f"G{i}") for i, p in enumerate(positions)]
    game.dice.force_str("d20=[20,1]")  # identical goblins share one Initiative roll
    roll_initiative(game, [brom, *gobs])
    assert game.combat.current is brom
    return brom, gobs


def test_ready_spends_the_action_and_holds_the_response(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    assert game.combat.turn.actions_used == 1
    assert game.combat.readied[brom.id].trigger == gob.id
    assert gob.hp == 10
    assert game.log.last("ready").rule == "GLOSS.ready#1"


def test_ready_refused_before_building_the_response_when_the_action_is_spent(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    game.combat.spend(brom, "action", "Dodge")
    built = []
    with pytest.raises(Refusal, match="already taken their action"):
        ready(game, brom, gob.id, 5, lambda: built.append(1))
    assert built == [] and game.combat.readied == {}


def test_ready_trigger_naming_no_creature_cites_the_trigger_clause(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    with pytest.raises(Refusal, match="ogre") as exc:
        ready(game, brom, "ogre", 5, lambda: readied_attack(game, brom, gob))
    assert (exc.value.page, exc.value.rule) == (186, "GLOSS.ready#3")
    assert game.combat.turn.actions_used == 0


def test_readied_attack_taken_with_the_reaction_when_the_creature_comes_within(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    end_turn(game)
    game.answer("readied", True, who=brom)
    game.dice.force_str("d20=[15]; d8=[2]")
    move(game, gob, to=(5, 0))
    assert gob.hp == 5
    assert brom.id in game.combat.reaction_used
    assert brom.id not in game.combat.readied


def test_readied_trigger_needs_the_creature_to_come_within_the_distance(game):
    brom, (gob,) = _brom_vs_goblins(game, (5, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    end_turn(game)
    game.answer("readied", True, who=brom)
    move(game, gob, to=(5, 5))  # already within 5 ft: it doesn't come within
    assert game.answers[(brom.id, "readied")]  # never asked
    assert brom.id in game.combat.readied


def test_a_refused_release_keeps_the_reaction_and_the_readied_response(game):
    brom, (gob, gob2) = _brom_vs_goblins(game, (20, 0), (40, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob2))
    end_turn(game)
    game.answer("readied", True, who=brom)
    move(game, gob, to=(5, 0))  # the trigger, but the Goblin 2 is far beyond reach
    assert brom.id not in game.combat.reaction_used
    assert brom.id in game.combat.readied
    assert "can't take the readied" in str(game.log.last("ready"))


def test_a_held_spell_refused_at_release_stays_held_with_its_concentration(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob, gob2 = (
        mon(game, "goblin warrior", (20, 0), name="G0"),
        mon(game, "goblin warrior", (100, 0), name="G1"),
    )
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [mialee, gob, gob2])

    def build():
        c = cast(game, mialee, "magic missile", [gob2], ready=True)
        return c.spell.title(), c.release, c.held

    ready(game, mialee, gob.id, 5, build)
    gob2.position = (200, 0)  # now beyond Magic Missile's 120 ft
    end_turn(game)
    game.answer("readied", True, who=mialee)
    move(game, gob, to=(5, 0))
    assert mialee.concentrating == "Magic Missile (readied)"
    assert game.combat.readied[mialee.id].held == "Magic Missile (readied)"
    assert mialee.id not in game.combat.reaction_used
    assert "beyond Magic Missile's range" in str(game.log.last("ready"))
    assert gob2.hp == 10


def test_a_held_spell_refused_at_release_is_released_by_a_later_trigger_for_its_one_slot(game):
    mialee = pc(game, "MIALEE", (0, 0))
    gob, gob2 = (
        mon(game, "goblin warrior", (10, 0), name="G0"),
        mon(game, "goblin warrior", (100, 0), name="G1"),
    )
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [mialee, gob, gob2])

    def build():
        c = cast(game, mialee, "magic missile", [gob2], ready=True)
        return c.spell.title(), c.release, c.held

    ready(game, mialee, gob.id, 5, build)
    assert mialee.slots_left(1) == 1
    gob2.position = (200, 0)
    end_turn(game)
    game.answer("readied", True, who=mialee)
    move(game, gob, to=(5, 0))  # refused: G1 is beyond range, and the spell stays held
    assert "beyond Magic Missile's range" in str(game.log.last("ready"))
    assert mialee.concentrating == "Magic Missile (readied)"
    gob2.position = (100, 0)
    move(game, gob, to=(10, 0))
    game.answer("readied", True, who=mialee)
    game.dice.force_str("d4=[1,1,1]")
    move(game, gob, to=(5, 0))
    assert gob2.hp == 4
    assert mialee.concentrating is None
    assert mialee.id not in game.combat.readied
    assert mialee.id in game.combat.reaction_used
    assert mialee.slots_left(1) == 1


def test_a_refused_release_still_holding_concentration_keeps_the_held_spell(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    held = "Fire Bolt (readied)"
    game.start_concentration(brom, held)

    def release(g):
        raise Refusal("the target is out of range")

    ready(game, brom, gob.id, 5, lambda: ("Fire Bolt", release, held))
    end_turn(game)
    game.answer("readied", True, who=brom)
    move(game, gob, to=(5, 0))
    assert brom.concentrating == held
    assert game.combat.readied[brom.id].held == held
    assert game.log.last("ready").rule == "GLOSS.ready#5"


def test_readied_response_lapses_at_the_start_of_the_readiers_next_turn(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    end_turn(game)
    end_turn(game)
    assert game.combat.current is brom
    assert game.combat.readied == {}
    assert game.log.last("ready").rule == "GLOSS.ready#2"


def test_ready_refused_outside_combat_and_for_a_bad_trigger(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    with pytest.raises(Refusal) as exc:
        ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    assert exc.value.rule == "GLOSS.ready#2"
    game.dice.force_str("d20=[20,1]")
    roll_initiative(game, [brom, gob])
    for trigger, feet in ((brom.id, 5), (gob.id, -5)):
        with pytest.raises(Refusal) as exc:
            ready(game, brom, trigger, feet, lambda: readied_attack(game, brom, gob))
        assert exc.value.rule == "GLOSS.ready#3"
    assert game.combat.readied == {}


def test_require_action_refuses_off_turn_incapacitated_and_a_surged_magic_action(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    cb = game.combat
    with pytest.raises(Refusal, match="isn't"):
        cb.require_action(gob)
    cb.turn.surge_active, cb.turn.actions, cb.turn.actions_used = True, 2, 1
    with pytest.raises(Refusal) as exc:
        cb.require_action(brom, "Magic")
    assert exc.value.page == 48
    cb.require_action(brom, "Attack")  # the surged action is free for anything else
    brom.add_condition("incapacitated", "test")
    with pytest.raises(Refusal) as exc:
        cb.require_action(brom)
    assert exc.value.rule == "GLOSS.incapacitated"


@pytest.mark.parametrize("what", ["action", "bonus", "free"])
def test_spend_refuses_off_turn_and_incapacitated_without_spending(game, what):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    cb = game.combat
    before = (cb.turn.actions_used, cb.turn.bonus_used, cb.turn.free_interaction, list(cb.turn.log))
    with pytest.raises(Refusal, match="isn't"):
        cb.spend(gob, what, "Dash")
    brom.add_condition("incapacitated", "test")
    with pytest.raises(Refusal) as exc:
        cb.spend(brom, what, "Dash")
    assert exc.value.rule == "GLOSS.incapacitated"
    assert (cb.turn.actions_used, cb.turn.bonus_used, cb.turn.free_interaction, cb.turn.log) == before


@pytest.mark.parametrize(("what", "page"), [("bonus", 10), ("free", 13)])
def test_spend_bonus_or_free_interaction_once_per_turn(game, what, page):
    brom, _ = _brom_vs_goblins(game, (20, 0))
    cb = game.combat
    cb.spend(brom, what, "Second Wind")
    assert (cb.turn.bonus_used, cb.turn.free_interaction) == (what == "bonus", what == "free")
    with pytest.raises(Refusal) as exc:
        cb.spend(brom, what, "Second Wind")
    assert exc.value.page == page
    assert cb.turn.actions_used == 0


def test_readied_trigger_without_a_reaction_is_logged_and_not_asked(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    end_turn(game)
    game.combat.reaction_used.add(brom.id)
    game.answer("readied", True, who=brom)
    move(game, gob, to=(5, 0))
    assert game.answers[(brom.id, "readied")]
    assert "no Reaction available" in str(game.log.last("ready"))
    assert gob.hp == 10


def test_a_readied_response_lapses_when_combat_ends(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    ready(game, brom, gob.id, 5, lambda: readied_attack(game, brom, gob))
    end_combat(game)
    assert "combat ended" in str(game.log.last("ready"))


def test_readied_move_beyond_speed_cites_ruling_r20(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    with pytest.raises(Refusal, match="Speed") as exc:
        readied_move(game, brom, (-35, 0))
    assert (exc.value.page, exc.value.rule, exc.value.ruling) == (187, "GLOSS.ready#4", "R-20")


def test_readied_move_is_released_off_turn_without_a_movement_budget(game):
    brom, (gob,) = _brom_vs_goblins(game, (20, 0))
    ready(game, brom, gob.id, 5, lambda: readied_move(game, brom, (-30, 0)))
    end_turn(game)
    game.answer("readied", True, who=brom)
    game.answer("opportunity_attack", False, who=gob)
    move(game, gob, to=(5, 0))
    assert brom.position == (-30, 0)
