"""Unit tests for dungdra.encounters: the XP split (R-02) and encounter budgets (R-03) log their ruling."""

import pytest

from dungdra import encounters as E
from dungdra.rules import Refusal
from tests.support.helpers import pc

LV1 = [1, 1, 1, 1]


def test_xp_split_divides_evenly_rounding_down_and_logs_r02(game):
    party = [pc(game, n) for n in ("BROM", "LIDDA", "MIALEE")]
    share = E.award_xp(game, ["goblin boss", "goblin warrior"], party)  # 200 + 50 XP over 3 PCs
    assert share == 83 and all(p.xp == 83 for p in party)
    ev = game.log.assert_applied(ruling="R-02")[0]
    assert (ev.kind, ev.page, ev.visibility) == ("xp", "255", "player")


def test_an_over_high_rating_is_gm_only_and_logs_r03(game):
    n_player = len(game.log.visible())
    assert E.rate(game, LV1, ["ogre"])["band"] == "over high"
    ev = game.log.assert_applied(ruling="R-03")[0]
    assert (ev.kind, ev.page, ev.visibility) == ("encounter", "202", "gm")
    assert len(game.log.visible()) == n_player


def test_a_rating_within_budget_logs_no_ruling(game):
    assert E.rate(game, LV1, ["goblin warrior"] * 4)["band"] == "low"
    assert game.log.last("encounter").ruling is None
    assert not game.log.applied(ruling="R-03")


def test_reinforcements_over_high_are_refused_with_r03(game):
    with pytest.raises(Refusal) as exc:
        E.add_reinforcements(game, LV1, ["goblin boss"], ["ogre"])
    assert (exc.value.ruling, exc.value.page) == ("R-03", 202)
    assert not game.log.applied(ruling="R-03")


def test_justified_reinforcements_over_high_log_r03_gm_only(game):
    after = E.add_reinforcements(game, LV1, ["goblin boss"], ["ogre"], justification="it lives here")
    assert after == ["goblin boss", "ogre"]
    ev = game.log.assert_applied(ruling="R-03")[0]
    assert ev.visibility == "gm" and "it lives here" in ev.text


def test_reinforcements_within_budget_log_no_ruling(game):
    assert E.add_reinforcements(game, LV1, ["goblin warrior"], ["goblin warrior"]) == ["goblin warrior"] * 2
    assert not game.log.applied(ruling="R-03")
