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
