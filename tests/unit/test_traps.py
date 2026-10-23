"""Unit tests for dungdra.traps: disarming without Thieves' Tools follows ruling R-04 and logs it."""

import pytest

from dungdra import traps as T
from dungdra.rules import Refusal
from tests.support.helpers import pc


def _found_needle(game):
    t = T.place(game, "poisoned needle")
    t.detected = True
    return t


def test_disarming_without_thieves_tools_is_a_plain_check_and_logs_r04_gm_only(game):
    lidda = pc(game, "LIDDA")
    lidda.inventory.remove("thieves' tools", lidda.inventory.count("thieves' tools"))
    t = _found_needle(game)
    game.dice.force_str("d20=[20]")  # one d20: no tool+skill Advantage
    r = T.disarm(game, lidda, t)
    assert r.mode == "normal" and r.success and t.disabled
    ev = game.log.assert_applied(ruling="R-04")[0]
    assert (ev.kind, ev.page, ev.visibility) == ("ruling", "94", "gm")


def test_disarming_with_thieves_tools_logs_no_ruling(game):
    lidda = pc(game, "LIDDA")
    t = _found_needle(game)
    game.dice.force_str("d20=[4,9]")
    assert T.disarm(game, lidda, t).success and t.disabled
    assert not game.log.applied(ruling="R-04")


def test_a_trap_found_by_searching_is_detected(game):
    lidda = pc(game, "LIDDA", (0, 0))
    t = T.place(game, "collapsing roof")
    game.dice.force_str("d20=[15]")
    T.detect(game, lidda, t)
    assert t.detected


def test_a_spike_only_wedges_a_pit_that_has_been_found(game):
    brom = pc(game, "BROM", (0, 0))
    needle, pit = T.place(game, "poisoned needle"), T.place(game, "hidden pit")
    with pytest.raises(Refusal, match="doesn't disarm that trap"):
        T.wedge_spike(game, brom, needle)
    with pytest.raises(Refusal, match="haven't found anything"):
        T.wedge_spike(game, brom, pit)
