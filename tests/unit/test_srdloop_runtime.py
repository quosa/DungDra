"""Unit tests for the loop runtime: the claude wrapper, budget, tickets, test-file edits, stage
gates, mutation checks, the write-guard hook, and one unit end to end with fake agents."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.srdloop import claude as C
from scripts.srdloop import plan as P
from scripts.srdloop import runner as Run
from scripts.srdloop import state as S
from scripts.srdloop import tickets as T
from scripts.srdloop import units as U
from scripts.srdloop.mutate import mutate
from tests.unit.test_srdloop_core import CONTENT, unit
from tests.unit.test_srdloop_gates import git_repo, write

REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- the claude wrapper
def test_argv_per_role(monkeypatch):
    monkeypatch.chdir(REPO)
    a = C.argv("rule-analyst", "the prompt", 2.0)
    assert a[:3] == ["claude", "-p", "the prompt"]
    assert a[a.index("--tools") + 1] == ""  # the analyst has no tools: it never sees code
    assert a[a.index("--model") + 1] == "opus" and a[a.index("--max-budget-usd") + 1] == "2.00"
    assert a[a.index("--permission-mode") + 1] == "dontAsk"
    assert "--strict-mcp-config" in a and a[a.index("--setting-sources") + 1] == "project"
    assert json.loads(a[a.index("--json-schema") + 1])["required"][0] == "clauses"
    d = C.argv("test-designer", "p", 6.0)
    allowed = d[d.index("--allowedTools") + 1 :]
    assert "Write(tests/srd/**)" in allowed and not any("dungdra" in x for x in allowed)
    f = C.argv("fixer", "p", 6.0)
    assert "Edit(dungdra/**)" in f and "Edit(tests/srd/**)" not in f


def test_agent_files_match_roles():
    for role, r in C.ROLES.items():
        text = (REPO / ".claude/agents" / f"{role}.md").read_text()
        front = dict(line.split(": ", 1) for line in text.split("---")[1].strip().splitlines())
        assert front["name"] == role and front["model"] == r.model
        tools = {t.strip() for t in front["tools"].strip('"').split(",") if t.strip()}
        # interactively an empty tools list means "all tools", so the analyst's file says Read;
        # headless, the harness gives it none (--tools "")
        assert tools == (set(r.tools) or {"Read"})
        assert (C.SCHEMAS / f"{r.schema}.json").exists()


def fake_run(stdout: dict, code: int = 0, stderr: str = ""):
    calls = []

    def run(args, **kw):
        calls.append((args, kw))
        return subprocess.CompletedProcess(args, code, json.dumps(stdout), stderr)

    return run, calls


def test_invoke_parses_output_logs_cost_and_sets_the_role(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    run, calls = fake_run(
        {"structured_output": {"summary": "ok"}, "total_cost_usd": 0.42, "session_id": "s1"}
    )
    budget = C.Budget(5.0)
    ledger = tmp_path / "costs.jsonl"
    res = C.invoke("rule-analyst", "p", budget=budget, about="GLOSS.x", stage="A", run=run, ledger=ledger)
    assert res.output == {"summary": "ok"} and res.cost_usd == 0.42 and budget.spent_usd == 0.42
    assert calls[0][1]["env"]["SRDLOOP_ROLE"] == "rule-analyst"
    row = json.loads(ledger.read_text())
    assert (row["about"], row["stage"], row["cost_usd"], row["session_id"]) == ("GLOSS.x", "A", 0.42, "s1")


def test_invoke_pauses_before_overspending_and_on_transient_failures(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    run, calls = fake_run({})
    with pytest.raises(C.Paused, match="budget"):
        C.invoke(
            "rule-analyst",
            "p",
            budget=C.Budget(1.0, 0.5),
            about="u",
            stage="A",
            run=run,
            ledger=tmp_path / "c",
        )
    assert calls == []  # nothing started
    run, _ = fake_run({"result": "API Error: rate limit exceeded"}, code=1)
    with pytest.raises(C.Paused, match="transient"):
        C.invoke(
            "rule-analyst", "p", budget=C.Budget(9.0), about="u", stage="A", run=run, ledger=tmp_path / "c"
        )
    run, _ = fake_run({"subtype": "error_max_budget_usd", "total_cost_usd": 2.0}, code=1)
    res = C.invoke(
        "rule-analyst", "p", budget=C.Budget(9.0), about="u", stage="A", run=run, ledger=tmp_path / "c"
    )
    assert res.output is None and res.error == "error_max_budget_usd"


# ---------------------------------------------------------------- tickets
def test_tickets_ids_order_and_history(tmp_path):
    a = T.create("refactor", "U1", "tidy", [], tmp_path)
    b = T.create("bug", "U2", "wrong", ["t::a"], tmp_path)
    c = T.create("infra", "U3", "no map", [], tmp_path)
    assert [a["id"], b["id"], c["id"]] == ["T-1", "T-2", "T-3"]
    assert [t["id"] for t in T.open_tickets(tmp_path)] == ["T-2", "T-3", "T-1"]
    b["status"] = "fixed"
    T.record(b, "fixed", tmp_path, summary="done")
    assert T.load("T-2", tmp_path)["history"] == [{"event": "fixed", "summary": "done"}]
    assert [t["id"] for t in T.open_tickets(tmp_path)] == ["T-3", "T-1"]


def test_ticket_titles_lose_a_repeated_unit_id_and_file_reuses_an_open_one(tmp_path):
    a = T.create("infra", "GLOSS.x", "GLOSS.x: GLOSS.x: no map", [], tmp_path)
    assert a["title"] == "no map"
    assert T.file("infra", "GLOSS.y", "No  map.", ["t::b"], tmp_path)["id"] == "T-1"  # another unit, same gap
    assert T.load("T-1", tmp_path)["tests"] == ["t::b"]
    assert T.file("refactor", "GLOSS.x", "no map", [], tmp_path)["id"] == "T-2"  # another kind
    a = T.load("T-1", tmp_path)
    a["status"] = "fixed"
    T.save(a, tmp_path)
    assert T.file("infra", "GLOSS.x", "no map", [], tmp_path)["id"] == "T-3"  # fixed ones aren't reused


# ---------------------------------------------------------------- editing test files
SRC = """import pytest


