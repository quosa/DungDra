#!/usr/bin/env python3
"""PreToolUse hook for loop agents: a role may only write inside its zone (scripts/srdloop/gates.py
ZONES). Active only when SRDLOOP_ROLE is set, i.e. in agents the loop harness starts; a person's
own Claude Code session in this repo is unaffected. Exit 2 blocks the call; stderr tells the agent why.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path


def main() -> int:
    role = os.environ.get("SRDLOOP_ROLE")
    if not role:
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    sys.path.insert(0, str(project))
    from scripts.srdloop.gates import ZONES

    event = json.load(sys.stdin)
    tool = event.get("tool_input", {})
    raw = tool.get("file_path") or tool.get("notebook_path")
    if not raw:
        return 0
    path = Path(raw)
    path = (path if path.is_absolute() else project / path).resolve()
    try:
        rel = path.relative_to(project).as_posix()
    except ValueError:
        print(f"Blocked: {role} may not write outside the repository ({raw}).", file=sys.stderr)
        return 2
    zones = ZONES.get(role, ())
    if not any(fnmatch.fnmatch(rel, g) for g in zones):
        allowed = ", ".join(zones) or "nothing"
        print(
            f"Blocked: {role} may not write {rel}. Allowed: {allowed}. Report the issue instead.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
