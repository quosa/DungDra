"""One agent call = one headless `claude -p` process with a fresh context, one role's tools and
system prompt (.claude/agents/<role>.md), and a JSON Schema for its output.

Costs go to loop/costs.jsonl. A run has a budget; a call only starts if its cap still fits, so
the loop pauses cleanly between calls and resumes where it stopped.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

AGENTS = Path(".claude/agents")
SCHEMAS = Path(__file__).parent / "schemas"
LEDGER = Path("loop/costs.jsonl")
SETTINGS = Path(__file__).parent / "settings.json"  # loop-only: sandbox, deny rules, the write guard
TRANSIENT = re.compile(
    r"rate.?limit|usage limit|session limit|hit your (?:\w+ )?limit|limit reached|resets? at"
    r"|overloaded|529|503|timed? ?out|ECONN|network",
    re.I,
)
CALL_TIMEOUT_S = 3600  # one agent call; json output gives no progress to reset a timer on

READ = ("Read", "Grep", "Glob")
PYTEST = ("Bash(python -m pytest:*)", "Bash(pytest:*)")


def _write(*globs: str) -> tuple[str, ...]:
    return tuple(f"{tool}({g})" for g in globs for tool in ("Write", "Edit"))


@dataclass(frozen=True)
class Role:
    model: str
    tools: tuple[str, ...]  # built-in tools the agent has at all
    allowed: tuple[str, ...]  # permission rules; with --permission-mode dontAsk the rest is denied
    schema: str
    cap_usd: float = 5.0


ROLES: dict[str, Role] = {
    "rule-analyst": Role("opus", (), (), "analysis", 2.0),
    "scenario-auditor": Role("sonnet", READ, READ, "verdicts", 2.0),
    "test-designer": Role(
        "opus",
        (*READ, "Write", "Edit", "Bash"),
        (
            *READ,
            *PYTEST,
            *_write("tests/srd/**", "tests/scenarios/**", "tests/support/**"),
            *_write("docs/scenario-notes.md", "loop/abuse-catalogue.md"),
        ),
        "test-plan",
        6.0,
    ),
    "test-verifier": Role(
        "opus",
        (*READ, "Bash"),
        (*READ, *PYTEST, "Bash(python -m scripts.srdloop mutate:*)"),
        "verification",
        4.0,
    ),
    "fixer": Role(
        "opus",
        (*READ, "Write", "Edit", "Bash"),
        (
            *READ,
            *PYTEST,
            "Bash(ruff:*)",
            "Bash(python -m scripts.srdloop dev-gate:*)",
            *_write("dungdra/**", "tests/unit/**", "loop/requests/**"),
        ),
        "fix-result",
        6.0,
    ),
    "unit-test-writer": Role(
        "sonnet",
        (*READ, "Write", "Edit", "Bash"),
        (*READ, *PYTEST, *_write("tests/unit/**")),
        "fix-result",
        3.0,
    ),
    "fix-reviewer": Role(
        "opus",
        (*READ, "Bash"),
        (*READ, "Bash(git diff:*)", "Bash(git show:*)", "Bash(git log:*)"),
        "review",
        2.0,
    ),
}


class Paused(Exception):
    """The run stopped between calls (budget spent, or a transient failure). Resume later;
    `hint` says how."""

    def __init__(self, message: str, hint: str = "Run again to resume."):
        super().__init__(message)
        self.hint = hint


@dataclass
class Budget:
    """Spending for this run. A call starts only if its cap fits into what is left."""

    limit_usd: float
    spent_usd: float = 0.0

    def check(self, cap: float) -> None:
        if self.spent_usd + cap > self.limit_usd:
            spent = f"${self.spent_usd:.2f} of ${self.limit_usd:.2f}"
            if cap > self.limit_usd:  # the same command would pause again at once
                hint = (
                    "That's more than this run's whole budget: "
                    f"run it again with --budget {math.ceil(cap)} or more."
                )
            else:
                hint = (
                    "Run the same command again to resume (a new run's budget starts at $0), "
                    f"or give one run room for it with --budget {math.ceil(self.spent_usd + cap)}."
                )
            raise Paused(f"budget: {spent} spent; the next call may cost up to ${cap:.2f}", hint)


@dataclass
class Result:
    output: dict | None
    cost_usd: float
    session_id: str | None
    error: str | None = None
    raw: dict = field(default_factory=dict)


def system_prompt(role: str, agents: Path = AGENTS) -> str:
    """The agent file's body, without its frontmatter."""
    text = (agents / f"{role}.md").read_text()
    return text.split("---", 2)[2].strip() if text.startswith("---") else text


