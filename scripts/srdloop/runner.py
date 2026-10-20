"""The two loops.

Audit loop (`run`): for each queued unit, stages A (rule-analyst) → B (scenario-auditor) →
C (test-designer) → D (test-verifier). Each stage's output must pass its gates; a failing
stage gets one retry with the problems in its prompt, then the unit is marked incomplete.
Outputs are checkpointed in loop/runs/<unit>/<stage>.json. At the end the harness removes
refuted tests, opens tickets for red tests and missing capabilities, and commits the unit.

Dev loop (`dev`): for each open ticket, the fixer changes the engine; the harness removes the
ticket's xfail markers, runs the acceptance tests and the dev gate, asks the fix-reviewer,
and commits, or rolls back and counts a failed attempt (three and the ticket is stuck).

The harness, not an agent, makes every commit.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from . import claude as C
from . import gates as Gt
from . import plan as P
from . import prompts as Pr
from . import quality as Q
from . import rulings as Ru
from . import state as S
from . import tickets as T
from .gates import git

RUNS = Path("loop/runs")
MAX_OPEN_BUGS = 15  # the audit loop's breaker; infra, refactor and coverage don't count
FOLLOWUP_FROM = ("bug", "infra")  # a refactor or coverage fix files no follow-ups: no chains
MAX_CONSECUTIVE_INCOMPLETE = 3
STAGE_ROLE = {"A": "rule-analyst", "B": "scenario-auditor", "C": "test-designer", "D": "test-verifier"}
AGENT_ZONES = ("tests", "docs/scenario-notes.md", "loop/abuse-catalogue.md")
DEV_ZONES = ("dungdra", "tests/unit", "loop/requests")
KEEP = Gt.HARNESS + ("loop/requests/**",)  # survives set_aside: a fixer's request is for a person to read


class Stop(Exception):
    """A circuit breaker: the loop must not continue without a person."""


Invoke = Callable[..., C.Result]


# ---------------------------------------------------------------- checkpoints
def checkpoint(uid: str, stage: str, output: dict, runs: Path = RUNS) -> None:
    d = runs / uid
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stage}.json").write_text(json.dumps(output, indent=1, ensure_ascii=False) + "\n")
    st = S.load(uid)
    st["stages"][stage] = {"at": round(time.time()), "summary": str(output.get("summary", ""))[:300]}
    S.save(st)


def stage_output(uid: str, stage: str, runs: Path = RUNS) -> dict:
    return json.loads((runs / uid / f"{stage}.json").read_text())


# ---------------------------------------------------------------- stage gates
def gate_analysis(unit: dict, out: dict, known: dict[str, dict]) -> list[str]:
    uid = unit["id"]
    problems = Gt.quotes(out["clauses"], "text", [unit["text"]], "clause")
    ids = [c["id"] for c in out["clauses"]]
    problems += [
        f"clause id {i!r} is not {uid}#<n>" for i in ids if not re.fullmatch(rf"{re.escape(uid)}#\d+", i)
    ]
    problems += [f"clause id {i} used twice" for i in {i for i in ids if ids.count(i) > 1}]
    for r in out["relations"]:
        tgt = known.get(r["target"])
        if tgt is None:
            problems.append(f"relation to unknown unit {r['target']!r}")
        else:
            problems += Gt.quotes([r], "evidence", [unit["text"], tgt["text"]], f"relation to {r['target']}")
    for field, items in (("quote", out["ambiguities"]), ("quote", out["gaps"]), ("quote", out["traps"])):
        problems += Gt.quotes(items, field, [unit["text"]], field)
    return problems


def _item_text(kind: str, item: str, scenarios: dict[str, str], fixtures: str = "") -> str:
    """The text a verdict's evidence must quote: the scenario with the shared fixtures it relies
    on, or the test or code file."""
    if kind == "scenario":
        return f"{scenarios[item]}\n{fixtures}" if item in scenarios else ""
    path = item.split("::")[0] if kind == "test" else item.rsplit(":", 1)[0]
    return Path(path).read_text() if Path(path).exists() else ""


def gate_verdicts(
    unit: dict, out: dict, related: dict, scenarios: dict[str, str], fixtures: str = ""
) -> list[str]:
    have = {v["item"] for v in out["verdicts"]}
    need = {s["id"] for s in related["scenarios"]}
    need |= {t for s in related["scenarios"] for t in s["tests"]} | set(related["srd_tests"])
    need |= {f"{c['file']}:{c['line']}" for c in related["code"] if c["match"] == "tag"}
    problems = [f"no verdict for {i}" for i in sorted(need - have)]
    problems += Gt.quotes(out["verdicts"], "rule_quote", [unit["text"]], "verdict")
    for v in out["verdicts"]:
        problems += Gt.quotes(
            [v],
            "evidence",
            [_item_text(v["kind"], v["item"], scenarios, fixtures)],
            f"verdict on {v['item']}",
        )
    return problems


def _test_exists(nodeid: str) -> bool:
    path, _, name = nodeid.partition("::")
    return Path(path).exists() and name.split("[")[0] in Gt._tests(Path(path).read_text())


def existing_tests(uid: str, root: str = "tests/srd") -> list[dict]:
    """The unit's tests already committed to the SRD suite (a revisit writes only new ones), with
    the clause and kind their markers give, so the coverage gate counts them too. Committed only:
    a test the designer just wrote must be in its plan to count."""
    out = []
    for f in git("ls-tree", "-r", "--name-only", "HEAD", "--", root).split():
        if Path(f).name.startswith("test_") and f.endswith(".py"):
            for name, m in Gt.srd_markers(git("show", f"HEAD:{f}")).items():
                if m["unit"] == uid:
                    out.append({"name": f"{f}::{name}", "clause": m["clause"], "kind": m["kind"]})
    return out


def gate_tests(
    unit: dict, out: dict, analysis: dict, unit_ids: set[str], ref: str = "HEAD", existing: list[dict] = ()
) -> list[str]:
    problems = Gt.quotes(out["tests"], "rule_quote", [unit["text"]], "test")
    untestable = {n["clause"]: n for n in out["not_testable"]}
    clauses = [
        {**c, "not_testable": c["id"] in untestable, "reason": untestable.get(c["id"], {}).get("reason", "")}
        for c in analysis["clauses"]
    ]
    ids = {c["id"] for c in clauses}
    earlier = [t for t in existing if t["clause"] in ids and t["kind"] in Gt.KINDS]
    problems += Gt.clause_coverage(clauses, out["tests"] + earlier, out["abuse"], out.get("kind_waivers", []))
    problems += [f"{t['name']}: no such test" for t in out["tests"] if not _test_exists(t["name"])]
    changed = Gt.changed_files(ref)
    problems += Gt.zone_problems(changed, "test-designer")
    rejected = frozenset(
        n
        for r in Ru.all_rulings()
        if r["status"] == "rejected" and r["unit"] == unit["id"]
        for n in r["tests"]
    )
    problems += Gt.append_only(ref, allow=rejected)  # tests of a rejected ruling must change
    known = Ru.known_ids()
    for f in changed:
        if f.startswith("tests/srd/") and Path(f).name.startswith("test_") and Path(f).exists():
            problems += Gt.test_file_problems(Path(f), unit_ids, rulings=known)
    py = [f for f in changed if f.endswith(".py") and Path(f).exists()]
    for f in py:
        tidy(f)  # formatting is the formatter's job; what it can't fix (line length, unused names) is theirs
    problems += Q.ruff(*py) if py else []
    names = {t["name"] for t in out["tests"]}
    for r in out["rulings_proposed"]:
        problems += [
            f"proposed ruling names {n!r}, which isn't one of your tests"
            for n in r["tests"]
            if n not in names
        ]
    live = [t for t in out["tests"] if _test_exists(t["name"])]
    problems += Gt.claimed_outcomes(
        {t["name"]: t["claim"] for t in live}, Gt.run_pytest([t["name"] for t in live])
    )
    return problems


def gate_verification(out: dict, plan: dict) -> list[str]:
    have = {v["test"] for v in out["verdicts"]}
    return [f"no verdict for {t['name']}" for t in plan["tests"] if t["name"] not in have]


# ---------------------------------------------------------------- editing test files
def _function_span(src: str, name: str) -> tuple[int, int] | None:
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            return start, node.end_lineno
    return None


def tidy(path: str) -> None:
    """After the harness edits a test file, the formatter cleans up (blank lines, spacing)."""
    Q.run("ruff", "format", "--quiet", path)


def remove_test(nodeid: str) -> None:
    """The harness removes a refuted test (the designer may not delete tests)."""
    path, _, name = nodeid.partition("::")
    src = Path(path).read_text()
    span = _function_span(src, name.split("[")[0])
    if span:
        lines = src.splitlines(keepends=True)
        del lines[span[0] - 1 : span[1]]
        Path(path).write_text("".join(lines))
        tidy(path)


def set_ticket(nodeid: str, tid: str) -> None:
    """Replace the placeholder T-new in a red test's xfail reason with the real ticket id."""
    path, _, name = nodeid.partition("::")
    src = Path(path).read_text()
    span = _function_span(src, name.split("[")[0])
    if span:
        lines = src.splitlines(keepends=True)
        for i in range(span[0] - 1, span[1]):
            lines[i] = lines[i].replace("T-new", tid)
        Path(path).write_text("".join(lines))
        tidy(path)


