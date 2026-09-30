"""python -m scripts.srdloop <command>

status               one-line summary of the loop
plan                 write loop/queue.json (pending and stale units, dependencies first)
related <unit-id>    scenarios, tests and engine code related to a unit (JSON)
report               write loop/COVERAGE.md
"""

from __future__ import annotations

import argparse
import json
import sys

from . import plan as P
from . import report as Rep
from . import units as U


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.srdloop", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("plan")
    rel = sub.add_parser("related")
    rel.add_argument("unit")
    sub.add_parser("report")
    a = ap.parse_args(argv)
    try:
        ctx = P.Context.load()
    except U.NotApproved as e:
        print(f"refusing to run: {e}", file=sys.stderr)
        return 2
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
