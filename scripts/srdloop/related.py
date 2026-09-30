"""What already exists for a rule unit: golden scenarios, tests and code that touch it.

Stage B (scenario-auditor) gets this list and must give every item a verdict. Matching is
deliberately generous (pages or the unit's own term); the agent decides what really applies.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

SCENARIOS = Path("docs/dnd-golden-scenarios-srd521.md")
SCENARIO_TESTS = Path("tests/scenarios")
SRD_TESTS = Path("tests/srd")
ENGINE = Path("dungdra")

HEADING = re.compile(r"^#### (?P<id>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*) · (?P<title>.+)$", re.M)
PAGE_REF = re.compile(r"p\.(\d+)(?:[–-](\d+))?")
SCENARIO_ID = re.compile(r"\b([A-Z]{2,}(?:-[A-Z]{3})?-\d{2}|J\d)\b")
TEST_KEY = re.compile(r"^test_([a-z_]+?)_?(\d+)")
TAG = re.compile(r"SRD\[([A-Z]+(?:\.[a-z0-9-]+)*)(?:#\d+)?\]")
PAGE_KW = re.compile(r"\bpage=(\d+)|\bp\.(\d+)")


@dataclass
class Scenario:
    id: str
    title: str
    pages: set[int]
    text: str
    tests: list[str] = field(default_factory=list)


def _pages(text: str) -> set[int]:
    out: set[int] = set()
    for m in PAGE_REF.finditer(text):
        lo = int(m.group(1))
        hi = int(m.group(2) or lo)
        out |= set(range(lo, hi + 1))
    return out


def parse_scenarios(path: Path = SCENARIOS) -> list[Scenario]:
    text = path.read_text()
    heads = list(HEADING.finditer(text))
    out = []
    for i, h in enumerate(heads):
        block = text[h.start() : heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        tests_line = next((ln for ln in block.splitlines() if ln.startswith("- **Tests:**")), "")
        out.append(Scenario(h.group("id"), h.group("title").strip(), _pages(tests_line), block))
    return out


def _scenario_keys(sid: str) -> set[tuple[str, int]]:
    """CLS-ROG-01 -> {("clsrog", 1), ("rog", 1)}: test names drop the CLS- prefix."""
    m = re.fullmatch(r"([A-Z-]+?)-?(\d+)", sid)
    if not m:
        return set()
    letters, num = m.group(1).replace("-", "").lower(), int(m.group(2))
    keys = {(letters, num)}
    if letters.startswith("cls"):
        keys.add((letters[3:], num))
    return keys


def index_tests(scenarios: list[Scenario], root: Path = SCENARIO_TESTS) -> None:
    """Attach test node ids to scenarios, by the banner comment above a test ("# CORE-02 · …")
    or by its name (test_core02a_…, test_rog01a_… for CLS-ROG-01)."""
    by_key: dict[tuple[str, int], Scenario] = {}
    by_id = {s.id: s for s in scenarios}
    for s in scenarios:
        for k in _scenario_keys(s.id):
            by_key.setdefault(k, s)
    for f in sorted(root.glob("test_*.py")):
        src = f.read_text()
        banners: list[tuple[int, list[str]]] = []
        for no, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                ids = [i for i in SCENARIO_ID.findall(line) if i in by_id]
                if ids:
                    banners.append((no, ids))
        for node in ast.parse(src).body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test"):
                continue
            nodeid = f"{f.as_posix()}::{node.name}"
            m = TEST_KEY.match(node.name)
            key = (m.group(1).replace("_", ""), int(m.group(2))) if m else None
            if key in by_key:  # the name says which scenario it tests
                owners = {by_key[key].id}
            else:  # otherwise the nearest banner comment above it
                above = [ids for no, ids in banners if no < node.lineno]
                owners = set(above[-1]) if above else set()
            for sid in owners:
                if nodeid not in by_id[sid].tests:
                    by_id[sid].tests.append(nodeid)


def srd_tests(root: Path = SRD_TESTS) -> dict[str, list[str]]:
    """unit id -> test node ids carrying @pytest.mark.srd("<unit id>", ...)."""
    out: dict[str, list[str]] = {}
    if not root.exists():
        return out
    for f in sorted(root.rglob("test_*.py")):
        for node in ast.walk(ast.parse(f.read_text())):
            if not isinstance(node, ast.FunctionDef):
                continue
            for d in node.decorator_list:
                if (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr == "srd"
                    and d.args
                    and isinstance(d.args[0], ast.Constant)
                ):
                    out.setdefault(d.args[0].value, []).append(f"{f.as_posix()}::{node.name}")
    return out


def engine_lines(root: Path = ENGINE) -> dict[str, list[str]]:
    return {f.as_posix(): f.read_text().splitlines() for f in sorted(root.rglob("*.py"))}


def code_sites(unit: dict, lines: dict[str, list[str]]) -> list[dict]:
    """Engine lines tagged SRD[<unit id>] (exact), or citing a page of the unit (a candidate)."""
    lo, hi = unit["pages"]
    out = []
    for f, src in lines.items():
        for no, line in enumerate(src, 1):
            if any(t == unit["id"] for t in TAG.findall(line)):
                out.append({"file": f, "line": no, "match": "tag", "code": line.strip()})
                continue
            for m in PAGE_KW.finditer(line):
                if lo <= int(m.group(1) or m.group(2)) <= hi:
                    out.append({"file": f, "line": no, "match": "page", "code": line.strip()})
                    break
    return out


def term(unit: dict) -> str:
    """The name a unit goes by in running text: "Level 1: Sneak Attack" -> "Sneak Attack",
    "Grappled [Condition]" -> "Grappled", "Crowbar (2 GP)" -> "Crowbar"."""
    t = re.sub(r"\s*\[[^\]]+\]$", "", unit["title"])
    t = re.sub(r"^Level \d+: ", "", t)
    return re.sub(r"\s*\((?:[\d,]+ [GSCEP]P|Varies)\)$", "", t)


def page_density(units: list[dict]) -> dict[int, int]:
    """How many units share each page (a glossary page holds about ten)."""
    out: dict[int, int] = {}
    for u in units:
        for p in range(u["pages"][0], u["pages"][1] + 1):
            out[p] = out.get(p, 0) + 1
    return out


def related(
    unit: dict,
    scenarios: list[Scenario],
    srd: dict[str, list[str]],
    density: dict[int, int] | None = None,
    engine: dict[str, list[str]] | None = None,
) -> dict:
    """A scenario is related when it uses the unit's term, or cites one of its pages and that
    page is not shared by more than three units (then the page alone says little)."""
    lo, hi = unit["pages"]
    pages = {p for p in range(lo, hi + 1) if (density or {}).get(p, 1) <= 3}
    word = re.compile(rf"\b{re.escape(term(unit))}\b")
    found = []
    for s in scenarios:
        why = []
        if s.pages & pages:
            why.append("pages")
        if len(term(unit)) >= 5 and word.search(s.text):
            why.append("term")
        if why:
            found.append({"id": s.id, "title": s.title, "match": why, "tests": s.tests})
    return {
        "unit": unit["id"],
        "scenarios": found,
        "srd_tests": srd.get(unit["id"], []),
        "code": code_sites(unit, engine if engine is not None else engine_lines()),
    }