def drop_xfail(nodeid: str, tid: str) -> bool:
    """After a fix: remove the xfail decorator that names the ticket, however many lines it
    spans. Returns whether one was removed."""
    path, _, name = nodeid.partition("::")
    src = Path(path).read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name.split("[")[0]:
            for d in node.decorator_list:
                text = ast.get_source_segment(src, d) or ""
                if "xfail" in text and re.search(rf"\b{re.escape(tid)}\b", text):
                    lines = src.splitlines(keepends=True)
                    del lines[d.lineno - 1 : d.end_lineno]
                    Path(path).write_text("".join(lines))
                    tidy(path)
                    return True
    return False


# ---------------------------------------------------------------- working tree
def dirty(ref: str = "HEAD") -> list[str]:
    return Gt.changed_files(ref)


def _paths(paths: tuple[str, ...]) -> list[str]:
    """Pathspecs for git: zone globs ("loop/state/**") as their directory; only existing paths."""
    out = [p.removesuffix("/**") for p in paths]
    return [p for p in out if Path(p).exists() or git("ls-files", "--", p).strip()]


def stash(paths: tuple[str, ...], message: str) -> None:
    """Set leftover agent changes aside (recoverable with git stash list / pop), never delete them."""
    present = _paths(paths)
    if present and git("status", "--porcelain", "--", *present).strip():
        git("stash", "push", "--include-untracked", "-m", message, "--", *present)


