"""Audit-loop gates: mechanical checks on what the agents produced. A stage's output is only
checkpointed once its gates pass; every function returns a list of problems (empty = pass)."""

from __future__ import annotations

import ast
import fnmatch
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

KINDS = ("positive", "negative", "boundary", "abuse")
REQUIRED_KINDS = ("positive", "negative")  # every clause; "boundary" too where the clause has a threshold
ACCEPTANCE = ("tests/srd", "tests/scenarios")  # append-only suites
TICKET = re.compile(r"\bT-(?:\d+|new)\b")  # "T-new": a red test before the harness numbers its ticket

# What each role may change. The harness itself writes loop/state, loop/runs, loop/tickets.
HARNESS = (
    "loop/state/**",
    "loop/runs/**",
    "loop/tickets/**",
    "loop/rulings/**",
    "loop/costs.jsonl",
    "loop/COVERAGE.md",
    "loop/RULEMAP.md",
)
ZONES: dict[str, tuple[str, ...]] = {
    "rule-analyst": (),
    "scenario-auditor": (),
    "test-verifier": (),
    "fix-reviewer": (),
    "test-designer": (
        "tests/srd/**",
        "tests/scenarios/**",
        "tests/support/**",
        "docs/scenario-notes.md",
        "loop/abuse-catalogue.md",
    ),
    "fixer": ("dungdra/**", "tests/unit/**", "loop/requests/**"),
    "unit-test-writer": ("tests/unit/**",),
}
MOCKS = re.compile(r"\b(unittest\.mock|MagicMock|Mock\(|patch\(|monkeypatch|mocker)\b")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------- stage outputs
def quotes(items: list[dict], field: str, texts: list[str], what: str) -> list[str]:
    """Every item[field] must be a verbatim (whitespace-insensitive) quote of one of `texts`."""
    corpus = [norm(t) for t in texts]
    out = []
    for i, it in enumerate(items):
        q = norm(it.get(field, ""))
        if not q:
            out.append(f"{what} #{i + 1}: empty {field}")
        elif not any(q in t for t in corpus):
            out.append(f"{what} #{i + 1}: {field} is not a verbatim quote: {q[:80]!r}")
    return out


def clause_coverage(clauses: list[dict], tests: list[dict], abuse: list[dict]) -> list[str]:
    """Each clause has tests of every required kind (boundary when it has a threshold), or a
    not_testable reason; each abuse case in the plan is implemented or justified."""
    out = []
    ids = {c["id"] for c in clauses}
    for t in tests:
        if t.get("clause") not in ids:
            out.append(f"test {t.get('name')!r} names unknown clause {t.get('clause')!r}")
        if t.get("kind") not in KINDS:
            out.append(f"test {t.get('name')!r} has kind {t.get('kind')!r}, not one of {KINDS}")
    for c in clauses:
        if c.get("not_testable"):
            if not norm(c.get("reason", "")):
                out.append(f"clause {c['id']}: not_testable without a reason")
            continue
        kinds = {t.get("kind") for t in tests if t.get("clause") == c["id"]}
        need = set(REQUIRED_KINDS) | ({"boundary"} if c.get("threshold") else set())
        missing = sorted(need - kinds)
        if missing:
            out.append(f"clause {c['id']}: no {', '.join(missing)} test")
    for a in abuse:
        if not a.get("test") and not norm(a.get("reason", "")):
            out.append(f"abuse case {a.get('case')!r}: neither a test nor a reason")
    return out


# ---------------------------------------------------------------- test files
def _marker(fn: ast.FunctionDef) -> ast.Call | None:
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "srd":
            return d
    return None


def _constants(tree: ast.Module) -> dict[str, str]:
    """Module-level NAME = "string" bindings, so a marker may say srd(U, ...) with U = "GLOSS.x"."""
    out = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            out |= {t.id: node.value.value for t in node.targets if isinstance(t, ast.Name)}
    return out


def _value(node: ast.AST | None, consts: dict[str, str]):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def srd_markers(src: str) -> dict[str, dict]:
    """test name -> {"unit", "clause", "kind"} from its @pytest.mark.srd(...) marker."""
    tree = ast.parse(src)
    consts = _constants(tree)
    out = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and (m := _marker(fn)) is not None:
            kw = {k.arg: _value(k.value, consts) for k in m.keywords}
            out[fn.name] = {
                "unit": _value(m.args[0], consts) if m.args else None,
                **{k: kw.get(k) for k in ("clause", "kind", "ruling")},
            }
    return out


def _asserts(fn: ast.AST) -> int:
    """Assertions in a test: assert statements, pytest.raises blocks, assert_* helper calls."""
    n = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            n += 1
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name == "raises" or name.startswith("assert_"):
                n += 1
    return n


def _tests(src: str) -> dict[str, ast.FunctionDef]:
    return {
        n.name: n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test")
    }


