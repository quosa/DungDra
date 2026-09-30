"""python -m scripts.srdloop <command>

status               one-line summary of the loop
plan                 write loop/queue.json (pending and stale units, dependencies first)
related <unit-id>    scenarios, tests and engine code related to a unit (JSON)
report               write loop/COVERAGE.md
gate --role R        audit gates on the working tree: write zones for role R, append-only
                     acceptance tests, SRD test-file rules (markers, assertions, no mocks)
dev-gate             dev-loop quality gates: lint, suppressions, coverage ratchet and diff
                     coverage, import layers, duplication, dead code, unit-test hygiene
run --budget USD [--units ID ...]
                     the audit loop (stages A-D per unit); exit 4 = paused, run again to resume
dev --budget USD [--tickets T-n ...]
                     the dev loop (fix open tickets)
tickets              list tickets
mutate FILE LINE OLD NEW NODEID
                     break one engine line in a scratch copy and run a test there

Interactive mode (the /srd-rule skill runs the stages in a Claude Code session):
prompt STAGE UNIT    print the prompt for stage A, B, C or D of a unit
accept STAGE UNIT FILE
                     gate a stage's JSON output; on success checkpoint it
finish UNIT          after stage D: remove refuted tests, open tickets, commit the unit

Rulings (ambiguities the test designer had to resolve):
ruling list          proposed, accepted and rejected rulings
ruling accept P-n [--note TEXT]
                     make it the next R-<n> in the README register; its tests' markers follow
ruling reject P-n --reason TEXT
                     re-queue the unit: stage C rewrites those tests for another reading
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import gates as Gt
from . import mutate as M
from . import plan as P
from . import quality as Q
from . import report as Rep
from . import rulings as Ru
from . import runner as Run
from . import tickets as T
from . import units as U


def _verdict(problems: list[str], note: str = "") -> int:
    for p in problems:
        print(f"  ! {p}")
    head = f"FAIL ({len(problems)} problems)" if problems else "PASS"
    print(head + (f"; {note}" if note else ""))
    return 1 if problems else 0


def _ruling(a) -> int:
    if a.action == "list":
        for r in Ru.all_rulings():
            rid = f" → {r['register_id']}" if r["register_id"] else ""
            print(f"{r['id']:5} {r['status']:9}{rid} {r['unit']}: {r['ruling']}")
            if r["reason"]:
                print(f"      rejected because: {r['reason']}")
        return 0
    if not a.id:
        print("which ruling? e.g. ruling accept P-1", file=sys.stderr)
        return 1
    if a.action == "reject" and not a.reason.strip():
        print("a rejection needs --reason: stage C uses it to pick another reading", file=sys.stderr)
        return 1
    r = Run.decide_ruling(a.id, a.action == "accept", a.note if a.action == "accept" else a.reason)
    print(f"{r['id']}: {r['status']}" + (f" as {r['register_id']}" if r["register_id"] else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.srdloop",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("plan")
    rel = sub.add_parser("related")
    rel.add_argument("unit")
    sub.add_parser("report")
    gate = sub.add_parser("gate")
    gate.add_argument("--role", required=True, choices=sorted(Gt.ZONES))
    gate.add_argument("--ref", default="HEAD")
    devg = sub.add_parser("dev-gate")
    devg.add_argument("--ref", default="HEAD")
    run = sub.add_parser("run")
    run.add_argument("--budget", type=float, required=True, help="USD for this run")
    run.add_argument("--units", nargs="*")
    dev = sub.add_parser("dev")
    dev.add_argument("--budget", type=float, required=True, help="USD for this run")
    dev.add_argument("--tickets", nargs="*")
    sub.add_parser("tickets")
    mut = sub.add_parser("mutate")
    mut.add_argument("file")
    mut.add_argument("line", type=int)
    mut.add_argument("old")
    mut.add_argument("new")
    mut.add_argument("nodeid")
    pr = sub.add_parser("prompt")
    pr.add_argument("stage", choices=list("ABCD"))
    pr.add_argument("unit")
    acc = sub.add_parser("accept")
    acc.add_argument("stage", choices=list("ABCD"))
    acc.add_argument("unit")
    acc.add_argument("file")
    fin = sub.add_parser("finish")
    fin.add_argument("unit")
    ru = sub.add_parser("ruling")
    ru.add_argument("action", choices=["list", "accept", "reject"])
    ru.add_argument("id", nargs="?")
    ru.add_argument("--note", default="")
    ru.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    if a.cmd == "ruling":
        return _ruling(a)
    if a.cmd == "mutate":
        print(M.mutate(a.file, a.line, a.old, a.new, a.nodeid))
        return 0
    if a.cmd == "tickets":
        for t in T.all_tickets():
            print(f"{t['id']:6} {t['status']:8} {t['kind']:8} {t['unit']}: {t['title']}")
        return 0
    if a.cmd == "run":
        return Run.run(a.budget, a.units)
    if a.cmd == "dev":
        return Run.dev(a.budget, a.tickets)
    if a.cmd == "dev-gate":
        problems, metrics = Q.dev_gate(a.ref)
        shown = {k: v for k, v in metrics.items() if not k.startswith("_")}
        return _verdict(problems, f"metrics {shown}")
    try:
        ctx = P.Context.load()
    except U.NotApproved as e:
        print(f"refusing to run: {e}", file=sys.stderr)
        return 2
    if a.cmd == "prompt":
        print(Run.stage_prompt(ctx, a.unit, a.stage))
        return 0
    if a.cmd == "accept":
        output = json.loads(Path(a.file).read_text())
        problems = Run.stage_gate(ctx, a.unit, a.stage, output)
        if not problems:
            Run.checkpoint(a.unit, a.stage, output)
        return _verdict(problems, f"stage {a.stage} of {a.unit} checkpointed" if not problems else "")
    if a.cmd == "finish":
        print(f"{a.unit}: {Run.finish_unit(ctx, a.unit)}")
        return 0
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
