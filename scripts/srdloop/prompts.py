"""What each agent is told. The system prompt (.claude/agents/<role>.md) says how to work; these
prompts carry the material: the rule text, earlier stages' results, related items, problems
from a failed gate."""

from __future__ import annotations

import json
from pathlib import Path

RULINGS = Path("README.md")  # the rulings register (R-01…) lives in the README
ABUSE = Path("loop/abuse-catalogue.md")


def _unit_block(u: dict) -> str:
    where = " › ".join([u["chapter"], *u["heading_path"]])
    pages = f"SRD p.{u['pages'][0]}–{u['pages'][1]}"
    return f"### {u['id']} — {u['title']} ({pages}; {where})\n\n{u['text']}"


def _rulings(unit_id: str | None = None) -> str:
    from . import rulings as Ru

    text = RULINGS.read_text() if RULINGS.exists() else ""
    rows = [ln for ln in text.splitlines() if ln.startswith("| R-")]
    out = "\n".join(rows) or "(none)"
    waiting = Ru.pending()
    if waiting:
        out += "\n\nProposed, not yet decided (don't build on these):\n"
        out += "\n".join(f"- {r['id']} ({r['unit']}): {r['ambiguity']} — {r['ruling']}" for r in waiting)
    rejected = [r for r in Ru.all_rulings() if r["status"] == "rejected" and r["unit"] == unit_id]
    if rejected:
        out += "\n\nRejected for this unit (rewrite the tests that used them; don't propose them again):\n"
        out += "\n".join(
            f"- {r['id']}: {r['ruling']} — rejected because: {r['reason']}. Tests: {r['tests']}"
            for r in rejected
        )
    return out


def _retry(problems: list[str]) -> str:
    if not problems:
        return ""
    lines = "\n".join(f"- {p}" for p in problems)
    return f"\n\n## Your previous attempt failed these checks; fix them\n\n{lines}"


def analysis(unit: dict, related_units: list[dict], problems: list[str] = ()) -> str:
    rel = "\n\n".join(_unit_block(u) for u in related_units) or "(none)"
    return (
        f"Analyse this SRD 5.2.1 rule unit.\n\n## The unit\n\n{_unit_block(unit)}\n\n"
        f"## Units it references (for relations and conflicts)\n\n{rel}\n\n"
        f"## Rulings register\n\n{_rulings(unit['id'])}" + _retry(problems)
    )


def verdicts(unit: dict, analysis: dict, related: dict, problems: list[str] = ()) -> str:
    return (
        f"Give every related item a verdict against this rule.\n\n## The unit\n\n{_unit_block(unit)}\n\n"
        f"## Stage A analysis\n\n```json\n{json.dumps(analysis, indent=1, ensure_ascii=False)}\n```\n\n"
        f"## Related items\n\n```json\n{json.dumps(related, indent=1, ensure_ascii=False)}\n```"
        + _retry(problems)
    )


def test_plan(unit: dict, analysis: dict, verdicts: dict, problems: list[str] = ()) -> str:
    abuse = ABUSE.read_text() if ABUSE.exists() else "(empty; start it)"
    return (
        f"Design and write the SRD tests for this rule unit.\n\n## The unit\n\n{_unit_block(unit)}\n\n"
        f"## Stage A analysis (clauses, relations, ambiguities)\n\n```json\n"
        f"{json.dumps(analysis, indent=1, ensure_ascii=False)}\n```\n\n"
        f"## Stage B verdicts on existing scenarios, tests and code\n\n```json\n"
        f"{json.dumps(verdicts, indent=1, ensure_ascii=False)}\n```\n\n"
        f"## Rulings register\n\n{_rulings(unit['id'])}\n\n## Abuse catalogue\n\n{abuse}" + _retry(problems)
    )


def verification(unit: dict, plan: dict, problems: list[str] = ()) -> str:
    tests = [{k: t[k] for k in ("name", "clause", "kind", "rule_quote", "claim")} for t in plan["tests"]]
    return (
        f"Try to refute each of these tests.\n\n## The unit\n\n{_unit_block(unit)}\n\n"
        f"## The tests\n\n```json\n{json.dumps(tests, indent=1, ensure_ascii=False)}\n```" + _retry(problems)
    )


def fix(ticket: dict, unit: dict | None, failures: str, problems: list[str] = ()) -> str:
    rule = _unit_block(unit) if unit else "(no unit)"
    waived = "".join(f"\n- `{k}`: {v}" for k, v in ticket.get("waive", {}).items())
    waived = f"\n\n## Checks a person waived for this ticket\n{waived}" if waived else ""
    return (
        f"Fix ticket {ticket['id']} ({ticket['kind']}): {ticket['title']}{waived}\n\n"
        f"## Acceptance tests that must pass\n\n" + "\n".join(f"- `{t}`" for t in ticket["tests"]) + "\n\n"
        f"## The rule\n\n{rule}\n\n## Current failures\n\n```\n{failures[-6000:]}\n```" + _retry(problems)
    )


def review(ticket: dict, diff: str, gate: str, open_tickets: list[dict] = ()) -> str:
    others = "\n".join(
        f"- {t['id']} ({t['kind']}): {t['title']}" for t in open_tickets if t["id"] != ticket["id"]
    )
    return (
        f"Review this fix for ticket {ticket['id']} ({ticket['kind']}): {ticket['title']}\n\n"
        f"## Gate results\n\n```\n{gate}\n```\n\n## The diff\n\n```diff\n{diff[-40000:]}\n```\n\n"
        f"## Open tickets (don't file a follow-up one of these already covers)\n\n{others or '(none)'}"
    )
