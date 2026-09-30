"""Unit tests for proposed rulings: filing, markers, accept into the register, reject and re-queue,
blocking the unit and the dev loop while a reading is undecided."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from scripts.srdloop import claude as C
from scripts.srdloop import gates as G
from scripts.srdloop import prompts as Pr
from scripts.srdloop import rulings as Ru
from scripts.srdloop import runner as Run
from scripts.srdloop import state as S
from scripts.srdloop import tickets as T
from tests.unit.test_srdloop_adversarial import PLAN, agents, repo, run
from tests.unit.test_srdloop_gates import git_repo, write

README = """# DungDra

| ID | Gap | Proposed ruling |
|---|---|---|
| R-01 | Same proficiency twice. | Pick another. |
| R-04 | Disarming without tools. | A plain Dexterity check. |

More text.
"""

TESTS = """import pytest

U = "GLOSS.grappled"


@pytest.mark.srd(U, clause=f"{U}#2", kind="boundary")
def test_a():
    assert True


@pytest.mark.srd(U, clause=f"{U}#4", kind="boundary", ruling="proposed: Tiny exemption is literal")
def test_b():
    assert True


@pytest.mark.srd(
    U,
    clause=f"{U}#1",
    kind="negative",
    ruling="R-01",
)
def test_c():
    assert True