@pytest.mark.srd("GLOSS.x", kind="positive")
def test_keep():
    assert True


@pytest.mark.srd("GLOSS.x", kind="negative")
@pytest.mark.xfail(strict=True, reason="T-new: engine allows it")
def test_red():
    assert False


def test_gone():
    assert 1
"""


def test_remove_test_set_ticket_drop_xfail(tmp_path):
    f = tmp_path / "test_x.py"
    f.write_text(SRC)
    Run.remove_test(f"{f}::test_gone")
    assert "test_gone" not in f.read_text() and f.read_text().endswith("assert False\n")
    Run.set_ticket(f"{f}::test_red", "T-7")
    assert 'reason="T-7: engine allows it"' in f.read_text()
    Run.drop_xfail(f"{f}::test_red", "T-7")
    assert (
        "xfail" not in f.read_text()
        and '@pytest.mark.srd("GLOSS.x", kind="negative")\ndef test_red' in f.read_text()
    )


def test_drop_xfail_removes_a_multi_line_marker_and_only_the_tickets(tmp_path):
    f = tmp_path / "test_m.py"
    f.write_text(
        "import pytest\n\n\n"
        '@pytest.mark.srd("GLOSS.x", kind="negative")\n'
        "@pytest.mark.xfail(\n"
        "    strict=True,\n"
        '    reason="T-1: attacking one grappler still has Disadvantage from the other grapple",\n'
        ")\ndef test_a():\n    assert True\n\n\n"
        '@pytest.mark.xfail(strict=True, reason="T-12: another ticket")\ndef test_b():\n    assert True\n'
    )
    assert Run.drop_xfail(f"{f}::test_a", "T-1") is True
    src = f.read_text()
    assert "T-1:" not in src and '@pytest.mark.srd("GLOSS.x", kind="negative")\ndef test_a' in src
    assert Run.drop_xfail(f"{f}::test_b", "T-1") is False and "T-12" in f.read_text()  # T-1 is not T-12


# ---------------------------------------------------------------- stage gates
GRAPPLED = unit(
    "GLOSS.grappled",
    title="Grappled [Condition]",
    text="Speed 0. Your Speed is 0 and can’t increase.\n\n"
    "Attacks Affected. You have Disadvantage on attack rolls.",
)
SPEED = unit("GLOSS.speed", title="Speed", text="A creature has a Speed.")


def analysis(**over):
    out = {
        "clauses": [
            {"id": "GLOSS.grappled#1", "text": "Your Speed is 0 and can’t increase.", "threshold": False}
        ],
        "relations": [{"type": "modifies", "target": "GLOSS.speed", "evidence": "A creature has a Speed."}],
        "ambiguities": [],
        "conflicts": [],
        "gaps": [],
        "traps": [],
        "summary": "s",
    }
    return {**out, **over}


def test_gate_analysis():
    known = {"GLOSS.grappled": GRAPPLED, "GLOSS.speed": SPEED}
    assert Run.gate_analysis(GRAPPLED, analysis(), known) == []
    bad = analysis(
        clauses=[
            {"id": "X#1", "text": "Speed is zero", "threshold": False},
            {"id": "X#1", "text": "Speed 0.", "threshold": 0},
        ],
        relations=[{"type": "requires", "target": "GLOSS.nope", "evidence": "x"}],
        traps=[{"quote": "made up", "note": "n"}],
    )
    assert Run.gate_analysis(GRAPPLED, bad, known) == [
        "clause #1: text is not a verbatim quote: 'Speed is zero'",
        "clause id 'X#1' is not GLOSS.grappled#<n>",
        "clause id 'X#1' is not GLOSS.grappled#<n>",
        "clause id X#1 used twice",
        "relation to unknown unit 'GLOSS.nope'",
        "quote #1: quote is not a verbatim quote: 'made up'",
    ]


def test_gate_verdicts_needs_a_verdict_for_every_related_item():
    related = {"scenarios": [{"id": "COND-02", "tests": ["t.py::t"]}], "srd_tests": [], "code": []}
    scen = {"COND-02": "- **Pass:** [H] the grappled creature's Speed is 0"}
    out = {
        "verdicts": [
            {
                "item": "COND-02",
                "kind": "scenario",
                "verdict": "consistent",
                "evidence": "Speed is 0",
                "rule_quote": "Your Speed is 0",
                "explanation": "",
            }
        ],
        "summary": "",
    }
    assert Run.gate_verdicts(GRAPPLED, out, related, scen) == ["no verdict for t.py::t"]


def test_scenario_evidence_may_quote_the_shared_fixtures_but_test_evidence_may_not():
    related = {"scenarios": [{"id": "MON-02", "tests": []}], "srd_tests": ["t.py::t"], "code": []}
    scen = {"MON-02": "- **Pass:** [H] (b) LIDDA is Prone (Medium or smaller, no save)."}
    fixtures = "| Wolf | Bite +4, 1d6+2; a Medium or smaller target gets the **Prone** condition (no save). |"
    quote = "a Medium or smaller target gets the **Prone** condition"
    v = {"verdict": "not-related", "evidence": quote, "rule_quote": "Your Speed is 0", "explanation": ""}
    out = {
        "verdicts": [{**v, "item": "MON-02", "kind": "scenario"}, {**v, "item": "t.py::t", "kind": "test"}]
    }
    assert Run.gate_verdicts(GRAPPLED, out, related, scen, fixtures) == [
        f"verdict on t.py::t #1: evidence is not a verbatim quote: {quote!r}"
    ]
    assert Run.gate_verdicts(GRAPPLED, out, related, scen)[0].startswith(
        "verdict on MON-02 #1: evidence is not"
    )


def test_gate_verification_needs_every_test():
    plan = {"tests": [{"name": "a"}, {"name": "b"}]}
    assert Run.gate_verification({"verdicts": [{"test": "a"}]}, plan) == ["no verdict for b"]


# ---------------------------------------------------------------- mutation check
def test_mutate_breaks_a_copy_and_runs_the_test_there(tmp_path):
    write(
        tmp_path,
        {
            "dungdra/__init__.py": "",
            "dungdra/rule.py": "def speed(grappled):\n    return 0 if grappled else 30\n",
            "tests/test_rule.py": "from dungdra.rule import speed\n\n\n"
            "def test_speed():\n    assert speed(True) == 0\n",
            "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n',
        },
    )
    args = ("dungdra/rule.py", 2, "0 if grappled", "30 if grappled", "tests/test_rule.py::test_speed")
    assert mutate(*args, root=tmp_path) == "failed"  # the test notices the broken rule
    assert (
        mutate("dungdra/rule.py", 2, "else 30", "else 31", "tests/test_rule.py::test_speed", root=tmp_path)
        == "passed"
    )
    assert "0 if grappled" in (tmp_path / "dungdra/rule.py").read_text()  # the original is untouched
    assert mutate("tests/test_rule.py", 5, "0", "1", "x", root=tmp_path).startswith("refused")
    assert mutate("dungdra/rule.py", 2, "nope", "x", "x", root=tmp_path).startswith("refused")


# ---------------------------------------------------------------- the write guard
@pytest.mark.parametrize(
    ("role", "path", "code"),
    [
        ("test-designer", "tests/srd/test_glossary.py", 0),
        ("test-designer", "dungdra/combat.py", 2),
        ("fixer", "dungdra/combat.py", 0),
        ("fixer", "tests/srd/test_glossary.py", 2),
        ("unit-test-writer", "dungdra/combat.py", 2),
        ("rule-analyst", "loop/state/x.json", 2),
        ("fixer", "/etc/passwd", 2),
        (None, "dungdra/combat.py", 0),  # a person's own session: not guarded
    ],
)
def test_guard_writes_hook(role, path, code):
    env = {k: v for k, v in os.environ.items() if k != "SRDLOOP_ROLE"} | {"CLAUDE_PROJECT_DIR": str(REPO)}
    if role:
        env["SRDLOOP_ROLE"] = role
    event = json.dumps({"tool_name": "Write", "tool_input": {"file_path": path}})
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/srdloop/hooks/guard_writes.py")],
        input=event,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert r.returncode == code, r.stderr


# ---------------------------------------------------------------- one unit end to end
TEST_FILE = """import pytest


