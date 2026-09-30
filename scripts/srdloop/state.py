"""Per-unit loop state: one JSON file per unit in loop/state/, so parallel worktrees never conflict.

A unit without a state file is pending. Stage outputs are checkpointed as soon as they pass
their gate, so an interrupted or budget-paused run resumes from the last completed stage.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

STATE_DIR = Path("loop/state")
STAGES = ("A", "B", "C", "D")
STATUSES = ("pending", "in-progress", "green", "red", "blocked", "incomplete", "out-of-scope")
TERMINAL = ("green", "red", "blocked", "incomplete", "out-of-scope")


def path_for(uid: str, root: Path = STATE_DIR) -> Path:
    return root / f"{uid}.json"


def load(uid: str, root: Path = STATE_DIR) -> dict:
    p = path_for(uid, root)
    if p.exists():
        return json.loads(p.read_text())
    return {"id": uid, "status": "pending", "stages": {}, "relations": [], "tickets": [], "fingerprint": None}


def save(state: dict, root: Path = STATE_DIR) -> None:
    """Atomic write: a crash never leaves a half-written state file."""
    root.mkdir(parents=True, exist_ok=True)
    p = path_for(state["id"], root)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def all_states(root: Path = STATE_DIR) -> dict[str, dict]:
    if not root.exists():
        return {}
    return {p.stem: json.loads(p.read_text()) for p in sorted(root.glob("*.json"))}


def next_stage(state: dict) -> str | None:
    """The first stage without a checkpoint, or None when all four are done."""
    return next((s for s in STAGES if s not in state.get("stages", {})), None)


def fingerprint(parts: dict[str, str]) -> str:
    """A stable hash of everything a unit's result depends on (see plan.inputs)."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def is_stale(state: dict, current: str) -> bool:
    """A finished unit whose inputs changed since it finished must run again. That includes an
    out-of-scope unit: once the engine code it relates to changes, it is looked at again."""
    return state.get("status") in TERMINAL and state.get("fingerprint") != current
