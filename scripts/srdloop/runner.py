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
MAX_OPEN_TICKETS = 15
MAX_CONSECUTIVE_INCOMPLETE = 3
STAGE_ROLE = {"A": "rule-analyst", "B": "scenario-auditor", "C": "test-designer", "D": "test-verifier"}
AGENT_ZONES = ("tests", "docs/scenario-notes.md", "loop/abuse-catalogue.md")
DEV_ZONES = ("dungdra", "tests/unit", "loop/requests")


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


def _item_text(kind: str, item: str, scenarios: dict[str, str]) -> str:
    if kind == "scenario":
        return scenarios.get(item, "")
    path = item.split("::")[0] if kind == "test" else item.rsplit(":", 1)[0]
    return Path(path).read_text() if Path(path).exists() else ""


def gate_verdicts(unit: dict, out: dict, related: dict, scenarios: dict[str, str]) -> list[str]:
    have = {v["item"] for v in out["verdicts"]}
    need = {s["id"] for s in related["scenarios"]}
    need |= {t for s in related["scenarios"] for t in s["tests"]} | set(related["srd_tests"])
    need |= {f"{c['file']}:{c['line']}" for c in related["code"] if c["match"] == "tag"}
    problems = [f"no verdict for {i}" for i in sorted(need - have)]
    problems += Gt.quotes(out["verdicts"], "rule_quote", [unit["text"]], "verdict")
    for v in out["verdicts"]:
        problems += Gt.quotes(
            [v], "evidence", [_item_text(v["kind"], v["item"], scenarios)], f"verdict on {v['item']}"
        )
    return problems


def _test_exists(nodeid: str) -> bool:
    path, _, name = nodeid.partition("::")
    return Path(path).exists() and name.split("[")[0] in Gt._tests(Path(path).read_text())


def gate_tests(unit: dict, out: dict, analysis: dict, unit_ids: set[str], ref: str = "HEAD") -> list[str]:
    problems = Gt.quotes(out["tests"], "rule_quote", [unit["text"]], "test")
    untestable = {n["clause"]: n for n in out["not_testable"]}
    clauses = [
        {**c, "not_testable": c["id"] in untestable, "reason": untestable.get(c["id"], {}).get("reason", "")}
        for c in analysis["clauses"]
    ]
    problems += Gt.clause_coverage(clauses, out["tests"], out["abuse"])
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


def set_aside(message: str) -> None:
    """After failed work: stash every change except the loop's own files, wherever the agent put
    it (a gate caught it writing outside its zone; that file must not stay behind either)."""
    import fnmatch

    files = [f for f in dirty() if not any(fnmatch.fnmatch(f, g) for g in Gt.HARNESS)]
    if files:
        git("stash", "push", "--include-untracked", "-m", message, "--", *files)


def commit(message: str, paths: tuple[str, ...]) -> str:
    git("add", "--all", "--", *_paths(paths))
    git("commit", "-q", "-m", message)
    return git("rev-parse", "--short", "HEAD").strip()


def preflight(harness_paths: tuple[str, ...] = Gt.HARNESS) -> None:
    """The loop only starts on a tree it understands: agent-zone leftovers of an interrupted
    unit are fine (resume keeps or stashes them); anything else is a person's work in progress."""
    import fnmatch

    foreign = [
        f
        for f in dirty()
        if not any(fnmatch.fnmatch(f, g) for g in harness_paths)
        and not f.startswith(AGENT_ZONES + DEV_ZONES)
        and f != "loop/quality-baseline.json"
    ]
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
        return gate_verdicts(unit, output, ctx.related(uid), {s.id: s.text for s in ctx.scenarios})
    if stage == "C":
        return gate_tests(unit, output, stage_output(uid, "A"), set(ctx.by_id))
    return gate_verification(output, stage_output(uid, "C"))


def _pending(uid: str, stage: str, runs: Path = RUNS) -> Path:
    return runs / uid / f"{stage}.pending.json"


def run_unit(ctx: P.Context, uid: str, budget: C.Budget, invoke: Invoke = C.invoke, runs: Path = RUNS) -> str:
    """Stages A-D for one unit. Every attempt's output and gate problems are kept in
    loop/runs/<unit>/<stage>.attempt<n>.json; a failed attempt leaves <stage>.pending.json, so a
    run that pauses before the retry resumes with the retry (and the agent's files), not from scratch."""
    st = S.load(uid)
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
            st.update(status="incomplete", problems={"stage": stage, "problems": problems[:40]})
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
    for n in missing:  # the engine should support it: an infra ticket
        tickets.append(T.create("infra", uid, f"{uid}: {n['infra_ticket']}", [])["id"])
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
        tests=[t["name"] for t in kept],
        out_of_scope=[{"clause": n["clause"], "reason": n["reason"]} for n in out_of_scope],
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
            if len(T.open_tickets()) > MAX_OPEN_TICKETS:
                raise Stop(f"more than {MAX_OPEN_TICKETS} open tickets; run the dev loop first")
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
        log(f"paused: {e}. Run again to resume.")
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
        commit(message, ("README.md", "tests/srd", "loop/rulings") + Gt.HARNESS)
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