"""


# ---------------------------------------------------------------- the store and markers
def test_create_pending_and_known_ids(tmp_path):
    reg = tmp_path / "README.md"
    reg.write_text(README)
    p1 = Ru.create(
        "GLOSS.grappled", "two grapplers?", "no Disadvantage against either", ["t::a"], tmp_path / "r"
    )
    p2 = Ru.create("GLOSS.prone", "?", "!", [], tmp_path / "r")
    assert (p1["id"], p2["id"]) == ("P-1", "P-2")
    assert [r["id"] for r in Ru.pending("GLOSS.grappled", tmp_path / "r")] == ["P-1"]
    assert Ru.register_ids(reg) == {"R-01", "R-04"}
    assert Ru.known_ids(tmp_path / "r", reg) == {"R-01", "R-04", "P-1", "P-2"}


def test_set_marker_adds_or_replaces_the_ruling(tmp_path):
    f = tmp_path / "test_g.py"
    f.write_text(TESTS)
    assert Ru.set_marker(f"{f}::test_a", "P-1") and Ru.set_marker(f"{f}::test_b", "P-2")
    assert Ru.set_marker(f"{f}::test_c", "R-05") and not Ru.set_marker(f"{f}::test_nope", "P-9")
    markers = G.srd_markers(f.read_text())
    assert {n: m["ruling"] for n, m in markers.items()} == {
        "test_a": "P-1",
        "test_b": "P-2",
        "test_c": "R-05",
    }
    assert markers["test_c"]["kind"] == "negative"  # the rest of the marker is untouched


def test_gate_rejects_free_text_and_unknown_rulings(tmp_path):
    f = tmp_path / "test_g.py"
    f.write_text(TESTS)
    problems = G.test_file_problems(f, {"GLOSS.grappled"}, rulings={"R-01"})
    assert len(problems) == 1 and "ruling 'proposed: Tiny exemption is literal' is neither" in problems[0]


# ---------------------------------------------------------------- decisions
def test_accept_adds_the_next_register_row_and_updates_markers(tmp_path):
    reg = tmp_path / "README.md"
    reg.write_text(README)
    f = tmp_path / "test_g.py"
    f.write_text(TESTS)
    root = tmp_path / "r"
    r = Ru.create("GLOSS.grappled", "Tiny by Tiny?", "Never extra cost.", [f"{f}::test_b"], root)
    Ru.set_marker(f"{f}::test_b", r["id"])
    out = Ru.accept(r["id"], note="as I read it", root=root, register=reg)
    assert out["register_id"] == "R-05" and out["status"] == "accepted"
    text = reg.read_text()
    row = "| R-05 | GLOSS.grappled: Tiny by Tiny? | Never extra cost. *Note: as I read it* |"
    assert f"| R-04 | Disarming without tools. | A plain Dexterity check. |\n{row}\n\nMore text." in text
    assert G.srd_markers(f.read_text())["test_b"]["ruling"] == "R-05"
    with pytest.raises(ValueError, match="accepted, not proposed"):
        Ru.accept(r["id"], root=root, register=reg)


def test_reject_needs_a_reason(tmp_path):
    r = Ru.create("GLOSS.x", "?", "!", [], tmp_path)
    with pytest.raises(ValueError, match="needs a reason"):
        Ru.reject(r["id"], "  ", tmp_path)
    assert Ru.reject(r["id"], "the rule means the grappler's size", tmp_path)["status"] == "rejected"


# ---------------------------------------------------------------- in the loop
def with_ruling(plan):
    p = copy.deepcopy(plan)
    p["rulings_proposed"] = [
        {
            "ambiguity": "Speed bonus while grappled?",
            "ruling": "No bonus applies.",
            "tests": [PLAN["tests"][1]["name"]],
        }
    ]
    return p


def ruling_agents():
    base = agents("none", lambda: None)

    def invoke(role, prompt, *, budget, about, stage, cap):
        res = base(role, prompt, budget=budget, about=about, stage=stage, cap=cap)
        return C.Result(with_ruling(res.output), 0.1, "c") if stage == "C" else res

    return invoke


def test_a_proposal_is_filed_marked_and_blocks_the_unit_and_its_ticket(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    assert run(ctx, ruling_agents()) == "blocked"
    [r] = Ru.all_rulings()
    assert (r["id"], r["status"], r["tests"]) == ("P-1", "proposed", [PLAN["tests"][1]["name"]])
    markers = G.srd_markers(Path("tests/srd/test_glossary.py").read_text())
    assert markers["test_grappled_speed_cannot_increase"]["ruling"] == "P-1"
    [tk] = T.all_tickets()
    assert Run.waits_for_ruling(tk) == "P-1"  # the dev loop won't build on an undecided reading
    assert "P-1 (GLOSS.grappled)" in Pr._rulings("GLOSS.grappled")


def test_accepting_unblocks_the_unit_and_the_ticket(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    write(Path("."), {"README.md": README})
    subprocess.run(["git", "commit", "-qam", "register"], check=True)
    run(ctx, ruling_agents())
    r = Run.decide_ruling("P-1", accept=True, text="for now")
    assert r["register_id"] == "R-05" and S.load("GLOSS.grappled")["status"] == "red"
    assert Run.waits_for_ruling(T.all_tickets()[0]) is None
    log = subprocess.run(
        ["git", "log", "--format=%s", "-1"], capture_output=True, text=True, check=True
    ).stdout
    assert log.strip() == "ruling: P-1 accepted as R-05 (GLOSS.grappled red)"
    assert (
        subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout
        == ""
    )


def test_rejecting_requeues_the_unit_voids_its_tickets_and_lets_its_tests_change(tmp_path, monkeypatch):
    ctx = repo(tmp_path, monkeypatch)
    run(ctx, ruling_agents())
    Run.decide_ruling("P-1", accept=False, text="a Speed bonus does apply")
    st = S.load("GLOSS.grappled")
    assert st["fingerprint"] is None and set(st["stages"]) == {"A", "B"}  # C and D run again
    assert [t["status"] for t in T.all_tickets()] == ["void"]
    prompt = Pr._rulings("GLOSS.grappled")
    assert "rejected because: a Speed bonus does apply" in prompt
    write(Path("."), {"tests/srd/test_glossary.py": "import pytest\n"})  # stage C may now rewrite them
    rejected = frozenset(Ru.load("P-1")["tests"])
    assert all("test_grappled_speed_cannot_increase" not in p for p in G.append_only(allow=rejected))
    assert any("test_grappled_speed_cannot_increase: removed" in p for p in G.append_only())


def test_decide_ruling_on_a_bad_id_fails_cleanly(tmp_path, monkeypatch):
    git_repo(tmp_path, {"README.md": README})
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        Run.decide_ruling("P-9", accept=True)
    assert json.loads(json.dumps(Ru.all_rulings())) == []
