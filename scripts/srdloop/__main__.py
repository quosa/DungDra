"""python -m scripts.srdloop <command>

status               one-line summary of the loop
plan                 write loop/queue.json (pending and stale units, dependencies first)
related <unit-id>    scenarios, tests and engine code related to a unit (JSON)
report               write loop/COVERAGE.md
gate --role R        audit gates on the working tree: write zones for role R, append-only
                     acceptance tests, SRD test-file rules (markers, assertions, no mocks)
dev-gate             dev-loop quality gates: lint, suppressions, coverage ratchet and diff
                     coverage, import layers, duplication, dead code, unit-test hygiene
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import gates as Gt
from . import plan as P
from . import quality as Q
from . import report as Rep
from . import units as U


def _verdict(problems: list[str], note: str = "") -> int:
    for p in problems:
        print(f"  ! {p}")
    head = f"FAIL ({len(problems)} problems)" if problems else "PASS"
    print(head + (f"; {note}" if note else ""))
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.srdloop", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("plan")
    rel = sub.add_parser("related")
    rel.add_argument("unit")
    sub.add_parser("report")
    gate = sub.add_parser("gate")
    gate.add_argument("--role", required=True, choices=sorted(Gt.ZONES))
    gate.add_argument("--ref", default="HEAD")
    dev = sub.add_parser("dev-gate")
    dev.add_argument("--ref", default="HEAD")
    a = ap.parse_args(argv)
    if a.cmd == "dev-gate":
        problems, metrics = Q.dev_gate(a.ref)
        shown = {k: v for k, v in metrics.items() if not k.startswith("_")}
        return _verdict(problems, f"metrics {shown}")
    try:
        ctx = P.Context.load()
    except U.NotApproved as e:
        print(f"refusing to run: {e}", file=sys.stderr)
        return 2
    if a.cmd == "gate":
        problems = Gt.zone_problems(Gt.changed_files(a.ref), a.role) + Gt.append_only(a.ref)
        for f in sorted(Path("tests/srd").rglob("test_*.py")):
            problems += Gt.test_file_problems(f, set(ctx.by_id))
        return _verdict(problems)
    if a.cmd == "related":
        if a.unit not in ctx.by_id:
            print(f"no such unit: {a.unit}", file=sys.stderr)
            return 1
        print(json.dumps(ctx.related(a.unit), indent=1, ensure_ascii=False))
        return 0
    queue = P.build(ctx)
    if a.cmd == "plan":
        P.write(queue)
        print(f"{len(queue)} units queued -> {P.QUEUE}")
        for q in queue[:10]:
            print(f"  {q['id']}  ({q['scope']}, from stage {q['next_stage']})")
    elif a.cmd == "report":
        Rep.write(ctx, queue)
        print(f"wrote {Rep.REPORT}")
    else:
        done = sum(1 for s in ctx.states.values() if s.get("status") in ("green", "red", "blocked"))
        print(f"{len(ctx.units)} units; {len(queue)} to do; {done} finished; {len(ctx.states)} with state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
