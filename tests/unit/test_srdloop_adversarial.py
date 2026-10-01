"""Negative tests for the loop itself: agents that produce bad work must not get it through.

The whole harness runs for real (stage gates, git, pytest, stashing, commits) in a scratch
repository; only the model is replaced, by fake agents that misbehave in one specific way. Each
case must end with the unit incomplete at the right stage, the problem named, the bad files set
aside, and nothing committed but the loop's own state.
"""

import copy
import subprocess
from pathlib import Path

import pytest

from scripts.srdloop import claude as C
from scripts.srdloop import plan as P
from scripts.srdloop import runner as Run
from scripts.srdloop import state as S
from scripts.srdloop import tickets as T
from scripts.srdloop import units as U
from tests.unit.test_srdloop_core import CONTENT
from tests.unit.test_srdloop_gates import git_repo, write
from tests.unit.test_srdloop_runtime import GRAPPLED, PLAN, SPEED, TEST_FILE, analysis

SCENARIO_TEST = """def test_cmb06_grapple(game):
    assert 1 == 1
    assert 2 == 2
"""
RELATED = {
    "id": "CMB-06",
    "title": "Grapple",
    "match": ["term"],
    "tests": ["tests/scenarios/test_combat.py::test_cmb06_grapple"],
}


def repo(tmp_path, monkeypatch):
    git_repo(
        tmp_path,
        {
            ".gitignore": "__pycache__/\n",
            "README.md": "x\n",
            "dungdra/__init__.py": "",
            "tests/srd/__init__.py": "",
            "tests/scenarios/__init__.py": "",
            "tests/scenarios/test_combat.py": SCENARIO_TEST,
        },
    )
    monkeypatch.chdir(tmp_path)
    units = [GRAPPLED, SPEED]
    ctx = P.Context(units, U.by_id(units), CONTENT, [], {}, {}, {}, {}, [])
    return ctx


def good_verdicts():
    v = {
        "item": "CMB-06",
        "kind": "scenario",
        "verdict": "consistent",
        "evidence": "Speed is 0",
        "rule_quote": "Your Speed is 0",
        "explanation": "",
    }
    t = {**v, "item": RELATED["tests"][0], "kind": "test", "evidence": "assert 1 == 1"}
    return {"verdicts": [v, t], "summary": ""}


def agents(stage_bad: str, bad):
    """Fake agents that do good work, except at `stage_bad`, where `bad()` returns the output
    (after doing whatever damage it does to the working tree)."""

    def invoke(role, prompt, *, budget, about, stage, cap):
        if stage == stage_bad:
            return C.Result(bad(), 0.1, "bad")
        if stage == "A":
            return C.Result(analysis(), 0.1, "a")
        if stage == "B":
            return C.Result(good_verdicts(), 0.1, "b")
        if stage == "C":
            write(Path("."), {"tests/srd/test_glossary.py": TEST_FILE})
            return C.Result(copy.deepcopy(PLAN), 0.1, "c")
        keep = [
            {"test": t["name"], "verdict": "keep", "reason": "", "mutation": "", "confidence": 0.9}
            for t in PLAN["tests"]
        ]
        return C.Result({"verdicts": keep, "summary": ""}, 0.1, "d")

    return invoke


def run(ctx, invoke, related=True):
    if related:
        scen = type("S", (), {"id": "CMB-06", "text": "- **Pass:** [H] the grappled creature's Speed is 0"})()
        ctx.scenarios = [scen]
        ctx.related = lambda uid: {"unit": uid, "scenarios": [RELATED], "srd_tests": [], "code": []}
    return Run.run_unit(ctx, "GLOSS.grappled", C.Budget(50.0), invoke)


def plan_with(**over):
    p = copy.deepcopy(PLAN)
    p.update(over)
    return p


def designer(files: dict[str, str], plan=None):
    def bad():
        write(Path("."), files)
        return plan if plan is not None else copy.deepcopy(PLAN)

    return bad


GREEN_BUT_FAILS = TEST_FILE.replace("assert 0 == 0", "assert 0 == 1")
RED_BUT_PASSES = TEST_FILE.replace("assert 10 == 0", "assert 0 == 0")
NO_MARKER = TEST_FILE.replace(
    '@pytest.mark.srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="positive")\n', ""
)
MOCKED = "from unittest.mock import patch\n" + TEST_FILE
UNKNOWN_UNIT = TEST_FILE.replace(
    'srd("GLOSS.grappled", clause="GLOSS.grappled#1", kind="positive"', 'srd("GLOSS.nope", kind="positive"'
)
SKIPPED = TEST_FILE.replace(
    "def test_grappled_speed_is_zero", "@pytest.mark.skip\ndef test_grappled_speed_is_zero"
)
NO_TICKET = TEST_FILE.replace(
    'reason="T-new: speed bonus applies while grappled"', 'reason="engine is wrong"'
)
ONLY_POSITIVE = plan_with(tests=[PLAN["tests"][0]])
INVENTED_QUOTE = plan_with(
    tests=[{**PLAN["tests"][0], "rule_quote": "Grappled creatures can't move at all"}, PLAN["tests"][1]]
)
GHOST_TEST = plan_with(
    tests=[*PLAN["tests"], {**PLAN["tests"][0], "name": "tests/srd/test_glossary.py::test_ghost"}]
)


