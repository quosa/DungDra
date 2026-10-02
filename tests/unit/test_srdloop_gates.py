"""Unit tests for the loop's gates (scripts/srdloop/gates.py, quality.py) and the SRD-suite
helpers (tests/support/srd.py, tests/srd/conftest.py)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dungdra.rules import Refusal
from scripts.srdloop import gates as G
from scripts.srdloop import quality as Q
from tests.support.srd import assert_refused_cleanly

REPO = Path(__file__).resolve().parents[2]


def git_repo(tmp: Path, files: dict[str, str]) -> None:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(tmp), "config", k, v], check=True)
    write(tmp, files)
    subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-q", "-m", "base"], check=True)


def write(tmp: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


# ---------------------------------------------------------------- stage outputs
def test_quotes_must_be_verbatim_whitespace_insensitive():
    text = "Your Speed is 0 and\ncan’t increase."
    items = [{"quote": "Speed is 0 and can’t   increase"}, {"quote": "Speed is zero"}, {"quote": ""}]
    assert G.quotes(items, "quote", [text], "clause") == [
        "clause #2: quote is not a verbatim quote: 'Speed is zero'",
        "clause #3: empty quote",
    ]


def test_clause_coverage_requires_kinds_boundaries_and_reasons():
    clauses = [
        {"id": "c1"},
        {"id": "c2", "threshold": True},
        {"id": "c3", "not_testable": True, "reason": "needs a map (infra ticket)"},
        {"id": "c4", "not_testable": True},
    ]
    tests = [
        {"name": "a", "clause": "c1", "kind": "positive"},
        {"name": "b", "clause": "c1", "kind": "negative"},
        {"name": "c", "clause": "c2", "kind": "positive"},
        {"name": "d", "clause": "c2", "kind": "negative"},
        {"name": "e", "clause": "c9", "kind": "sneaky"},
    ]
    abuse = [{"case": "move through a wall", "test": "e"}, {"case": "act twice"}]
    assert G.clause_coverage(clauses, tests, abuse) == [
        "test 'e' names unknown clause 'c9'",
        "test 'e' has kind 'sneaky', not one of ('positive', 'negative', 'boundary', 'abuse')",
        "clause c2: no boundary test",
        "clause c4: not_testable without a reason",
        "abuse case 'act twice': neither a test nor a reason",
    ]


# ---------------------------------------------------------------- test files
SRD_OK = """import pytest

@pytest.mark.srd("GLOSS.prone", clause="GLOSS.prone#1", kind="negative")
def test_prone_cannot_stand_without_movement(game):
    assert game is not None
