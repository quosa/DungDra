"""The loop overview page builds from the loop's own files, and its numbers are read from them."""

import json

import pdfplumber

from scripts.docs import loop_overview as LO


def loop_files(root):
    (root / "loop/state").mkdir(parents=True)
    (root / "loop/tickets").mkdir()
    (root / "loop/rulings").mkdir()
    unit = {"id": "GLOSS.x", "status": "red", "tests": ["a", "b"]}
    (root / "loop/state/GLOSS.x.json").write_text(json.dumps(unit))
    (root / "loop/state/GLOSS.y.json").write_text(json.dumps({"id": "GLOSS.y", "status": "pending"}))
    for i, (kind, status) in enumerate((("bug", "fixed"), ("infra", "open")), 1):
        (root / f"loop/tickets/T-{i}.json").write_text(json.dumps({"kind": kind, "status": status}))
    (root / "loop/rulings/P-1.json").write_text(json.dumps({"status": "accepted"}))
    costs = [{"about": "GLOSS.x", "cost_usd": 2.5}, {"about": "T-1", "cost_usd": 1.0}]
    (root / "loop/costs.jsonl").write_text("".join(json.dumps(c) + "\n" for c in costs))


def test_numbers_come_from_the_loop_files(tmp_path):
    loop_files(tmp_path)
    n = LO.numbers(tmp_path)
    assert (n["units"], n["tests"], n["fixed"], n["rulings"]["accepted"]) == (1, 2, 1, 1)
    assert n["tickets"] == {"bug": 1, "infra": 1} and n["audit_per_unit"] == 2.5 and n["dev"] == 1.0


def test_the_page_builds_and_shows_every_stage_and_discovery(tmp_path):
    loop_files(tmp_path)
    out = tmp_path / "overview.pdf"
    LO.draw(out, tmp_path)
    with pdfplumber.open(out) as pdf:
        assert len(pdf.pages) == 1
        text = pdf.pages[0].extract_text()
    agents = ("rule-analyst", "scenario-auditor", "test-designer", "test-verifier", "fixer", "fix-reviewer")
    assert all(word in text for word in agents)
    for word in ("Bug ticket", "Infra ticket", "Ruling proposal", "Test to review", "Dispute", "Follow-up"):
        assert word in text