@pytest.mark.srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="positive")
def test_grappled_speed_is_zero():
    assert 0 == 0


@pytest.mark.srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="negative")
@pytest.mark.xfail(strict=True, reason="T-new: speed bonus applies while grappled")
def test_grappled_speed_cannot_increase():
    assert 10 == 0
"""

PLAN = {
    "interactions": [],
    "abuse": [{"case": "Dash while grappled", "test": None, "reason": "Dash adds movement, not Speed"}],
    "tests": [
        {
            "name": "tests/srd/test_glossary.py::test_grappled_speed_is_zero",
            "clause": "GLOSS.grappled#1",
            "kind": "positive",
            "rule_quote": "Your Speed is 0",
            "claim": "green",
            "ticket_title": None,
        },
        {
            "name": "tests/srd/test_glossary.py::test_grappled_speed_cannot_increase",
            "clause": "GLOSS.grappled#1",
            "kind": "negative",
            "rule_quote": "can’t increase",
            "claim": "red",
            "ticket_title": "Grappled: a Speed bonus still applies",
        },
    ],
    "not_testable": [],
    "scenario_changes": [],
    "rulings_proposed": [],
    "summary": "two tests",
}


def fake_agents(calls):
    def invoke(role, prompt, *, budget, about, stage, cap):
        calls.append(stage)
        if stage == "A":
            return C.Result(analysis(), 0.1, "a")
        if stage == "B":
            return C.Result({"verdicts": [], "summary": "nothing related"}, 0.1, "b")
        if stage == "C":
            write(Path("."), {"tests/srd/test_glossary.py": TEST_FILE})
            return C.Result(PLAN, 0.5, "c")
        keep = [
            {"test": t["name"], "verdict": "keep", "reason": "", "mutation": "", "confidence": 0.9}
            for t in PLAN["tests"]
        ]
        return C.Result({"verdicts": keep, "summary": "both hold"}, 0.2, "d")

    return invoke


def test_run_unit_end_to_end_with_fake_agents(tmp_path, monkeypatch):
    git_repo(tmp_path, {".gitignore": "__pycache__/\n", "tests/srd/__init__.py": "", "README.md": "x\n"})
    monkeypatch.chdir(tmp_path)
    units = [GRAPPLED, SPEED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    calls: list[str] = []
    status = Run.run_unit(ctx, "GLOSS.grappled", C.Budget(10.0), fake_agents(calls))
    assert (status, calls) == ("red", ["A", "B", "C", "D"])
    st = S.load("GLOSS.grappled")
    assert st["status"] == "red" and st["tickets"] == ["T-1"] and len(st["tests"]) == 2
    assert st["relations"][0]["target"] == "GLOSS.speed" and st["fingerprint"]
    assert T.load("T-1")["tests"] == ["tests/srd/test_glossary.py::test_grappled_speed_cannot_increase"]
    assert 'reason="T-1: speed bonus' in Path("tests/srd/test_glossary.py").read_text()
    log = subprocess.run(["git", "log", "--format=%s"], capture_output=True, text=True, check=True).stdout
    assert log.splitlines()[0] == "srd: GLOSS.grappled — red, 2 tests, 1 tickets"
    assert (
        subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout
        == ""
    )


def test_run_unit_resumes_from_the_last_checkpoint(tmp_path, monkeypatch):
    git_repo(tmp_path, {".gitignore": "__pycache__/\n", "tests/srd/__init__.py": "", "README.md": "x\n"})
    monkeypatch.chdir(tmp_path)
    units = [GRAPPLED, SPEED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    Run.checkpoint("GLOSS.grappled", "A", analysis())
    Run.checkpoint("GLOSS.grappled", "B", {"verdicts": [], "summary": ""})
    calls: list[str] = []
    assert Run.run_unit(ctx, "GLOSS.grappled", C.Budget(10.0), fake_agents(calls)) == "red"
    assert calls == ["C", "D"]  # A and B were not paid for twice


def test_run_unit_marks_incomplete_after_two_failed_attempts(tmp_path, monkeypatch):
    git_repo(tmp_path, {".gitignore": "__pycache__/\n", "README.md": "x\n"})
    monkeypatch.chdir(tmp_path)
    units = [GRAPPLED, SPEED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    prompts: list[str] = []

    def bad(role, prompt, **kw):
        prompts.append(prompt)
        return C.Result(
            analysis(clauses=[{"id": "GLOSS.grappled#1", "text": "invented", "threshold": False}]), 0.1, "x"
        )

    assert Run.run_unit(ctx, "GLOSS.grappled", C.Budget(10.0), bad) == "incomplete"
    assert len(prompts) == 2 and "previous attempt failed" in prompts[1]
    st = S.load("GLOSS.grappled")
    assert st["status"] == "incomplete" and st["problems"]["stage"] == "A"


# ---------------------------------------------------------------- one ticket end to end
RULE = "def grappled_speed(bonus):\n    return 0 + bonus\n"
RED = """import pytest

