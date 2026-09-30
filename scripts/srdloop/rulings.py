"""Proposed rulings: where the SRD is ambiguous and a test had to pick a reading.

The test designer reports each one (with the tests that depend on it); the harness files it as
P-<n> in loop/rulings/ and writes `ruling="P-<n>"` into those tests' srd markers. A person decides:

- accept: it becomes the next R-<n> in the rulings register (README.md), and the markers follow;
- reject: the unit goes stale, and stage C rewrites those tests for another reading, with the
  reason in its prompt (the append-only gate lets them change).

While a proposal is pending, its unit is blocked and the dev loop skips tickets whose tests
depend on it: no engine code is written for a reading nobody has agreed to.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

RULINGS = Path("loop/rulings")
REGISTER = Path("README.md")
REGISTER_ROW = re.compile(r"^\| R-(\d+) \|", re.M)


def _next_id(root: Path) -> str:
    nums = [int(m.group(1)) for p in root.glob("P-*.json") if (m := re.fullmatch(r"P-(\d+)\.json", p.name))]
    return f"P-{max(nums, default=0) + 1}"


def save(r: dict, root: Path = RULINGS) -> None:
    root.mkdir(parents=True, exist_ok=True)
    p = root / f"{r['id']}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def load(pid: str, root: Path = RULINGS) -> dict:
    return json.loads((root / f"{pid}.json").read_text())


def all_rulings(root: Path = RULINGS) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(root.glob("P-*.json"), key=lambda p: int(p.stem[2:]))]


def create(unit: str, ambiguity: str, ruling: str, tests: list[str], root: Path = RULINGS) -> dict:
    r = {
        "id": _next_id(root),
        "unit": unit,
        "ambiguity": ambiguity,
        "ruling": ruling,
        "tests": tests,
        "status": "proposed",
        "register_id": None,
        "note": "",
        "reason": "",
    }
    save(r, root)
    return r


def pending(unit: str | None = None, root: Path = RULINGS) -> list[dict]:
    return [r for r in all_rulings(root) if r["status"] == "proposed" and (unit is None or r["unit"] == unit)]


def register_ids(register: Path = REGISTER) -> set[str]:
    return (
        {f"R-{int(m.group(1)):02d}" for m in REGISTER_ROW.finditer(register.read_text())}
        if register.exists()
        else set()
    )


def known_ids(root: Path = RULINGS, register: Path = REGISTER) -> set[str]:
    """Ids a marker may name: accepted R-<n> and open P-<n> (a rejected one may not stay)."""
    return register_ids(register) | {r["id"] for r in all_rulings(root) if r["status"] == "proposed"}


# ---------------------------------------------------------------- markers
def set_marker(nodeid: str, value: str) -> bool:
    """Set ruling="<value>" in a test's srd marker (replacing any ruling there). Returns success."""
    path, _, name = nodeid.partition("::")
    if not Path(path).exists():
        return False
    src = Path(path).read_text()
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.FunctionDef) and node.name == name.split("[")[0]):
            continue
        for d in node.decorator_list:
            if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "srd"):
                continue
            lines = src.splitlines(keepends=True)
            kw = next((k for k in d.keywords if k.arg == "ruling"), None)
            if kw is not None:  # replace the value, wherever it is
                v = kw.value
                line = lines[v.lineno - 1]
                if v.lineno == v.end_lineno:
                    lines[v.lineno - 1] = line[: v.col_offset] + json.dumps(value) + line[v.end_col_offset :]
                else:
                    first = lines[v.lineno - 1][: v.col_offset] + json.dumps(value)
                    last = lines[v.end_lineno - 1][v.end_col_offset :]
                    lines[v.lineno - 1 : v.end_lineno] = [first + last]
            else:  # add it before the closing parenthesis
                line = lines[d.end_lineno - 1]
                close = d.end_col_offset - 1
                lines[d.end_lineno - 1] = line[:close] + f', ruling="{value}"' + line[close:]
            Path(path).write_text("".join(lines))
            return True
    return False


# ---------------------------------------------------------------- decisions
def _register_row(r: dict, rid: str) -> str:
    note = f" *Note: {r['note']}*" if r["note"] else ""
    return f"| {rid} | {r['unit']}: {r['ambiguity']} | {r['ruling']}{note} |"


def accept(pid: str, note: str = "", root: Path = RULINGS, register: Path = REGISTER) -> dict:
    """The proposal becomes the next R-<n> in the register; its tests' markers follow."""
    r = load(pid, root)
    if r["status"] != "proposed":
        raise ValueError(f"{pid} is {r['status']}, not proposed")
    text = register.read_text()
    rows = list(REGISTER_ROW.finditer(text))
    if not rows:
        raise ValueError(f"no rulings register (| R-<n> | rows) in {register}")
    rid = f"R-{max(int(m.group(1)) for m in rows) + 1:02d}"
    r.update(status="accepted", register_id=rid, note=note)
    end = text.index("\n", rows[-1].start()) + 1
    register.write_text(text[:end] + _register_row(r, rid) + "\n" + text[end:])
    for n in r["tests"]:
        set_marker(n, rid)
    save(r, root)
    return r


def reject(pid: str, reason: str, root: Path = RULINGS) -> dict:
    """Recorded with the reason; the unit's state is made stale by the caller (runner)."""
    r = load(pid, root)
    if r["status"] != "proposed":
        raise ValueError(f"{pid} is {r['status']}, not proposed")
    if not reason.strip():
        raise ValueError("a rejection needs a reason: stage C uses it to pick another reading")
    r.update(status="rejected", reason=reason)
    save(r, root)
    return r