def restore_set_aside(uid: str, stage: str) -> bool:
    """Bring back the files a unit's failed stage set aside (the test files stage C wrote, for a
    resume at D). False when there is no such stash or it doesn't apply cleanly."""
    message = f"srdloop: {uid} incomplete at stage {stage}"
    for line in git("stash", "list").splitlines():
        ref, _, rest = line.partition(": ")
        if rest.endswith(message):
            popped = subprocess.run(["git", "stash", "pop", ref], capture_output=True, check=False)
            if popped.returncode != 0:  # a conflicted pop keeps the stash; undo what it half applied
                git("checkout", "--", ".")
                return False
            return True
    return False


def set_aside(message: str) -> str:
    """After failed work: stash every change except the loop's own files and the fixer's
    requests to a person, wherever the agent put it (a gate caught it writing outside its zone;
    that file must not stay behind either). Returns the stash message, or "" if nothing was set aside."""
    import fnmatch

    files = [f for f in dirty() if not any(fnmatch.fnmatch(f, g) for g in KEEP)]
    if not files:
        return ""
    git("stash", "push", "--include-untracked", "-m", message, "--", *files)
    return message


def commit(message: str, paths: tuple[str, ...]) -> str:
    git("add", "--all", "--", *_paths(paths))
    git("commit", "-q", "-m", message)
    return git("rev-parse", "--short", "HEAD").strip()


def foreign_changes(harness_paths: tuple[str, ...] = Gt.HARNESS) -> list[str]:
    """Uncommitted changes that belong to no agent zone: a person's work in progress."""
    import fnmatch

    return [
        f
        for f in dirty()
        if not any(fnmatch.fnmatch(f, g) for g in harness_paths)
        and not f.startswith(AGENT_ZONES + DEV_ZONES)
        and f != "loop/quality-baseline.json"
    ]


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def todo(states: dict[str, dict]) -> tuple[list[str], list[str]]:
    """What the loop and a person still have to do: (backlog lines, waiting-for-you lines)."""
    active = [t for t in T.all_tickets() if t["status"] in T.ACTIVE]
    open_ = [t for t in active if t["status"] == "open"]
    by_kind = ", ".join(f"{sum(t['kind'] == k for t in open_)} {k}" for k in T.PRIORITY)
    full = ": run the dev loop first" if len(T.open_bugs()) > MAX_OPEN_BUGS else ""
    backlog = [
        f"{_n(len(open_), 'open ticket')} ({by_kind}); "
        f"the audit loop stops above {MAX_OPEN_BUGS} open bugs{full}"
    ]
    parked = T.parked()
    if parked:
        backlog.append(f"{len(parked)} parked (built only when named): ticket list --all")
    waiting_ruling = [t["id"] for t in open_ if waits_for_ruling(t)]
    if waiting_ruling:
        backlog.append(f"  {len(waiting_ruling)} of them wait for a ruling: {', '.join(waiting_ruling)}")
    you = []
    proposals = Ru.pending()
    if proposals:
        ids = ", ".join(r["id"] for r in proposals)
        you.append(f"{_n(len(proposals), 'ruling')} to decide ({ids}): ruling list")
    doubted = S.waiting_review(states)
    if doubted:
        you.append(f"{_n(len(doubted), 'test')} to review: review list")
    for status, how in (("dispute", "disputed by the fixer"), ("stuck", "stuck after 3 attempts")):
        ids = [t["id"] for t in active if t["status"] == status]
        if ids:
            you.append(f"{_n(len(ids), 'ticket')} {how} ({', '.join(ids)}): ticket show <T-n>")
    incomplete = sorted(u for u, st in states.items() if st.get("status") == "incomplete")
    if incomplete:
        names = ", ".join(incomplete)
        you.append(f"{_n(len(incomplete), 'unit')} failed its gates twice ({names}): loop/state/<unit>.json")
    done = {t["id"] for t in T.all_tickets() if t["status"] in ("fixed", "void")}
    stashes = [ln for ln in git("stash", "list").splitlines() if "srdloop: " in ln]
    live = [ln for ln in stashes if not any(f"srdloop: {tid} " in ln for tid in done)]
    if live:
        you.append(f"{_n(len(live), 'set-aside attempt')} of unfinished work: git stash list")
    if len(stashes) > len(live):
        n = len(stashes) - len(live)
        you.append(f"{_n(n, 'set-aside attempt')} of finished tickets, safe to drop: git stash list")
    foreign = foreign_changes()
    if foreign:
        you.append(f"uncommitted changes the loop won't start with: {', '.join(foreign[:5])}")
    return backlog, you


