"""Unit tests for dungdra.d20: each D20 Test logs the rule it applies, then the rulings that shaped it."""

import pytest

from dungdra.d20 import D20_RULES, D20Roll, roll_d20_test
from dungdra.events import GM


@pytest.mark.parametrize("kind", sorted(D20_RULES))
def test_a_d20_test_logs_the_rule_of_its_kind(game, kind):
    game.dice.force_str("d20=[12]")
    roll_d20_test(game, None, D20Roll(kind, "a test", "nobody", target=10))
    assert game.log.last(kind).rule == D20_RULES[kind]


def test_the_caller_can_name_a_narrower_rule(game):
    game.dice.force_str("d20=[12]")
    roll_d20_test(game, None, D20Roll("save", "a save", "nobody", target=10), rule="GLOSS.concentration")
    assert game.log.last("save").rule == "GLOSS.concentration"


def test_an_automatic_result_logs_its_rule_too(game):
    roll = D20Roll("save", "a save", "nobody", target=10)
    roll.auto, roll.auto_reason = "fail", "Paralyzed"
    roll_d20_test(game, None, roll)
    assert game.log.last("save").rule == "PLAY.d20-tests.saving-throws"


def test_each_ruling_is_logged_for_the_gm_after_the_roll(game):
    game.dice.force_str("d20=[12]")
    roll_d20_test(
        game,
        None,
        D20Roll("attack", "an attack", "nobody", target=10),
        rulings=[("GLOSS.grappled#2", "R-06", "either grappler")],
    )
    roll_ev, ruling_ev = game.log.events[-2:]
    assert roll_ev.kind == "attack" and roll_ev.ruling is None
    assert (ruling_ev.kind, ruling_ev.rule, ruling_ev.ruling, ruling_ev.visibility) == (
        "ruling",
        "GLOSS.grappled#2",
        "R-06",
        GM,
    )
    assert "either grappler" in ruling_ev.text


def test_no_rulings_log_nothing_extra(game):
    game.dice.force_str("d20=[12]")
    roll_d20_test(game, None, D20Roll("check", "a check", "nobody", target=10))
    assert game.log.of_kind("ruling") == []


def test_inspiration_reroll_replaces_the_picked_die_and_spends_inspiration(game):
    from dungdra.d20 import inspiration_reroll
    from tests.support.helpers import pc

    jozan = pc(game, "JOZAN", (0, 0))
    jozan.heroic_inspiration = True
    game.answer("inspiration_damage", 1)
    game.dice.force_str("d6=[2]")
    assert inspiration_reroll(game, jozan, [5, 1], 6) == [5, 2]
    assert jozan.heroic_inspiration is False
    ev = game.log.last("inspiration")
    assert (ev.rule, ev.page) == ("GLOSS.heroic-inspiration#1", "183")


def test_inspiration_reroll_declined_or_unavailable_keeps_the_rolls(game):
    from dungdra.d20 import inspiration_reroll
    from tests.support.helpers import pc

    jozan = pc(game, "JOZAN", (0, 0))
    assert inspiration_reroll(game, jozan, [1], 8, "inspiration", "Hit Die") == [1]
    jozan.heroic_inspiration = True
    assert inspiration_reroll(game, jozan, [1], 8, "inspiration", "Hit Die") == [1]
    assert jozan.heroic_inspiration is True
