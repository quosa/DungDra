"""Dev-loop quality gates: what a fix must satisfy before the harness commits it.

Ratchets compare against loop/quality-baseline.json; after a successful commit the harness
raises the baseline with `update_baseline`. Every check returns a list of problems.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib

from .gates import _asserts, _tests, git

BASELINE = Path("loop/quality-baseline.json")
DIFF_COVERAGE_MIN = 90.0
SUPPRESSION = re.compile(
    r"#\s*noqa|type:\s*ignore|pragma:\s*no\s*cover|pylint:\s*disable|fmt:\s*(?:skip|off)|per-file-ignores|extend-ignore|"
    r"ignore_imports|pytest\.mark\.skip|@pytest\.mark\.xfail(?![^\n]*\bT-\d+)"
)
ALLOWED_SEAMS = ("random", "input", "open", "time")  # what unit tests may patch (tests/unit/SEAMS.md)


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), capture_output=True, text=True, check=False)


# ---------------------------------------------------------------- lint
def ruff() -> list[str]:
    out = []
    check = run("ruff", "check", "--output-format", "json", ".")
    found = json.loads(check.stdout or "[]")
    out += [f"ruff {f['code']} {f['filename']}:{f['location']['row']}: {f['message']}" for f in found]
    fmt = run("ruff", "format", "--check", ".")
    out += [f"ruff format: {line}" for line in fmt.stdout.splitlines() if line.startswith("Would reformat")]
    return out


def added_lines(ref: str = "HEAD", paths: tuple[str, ...] = ()) -> list[tuple[str, int, str]]:
    """(file, line number, text) of every line added since `ref`."""
    diff = git("diff", "-U0", ref, "--", *paths)
    out, f, no = [], None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            f = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            no = int(re.search(r"\+(\d+)", line).group(1))
        elif line.startswith("+") and f:
            out.append((f, no, line[1:]))
            no += 1
    return out


def suppressions(ref: str = "HEAD") -> list[str]:
    """No new noqa, type: ignore, pragma: no cover, ignore lists, skips or ticketless xfails."""
    return [
        f"{f}:{n}: adds a suppression: {t.strip()}" for f, n, t in added_lines(ref) if SUPPRESSION.search(t)
    ]


# ---------------------------------------------------------------- coverage
def unit_coverage() -> dict:
    """Coverage of dungdra/ by the unit tests alone (tests/unit), as coverage.py's JSON report."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "cov.json"
        pytest = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/unit"]
        run(*pytest, "--cov=dungdra", "--cov-branch", f"--cov-report=json:{report}", "--cov-report=")
        return (
            json.loads(report.read_text())
            if report.exists()
            else {"totals": {"percent_covered": 0.0}, "files": {}}
        )


def diff_coverage(cov: dict, ref: str = "HEAD") -> tuple[float | None, list[str]]:
    """Percent of changed executable lines in dungdra/ that the unit tests run, and the misses."""
    changed: dict[str, set[int]] = {}
    for f, n, _ in added_lines(ref, ("dungdra",)):
        if f.endswith(".py"):
            changed.setdefault(f, set()).add(n)
    total = hit = 0
    misses = []
    for f, lines in changed.items():
        data = cov.get("files", {}).get(f)
        if data is None:
            executable, executed = lines, set()
        else:
            executed = set(data.get("executed_lines", []))
            executable = lines & (executed | set(data.get("missing_lines", [])))
        total += len(executable)
        hit += len(executable & executed)
        misses += [f"{f}:{n}" for n in sorted(executable - executed)]
    return (100.0 * hit / total if total else None), misses


# ---------------------------------------------------------------- architecture and hygiene
def import_contract() -> tuple[bool, int]:
    """Whether lint-imports passes, and how many ignored imports the contract carries."""
    ok = run("lint-imports").returncode == 0
    cfg = tomllib.loads(Path("pyproject.toml").read_text())
    ignored = sum(len(c.get("ignore_imports", [])) for c in cfg["tool"]["importlinter"]["contracts"])
    return ok, ignored


def duplication() -> int:
    flags = ["--disable=all", "--enable=duplicate-code", "--min-similarity-lines=6"]
    r = run("pylint", *flags, "--ignore-imports=y", "--ignore-docstrings=y", "dungdra")
    return r.stdout.count("R0801")