def preflight(harness_paths: tuple[str, ...] = Gt.HARNESS) -> None:
    """The loop only starts on a tree it understands: agent-zone leftovers of an interrupted
    unit are fine (resume keeps or stashes them); anything else is a person's work in progress."""
    foreign = foreign_changes(harness_paths)
    if foreign:
        raise Stop(
            "the working tree has changes the loop didn't make; commit or stash them: "
            + ", ".join(foreign[:8])
        )


def suite_red() -> list[str]:
    """Acceptance and unit tests that fail outright (xfail is fine) before the loop starts."""
    out = Gt.run_pytest(["tests"])
    return [n for n, o in out.items() if o in ("failed", "error", "xpassed")]


# ---------------------------------------------------------------- audit loop
def stage_prompt(ctx: P.Context, uid: str, stage: str, problems: list[str] = ()) -> str:
    unit = ctx.by_id[uid]
    if stage == "A":
        rel_ids = sorted({e.dst for e in ctx.edges if e.src == uid})
        return Pr.analysis(unit, [ctx.by_id[i] for i in rel_ids if i in ctx.by_id], problems)
    if stage == "B":
        return Pr.verdicts(unit, stage_output(uid, "A"), ctx.related(uid), problems)
    if stage == "C":
        return Pr.test_plan(unit, stage_output(uid, "A"), stage_output(uid, "B"), problems)
    return Pr.verification(unit, stage_output(uid, "C"), problems)


def stage_gate(ctx: P.Context, uid: str, stage: str, output: dict) -> list[str]:
    unit = ctx.by_id[uid]
    if stage == "A":
        return gate_analysis(unit, output, ctx.by_id)
    if stage == "B":
        scenarios = {s.id: s.text for s in ctx.scenarios}
        return gate_verdicts(unit, output, ctx.related(uid), scenarios, ctx.fixtures)
    if stage == "C":
        return gate_tests(unit, output, stage_output(uid, "A"), set(ctx.by_id), existing=existing_tests(uid))
    return gate_verification(output, stage_output(uid, "C"))


def _pending(uid: str, stage: str, runs: Path = RUNS) -> Path:
    return runs / uid / f"{stage}.pending.json"


def run_unit(ctx: P.Context, uid: str, budget: C.Budget, invoke: Invoke = C.invoke, runs: Path = RUNS) -> str:
    """Stages A-D for one unit. Every attempt's output and gate problems are kept in
    loop/runs/<unit>/<stage>.attempt<n>.json; a failed attempt leaves <stage>.pending.json, so a
    run that pauses before the retry resumes with the retry (and the agent's files), not from scratch."""
    st = S.load(uid)
    if st["status"] == "incomplete" and S.next_stage(st) == "D" and not restore_set_aside(uid, "D"):
        st["stages"].pop("C", None)  # D verifies C's test files; without them, C writes them again
    st["status"] = "in-progress"
    S.save(st)
    for stage in [s for s in S.STAGES if s not in st["stages"]]:
        role = C.ROLES[STAGE_ROLE[stage]]
        pending = _pending(uid, stage, runs)
        first, problems = 1, []
        if pending.exists():  # resume a retry
            p = json.loads(pending.read_text())
            first, problems = p["attempt"] + 1, p["problems"]
        elif stage == "C":
            stash(AGENT_ZONES, f"srdloop: {uid} stage C leftovers")  # C starts from a clean test tree
        for attempt in range(first, 3):
            left = budget.limit_usd - budget.spent_usd
            cap = role.cap_usd if attempt == 1 else max(role.cap_usd, min(role.cap_usd * 1.5, left))
            prompt = stage_prompt(ctx, uid, stage, problems)
            res = invoke(STAGE_ROLE[stage], prompt, budget=budget, about=uid, stage=stage, cap=cap)
            if res.output is None:
                problems = [f"no structured output ({res.error})"]
            else:
                problems = stage_gate(ctx, uid, stage, res.output)
            (runs / uid).mkdir(parents=True, exist_ok=True)
            record = {
                "output": res.output,
                "problems": problems,
                "cost_usd": res.cost_usd,
                "session": res.session_id,
                "error": res.error,  # the CLI's exit code, subtype and message when there was no output
            }
            (runs / uid / f"{stage}.attempt{attempt}.json").write_text(
                json.dumps(record, indent=1, ensure_ascii=False)
            )
            if not problems:
                pending.unlink(missing_ok=True)
                checkpoint(uid, stage, res.output, runs)
                break
            pending.write_text(json.dumps({"attempt": attempt, "problems": problems}, ensure_ascii=False))
        else:
            pending.unlink(missing_ok=True)
            st = S.load(uid)
            st.update(
                status="incomplete",
                problems={"stage": stage, "problems": problems[:40]},
                fingerprint=S.fingerprint(
                    P.inputs(ctx, uid)
                ),  # a re-run resumes here unless the rule changed
            )
            S.save(st)
            set_aside(f"srdloop: {uid} incomplete at stage {stage}")
            commit(f"srd: {uid} incomplete at stage {stage}", Gt.HARNESS)
            return "incomplete"
    return finish_unit(ctx, uid)


