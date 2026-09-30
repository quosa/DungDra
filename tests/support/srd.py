"""Helpers for the SRD rule suite (tests/srd), written by the test-designer agent.

A refused command must cost nothing: no state change, no turn resource, no log entry other
than the refusal itself. `assert_refused_cleanly` checks all of that in one call.
"""

from __future__ import annotations

import dataclasses
import re

from dungdra.rules import Refusal


def refusal_state(game) -> dict:
    """Everything a refused command must leave untouched."""
    cb = game.combat
    return {
        "snapshot": game.snapshot(),
        "turn": dataclasses.asdict(cb.turn) if cb is not None and cb.turn is not None else None,
        "reactions": sorted(cb.reaction_used) if cb is not None else None,
    }


def assert_refused_cleanly(game, action, *args, match: str | None = None, **kwargs):
    """Call `action(*args, **kwargs)` and require a clean refusal.

    `action` is an engine call that must raise Refusal (with a page or ruling), or
    `session.execute` with a command dict, which must return {"ok": False}. Either way the
    game state, the turn's resources and the log must be as before (apart from a "refused"
    entry). Returns the Refusal, or the session result."""
    before = refusal_state(game)
    start = len(game.log.events)
    try:
        out = action(*args, **kwargs)
    except Refusal as e:
        if match is not None:
            assert re.search(match, e.reason), f"refusal {e.reason!r} doesn't match {match!r}"
        assert e.page is not None or e.ruling is not None, f"refusal {e.reason!r} cites no SRD page or ruling"
        result = e
    else:
        assert isinstance(out, dict) and out.get("ok") is False, f"expected a refusal, got {out!r}"
        if match is not None:
            assert re.search(match, out.get("error", "")), (
                f"refusal {out.get('error')!r} doesn't match {match!r}"
            )
        result = out
    new = [e for e in game.log.events[start:] if e.kind != "refused"]
    assert not new, "a refused command logged: " + "; ".join(str(e) for e in new)
    after = refusal_state(game)
    for key in before:
        assert after[key] == before[key], f"a refused command changed the {key}"
    return result
