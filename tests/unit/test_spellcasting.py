"""Unit tests for dungdra.spellcasting: the slots Arcane Recovery offers."""

from dungdra import rest as R
from tests.support.helpers import pc


def test_arcane_recovery_takes_any_expended_slots_the_wizard_picks(game):
    mialee = pc(game, "MIALEE")
    mialee.award_xp(900, "testing")  # level 3: up to 2 slot levels
    mialee.slots_used = {1: 2, 2: 1}
    game.answer("arcane_recovery", [1, 1])  # not the default, which is the level 2 slot
    R.short_rest(game, [mialee])
    assert mialee.slots_used == {1: 0, 2: 1}


def test_arcane_recovery_can_be_declined_with_no_picks(game):
    mialee = pc(game, "MIALEE")
    mialee.slots_used = {1: 1}
    game.answer("arcane_recovery", [])
    R.short_rest(game, [mialee])
    assert mialee.slots_used == {1: 1} and mialee.resource_left("arcane recovery") == 1