def finish_unit(ctx: P.Context, uid: str) -> str:
    plan, check = stage_output(uid, "C"), stage_output(uid, "D")
    st = S.load(uid)
    verdicts = {v["test"]: v for v in check["verdicts"]}
    refuted = [t for t in plan["tests"] if verdicts[t["name"]]["verdict"] == "refute"]
    for t in refuted:
        if verdicts[t["name"]]["confidence"] >= 0.5:
            remove_test(t["name"])
    for_review = [t["name"] for t in refuted if verdicts[t["name"]]["confidence"] < 0.5]
    kept = [t for t in plan["tests"] if t not in refuted or t["name"] in for_review]
    removed = {t["name"] for t in refuted} - set(for_review)
    keep_old = [n for n in st.get("tests", []) if n not in removed]  # a revisit's earlier tests stay
    tickets = []
    by_title: dict[str, list[str]] = {}
    for t in kept:
        if t["claim"] == "red":
            by_title.setdefault(t.get("ticket_title") or f"{uid}: {t['clause']}", []).append(t["name"])
    for title, names in by_title.items():
        tk = T.create("bug", uid, title, names)
        for n in names:
            set_ticket(n, tk["id"])
        tickets.append(tk["id"])
    missing = [n for n in plan["not_testable"] if n.get("kind", "missing") == "missing"]
    out_of_scope = [n for n in plan["not_testable"] if n.get("kind") == "out-of-scope"]
    for n in missing:  # the engine should support it: an infra ticket (one per capability)
        tid = T.file("infra", uid, n["infra_ticket"], [])["id"]
        tickets += [tid] if tid not in tickets else []
    kept_names = {t["name"] for t in kept}
    for r in plan["rulings_proposed"]:  # file each proposal and mark the tests that depend on it
        tests = [n for n in r["tests"] if n in kept_names]
        if tests:
            pr = Ru.create(uid, r["ambiguity"], r["ruling"], tests)
            for n in tests:
                Ru.set_marker(n, pr["id"])
                tidy(n.split("::")[0])
    analysis = stage_output(uid, "A")
    clauses = {c["id"] for c in analysis["clauses"]}
    if Ru.pending(uid):
        status = "blocked"  # a reading nobody has agreed to yet: python -m scripts.srdloop ruling ...
    elif by_title:
        status = "red"
    elif missing:
        status = "blocked"
    elif out_of_scope and not kept and clauses <= {n["clause"] for n in out_of_scope}:
        status = "out-of-scope"  # nothing here the implemented subset covers; re-queued when that changes
    else:
        status = "green"
    st.update(
        status=status,
        relations=analysis["relations"],
        tickets=st.get("tickets", []) + tickets,
        refuted=[t["name"] for t in refuted if t["name"] not in for_review],
        for_review=for_review,
        tests=list(dict.fromkeys([*keep_old, *(t["name"] for t in kept)])),  # a revisit adds to the list
        out_of_scope=[{"clause": n["clause"], "reason": n["reason"]} for n in out_of_scope],
        kind_waivers=plan.get("kind_waivers", []),
        fingerprint=S.fingerprint(P.inputs(ctx, uid)),
    )
    st.pop("problems", None)
    S.save(st)
    n_tests = len(kept)
    commit(f"srd: {uid} — {status}, {n_tests} tests, {len(tickets)} tickets", AGENT_ZONES + Gt.HARNESS)
    return status