def argv(role: str, prompt: str, cap: float, agents: Path = AGENTS) -> list[str]:
    r = ROLES[role]
    schema = (SCHEMAS / f"{r.schema}.json").read_text()
    args = [
        "claude",
        "-p",
        prompt,
        "--append-system-prompt",
        system_prompt(role, agents),
        "--model",
        r.model,
        "--output-format",
        "json",
        "--json-schema",
        schema,
        "--max-budget-usd",
        f"{cap:.2f}",
        "--permission-mode",
        "dontAsk",
        "--setting-sources",
        "project",  # not the user's personal settings
        "--settings",
        str(SETTINGS),
        "--strict-mcp-config",  # no MCP servers in loop agents
        "--no-session-persistence",
        "--tools",
        ",".join(r.tools),
    ]
    if r.allowed:
        args += ["--allowedTools", *r.allowed]
    return args


def log_cost(entry: dict, ledger: Path = LEDGER) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def invoke(
    role: str,
    prompt: str,
    *,
    budget: Budget,
    about: str,
    stage: str,
    cap: float | None = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ledger: Path = LEDGER,
) -> Result:
    """Run one agent. Raises Paused before starting if the budget can't cover `cap`, or after a
    transient failure (rate limit, usage limit, network) so the run can resume later."""
    cap = cap if cap is not None else ROLES[role].cap_usd
    budget.check(cap)
    env = {**os.environ, "SRDLOOP_ROLE": role}
    started = time.time()
    try:
        proc = run(
            argv(role, prompt, cap),
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=CALL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        log_cost(
            {"at": round(started), "about": about, "stage": stage, "role": role, "model": ROLES[role].model}
            | {
                "cost_usd": 0.0,
                "seconds": round(time.time() - started, 1),
                "session_id": None,
                "exit": "timeout",
            },
            ledger,
        )
        raise Paused(
            f"{role} ran for {CALL_TIMEOUT_S // 60} minutes without finishing; its cost is unknown"
        ) from None
    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        raw = {"result": proc.stdout}
    cost = float(raw.get("total_cost_usd") or 0.0)
    budget.spent_usd += cost
    log_cost(
        {
            "at": round(started),
            "about": about,
            "stage": stage,
            "role": role,
            "model": ROLES[role].model,
            "cost_usd": round(cost, 4),
            "seconds": round(time.time() - started, 1),
            "session_id": raw.get("session_id"),
            "exit": proc.returncode,
        },
        ledger,
    )
    text = f"{raw.get('result', '')} {proc.stderr}".strip()
    detail = f"exit {proc.returncode}, {raw.get('subtype') or 'no subtype'}" + (
        f": {text[:300]}" if text else ""
    )
    if proc.returncode != 0:
        # A call that failed without doing anything (cost 0) or names a limit didn't really run: a usage
        # or rate limit, an outage. Pause instead of spending one of the stage's attempts on it.
        if cost == 0 or TRANSIENT.search(text):
            raise Paused(f"{role} didn't run ({detail})")
        return Result(None, cost, raw.get("session_id"), detail, raw)  # a non-zero exit is never a result
    output = raw.get("structured_output")
    return Result(output, cost, raw.get("session_id"), None if output is not None else detail, raw)
