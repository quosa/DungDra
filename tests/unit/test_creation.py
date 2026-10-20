"""Unit tests for dungdra.creation: a tool proficiency gained twice is replaced (R-01) and logged."""

from dungdra.creation import CharacterBuilder
from dungdra.fixtures import FIXTURES


def test_a_duplicate_tool_proficiency_is_replaced_and_logs_r01(game):
    # Rogue and Criminal both grant Thieves' Tools
    b = CharacterBuilder(game).update(**FIXTURES["LIDDA"])
    assert b.duplicate_tools() == ["thieves' tools"]
    pc = b.build()
    assert {"thieves' tools", "disguise kit"} <= pc.tools
    ev = game.log.assert_applied(ruling="R-01")[0]
    assert (ev.page, ev.visibility) == ("83", "player") and "Disguise Kit" in ev.text


def test_the_replacement_tool_is_asked_for_citing_r01(game):
    fx = {k: v for k, v in FIXTURES["LIDDA"].items() if k != "replacement_tool"}
    asks = dict(CharacterBuilder(game).update(**fx).missing())
    assert "R-01" in asks["replacement_tool"]


def test_distinct_tool_proficiencies_log_no_ruling(game):
    b = CharacterBuilder(game).update(**FIXTURES["BROM"])
    assert b.duplicate_tools() == []
    b.build()
    assert not game.log.applied(ruling="R-01")