def run(budget_usd: float, only: list[str] | None = None, invoke: Invoke = C.invoke, log=print) -> int:
    """The audit loop. Exit codes: 0 done, 3 stopped by a circuit breaker, 4 paused (budget or
    transient failure; run again to resume)."""
    budget = C.Budget(budget_usd)
    try:
        preflight()
        red = suite_red()
        if red:
            raise Stop(f"the test suite is red before the loop starts: {red[:5]}")
        incomplete_in_a_row = 0
        while True:
            ctx = P.Context.load()
            queue = [q for q in P.build(ctx) if only is None or q["id"] in only]
            if not queue:
                log("audit loop: nothing left to do")
                return 0
            if len(T.open_bugs()) > MAX_OPEN_BUGS:
                raise Stop(f"more than {MAX_OPEN_BUGS} open bugs; run the dev loop first")
            uid = queue[0]["id"]
            if queue[0]["revisit"] or queue[0]["stale"]:  # start over from its first stage to redo
                st = S.load(uid)
                keep = S.STAGES[: S.STAGES.index(queue[0]["next_stage"])]
                st["stages"] = {k: v for k, v in st["stages"].items() if k in keep}
                st["revisit"] = False
                S.save(st)
            log(f"» {uid} (from stage {queue[0]['next_stage']}; ${budget.spent_usd:.2f} spent)")
            status = run_unit(ctx, uid, budget, invoke)
            log(f"  {uid}: {status}")
            incomplete_in_a_row = incomplete_in_a_row + 1 if status == "incomplete" else 0
            if incomplete_in_a_row >= MAX_CONSECUTIVE_INCOMPLETE:
                raise Stop(f"{MAX_CONSECUTIVE_INCOMPLETE} units in a row failed their gates")
            if only is not None:
                only = [u for u in only if u != uid]
    except C.Paused as e:
        log(f"paused: {e}. {e.hint}")
        return 4
    except Stop as e:
        log(f"stopped: {e}")
        return 3


# ---------------------------------------------------------------- dev loop
def xfail_ticket(nodeid: str) -> str | None:
    """The ticket id named in a test's xfail marker, if it has one."""
    path, _, name = nodeid.partition("::")
    if not Path(path).exists():
        return None
    src = Path(path).read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name.split("[")[0]:
            for d in node.decorator_list:
                text = ast.get_source_segment(src, d) or ""
                if "xfail" in text and (m := re.search(r"\bT-\d+\b", text)):
                    return m.group(0)
    return None


def close_co_fixed(tk: dict, red: list[str]) -> tuple[list[dict], list[str]]:
    """A fix may also fix another open ticket: its strict-xfail tests now xpass. Drop those
    markers and re-run that ticket's tests; if they all pass, the ticket is fixed too."""
    fixed, problems = [], []
    others = sorted({t for n in red if (t := xfail_ticket(n)) and t != tk["id"]})
    for tid in others:
        other = T.load(tid)
        if other["status"] != "open":
            continue
        for n in other["tests"]:
            drop_xfail(n, tid)
        outcomes = Gt.run_pytest(other["tests"])
        if all(o == "passed" for o in outcomes.values()):
            fixed.append(other)
        else:
            problems += [f"{n}: {o} (after also fixing {tid})" for n, o in outcomes.items() if o != "passed"]
    return fixed, problems


def waits_for_ruling(tk: dict) -> str | None:
    """A ticket whose tests depend on a proposed (undecided) ruling waits: returns its id."""
    pending = {r["id"] for r in Ru.pending()}
    for n in tk["tests"]:
        path, _, name = n.partition("::")
        if Path(path).exists():
            ruling = Gt.srd_markers(Path(path).read_text()).get(name.split("[")[0], {}).get("ruling")
            if ruling in pending:
                return ruling
    return None


def refresh_status(uid: str) -> str:
    """After a ruling decision: blocked while proposals are pending, else red while tickets are open."""
    st = S.load(uid)
    if st["status"] not in ("blocked", "red", "green"):
        return st["status"]
    open_ids = {t["id"] for t in T.open_tickets()}
    bugs = [t for t in st.get("tickets", []) if t in open_ids]
    st["status"] = "blocked" if Ru.pending(uid) else ("red" if bugs else "green")
    S.save(st)
    return st["status"]


def decide_ruling(pid: str, accept: bool, text: str = "") -> dict:
    """Accept (text = an optional note) or reject (text = the reason) a proposal, then commit."""
    if accept:
        r = Ru.accept(pid, note=text)
        for n in r["tests"]:
            tidy(n.split("::")[0])
        status = refresh_status(r["unit"])
        message = f"ruling: {pid} accepted as {r['register_id']} ({r['unit']} {status})"
        commit(message, ("README.md", *Gt.ACCEPTANCE, "loop/rulings") + Gt.HARNESS)
        return r
    r = Ru.reject(pid, reason=text)
    st = S.load(r["unit"])
    st["fingerprint"] = None  # stale: stage C rewrites the tests that used this reading
    st["stages"].pop("C", None)
    st["stages"].pop("D", None)
    S.save(st)
    for t in T.open_tickets():  # tickets built on the rejected reading are void
        if set(t["tests"]) & set(r["tests"]):
            t["status"] = "void"
            T.record(t, "void", reason=f"ruling {pid} rejected")
    commit(f"ruling: {pid} rejected ({r['unit']} re-queued)", ("loop/rulings",) + Gt.HARNESS)
    return r