def run_ticket(ctx: P.Context, tk: dict, budget: C.Budget, invoke: Invoke = C.invoke) -> str:
    unit = ctx.by_id.get(tk["unit"])
    failures = "\n".join(f"{n}: {o}" for n, o in Gt.run_pytest(tk["tests"]).items())
    problems: list[str] = []
    cap = tk.get("cap_usd") or C.ROLES["fixer"].cap_usd
    prompt = Pr.fix(tk, unit, failures, problems)
    res = invoke("fixer", prompt, budget=budget, about=tk["id"], stage="fix", cap=cap)
    out = res.output or {}
    if out.get("dispute") or out.get("test_change_request"):
        tk["status"] = "dispute"
        T.record(tk, "dispute", reason=out.get("dispute") or out.get("test_change_request"))
        set_aside(f"srdloop: {tk['id']} dispute")
        commit(f"dev: {tk['id']} disputed", Gt.HARNESS)
        return "dispute"
    for n in tk["tests"]:
        drop_xfail(n, tk["id"])
    outcomes = Gt.run_pytest(tk["tests"])
    problems = [f"{n}: {o}" for n, o in outcomes.items() if o != "passed"]
    problems += Gt.zone_problems([f for f in Gt.changed_files() if not f.startswith("tests/srd")], "fixer")
    co_fixed, co_problems = close_co_fixed(tk, suite_red())
    problems += co_problems
    red = [n for n in suite_red() if n not in tk["tests"]]
    problems += [f"now failing: {n}" for n in red]
    gate_problems, metrics = Q.dev_gate(waive=tk.get("waive", {}))
    problems += gate_problems
    verdict = None
    if not problems:
        prompt = Pr.review(tk, git("diff", "HEAD"), "all gates pass", T.open_tickets())
        rev = invoke("fix-reviewer", prompt, budget=budget, about=tk["id"], stage="review")
        verdict = rev.output or {"verdict": "reject", "findings": [], "followups": []}
        if verdict["verdict"] != "approve":  # a rejection blocks even without findings
            problems.append(f"review: rejected ({verdict.get('summary') or 'no reason given'})")
            problems += [
                f"review: {f['kind']} {f['file']}:{f['line']} {f['explanation']}" for f in verdict["findings"]
            ]
    tk["attempts"] += 1
    if problems:
        git("checkout", "--", "tests/srd")  # restore the xfail markers the harness dropped
        set_aside(f"srdloop: {tk['id']} attempt {tk['attempts']}")
        tk["status"] = "stuck" if tk["attempts"] >= T.MAX_ATTEMPTS else "open"
        T.record(tk, "failed", problems=problems[:30])
        commit(f"dev: {tk['id']} attempt {tk['attempts']} failed", Gt.HARNESS)
        return tk["status"]
    for f in verdict.get("followups", []):
        T.create(f["kind"], tk["unit"], f["title"], [])
    tk["status"] = "fixed"
    T.record(tk, "fixed", summary=out.get("summary", ""))
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
        DEV_ZONES + ("tests/srd", "loop/quality-baseline.json") + Gt.HARNESS,
    )
    return f"fixed ({sha})"


def dev(budget_usd: float, only: list[str] | None = None, invoke: Invoke = C.invoke, log=print) -> int:
    budget = C.Budget(budget_usd)
    try:
        preflight()
        red = suite_red()
        if red:
            raise Stop(f"the test suite is red before the dev loop starts: {red[:5]}")
        while True:
            ctx = P.Context.load()
            todo = [
                t for t in T.open_tickets() if (only is None or t["id"] in only) and not waits_for_ruling(t)
            ]
            if not todo:
                log("dev loop: no open tickets")
                return 0
            tk = todo[0]
            log(f"» {tk['id']} ({tk['kind']}): {tk['title']}  (${budget.spent_usd:.2f} spent)")
            log(f"  {tk['id']}: {run_ticket(ctx, tk, budget, invoke)}")
    except C.Paused as e:
        log(f"paused: {e}. Run again to resume.")
        return 4
    except Stop as e:
        log(f"stopped: {e}")
        return 3