from dungdra.rule import grappled_speed


@pytest.mark.srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="negative")
@pytest.mark.xfail(
    strict=True,
    reason="T-1: a Speed bonus still applies",
)
def test_bonus_does_not_raise_grappled_speed():
    assert grappled_speed(10) == 0
"""


def dev_repo(tmp_path):
    git_repo(
        tmp_path,
        {
            ".gitignore": "__pycache__/\n",
            "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n',
            "dungdra/__init__.py": "",
            "dungdra/rule.py": RULE,
            "tests/__init__.py": "",
            "tests/srd/__init__.py": "",
            "tests/srd/test_rule.py": RED,
        },
    )
    T.create(
        "bug",
        "GLOSS.grappled",
        "a Speed bonus still applies",
        ["tests/srd/test_rule.py::test_bonus_does_not_raise_grappled_speed"],
    )
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "ticket"], check=True)


def fake_dev(fix: bool, review: str = "approve"):
    def invoke(role, prompt, *, budget, about, stage, cap=None):
        if role == "fixer":
            if fix:
                fixed = "def grappled_speed(bonus):\n    return 0  # SRD[GLOSS.grappled#1]\n"
                write(Path("."), {"dungdra/rule.py": fixed})
            out = {"summary": "Speed stays 0", "files": ["dungdra/rule.py"], "unit_tests": [], "srd_tags": []}
            out |= {"dispute": None, "test_change_request": None}
            return C.Result(out, 0.5, "f")
        return C.Result({"verdict": review, "findings": [], "followups": [], "summary": ""}, 0.1, "r")

    return invoke


@pytest.fixture
def no_quality_gate(monkeypatch):
    monkeypatch.setattr(Run.Q, "dev_gate", lambda ref="HEAD", waive=None: ([], {"unit_branch_pct": 0.0}))
    monkeypatch.setattr(Run.Q, "update_baseline", lambda metrics: None)


def test_run_ticket_fixes_removes_the_marker_and_commits(tmp_path, monkeypatch, no_quality_gate):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    result = Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dev(fix=True))
    assert result.startswith("fixed")
    assert T.load("T-1")["status"] == "fixed" and "xfail" not in Path("tests/srd/test_rule.py").read_text()
    log = subprocess.run(["git", "log", "--format=%s"], capture_output=True, text=True, check=True).stdout
    assert log.splitlines()[0] == "fix: T-1 a Speed bonus still applies"


def test_run_ticket_rolls_back_a_failed_attempt(tmp_path, monkeypatch, no_quality_gate):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    assert Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dev(fix=False)) == "open"
    tk = T.load("T-1")
    assert tk["attempts"] == 1 and "passed" not in tk["history"][-1]["problems"][0]
    assert 'reason="T-1:' in Path("tests/srd/test_rule.py").read_text()  # marker restored
    assert Path("dungdra/rule.py").read_text() == RULE
    for _ in range(2):
        Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dev(fix=True, review="reject"))
    assert T.load("T-1")["status"] == "stuck"  # three failed attempts: a person decides


RED_2 = """

