"""Helpers shared by the unit tests."""

from dungdra.effects import Condition


def grappled_by(target, *grapplers):
    """Give target one Grappled condition per grappler."""
    for g in grapplers:
        target.add_effect(Condition("grappled", f"grappled by {g.name}", caster=g, grappler=g.id))