def decide_review(refs: list[str], keep: bool, reason: str) -> str:
    """A person's decision on tests the verifier doubted: keep them, or remove them. `refs` are
    numbers from `review list` or node ids. Each leaves its unit's for_review list, with the
    decision recorded in the unit's state; one commit for the lot."""
    if not reason.strip():
        raise ValueError("a review decision needs a reason")
    waiting = S.waiting_review()
    chosen = []
    for ref in refs:
        if ref.isdigit() and 1 <= int(ref) <= len(waiting):
            chosen.append(waiting[int(ref) - 1])
        elif any(n == ref for _, n in waiting):
            chosen.append(next(w for w in waiting if w[1] == ref))
        else:
            raise ValueError(f"{ref} isn't waiting for review (see: review list)")
    if not chosen:
        raise ValueError("name the tests to decide on: numbers from `review list`, or node ids")
    decision = "kept" if keep else "removed"
    for uid, nodeid in dict.fromkeys(chosen):
        if not keep:
            remove_test(nodeid)
        st = S.load(uid)
        st["for_review"].remove(nodeid)
        st.setdefault("reviewed", []).append({"test": nodeid, "decision": decision, "reason": reason})
        if not keep:
            st["tests"] = [n for n in st.get("tests", []) if n != nodeid]
        S.save(st)
    names = ", ".join(n.partition("::")[2] for _, n in dict.fromkeys(chosen))
    units = ", ".join(sorted({u for u, _ in chosen}))
    commit(f"review: {decision} {names} ({units}): {reason}", Gt.ACCEPTANCE + Gt.HARNESS)
    return f"{decision} {len(dict.fromkeys(chosen))}"


def _attempt_record(tk, fixer, cost, problems, review, result, stashed, runs: Path = RUNS) -> None:
    """Everything a fix attempt produced, as the audit stages keep it: loop/runs/<T-n>/fix.attempt<n>.json."""
    d = runs / tk["id"]
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.glob("fix.attempt*.json"))) + 1
    record = {"result": result, "fixer": fixer, "review": review, "problems": problems}
    record |= {"cost_usd": round(cost, 4), "stash": stashed}
    (d / f"fix.attempt{n}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")


def outcome(tid: str) -> list[str]:
    """What a person needs after a ticket's turn: the result, why, and where its work went."""
    tk = T.load(tid)
    last = tk["history"][-1] if tk["history"] else {}
    lines = [f"  {tid}: {tk['status']}"]
    if last.get("reason"):
        lines.append(f"    why: {last['reason']}")
    lines += [f"    - {p}" for p in last.get("problems", [])[:8]]
    runs = sorted(
        (RUNS / tid).glob("fix.attempt*.json"), key=lambda p: int(p.stem.removeprefix("fix.attempt"))
    )
    if runs:
        rec = json.loads(runs[-1].read_text())
        if rec.get("stash"):
            lines.append(f"    code set aside: git stash list | grep '{rec['stash']}'")
        lines.append(f"    details: {runs[-1]}")
    return lines