@pytest.mark.srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="abuse")
@pytest.mark.xfail(strict=True, reason="T-2: a large bonus still applies")
def test_large_bonus_does_not_raise_grappled_speed():
    assert grappled_speed(30) == 0
"""


def test_one_fix_that_also_fixes_another_ticket_closes_both(tmp_path, monkeypatch, no_quality_gate):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    write(tmp_path, {"tests/srd/test_rule.py": RED + RED_2})
    T.create(
        "bug",
        "GLOSS.grappled",
        "a large bonus still applies",
        ["tests/srd/test_rule.py::test_large_bonus_does_not_raise_grappled_speed"],
    )
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second ticket"], check=True)
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    assert Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dev(fix=True)).startswith("fixed")
    assert T.load("T-2")["status"] == "fixed" and T.load("T-2")["history"][-1] == {
        "event": "fixed",
        "by": "T-1",
    }
    assert "xfail" not in Path("tests/srd/test_rule.py").read_text()
    log = subprocess.run(["git", "log", "--format=%s"], capture_output=True, text=True, check=True).stdout
    assert log.splitlines()[0] == "fix: T-1 a Speed bonus still applies (also fixes T-2)"


def test_recheck_gates_and_commits_a_change_already_in_the_tree(tmp_path, monkeypatch, no_quality_gate):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    write(tmp_path, {"dungdra/rule.py": "def grappled_speed(bonus):\n    return 0\n"})  # a person's change
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    roles: list[str] = []

    def reviewer_only(role, prompt, **kw):
        roles.append(role)
        return fake_dev(fix=False)(role, prompt, **kw)

    assert Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), reviewer_only, recheck=True).startswith("fixed")
    assert roles == ["fix-reviewer"] and T.load("T-1")["status"] == "fixed"


def test_a_ticket_whose_red_test_is_a_scenario_is_fixed_and_committed(tmp_path, monkeypatch, no_quality_gate):
    """The harness drops xfail markers in either acceptance suite; that isn't the fixer's change."""
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    scenario = RED.replace(
        '@pytest.mark.srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="negative")\n', ""
    )
    write(tmp_path, {"tests/scenarios/__init__.py": "", "tests/scenarios/test_cmb.py": scenario})
    tk = T.load("T-1")
    tk["tests"].append("tests/scenarios/test_cmb.py::test_bonus_does_not_raise_grappled_speed")
    T.save(tk)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "scenario"], check=True)
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    assert Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dev(fix=True)).startswith("fixed")
    assert "xfail" not in Path("tests/scenarios/test_cmb.py").read_text()
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    assert status.stdout == ""  # the dropped markers are committed with the fix


def test_a_fixer_that_edits_a_scenario_is_still_caught(tmp_path, monkeypatch, no_quality_gate):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    write(
        tmp_path,
        {"tests/scenarios/__init__.py": "", "tests/scenarios/test_cmb.py": "def test_x():\n    assert 1\n"},
    )
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "scenario"], check=True)
    fix = fake_dev(fix=True)

    def invoke(role, prompt, **kw):
        if role == "fixer":
            write(Path("."), {"tests/scenarios/test_cmb.py": "def test_x():\n    assert 2\n"})
        return fix(role, prompt, **kw)

    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    assert Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), invoke) == "open"
    assert T.load("T-1")["history"][-1]["problems"] == ["fixer may not change tests/scenarios/test_cmb.py"]
    assert Path("tests/scenarios/test_cmb.py").read_text() == "def test_x():\n    assert 1\n"


def fake_dispute(request: bool):
    def invoke(role, prompt, *, budget, about, stage, cap=None):
        write(Path("."), {"dungdra/rule.py": "def grappled_speed(bonus):\n    return 0\n"})
        if request:
            write(Path("."), {"loop/requests/T-1-why.md": "SPL-05 needs a person\n"})
        out = {"summary": "half done", "files": ["dungdra/rule.py"], "unit_tests": [], "srd_tags": []}
        out |= {"dispute": "the scenario expects the old reading", "test_change_request": None}
        return C.Result(out, 0.8, "f")

    return invoke


def test_a_dispute_keeps_the_request_records_the_attempt_and_says_where_the_code_went(
    tmp_path, monkeypatch, no_quality_gate
):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    assert Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dispute(request=True)) == "dispute"
    assert Path("dungdra/rule.py").read_text() == RULE  # the code is set aside...
    assert Path("loop/requests/T-1-why.md").read_text() == "SPL-05 needs a person\n"  # ...the request isn't
    rec = json.loads(Path("loop/runs/T-1/fix.attempt1.json").read_text())
    assert rec["result"] == "dispute" and rec["fixer"]["summary"] == "half done" and rec["cost_usd"] == 0.8
    assert rec["stash"] == "srdloop: T-1 dispute"
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    assert status.stdout == ""  # request and record are committed with the ticket
    lines = Run.outcome("T-1")
    assert lines[0] == "  T-1: dispute" and "the scenario expects the old reading" in lines[1]
    assert "git stash list | grep 'srdloop: T-1 dispute'" in lines[2]
    assert lines[3] == "    details: loop/runs/T-1/fix.attempt1.json"


def test_a_failed_attempt_is_recorded_with_its_problems(tmp_path, monkeypatch, no_quality_gate):
    monkeypatch.chdir(tmp_path)
    dev_repo(tmp_path)
    units = [GRAPPLED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    Run.run_ticket(ctx, T.load("T-1"), C.Budget(10.0), fake_dev(fix=False))
    rec = json.loads(Path("loop/runs/T-1/fix.attempt1.json").read_text())
    assert rec["result"] == "failed" and rec["problems"] and rec["stash"] == ""  # the fixer changed nothing
    assert any(line.startswith("    - tests/srd/test_rule.py::") for line in Run.outcome("T-1"))


def test_the_report_lists_doubted_tests_and_tickets_waiting_for_a_person(tmp_path, monkeypatch):
    from scripts.srdloop import report

    monkeypatch.chdir(tmp_path)
    nodeid = "tests/srd/test_g.py::test_maybe"
    write(
        tmp_path,
        {
            "loop/runs/GLOSS.grappled/D.json": json.dumps(
                {
                    "verdicts": [
                        {
                            "test": nodeid,
                            "verdict": "refute",
                            "reason": "may pass for the\nwrong | reason",
                            "confidence": 0.3,
                        }
                    ]
                }
            )
        },
    )
    T.create("bug", "GLOSS.grappled", "speed bonus", [nodeid])
    tk = T.load("T-1")
    tk["status"] = "dispute"
    T.save(tk)
    units = [GRAPPLED]
    states = {"GLOSS.grappled": {"status": "red", "for_review": [nodeid]}}
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, states, [])
    text = report.render(ctx, [])
    assert f"| 1 | `{nodeid}` | may pass for the wrong \\| reason |" in text
    assert "- T-1 (dispute, `GLOSS.grappled`): speed bonus" in text


def test_a_person_keeps_or_removes_doubted_tests_by_number_or_node_id(tmp_path, monkeypatch):
    git_repo(tmp_path, {"tests/srd/test_g.py": SRC})
    monkeypatch.chdir(tmp_path)
    keep, red, gone = (f"tests/srd/test_g.py::{n}" for n in ("test_keep", "test_red", "test_gone"))
    S.save({**S.load("GLOSS.x"), "tests": [keep, red, gone], "for_review": [keep, red, gone]})
    assert S.waiting_review() == [("GLOSS.x", keep), ("GLOSS.x", red), ("GLOSS.x", gone)]
    with pytest.raises(ValueError, match="needs a reason"):
        Run.decide_review(["1"], keep=True, reason=" ")
    with pytest.raises(ValueError, match="4 isn't waiting for review"):
        Run.decide_review(["1", "4"], keep=True, reason="x")  # nothing decided if one ref is bad
    assert len(S.waiting_review()) == 3
    assert Run.decide_review(["1", "2", "1"], keep=True, reason="guards cover since T-16") == "kept 2"
    assert S.waiting_review() == [("GLOSS.x", gone)]  # numbers follow the list as it is now
    assert Run.decide_review([gone], keep=False, reason="duplicate") == "removed 1"
    st = S.load("GLOSS.x")
    assert st["for_review"] == [] and st["tests"] == [keep, red]
    assert [r["decision"] for r in st["reviewed"]] == ["kept", "kept", "removed"]
    src = Path("tests/srd/test_g.py").read_text()
    assert "def test_keep" in src and "def test_gone" not in src
    log = subprocess.run(["git", "log", "--format=%s", "-2"], capture_output=True, text=True, check=True)
    assert log.stdout.splitlines() == [
        "review: removed test_gone (GLOSS.x): duplicate",
        "review: kept test_keep, test_red (GLOSS.x): guards cover since T-16",
    ]
    with pytest.raises(ValueError, match="name the tests"):
        Run.decide_review([], keep=True, reason="x")