@pytest.mark.parametrize(
    ("stage", "bad", "expected"),
    [
        # stage A: the rule analyst
        (
            "A",
            lambda: analysis(
                clauses=[{"id": "GLOSS.grappled#1", "text": "Grappled means stuck", "threshold": False}]
            ),
            "is not a verbatim quote",
        ),
        (
            "A",
            lambda: analysis(relations=[{"type": "requires", "target": "GLOSS.invented", "evidence": "x"}]),
            "relation to unknown unit 'GLOSS.invented'",
        ),
        (
            "A",
            lambda: analysis(clauses=[{"id": "grappled-1", "text": "Your Speed is 0", "threshold": False}]),
            "is not GLOSS.grappled#<n>",
        ),
        ("A", lambda: None, "no structured output"),
        # stage B: the scenario auditor
        (
            "B",
            lambda: {"verdicts": good_verdicts()["verdicts"][:1], "summary": ""},
            "no verdict for tests/scenarios",
        ),
        (
            "B",
            lambda: {
                "verdicts": [{**v, "evidence": "fabricated line"} for v in good_verdicts()["verdicts"]],
                "summary": "",
            },
            "evidence is not a verbatim quote",
        ),
        # stage C: the test designer
        ("C", designer({"tests/srd/test_glossary.py": GREEN_BUT_FAILS}), "claimed green, but failed"),
        ("C", designer({"tests/srd/test_glossary.py": RED_BUT_PASSES}), "claimed red, but"),
        ("C", designer({"tests/srd/test_glossary.py": NO_MARKER}), "no @pytest.mark.srd"),
        ("C", designer({"tests/srd/test_glossary.py": MOCKED}), "uses mocks"),
        (
            "C",
            designer({"tests/srd/test_glossary.py": UNKNOWN_UNIT}),
            "marker names unknown unit 'GLOSS.nope'",
        ),
        ("C", designer({"tests/srd/test_glossary.py": SKIPPED}), "only an xfail naming a ticket"),
        ("C", designer({"tests/srd/test_glossary.py": NO_TICKET}), "only an xfail naming a ticket"),
        (
            "C",
            designer({"tests/srd/test_glossary.py": TEST_FILE, "dungdra/hack.py": "x = 1\n"}),
            "test-designer may not change dungdra/hack.py",
        ),
        (
            "C",
            designer(
                {
                    "tests/srd/test_glossary.py": TEST_FILE,
                    "tests/scenarios/test_combat.py": "def test_cmb06_grapple(game):\n    assert 1 == 1\n",
                }
            ),
            "assertions dropped from 2 to 1",
        ),
        (
            "C",
            designer({"tests/srd/test_glossary.py": TEST_FILE, "tests/scenarios/test_combat.py": "\n"}),
            "removed",
        ),
        (
            "C",
            designer({"tests/srd/test_glossary.py": TEST_FILE}, ONLY_POSITIVE),
            "clause GLOSS.grappled#1: no negative test",
        ),
        (
            "C",
            designer({"tests/srd/test_glossary.py": TEST_FILE}, INVENTED_QUOTE),
            "rule_quote is not a verbatim quote",
        ),
        ("C", designer({"tests/srd/test_glossary.py": TEST_FILE}, GHOST_TEST), "test_ghost: no such test"),
        # stage D: the test verifier
        ("D", lambda: {"verdicts": [], "summary": "looks fine"}, "no verdict for tests/srd/test_glossary.py"),
    ],
)
def test_bad_agent_work_does_not_get_through(tmp_path, monkeypatch, stage, bad, expected):
    ctx = repo(tmp_path, monkeypatch)
    status = run(ctx, agents(stage, bad))
    st = S.load("GLOSS.grappled")
    assert status == "incomplete" and st["problems"]["stage"] == stage
    assert any(expected in p for p in st["problems"]["problems"]), st["problems"]["problems"]
    assert T.all_tickets() == []  # nothing reaches the dev loop
    log = subprocess.run(["git", "log", "--format=%s"], capture_output=True, text=True, check=True).stdout
    assert log.splitlines()[0] == f"srd: GLOSS.grappled incomplete at stage {stage}"
    changed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"], capture_output=True, text=True, check=True
    )
    assert all(f.startswith("loop/") for f in changed.stdout.split()), (
        changed.stdout
    )  # only the loop's own state
    assert Path("tests/scenarios/test_combat.py").read_text() == SCENARIO_TEST  # damage set aside (git stash)
    assert not Path("dungdra/hack.py").exists()


