"""Tickets: work for the dev loop, one JSON file each in loop/tickets/ (T-1.json, …).

kinds: bug (a red SRD test), infra (a capability the engine lacks), refactor, coverage.
status: open → fixed | stuck (3 failed attempts; a person decides) | dispute (the fixer thinks
the test is wrong; a person decides).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

TICKETS = Path("loop/tickets")
PRIORITY = {"bug": 0, "infra": 1, "refactor": 2, "coverage": 3}
MAX_ATTEMPTS = 3


def _next_id(root: Path) -> str:
    nums = [int(m.group(1)) for p in root.glob("T-*.json") if (m := re.fullmatch(r"T-(\d+)\.json", p.name))]
    return f"T-{max(nums, default=0) + 1}"


def create(kind: str, unit: str, title: str, tests: list[str], root: Path = TICKETS) -> dict:
    assert kind in PRIORITY, kind
    root.mkdir(parents=True, exist_ok=True)
    t = {
        "id": _next_id(root),
        "kind": kind,
        "unit": unit,
        "title": title,
        "tests": tests,
        "status": "open",
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


def open_tickets(root: Path = TICKETS) -> list[dict]:
    """Open tickets in dev-loop order: bugs, then infra, refactor, coverage; oldest first."""
    tickets = [t for t in all_tickets(root) if t["status"] == "open"]
    return sorted(tickets, key=lambda t: (PRIORITY[t["kind"]], int(t["id"][2:])))


def record(t: dict, event: str, root: Path = TICKETS, **details) -> None:
    t["history"].append({"event": event, **details})
    save(t, root)