def run_ticket(
    ctx: P.Context, tk: dict, budget: C.Budget, invoke: Invoke = C.invoke, recheck: bool = False
) -> str:
    """One attempt at a ticket. With recheck, the change is already in the working tree (a
    person restored or wrote it): skip the fixer and run the gates, the review and the commit."""
    unit = ctx.by_id.get(tk["unit"])
    problems: list[str] = []
    cost = 0.0
    if recheck:
        out = {"summary": "rechecked the change already in the working tree"}
    else:
        failures = "\n".join(f"{n}: {o}" for n, o in Gt.run_pytest(tk["tests"]).items())
        cap = tk.get("cap_usd") or C.ROLES["fixer"].cap_usd
        prompt = Pr.fix(tk, unit, failures, problems)
        res = invoke("fixer", prompt, budget=budget, about=tk["id"], stage="fix", cap=cap)
        out, cost = res.output or {}, res.cost_usd
        if res.output is None:
            problems.append(f"fixer: no structured output ({res.error})")
    if out.get("dispute") or out.get("test_change_request"):
        tk["status"] = "dispute"
        T.record(tk, "dispute", reason=out.get("dispute") or out.get("test_change_request"))
        stashed = set_aside(f"srdloop: {tk['id']} dispute")
        _attempt_record(tk, out, cost, problems, None, "dispute", stashed)
        commit(f"dev: {tk['id']} disputed", KEEP)
        return "dispute"
    # before the harness drops xfail markers: any acceptance-suite change now is the fixer's
    problems = Gt.zone_problems(Gt.changed_files(), "fixer")
    for n in tk["tests"]:
        drop_xfail(n, tk["id"])
    outcomes = Gt.run_pytest(tk["tests"])
    problems += [f"{n}: {o}" for n, o in outcomes.items() if o != "passed"]
    co_fixed, co_problems = close_co_fixed(tk, suite_red())
    problems += co_problems
    red = [n for n in suite_red() if n not in tk["tests"]]
    problems += [f"now failing: {n}" for n in red]
    gate_problems, metrics = Q.dev_gate(waive=tk.get("waive", {}))
    problems += gate_problems
    verdict = None
    if not problems:
        prompt = Pr.review(
            tk,
            git("diff", "HEAD"),
            "all gates pass",
            T.open_tickets() + T.parked(),
            tk["kind"] in FOLLOWUP_FROM,
        )
        rev = invoke("fix-reviewer", prompt, budget=budget, about=tk["id"], stage="review")
        cost += rev.cost_usd
        verdict = rev.output or {"verdict": "reject", "findings": [], "followups": []}
        if verdict["verdict"] != "approve":  # a rejection blocks even without findings
            problems.append(f"review: rejected ({verdict.get('summary') or 'no reason given'})")
            problems += [
                f"review: {f['kind']} {f['file']}:{f['line']} {f['explanation']}" for f in verdict["findings"]
            ]
    tk["attempts"] += 1
    if problems:
        git("checkout", "--", *_paths(Gt.ACCEPTANCE))  # restore the xfail markers the harness dropped
        stashed = set_aside(f"srdloop: {tk['id']} attempt {tk['attempts']}")
        tk["status"] = "stuck" if tk["attempts"] >= T.MAX_ATTEMPTS else "open"
        T.record(tk, "failed", problems=problems[:30])
        _attempt_record(tk, out, cost, problems, verdict, "failed", stashed)
        commit(f"dev: {tk['id']} attempt {tk['attempts']} failed", KEEP)
        return tk["status"]
    if tk["kind"] in FOLLOWUP_FROM:  # at most one, parked: a menu for a person, not the loop's to-do
        for f in verdict.get("followups", [])[:1]:
            T.record(T.file(f["kind"], tk["unit"], f["title"], [], status=T.PARKED), "followup", of=tk["id"])
    tk["status"] = "fixed"
    T.record(tk, "fixed", summary=out.get("summary", ""))
    _attempt_record(tk, out, cost, [], verdict, "fixed", "")
    for other in co_fixed:
        other["status"] = "fixed"
        T.record(other, "fixed", by=tk["id"])
    for t in [tk, *co_fixed]:  # a capability the unit's untestable clauses waited for now exists
        if t["kind"] == "infra" and t["unit"] in ctx.by_id:
            st = S.load(t["unit"])
            st["revisit"] = True
            S.save(st)
    Q.update_baseline(metrics)
    also = f" (also fixes {', '.join(o['id'] for o in co_fixed)})" if co_fixed else ""
    if metrics.get("_waived"):
        T.record(tk, "waived", checks=metrics["_waived"])
        also += "\n\nWaived by a person for this ticket: " + "; ".join(metrics["_waived"])
    sha = commit(
        f"fix: {tk['id']} {tk['title']}{also}",
        DEV_ZONES + Gt.ACCEPTANCE + ("loop/quality-baseline.json",) + Gt.HARNESS,
    )
    return f"fixed ({sha})"


def recheck(tid: str, budget_usd: float, invoke: Invoke = C.invoke, log=print) -> int:
    """Gates, review and commit for a ticket whose change is already in the working tree."""
    budget = C.Budget(budget_usd)
    try:
        result = run_ticket(P.Context.load(), T.load(tid), budget, invoke, recheck=True)
    except C.Paused as e:
        log(f"paused: {e}. {e.hint}")
        return 4
    log("\n".join(outcome(tid)) if not result.startswith("fixed") else f"  {tid}: {result}")
    return 0 if result.startswith("fixed") else 1


def dev(budget_usd: float, only: list[str] | None = None, invoke: Invoke = C.invoke, log=print) -> int:
    budget = C.Budget(budget_usd)
    try:
        preflight()
        red = suite_red()
        if red:
            raise Stop(f"the test suite is red before the dev loop starts: {red[:5]}")
        while True:
            ctx = P.Context.load()
            todo = [t for t in T.workable(only) if not waits_for_ruling(t)]
            if not todo:
                log("dev loop: no open tickets")
                return 0
            tk = todo[0]
            log(f"» {tk['id']} ({tk['kind']}): {tk['title']}  (${budget.spent_usd:.2f} spent)")
            result = run_ticket(ctx, tk, budget, invoke)
            log("\n".join(outcome(tk["id"])) if not result.startswith("fixed") else f"  {tk['id']}: {result}")
    except C.Paused as e:
        log(f"paused: {e}. {e.hint}")
        return 4
    except Stop as e:
        log(f"stopped: {e}")
        return 3