"""


def test_test_file_problems_markers_asserts_mocks(tmp_path):
    ok = tmp_path / "test_ok.py"
    ok.write_text(SRD_OK)
    assert G.test_file_problems(ok, {"GLOSS.prone"}) == []
    bad = tmp_path / "test_bad.py"
    bad.write_text(
        "from unittest.mock import patch\nimport pytest\n\n"
        '@pytest.mark.srd("GLOSS.nope", kind="sideways")\ndef test_a(game):\n    pass\n\n'
        "def test_b(game):\n    assert True\n"
    )
    problems = G.test_file_problems(bad, {"GLOSS.prone"})
    assert problems[0].endswith("uses mocks (unittest.mock); the SRD suites use the real engine")
    assert [p.split("::")[1] for p in problems[1:]] == [
        "test_a: asserts nothing (counted: assert statements, pytest.raises and calls to assert_* helpers)",
        "test_a: marker names unknown unit 'GLOSS.nope'",
        "test_a: marker kind 'sideways' is not one of ('positive', 'negative', 'boundary', 'abuse')",
        "test_b: no @pytest.mark.srd(...) marker",
    ]


def test_a_helper_that_asserts_must_be_named_assert(tmp_path):
    f = tmp_path / "test_helpers.py"
    f.write_text(
        "import pytest\n\n"
        "def setup(game):\n    assert game\n    return game\n\n"
        "def check_save(game, n):\n    assert n == 1\n\n"
        "def assert_save(game, n):\n    assert n == 1\n\n"
        '@pytest.mark.srd("GLOSS.prone", clause=1, kind="positive")\n'
        "def test_via_check(game):\n    check_save(setup(game), 1)\n\n"
        '@pytest.mark.srd("GLOSS.prone", clause=1, kind="positive")\n'
        "def test_via_setup(game):\n    setup(game)\n\n"
        '@pytest.mark.srd("GLOSS.prone", clause=1, kind="positive")\n'
        "def test_via_assert(game):\n    assert_save(setup(game), 1)\n"
    )
    only = "but only calls to assert_* helpers count; rename it"
    assert [p.split("::")[1] for p in G.test_file_problems(f, {"GLOSS.prone"})] == [
        "check_save: a helper that asserts must be named assert_save, "
        "so the tests calling it count as asserting",
        f"test_via_check: asserts nothing (its helper check_save() asserts, {only})",
        f"test_via_setup: asserts nothing (its helper setup() asserts, {only})",
    ]


def test_append_only_catches_removed_weakened_and_skipped_tests(tmp_path, monkeypatch):
    base = (
        "def test_keep():\n    assert 1\n    assert 2\n\n"
        "def test_gone():\n    assert 1\n\n"
        "def test_skip():\n    assert 1\n\n"
        "def test_red():\n    assert 1\n"
    )
    git_repo(tmp_path, {"tests/srd/test_x.py": base})
    monkeypatch.chdir(tmp_path)
    assert G.append_only() == []
    write(
        tmp_path,
        {
            "tests/srd/test_x.py": "import pytest\n\n"
            "def test_keep():\n    assert 1\n\n"
            "@pytest.mark.skip\ndef test_skip():\n    assert 1\n\n"
            '@pytest.mark.xfail(strict=True, reason="T-12")\ndef test_red():\n    assert 1\n'
        },
    )
    assert G.append_only() == [
        "tests/srd/test_x.py::test_keep: assertions dropped from 2 to 1",
        "tests/srd/test_x.py::test_gone: removed",
        "tests/srd/test_x.py::test_skip: pytest.mark.skip (only an xfail naming a ticket T-<n> is allowed)",
    ]


def test_zones_per_role(tmp_path, monkeypatch):
    git_repo(tmp_path, {"dungdra/a.py": "x = 1\n"})
    monkeypatch.chdir(tmp_path)
    write(tmp_path, {"dungdra/a.py": "x = 2\n", "tests/srd/test_new.py": "", "loop/state/GLOSS.x.json": "{}"})
    changed = G.changed_files()
    assert changed == ["dungdra/a.py", "loop/state/GLOSS.x.json", "tests/srd/test_new.py"]
    assert G.zone_problems(changed, "test-designer") == ["test-designer may not change dungdra/a.py"]
    assert G.zone_problems(changed, "fixer") == ["fixer may not change tests/srd/test_new.py"]
    assert len(G.zone_problems(changed, "rule-analyst")) == 2


def test_run_pytest_and_claimed_outcomes(tmp_path, monkeypatch):
    write(
        tmp_path,
        {
            "t/test_o.py": "import pytest\n\n"
            "def test_pass():\n    assert True\n\n"
            "def test_fail():\n    assert False\n\n"
            '@pytest.mark.xfail(strict=True, reason="T-1")\ndef test_red():\n    assert False\n'
        },
    )
    monkeypatch.chdir(tmp_path)
    ids = [f"t/test_o.py::{n}" for n in ("test_pass", "test_fail", "test_red")]
    outcomes = G.run_pytest(ids)
    assert outcomes == dict(zip(ids, ["passed", "failed", "xfailed"], strict=True))
    claims = {ids[0]: "green", ids[1]: "green", ids[2]: "red"}
    assert G.claimed_outcomes(claims, outcomes) == ["t/test_o.py::test_fail: claimed green, but failed"]


# ---------------------------------------------------------------- quality
def test_suppressions_in_added_lines_only(tmp_path, monkeypatch):
    git_repo(tmp_path, {"dungdra/a.py": "x = 1  # noqa: E501\n"})
    monkeypatch.chdir(tmp_path)
    write(
        tmp_path,
        {
            "dungdra/a.py": "x = 1  # noqa: E501\ny = 2  # type: ignore\nz = 3\n"
            '@pytest.mark.xfail(reason="T-4")\n@pytest.mark.xfail\n',
        },
    )
    subprocess.run(["git", "add", "-A"], check=True)
    assert Q.suppressions() == [
        "dungdra/a.py:2: adds a suppression: y = 2  # type: ignore",
        "dungdra/a.py:5: adds a suppression: @pytest.mark.xfail",
    ]


def test_diff_coverage_counts_changed_executable_lines(tmp_path, monkeypatch):
    git_repo(tmp_path, {"dungdra/a.py": "def f():\n    return 1\n"})
    monkeypatch.chdir(tmp_path)
    write(tmp_path, {"dungdra/a.py": "def f():\n    return 1\n\n\ndef g():\n    return 2\n# comment\n"})
    cov = {"files": {"dungdra/a.py": {"executed_lines": [1, 2, 5], "missing_lines": [6]}}}
    pct, misses = Q.diff_coverage(cov)
    assert (pct, misses) == (50.0, ["dungdra/a.py:6"])  # lines 5 and 6 changed; the comment isn't executable


def test_unit_test_hygiene(tmp_path):
    p = tmp_path / "test_combat.py"
    p.write_text(
        "def test_a(monkeypatch):\n    monkeypatch.setattr('dungdra.combat.attack', None)\n    assert 1\n\n"
        "def test_b(monkeypatch):\n    monkeypatch.setattr('dungdra.combat.random', None)\n    assert 1\n\n"
        "def test_c():\n    pass\n"
    )
    assert Q.unit_test_hygiene([p]) == [
        f"{p}::test_a: patches dungdra.combat.attack, inside the module under test",
        f"{p}::test_c: asserts nothing",
    ]


def test_ratchet_and_baseline_only_improve(tmp_path):
    base = {
        "coverage": {"unit_suite_branch_pct": 40.0},
        "duplication_blocks": {"dungdra_min6": 3},
        "vulture_min80": 3,
        "import_contract_ignored_edges": 2,
    }
    worse = {
        "unit_branch_pct": 39.5,
        "duplication": 4,
        "dead_code": 3,
        "import_ignored": 2,
        "import_contract_ok": False,
    }
    assert Q.ratchet(worse, base) == [
        "unit coverage fell from 40.0% to 39.5%",
        "duplication grew from 3 to 4",
        "lint-imports: the layer contract is broken",
    ]
    f = tmp_path / "b.json"
    f.write_text(json.dumps(base))
    Q.update_baseline({"unit_branch_pct": 45.0, "duplication": 5, "dead_code": 1, "import_ignored": 2}, f)
    b = json.loads(f.read_text())
    assert (
        b["coverage"]["unit_suite_branch_pct"],
        b["duplication_blocks"]["dungdra_min6"],
        b["vulture_min80"],
    ) == (
        45.0,
        3,
        1,
    )


# ---------------------------------------------------------------- SRD-suite helpers
class FakeLog:
    def __init__(self):
        self.events = []


class FakeGame:
    """Only what assert_refused_cleanly reads: snapshot(), combat, log.events."""

    combat = None

    def __init__(self):
        self.hp = 10
        self.log = FakeLog()

    def snapshot(self):
        return {"hp": self.hp}


class Event:
    def __init__(self, kind):
        self.kind = kind

    def __str__(self):
        return self.kind


def test_assert_refused_cleanly_accepts_a_clean_refusal():
    g = FakeGame()

    def refuse():
        g.log.events.append(Event("refused"))
        raise Refusal("You can't", page=186)

    assert assert_refused_cleanly(g, refuse, match="can't").page == 186


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (lambda g: (_ for _ in ()).throw(Refusal("no page")), "cites no SRD page"),
        (lambda g: None, "expected a refusal"),
        (
            lambda g: setattr(g, "hp", 9) or (_ for _ in ()).throw(Refusal("no", page=1)),
            "changed the snapshot",
        ),
        (
            lambda g: g.log.events.append(Event("cast")) or (_ for _ in ()).throw(Refusal("no", page=1)),
            "logged: cast",
        ),
        (lambda g: {"ok": True}, "expected a refusal"),
    ],
)
def test_assert_refused_cleanly_catches_dirty_refusals(action, message):
    g = FakeGame()
    with pytest.raises(AssertionError, match=message):
        assert_refused_cleanly(g, action, g)


def test_srd_conftest_fails_a_passing_test_that_left_forced_dice_unrolled(tmp_path):
    shutil.copy(REPO / "tests/srd/conftest.py", tmp_path / "conftest.py")
    (tmp_path / "test_dice.py").write_text(
        "import pytest\nfrom dungdra import Game\n\n"
        "@pytest.fixture\ndef game():\n    return Game(seed=1)\n\n"
        "def test_unused(game):\n    game.dice.force_str('d20=[5]')\n    assert True\n\n"
        "def test_used(game):\n    game.dice.force_str('d20=[5]')\n    assert game.dice.roll(20) == 5\n"
    )
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--color=no", "-p", "no:cacheprovider", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert "1 failed, 1 passed" in r.stdout, r.stdout
    assert "forced dice were never rolled: {'d20': [5]}" in r.stdout


def test_a_waiver_turns_only_diff_coverage_into_a_note(tmp_path, monkeypatch):
    monkeypatch.setattr(Q, "ruff", lambda: [])
    monkeypatch.setattr(Q, "suppressions", lambda ref="HEAD": [])
    monkeypatch.setattr(Q, "unit_test_hygiene", lambda paths: [])
    monkeypatch.setattr(Q, "rule_references", lambda: [])
    metrics = {
        "unit_branch_pct": 50.0,
        "duplication": 0,
        "dead_code": 0,
        "import_ignored": 0,
        "import_contract_ok": True,
        "_coverage": {},
    }
    monkeypatch.setattr(Q, "measure", lambda: dict(metrics))
    monkeypatch.setattr(Q, "diff_coverage", lambda cov, ref="HEAD": (40.0, ["dungdra/a.py:3"]))
    base = tmp_path / "b.json"
    base.write_text(
        json.dumps(
            {
                "coverage": {"unit_suite_branch_pct": 10.0},
                "duplication_blocks": {"dungdra_min6": 1},
                "vulture_min80": 3,
                "import_contract_ignored_edges": 2,
            }
        )
    )
    problems, _ = Q.dev_gate(baseline_path=base)
    assert problems == ["changed engine lines 40% covered by unit tests (< 90%): ['dungdra/a.py:3']"]
    problems, m = Q.dev_gate(
        baseline_path=base, waive={"diff_coverage": "a cross-cutting change", "ruff": "no"}
    )
    assert problems == [] and m["_waived"] == ["diff_coverage (40%): a cross-cutting change"]


def test_rule_references_must_name_real_units(tmp_path):
    (tmp_path / "a.py").write_text(
        'log(kind, text, page=182, rule="GLOSS.grappled#2")  # SRD[GLOSS.grappled#3]\n'
        "raise Refusal('no', rule='GLOSS.invented#1')\n"
        "x = 1  # SRD[GLOSS.grappled#two]\n"
    )
    assert Q.rule_references(tmp_path, {"GLOSS.grappled"}) == [
        f"{tmp_path / 'a.py'}:2: 'GLOSS.invented#1' is not <unit id>[#<clause number>] of a real SRD unit",
        f"{tmp_path / 'a.py'}:3: 'GLOSS.grappled#two' is not <unit id>[#<clause number>] of a real SRD unit",
    ]


def test_rule_references_check_clause_numbers_against_stage_a(tmp_path):
    (tmp_path / "a.py").write_text('x(rule="GLOSS.grappled#4")\ny(rule="GLOSS.grappled#5")\n')
    problems = Q.rule_references(tmp_path, {"GLOSS.grappled"}, {"GLOSS.grappled": 4})
    assert problems == [f"{tmp_path / 'a.py'}:2: 'GLOSS.grappled#5': stage A numbered GLOSS.grappled #1..#4"]
