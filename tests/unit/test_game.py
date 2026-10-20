"""Unit tests for dungdra.game: cover between an attacker and a target, and its bonus."""

from tests.support.helpers import mon, pc


def setup(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    return lidda, gob


def test_a_creature_in_the_line_gives_half_cover(game):
    lidda, gob = setup(game)
    screen = mon(game, "goblin warrior", (15, 0), name="Screen")
    assert game.creatures_in_the_way(lidda, gob) == [screen]
    assert game.cover_between(lidda, gob) == "half"


def test_several_creatures_still_give_only_half(game):
    lidda, gob = setup(game)
    mon(game, "goblin warrior", (10, 0), name="A")
    mon(game, "goblin warrior", (20, 0), name="B")
    assert game.cover_between(lidda, gob) == "half"


def test_a_scene_label_beats_creature_cover(game):
    lidda, gob = setup(game)
    mon(game, "goblin warrior", (15, 0), name="Screen")
    game.scene.cover[(lidda.id, gob.id)] = "three-quarters"
    assert game.cover_between(lidda, gob) == "three-quarters"


def test_creatures_off_the_line_behind_or_dead_give_none(game):
    lidda, gob = setup(game)
    mon(game, "goblin warrior", (15, 30), name="Aside")
    mon(game, "goblin warrior", (45, 0), name="Behind")
    corpse = mon(game, "goblin warrior", (15, 0), name="Corpse")
    corpse.dead = True
    assert game.cover_between(lidda, gob) is None


def test_a_creature_sharing_the_targets_space_is_not_in_the_way(game):
    lidda, gob = setup(game)
    pc(game, "BROM", (30, 0))
    assert game.cover_between(lidda, gob) is None


def test_a_dead_creature_is_not_in_the_way(game):
    lidda, gob = setup(game)
    screen = mon(game, "goblin warrior", (15, 0), name="Screen")
    screen.dead = True
    assert game.cover_between(lidda, gob) is None


def test_cover_bonus_is_plus_two_for_half_and_logged_with_its_clause(game):
    lidda, gob = setup(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    assert game.cover_bonus(lidda, gob, "AC") == [(2, "Half Cover")]
    (ev,) = game.log.applied(rule="PLAY.combat.cover")
    assert ev.rule == "PLAY.combat.cover#5" and ev.page == "15"


def test_cover_bonus_is_plus_five_for_three_quarters(game):
    lidda, gob = setup(game)
    game.scene.cover_all[gob.id] = "three-quarters"
    assert game.cover_bonus(lidda, gob, "AC") == [(5, "Three-Quarters Cover")]
    assert [e.rule for e in game.log.applied(rule="PLAY.combat.cover")] == ["PLAY.combat.cover#7"]


def test_no_or_total_cover_gives_no_bonus_and_logs_nothing(game):
    lidda, gob = setup(game)
    assert game.cover_bonus(lidda, gob, "AC") == []
    game.scene.cover[(lidda.id, gob.id)] = "total"
    assert game.cover_bonus(lidda, gob, "AC") == []
    assert game.log.applied(rule="PLAY.combat.cover") == []


def test_cover_from_a_point_of_origin_reads_the_scene_label_for_that_point(game):
    lidda, gob = setup(game)
    game.scene.cover[((40, 0), gob.id)] = "total"
    assert game.cover_between((40, 0), gob) == "total"
    # the label is for that point only, not for the caster nor another point
    assert game.cover_between(lidda, gob) is None
    assert game.cover_between((20, 0), gob) is None


def test_labelled_cover_reads_an_objects_labels_by_name_and_keeps_the_most_protective(game):
    lidda, _ = setup(game)
    assert game.labelled_cover(lidda, "hay") is None
    game.scene.cover_all["hay"] = "half"
    game.scene.cover[((40, 0), "hay")] = "total"
    assert game.labelled_cover((40, 0), "hay") == "total"
    assert game.labelled_cover(lidda, "hay") == "half"
    assert game.labelled_cover(None, "hay") == "half"


def test_a_creature_between_a_point_of_origin_and_the_target_gives_half_cover(game):
    _, gob = setup(game)
    mon(game, "goblin warrior", (50, 0), name="SHIELD")
    assert game.cover_between((70, 2.5), gob) == "half"
    # the same creature is behind the target as seen from the caster's side
    assert game.cover_between((0, 2.5), gob) is None


def test_cover_bonus_against_a_point_names_the_point_in_the_log(game):
    _, gob = setup(game)
    game.scene.cover[((40, 0), gob.id)] = "half"
    assert game.cover_bonus([40, 0], gob, "the Dexterity saving throw") == [(2, "Half Cover")]
    (ev,) = game.log.applied(rule="PLAY.combat.cover")
    assert "point of origin at [40, 0]" in ev.text and ev.rule == "PLAY.combat.cover#5"


def guard(game, attitude):
    g = mon(game, "guard", (10, 0), name="WATCHMAN")
    g.team = "neutral"
    g.attitude = attitude
    return g


def test_a_friendly_creature_off_both_sides_is_an_ally_of_the_party_and_back(game):
    lidda = pc(game, "LIDDA", (0, 0))
    g = guard(game, "friendly")
    assert g in game.allies_of(lidda)
    assert lidda in game.allies_of(g)


def test_an_indifferent_or_hostile_creature_off_both_sides_is_no_ally(game):
    lidda = pc(game, "LIDDA", (0, 0))
    g = guard(game, "indifferent")
    assert g not in game.allies_of(lidda)
    g.attitude = "hostile"
    assert g not in game.allies_of(lidda)


def test_a_friendly_creature_is_no_ally_of_the_enemy_side(game):
    gob = mon(game, "goblin warrior", (30, 0))
    g = guard(game, "friendly")
    assert g not in game.allies_of(gob)


def test_a_creature_is_never_its_own_ally(game):
    lidda = pc(game, "LIDDA", (0, 0))
    assert not game.is_ally(lidda, lidda)
    assert lidda not in game.allies_of(lidda)


def test_creatures_on_the_same_side_are_allies_and_the_other_side_is_not(game):
    lidda = pc(game, "LIDDA", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    assert game.is_ally(lidda, brom)
    assert brom in game.allies_of(lidda)
    assert gob not in game.allies_of(lidda)


def test_a_monster_added_to_the_party_side_is_an_ally_but_not_on_the_pc_roster(game):
    lidda = pc(game, "LIDDA", (0, 0))
    g = mon(game, "guard", (10, 0))
    game.remove(g)
    game.add(g, team="party", position=(10, 0))
    assert g in game.allies_of(lidda)
    assert lidda in game.allies_of(g)
    assert game.pcs() == [lidda]
