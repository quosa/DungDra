"""Unit tests for dungdra.events: the SRD rule and register ruling each event applied."""

import pytest

from dungdra.events import GM, Event, EventLog


def test_an_event_keeps_its_rule_next_to_its_page():
    log = EventLog()
    ev = log.player("move", "Brom moves 10 ft", page=14, rule="PLAY.combat.movement-and-position")
    assert (ev.page, ev.rule, ev.ruling) == ("14", "PLAY.combat.movement-and-position", None)
    assert ev.to_dict()["rule"] == "PLAY.combat.movement-and-position"


def test_the_rule_doesnt_change_the_player_facing_text():
    log = EventLog()
    ev = log.player("move", "Brom moves 10 ft", page=14, rule="PLAY.combat.movement-and-position")
    assert str(ev) == "Brom moves 10 ft  [p.14]"


def test_rules_lists_the_rules_the_log_applied():
    log = EventLog()
    log.player("condition", "Gob is Grappled", rule="GLOSS.grappled")
    log.gm("ruling", "R-06 applies", rule="GLOSS.grappled#2", ruling="R-06")
    log.player("note", "flavour text")
    assert log.rules() == {"GLOSS.grappled", "GLOSS.grappled#2"}
    assert log.rulings() == {"R-06"}


def test_a_unit_matches_any_of_its_clauses():
    ev = Event("move", "", rule="GLOSS.grappled#4")
    assert ev.applies("GLOSS.grappled")
    assert ev.applies("GLOSS.grappled#4")


def test_a_clause_matches_only_itself():
    ev = Event("move", "", rule="GLOSS.grappled#4")
    assert not ev.applies("GLOSS.grappled#3")
    assert not ev.applies("GLOSS.grappling")
    assert not Event("move", "").applies("GLOSS.grappled")


def test_applied_filters_by_rule_and_ruling():
    log = EventLog()
    a = log.player("move", "drag", rule="GLOSS.grappled#4", ruling="R-05")
    b = log.player("move", "drag", rule="GLOSS.grappled#4")
    log.player("move", "walk", rule="PLAY.combat.movement-and-position")
    assert log.applied("GLOSS.grappled") == [a, b]
    assert log.applied("GLOSS.grappled#4", ruling="R-05") == [a]
    assert log.applied(ruling="R-05") == [a]


def test_assert_applied_returns_the_events_that_applied_it():
    log = EventLog()
    ev = log.gm("ruling", "R-06 applies", rule="GLOSS.grappled#2", ruling="R-06")
    assert log.assert_applied("GLOSS.grappled", ruling="R-06") == [ev]
    assert ev.visibility == GM


def test_assert_applied_fails_naming_what_was_applied():
    log = EventLog()
    log.player("move", "walk", rule="PLAY.combat.movement-and-position")
    with pytest.raises(AssertionError, match=r"no event applied rule GLOSS.grappled and ruling R-05") as exc:
        log.assert_applied("GLOSS.grappled", ruling="R-05")
    assert "PLAY.combat.movement-and-position" in str(exc.value)


def test_assert_applied_needs_something_to_look_for():
    with pytest.raises(ValueError):
        EventLog().assert_applied()
