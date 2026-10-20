"""Tickets: work for the dev loop, one JSON file each in loop/tickets/ (T-1.json, …).

kinds: bug (a red SRD test), infra (a capability the engine lacks), refactor, coverage.
status: open → fixed | stuck (3 failed attempts; a person decides) | dispute (the fixer thinks
the test is wrong; a person decides) | void (no longer wanted: a duplicate, a rejected ruling).
parked: a menu, not a to-do list. Reviewers' follow-ups start here, and a person parks tickets to
build later. The dev loop takes a parked ticket only when it is named (`dev --tickets T-n`).
A person reopens a stuck, disputed or parked ticket, parks or voids one, with a reason.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

TICKETS = Path("loop/tickets")
PRIORITY = {"bug": 0, "infra": 1, "refactor": 2, "coverage": 3}
MAX_ATTEMPTS = 3
ACTIVE = ("open", "stuck", "dispute")  # still needs the loop or a person; fixed and void are done
PARKED = "parked"


def _next_id(root: Path) -> str:
    nums = [int(m.group(1)) for p in root.glob("T-*.json") if (m := re.fullmatch(r"T-(\d+)\.json", p.name))]
    return f"T-{max(nums, default=0) + 1}"


def unprefixed(text: str, unit: str) -> str:
    """Titles are shown after their unit ("<unit>: <title>"): drop the unit the agent repeated."""
    while text.startswith(f"{unit}:"):
        text = text[len(unit) + 1 :].lstrip()
    return text


def _same(a: str, b: str) -> bool:
    def key(s):
        return re.sub(r"\s+", " ", s).strip().rstrip(".").lower()

    return key(a) == key(b)


def create(
    kind: str, unit: str, title: str, tests: list[str], root: Path = TICKETS, status: str = "open"
) -> dict:
    assert kind in PRIORITY, kind
    assert status in ("open", PARKED), status
    root.mkdir(parents=True, exist_ok=True)
    t = {
        "id": _next_id(root),
        "kind": kind,
        "unit": unit,
        "title": unprefixed(title, unit),
        "tests": tests,
        "status": status,
        "attempts": 0,
        "history": [],
    }
    save(t, root)
    return t


def save(t: dict, root: Path = TICKETS) -> None:
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{t['id']}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def load(tid: str, root: Path = TICKETS) -> dict:
    return json.loads((root / f"{tid}.json").read_text())


def all_tickets(root: Path = TICKETS) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(root.glob("T-*.json"), key=lambda p: int(p.stem[2:]))]


def _in_order(tickets: list[dict]) -> list[dict]:
    """Dev-loop order: bugs, then infra, refactor, coverage; oldest first."""
    return sorted(tickets, key=lambda t: (PRIORITY[t["kind"]], int(t["id"][2:])))


def open_tickets(root: Path = TICKETS) -> list[dict]:
    return _in_order([t for t in all_tickets(root) if t["status"] == "open"])


def open_bugs(root: Path = TICKETS) -> list[dict]:
    """What the audit loop's circuit breaker counts: the engine contradicting the SRD."""
    return [t for t in open_tickets(root) if t["kind"] == "bug"]


def parked(root: Path = TICKETS) -> list[dict]:
    return _in_order([t for t in all_tickets(root) if t["status"] == PARKED])


def workable(only: list[str] | None, root: Path = TICKETS) -> list[dict]:
    """The dev loop's candidates: open tickets, plus parked ones only when named in `only`."""
    tickets = [
        t
        for t in all_tickets(root)
        if t["status"] == "open" or (only is not None and t["status"] == PARKED and t["id"] in only)
    ]
    return _in_order([t for t in tickets if only is None or t["id"] in only])


def record(t: dict, event: str, root: Path = TICKETS, **details) -> None:
    t["history"].append({"event": event, **details})
    save(t, root)


def file(
    kind: str, unit: str, title: str, tests: list[str], root: Path = TICKETS, status: str = "open"
) -> dict:
    """create(), unless an open or parked ticket of the same kind already says the same: reuse
    that one (two units, or one plan, naming the same missing capability get one ticket)."""
    title = unprefixed(title, unit)
    for t in open_tickets(root) + parked(root):
        if t["kind"] == kind and _same(t["title"], title):
            t["tests"] += [n for n in tests if n not in t["tests"]]
            save(t, root)
            return t
    return create(kind, unit, title, tests, root, status)


def _need(reason: str, what: str) -> None:
    if not reason.strip():
        raise ValueError(f"{what} needs a reason")


def reopen(tid: str, reason: str, root: Path = TICKETS) -> dict:
    """Back to the dev loop with a fresh set of attempts (after a dispute is settled, or a stuck
    ticket was rewritten or capped)."""
    _need(reason, "reopening a ticket")
    t = load(tid, root)
    if t["status"] == "open":
        raise ValueError(f"{tid} is already open")
    was, t["status"], t["attempts"] = t["status"], "open", 0
    record(t, "reopened", root, was=was, reason=reason)
    return t


def park(tid: str, reason: str, root: Path = TICKETS) -> dict:
    """Off the dev loop's list until a person names it (`dev --tickets`) or reopens it."""
    _need(reason, "parking a ticket")
    t = load(tid, root)
    if t["status"] != "open":
        raise ValueError(f"{tid} is {t['status']}; only an open ticket can be parked")
    t["status"] = PARKED
    record(t, "parked", root, reason=reason)
    return t


def void(tid: str, reason: str, root: Path = TICKETS) -> dict:
    _need(reason, "voiding a ticket")
    t = load(tid, root)
    if t["status"] == "void":
        raise ValueError(f"{tid} is already void")
    t["status"] = "void"
    record(t, "void", root, reason=reason)
    return t
