"""Mutation check for the test verifier: break one line of the engine in a scratch copy and run a
test there. A test that still passes with its rule broken doesn't test that rule. The
repository itself is never touched."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

COPY = ("dungdra", "tests", "scripts", "pyproject.toml", "docs/srd")


def mutate(file: str, line: int, old: str, new: str, nodeid: str, root: Path = Path(".")) -> str:
    """Replace `old` with `new` on `line` of `file` (under dungdra/) in a copy, run `nodeid`
    there. Returns "passed", "failed", or an explanation of why nothing ran."""
    if not file.startswith("dungdra/"):
        return f"refused: only engine files (dungdra/) can be mutated, not {file}"
    with tempfile.TemporaryDirectory(prefix="srdloop-mutate-") as tmp:
        for part in COPY:
            src = root / part
            if src.is_dir():
                shutil.copytree(src, Path(tmp) / part, ignore=shutil.ignore_patterns("__pycache__"))
            elif src.exists():
                (Path(tmp) / part).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, Path(tmp) / part)
        target = Path(tmp) / file
        if not target.exists():
            return f"refused: no such file {file}"
        lines = target.read_text().splitlines(keepends=True)
        if not 1 <= line <= len(lines) or old not in lines[line - 1]:
            return f"refused: {old!r} is not on line {line} of {file}"
        lines[line - 1] = lines[line - 1].replace(old, new, 1)
        target.write_text("".join(lines))
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--color=no",
                "-p",
                "no:cacheprovider",
                "--runxfail",
                nodeid,
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0:
            return "passed"
        if r.returncode == 1:
            return "failed"
        return f"error: {(r.stdout + r.stderr).strip()[-400:]}"
