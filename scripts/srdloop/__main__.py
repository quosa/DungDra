"""python -m scripts.srdloop <command> [--help]

The SRD rule loop's command line. `--help` after any command gives its details.
Lists show what still needs the loop or a person; --all adds the finished ones.
Every decision a person makes here is committed with its reason.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import gates as Gt
from . import mutate as M
from . import plan as P
from . import quality as Q
from . import report as Rep
from . import rulings as Ru
from . import runner as Run
from . import state as S
from . import tickets as T
from . import units as U


def _verdict(problems: list[str], note: str = "") -> int:
    for p in problems:
        print(f"  ! {p}")
    head = f"FAIL ({len(problems)} problems)" if problems else "PASS"
    print(head + (f"; {note}" if note else ""))
    return 1 if problems else 0


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _ticket_row(t: dict) -> str:
    return f"{t['id']:6} {t['status']:8} {t['kind']:8} {t['unit']}: {t['title']}"


def _short(v, n: int = 240) -> str:
    v = " ".join(str(v).split())
    return v if len(v) <= n else v[: n - 1] + "…"


def _ticket_show(tid: str) -> int:
    t = T.load(tid)
    print(_ticket_row(t))
    for n in t["tests"]:
        print(f"  test: {n}")
    extras = {k: t[k] for k in ("waive", "cap_usd") if t.get(k)}
    if extras:
        print(f"  {extras}")
    for h in t["history"]:
        rest = ", ".join(f"{k}={_short(v)}" for k, v in h.items() if k not in ("event", "problems"))
        print(f"  - {h['event']}" + (f": {rest}" if rest else ""))
        for p in h.get("problems", []):
            print(f"      ! {_short(p)}")
    for rec in sorted(Run.RUNS.glob(f"{tid}/fix.attempt*.json"), key=lambda p: int(p.stem[11:])):
        r = json.loads(rec.read_text())
        stash = f", stash '{r['stash']}'" if r.get("stash") else ""
        print(f"  {rec}: {r['result']}, ${r['cost_usd']:.2f}{stash}")
    return 0


def _ticket(a) -> int:
    if a.action == "list":
        shown = [t for t in T.all_tickets() if (a.all or t["status"] in T.ACTIVE)]
        for t in shown:
            if a.only in (None, t["kind"]):
                print(_ticket_row(t))
        hidden = len(T.all_tickets()) - len(shown)
        if hidden:
            print(f"({hidden} fixed or void not shown; --all shows them)")
        return 0
    if a.action == "create":
        t = T.create(a.kind, a.unit, a.title, a.test or [])
        T.record(t, "created", by="person")
        Run.commit(f"ticket: {t['id']} created ({t['kind']}, {t['unit']}): {t['title']}", Gt.HARNESS)
        print(_ticket_row(t))
        return 0
    tid = a.id
    if not (T.TICKETS / f"{tid}.json").exists():
        return _fail(f"no ticket {tid} (ticket list --all shows them)")
    if a.action == "show":
        return _ticket_show(tid)
    try:
        if a.action in ("reopen", "void"):
            t = (T.reopen if a.action == "reopen" else T.void)(tid, a.reason)
            message = f"ticket: {tid} {t['status'] if a.action == 'void' else 'reopened'}: {a.reason}"
        elif a.action == "waive":
            check = a.check
            if not a.reason.strip():
                return _fail("a waiver needs --reason")
            t = T.load(tid)
            t.setdefault("waive", {})[check] = a.reason
            T.record(t, "waiver", check=check, reason=a.reason)
            message = f"ticket: {tid} waives {check}: {a.reason}"
        else:  # cap
            t = T.load(tid)
            t["cap_usd"] = a.usd
            T.record(t, "cap", usd=t["cap_usd"])
            message = f"ticket: {tid} fixer cap ${t['cap_usd']:.2f}"
    except ValueError as e:
        return _fail(str(e))
    Run.commit(message, Gt.HARNESS)
    print(_ticket_row(t))
    return 0


def _review(a) -> int:
    if a.action == "list":
        for i, (uid, n) in enumerate(S.waiting_review(), 1):
            print(f"{i:3}  {uid}: {n}")
        if a.all:
            for uid, st in sorted(S.all_states().items()):
                for r in st.get("reviewed", []):
                    print(f"  {r['decision']:7}  {uid}: {r['test']} ({r['reason']})")
        elif not S.waiting_review():
            print("(nothing waiting for review; --all shows the decided ones)")
        return 0
    try:
        print(Run.decide_review(a.refs, a.action == "keep", a.reason))
    except ValueError as e:
        return _fail(str(e))
    return 0


def _ruling(a) -> int:
    if a.action == "list":
        shown = [r for r in Ru.all_rulings() if a.all or r["status"] == "proposed"]
        for r in shown:
            rid = f" → {r['register_id']}" if r["register_id"] else ""
            print(f"{r['id']:5} {r['status']:9}{rid} {r['unit']}: {r['ruling']}")
            if r["reason"]:
                print(f"      rejected because: {r['reason']}")
        hidden = len(Ru.all_rulings()) - len(shown)
        if hidden:
            print(f"({hidden} decided not shown; --all shows them)")
        return 0
    if a.action == "reject" and not a.reason.strip():
        return _fail("a rejection needs --reason: stage C uses it to pick another reading")
    r = Run.decide_ruling(a.id, a.action == "accept", a.note if a.action == "accept" else a.reason)
    print(f"{r['id']}: {r['status']}" + (f" as {r['register_id']}" if r["register_id"] else ""))
    return 0


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m scripts.srdloop", description=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<command>")

    def cmd(parent, name, summary, details=""):
        return parent.add_parser(name, help=summary, description=f"{summary}. {details}".strip())

    cmd(sub, "help", "this help; `help <command> [<action>]` for one command's").add_argument(
        "topic", nargs="*", metavar="<command>"
    )
    cmd(
        sub, "status", "where the loop stands and what waits for you", "Units, the ticket backlog, decisions."
    )
    cmd(sub, "plan", "write loop/queue.json", "Pending and stale units, dependencies first.")
    rel = cmd(sub, "related", "scenarios, tests and engine code related to a unit (JSON)")
    rel.add_argument("unit")
    cmd(sub, "report", "write loop/COVERAGE.md", "States per chapter, the queue and what waits for a person.")
    run = cmd(
        sub, "run", "the audit loop: stages A-D per unit", "Exit 3: a circuit breaker; 4: paused, run again."
    )
    run.add_argument("--budget", type=float, required=True, help="USD for this run")
    run.add_argument("--units", nargs="*", metavar="ID", help="only these units (default: the queue)")
    dev = cmd(
        sub, "dev", "the dev loop: fix open tickets", "Exit 3: a circuit breaker; 4: paused, run again."
    )
    dev.add_argument("--budget", type=float, required=True, help="USD for this run")
    dev.add_argument("--tickets", nargs="*", metavar="T-n", help="only these tickets (default: all open)")
    dev.add_argument("--recheck", metavar="T-n", help="gate, review and commit a change already in the tree")
    gate = cmd(
        sub, "gate", "audit gates on the working tree", "Write zones, append-only, SRD test-file rules."
    )
    gate.add_argument("--role", required=True, choices=sorted(Gt.ZONES))
    gate.add_argument("--ref", default="HEAD")
    devg = cmd(
        sub, "dev-gate", "dev-loop quality gates", "Lint, suppressions, coverage, import layers, duplication."
    )
    devg.add_argument("--ref", default="HEAD")

    tk = cmd(sub, "ticket", "tickets: work for the dev loop", "See `ticket <action> --help`.")
    tks = tk.add_subparsers(dest="action", required=True, metavar="<action>")
    ls = cmd(tks, "list", "open, stuck and disputed tickets")
    ls.add_argument("--all", action="store_true", help="fixed and void too")
    ls.add_argument("--kind", dest="only", choices=sorted(T.PRIORITY), help="only this kind")
    cmd(tks, "show", "a ticket, its history and each fix attempt").add_argument("id", metavar="T-n")
    cr = cmd(tks, "create", "file a ticket by hand")
    cr.add_argument("kind", choices=sorted(T.PRIORITY))
    cr.add_argument("unit", help="the SRD unit id it belongs to (or ENGINE)")
    cr.add_argument("title", help="what is wrong, as the rule versus the engine")
    cr.add_argument("--test", action="append", metavar="NODEID", help="a test it must make pass (repeatable)")
    for name, summary in (
        ("reopen", "back to the dev loop with fresh attempts (a settled dispute, a stuck ticket)"),
        ("void", "no longer wanted (a duplicate, superseded)"),
    ):
        p = cmd(tks, name, summary)
        p.add_argument("id", metavar="T-n")
        p.add_argument("--reason", required=True)
    wv = cmd(tks, "waive", "waive one gate for one ticket")
    wv.add_argument("id", metavar="T-n")
    wv.add_argument("check", choices=sorted(Q.WAIVABLE))
    wv.add_argument("--reason", required=True)
    cp = cmd(tks, "cap", "a larger per-call budget for the fixer on a big ticket")
    cp.add_argument("id", metavar="T-n")
    cp.add_argument("usd", type=float, metavar="USD")

    ru = cmd(
        sub,
        "ruling",
        "rulings: ambiguities the test designer had to resolve",
        "See `ruling <action> --help`.",
    )
    rus = ru.add_subparsers(dest="action", required=True, metavar="<action>")
    cmd(rus, "list", "proposals awaiting a decision").add_argument(
        "--all", action="store_true", help="accepted and rejected too"
    )
    acc = cmd(rus, "accept", "make it the next R-<n> in the README register; its tests' markers follow")
    acc.add_argument("id", metavar="P-n")
    acc.add_argument("--note", default="", help="shown with the ruling in the register")
    rej = cmd(rus, "reject", "re-queue the unit: stage C rewrites those tests for another reading")
    rej.add_argument("id", metavar="P-n")
    rej.add_argument("--reason", required=True, help="stage C uses it to pick another reading")

    rv = cmd(
        sub,
        "review",
        "tests the verifier doubted, kept until a person decides",
        "See `review <action> --help`.",
    )
    rvs = rv.add_subparsers(dest="action", required=True, metavar="<action>")
    cmd(rvs, "list", "numbered tests waiting for a decision").add_argument(
        "--all", action="store_true", help="the decided ones too"
    )
    for name in ("keep", "remove"):
        p = cmd(rvs, name, f"{name} tests, by number from `review list` or node id; one commit")
        p.add_argument("refs", nargs="+", metavar="N|NODEID")
        p.add_argument("--reason", required=True)

    mut = cmd(sub, "mutate", "break one engine line in a scratch copy and run a test there")
    for arg in ("file", "line", "old", "new", "nodeid"):
        mut.add_argument(arg, type=int if arg == "line" else str)
    pr = cmd(sub, "prompt", "interactive mode: print the prompt for a stage of a unit")
    pr.add_argument("stage", choices=list("ABCD"))
    pr.add_argument("unit")
    ac = cmd(sub, "accept", "interactive mode: gate a stage's JSON output; on success checkpoint it")
    ac.add_argument("stage", choices=list("ABCD"))
    ac.add_argument("unit")
    ac.add_argument("file")
    cmd(
        sub, "finish", "interactive mode: after stage D, remove refuted tests, open tickets, commit"
    ).add_argument("unit")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _parser()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        argv = ["help"]
    a = ap.parse_args(argv)
    if a.cmd == "help":  # the same as --help, at any depth: help ticket create == ticket create --help
        ap.parse_args([*a.topic, "--help"])
    if a.cmd == "ruling":
        return _ruling(a)
    if a.cmd == "review":
        return _review(a)
    if a.cmd == "ticket":
        return _ticket(a)
    if a.cmd == "mutate":
        print(M.mutate(a.file, a.line, a.old, a.new, a.nodeid))
        return 0
    if a.cmd == "run":
        return Run.run(a.budget, a.units)
    if a.cmd == "dev":
        return Run.recheck(a.recheck, a.budget) if a.recheck else Run.dev(a.budget, a.tickets)
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
        _status(ctx, queue)
    return 0


def _status(ctx: P.Context, queue: list[dict]) -> None:
    states = Counter(s.get("status") for s in ctx.states.values())
    finished = ", ".join(f"{states[k]} {k}" for k in ("green", "red", "blocked", "out-of-scope") if states[k])
    audited = f"{sum(states.values())} audited ({finished or 'none'})"
    print(f"{len(ctx.units)} units: {len(queue)} in the queue; {audited}")
    backlog, you = Run.todo(ctx.states)
    print("\n".join(backlog))
    print("Waiting for you:" if you else "Nothing waiting for you.")
    for line in you:
        print(f"  - {line}")


if __name__ == "__main__":
    sys.exit(main())