def test_good_work_still_gets_through(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    assert run(ctx, agents("none", lambda: None)) == "red"  # one red test: a ticket, not a failure
    assert [t["title"] for t in T.all_tickets()] == ["Grappled: a Speed bonus still applies"]


def test_a_paused_retry_resumes_with_the_problems_and_keeps_the_designers_files(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    prompts: list[str] = []
    good = agents("none", lambda: None)

    def once_bad_then_paused(role, prompt, *, budget, about, stage, cap):
        prompts.append(f"{stage}: {prompt}")
        if stage == "C" and sum(p.startswith("C:") for p in prompts) == 1:
            write(Path("."), {"tests/srd/test_glossary.py": NO_MARKER})
            return C.Result(copy.deepcopy(PLAN), 0.1, "c1")
        if stage == "C":
            raise C.Paused("budget")
        return good(role, prompt, budget=budget, about=about, stage=stage, cap=cap)

    with pytest.raises(C.Paused):
        run(ctx, once_bad_then_paused)
    assert Path("loop/runs/GLOSS.grappled/C.pending.json").exists()
    assert Path("tests/srd/test_glossary.py").read_text() == NO_MARKER  # still there for the retry

    def fixing(role, prompt, *, budget, about, stage, cap):
        prompts.append(f"{stage}: {prompt}")
        if stage == "C":
            assert "no @pytest.mark.srd" in prompt  # the retry is told what failed
            write(Path("."), {"tests/srd/test_glossary.py": TEST_FILE})
            return C.Result(copy.deepcopy(PLAN), 0.1, "c2")
        return good(role, prompt, budget=budget, about=about, stage=stage, cap=cap)

    assert run(ctx, fixing) == "red"
    assert (
        Path("loop/runs/GLOSS.grappled/C.attempt1.json").exists()
        and Path("loop/runs/GLOSS.grappled/C.attempt2.json").exists()
    )
    assert not Path("loop/runs/GLOSS.grappled/C.pending.json").exists()


def test_a_unit_entirely_out_of_scope_gets_no_tickets(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    oos = plan_with(
        tests=[],
        abuse=[],
        not_testable=[
            {
                "clause": "GLOSS.grappled#1",
                "kind": "out-of-scope",
                "reason": "needs level 5",
                "infra_ticket": "",
            }
        ],
    )
    assert run(ctx, agents("C", lambda: copy.deepcopy(oos))) == "out-of-scope"
    st = S.load("GLOSS.grappled")
    assert (
        st["out_of_scope"] == [{"clause": "GLOSS.grappled#1", "reason": "needs level 5"}]
        and T.all_tickets() == []
    )


def test_a_missing_capability_opens_an_infra_ticket(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    missing = plan_with(
        tests=[],
        abuse=[],
        not_testable=[
            {
                "clause": "GLOSS.grappled#1",
                "kind": "missing",
                "reason": "no drag",
                "infra_ticket": "dragging",
            },
            # the same capability again, with the unit id the harness adds anyway: one ticket
            {
                "clause": "GLOSS.grappled#2",
                "kind": "missing",
                "reason": "no drag",
                "infra_ticket": "GLOSS.grappled: Dragging.",
            },
        ],
    )
    assert run(ctx, agents("C", lambda: copy.deepcopy(missing))) == "blocked"
    assert [(t["kind"], t["title"]) for t in T.all_tickets()] == [("infra", "dragging")]
    assert S.load("GLOSS.grappled")["tickets"] == ["T-1"]


def test_a_lint_error_in_the_designers_file_fails_the_gate(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    write(Path("."), {"pyproject.toml": '[tool.ruff]\nline-length = 110\n[tool.ruff.lint]\nselect = ["E"]\n'})
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "ruff config"], check=True)
    long_comment = "# " + "x" * 120 + "\n"
    bad = designer({"tests/srd/test_glossary.py": TEST_FILE + long_comment})
    assert run(ctx, agents("C", bad)) == "incomplete"
    problems = S.load("GLOSS.grappled")["problems"]["problems"]
    assert any(p.startswith("ruff E501 tests/srd/test_glossary.py") for p in problems), problems


def test_an_xfail_reason_held_in_a_constant_fails_the_gate(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    held = TEST_FILE.replace('reason="T-new: speed bonus applies while grappled"', "reason=WHY").replace(
        "import pytest\n", 'import pytest\n\nWHY = "T-new: speed bonus applies while grappled"\n', 1
    )
    assert held != TEST_FILE
    assert run(ctx, agents("C", designer({"tests/srd/test_glossary.py": held}))) == "incomplete"
    problems = S.load("GLOSS.grappled")["problems"]["problems"]
    assert any("write the reason out in the marker" in p for p in problems)