def dead_code() -> int:
    return len(run("vulture", "dungdra", "--min-confidence", "80").stdout.splitlines())


def _patch_targets(fn: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in ("patch", "setattr") and node.args and isinstance(node.args[0], ast.Constant):
                out.append(str(node.args[0].value))
    return out


def unit_test_hygiene(paths: list[Path]) -> list[str]:
    """Unit tests assert something, and never patch the module they test: tests/unit/test_combat.py
    may not patch dungdra.combat.* (only declared seams such as random, input, time)."""
    out = []
    for p in paths:
        module = p.stem.removeprefix("test_")
        for name, fn in _tests(p.read_text()).items():
            if _asserts(fn) == 0:
                out.append(f"{p}::{name}: asserts nothing")
            for target in _patch_targets(fn):
                if target.startswith(f"dungdra.{module}") and target.split(".")[-1] not in ALLOWED_SEAMS:
                    out.append(f"{p}::{name}: patches {target}, inside the module under test")
    return out


# ---------------------------------------------------------------- the ratchet
def measure() -> dict:
    cov = unit_coverage()
    ok, ignored = import_contract()
    return {
        "unit_branch_pct": round(cov["totals"]["percent_covered"], 2),
        "duplication": duplication(),
        "dead_code": dead_code(),
        "import_contract_ok": ok,
        "import_ignored": ignored,
        "_coverage": cov,
    }


def ratchet(metrics: dict, baseline: dict) -> list[str]:
    out = []
    base = {
        "unit_branch_pct": baseline["coverage"]["unit_suite_branch_pct"],
        "duplication": baseline["duplication_blocks"]["dungdra_min6"],
        "dead_code": baseline["vulture_min80"],
        "import_ignored": baseline["import_contract_ignored_edges"],
    }
    if metrics["unit_branch_pct"] < base["unit_branch_pct"]:
        out.append(f"unit coverage fell from {base['unit_branch_pct']}% to {metrics['unit_branch_pct']}%")
    for key in ("duplication", "dead_code", "import_ignored"):
        if metrics[key] > base[key]:
            out.append(f"{key} grew from {base[key]} to {metrics[key]}")
    if not metrics["import_contract_ok"]:
        out.append("lint-imports: the layer contract is broken")
    return out


WAIVABLE = {"diff_coverage"}  # a person may waive only these, per ticket, with a reason


def dev_gate(
    ref: str = "HEAD", baseline_path: Path = BASELINE, waive: dict[str, str] | None = None
) -> tuple[list[str], dict]:
    """Everything a dev-loop change must pass. Returns (problems, metrics); metrics["_waived"]
    lists the checks a person waived for this ticket that would otherwise have failed."""
    waive = {k: v for k, v in (waive or {}).items() if k in WAIVABLE}
    problems = ruff() + suppressions(ref)
    metrics = measure()
    metrics["_waived"] = []
    problems += ratchet(metrics, json.loads(baseline_path.read_text()))
    pct, misses = diff_coverage(metrics["_coverage"], ref)
    if pct is not None and pct < DIFF_COVERAGE_MIN:
        floor = f"{DIFF_COVERAGE_MIN:.0f}%"
        finding = f"changed engine lines {pct:.0f}% covered by unit tests (< {floor}): {misses[:8]}"
        if "diff_coverage" in waive:
            metrics["_waived"].append(f"diff_coverage ({pct:.0f}%): {waive['diff_coverage']}")
        else:
            problems.append(finding)
    problems += unit_test_hygiene(sorted(Path("tests/unit").glob("test_*.py")))
    return problems, metrics


def update_baseline(metrics: dict, baseline_path: Path = BASELINE) -> None:
    """After a commit: the ratchet only moves in the good direction."""
    b = json.loads(baseline_path.read_text())
    b["coverage"]["unit_suite_branch_pct"] = max(
        b["coverage"]["unit_suite_branch_pct"], metrics["unit_branch_pct"]
    )
    b["duplication_blocks"]["dungdra_min6"] = min(
        b["duplication_blocks"]["dungdra_min6"], metrics["duplication"]
    )
    b["vulture_min80"] = min(b["vulture_min80"], metrics["dead_code"])
    b["import_contract_ignored_edges"] = min(b["import_contract_ignored_edges"], metrics["import_ignored"])
    baseline_path.write_text(json.dumps(b, indent=2) + "\n")