def test_file_problems(
    path: Path, unit_ids: set[str], srd: bool = True, rulings: set[str] | None = None
) -> list[str]:
    """SRD tests: an srd("<unit id>", kind=…) marker naming a real unit, at least one
    assertion, and no mocks anywhere in the file."""
    src = path.read_text()
    out = [
        f"{path}: uses mocks ({m.group(1)}); the SRD suites use the real engine" for m in MOCKS.finditer(src)
    ][:1]
    markers = srd_markers(src)
    for name, fn in _tests(src).items():
        if _asserts(fn) == 0:
            out.append(f"{path}::{name}: asserts nothing")
        out += [
            f'{path}::{name}: {x}: write the reason out in the marker (reason="T-new: …"), not as a name'
            for x in _xfail_reasons(fn)
        ]
        if not srd:
            continue
        m = markers.get(name)
        if m is None:
            out.append(f"{path}::{name}: no @pytest.mark.srd(...) marker")
            continue
        if m["unit"] not in unit_ids:
            out.append(f"{path}::{name}: marker names unknown unit {m['unit']!r}")
        if m["kind"] not in KINDS:
            out.append(f"{path}::{name}: marker kind {m['kind']!r} is not one of {KINDS}")
        if rulings is not None and m["ruling"] is not None and m["ruling"] not in rulings:
            out.append(
                f"{path}::{name}: ruling {m['ruling']!r} is neither in the register nor pending; "
                "name an R-<n> or leave it out (report the ambiguity in rulings_proposed and the "
                "harness adds P-<n>)"
            )
    return out


def _xfail_reasons(fn: ast.FunctionDef) -> list[str]:
    """xfail markers whose reason isn't written out as a string in the decorator: the harness
    fills in the ticket number (T-new → T-<n>) within the test, so a constant elsewhere hides it."""
    out = []
    for d in fn.decorator_list:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "xfail":
            reason = next((k.value for k in d.keywords if k.arg == "reason"), None)
            if not (isinstance(reason, ast.Constant) and isinstance(reason.value, str)):
                out.append(ast.unparse(d))
    return out


def _skips(fn: ast.FunctionDef) -> list[str]:
    """skip/xfail markers on a test, as source text."""
    return [
        ast.unparse(d) for d in fn.decorator_list if re.search(r"\b(skip|skipif|xfail)\b", ast.unparse(d))
    ]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout


def append_only(
    ref: str = "HEAD", roots: tuple[str, ...] = ACCEPTANCE, allow: frozenset[str] = frozenset()
) -> list[str]:
    """Acceptance tests may be added to, never weakened: no test removed, no assertion dropped,
    no skip, and no xfail that doesn't name a ticket (T-<n>). `allow`: node ids that may change
    anyway (tests of a rejected ruling, which stage C must rewrite)."""
    out = []
    old_files = [
        f for f in git("ls-tree", "-r", "--name-only", ref, "--", *roots).splitlines() if f.endswith(".py")
    ]
    for f in old_files:
        old = _tests(git("show", f"{ref}:{f}"))
        new = _tests(Path(f).read_text()) if Path(f).exists() else {}
        for name, fn in old.items():
            if f"{f}::{name}" in allow:
                continue
            if name not in new:
                out.append(f"{f}::{name}: removed")
            elif _asserts(new[name]) < _asserts(fn):
                out.append(f"{f}::{name}: assertions dropped from {_asserts(fn)} to {_asserts(new[name])}")
    for root in roots:
        for f in sorted(Path(root).rglob("test_*.py")):
            for name, fn in _tests(f.read_text()).items():
                for s in _skips(fn):
                    if "xfail" not in s or not TICKET.search(s):
                        out.append(f"{f}::{name}: {s} (only an xfail naming a ticket T-<n> is allowed)")
    return out


def changed_files(ref: str = "HEAD") -> list[str]:
    tracked = git("diff", "--name-only", ref).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({*tracked, *untracked})


def zone_problems(paths: list[str], role: str) -> list[str]:
    allowed = ZONES[role] + HARNESS
    return [f"{role} may not change {p}" for p in paths if not any(fnmatch.fnmatch(p, g) for g in allowed)]


# ---------------------------------------------------------------- running tests
def run_pytest(nodeids: list[str]) -> dict[str, str]:
    """Outcome per test: passed, failed, error, skipped, xfailed or xpassed."""
    if not nodeids:
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={xml}",
                "-o",
                "junit_family=xunit2",
                *nodeids,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if not xml.exists():
            return {n: "error" for n in nodeids}
        out = {}
        for case in ET.parse(xml).getroot().iter("testcase"):
            nodeid = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name')}"
            kinds = {child.tag for child in case}
            skipped = case.find("skipped")
            if "failure" in kinds:
                out[nodeid] = (
                    "xpassed" if "XPASS" in (case.find("failure").get("message") or "") else "failed"
                )
            elif "error" in kinds:
                out[nodeid] = "error"
            elif skipped is not None:
                out[nodeid] = "xfailed" if skipped.get("type") == "pytest.xfail" else "skipped"
            else:
                out[nodeid] = "passed"
        return out


def claimed_outcomes(claims: dict[str, str], outcomes: dict[str, str]) -> list[str]:
    """Tests the designer claimed green must pass; tests claimed red must be xfail-strict and fail."""
    out = []
    for nodeid, claim in claims.items():
        got = outcomes.get(nodeid, "missing")
        want = "passed" if claim == "green" else "xfailed"
        if got != want:
            out.append(f"{nodeid}: claimed {claim}, but {got}")
    return out
