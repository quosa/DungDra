"""Unit tests for dungdra.mounted: when a controlled mount moves."""

from dungdra.combat import end_turn, roll_initiative
from dungdra.mounted import dismount, mount, moves_on_riders_turn
from tests.support.helpers import mon, pc


def _mounted(game, controlled=True):
    jozan = pc(game, "JOZAN", (0, 0))
    horse = mon(game, "riding horse", (5, 0))
    gob = mon(game, "goblin warrior", (50, 0))
    game.dice.force_str("d20=[20,10,1]")
    roll_initiative(game, [jozan, horse, gob])
    mount(game, jozan, horse, controlled=controlled)
    return jozan, horse, gob


def test_controlled_mount_moves_on_its_riders_turn(game):
    jozan, horse, _ = _mounted(game)
    assert game.combat.is_turn(jozan)
    assert moves_on_riders_turn(game, horse) is True


def test_controlled_mount_doesnt_move_on_another_creatures_turn(game):
    jozan, horse, gob = _mounted(game)
    while not game.combat.is_turn(gob):
        end_turn(game)
    assert moves_on_riders_turn(game, horse) is False


def test_independent_mount_doesnt_move_on_its_riders_turn(game):
    _, horse, _ = _mounted(game, controlled=False)
    assert moves_on_riders_turn(game, horse) is False


def test_dismounted_steed_no_longer_moves_on_the_former_riders_turn(game):
    jozan, horse, _ = _mounted(game)
    dismount(game, jozan)
    assert moves_on_riders_turn(game, horse) is False
