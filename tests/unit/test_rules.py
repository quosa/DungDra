"""Unit tests for dungdra.rules: a Refusal carries the rule and ruling that forbid the action."""

from dungdra.rules import OutOfScope, Refusal


def test_a_refusal_carries_page_rule_and_ruling():
    r = Refusal("no", page=182, rule="GLOSS.grappled#1", ruling="R-07")
    assert (r.reason, r.page, r.rule, r.ruling) == ("no", 182, "GLOSS.grappled#1", "R-07")


def test_a_refusal_needs_no_rule():
    r = OutOfScope("not in this game")
    assert (r.page, r.rule, r.ruling) == (None, None, None)
