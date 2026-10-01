# DungDra

A rules-faithful, single-player D&D engine for SRD 5.2.1 (the 2024 rules), in pure Python 3.10+
with no runtime dependencies. All core rules and the Rules Glossary are implemented, with only a
subset of content. `README.md` covers play, architecture, scope and the rulings register.

This file is loaded into every Claude session in the repo, including the agents the SRD rule
loop launches. Anyone **operating or changing the loop** (`scripts/srdloop/`, `loop/`,
`.claude/agents/`) reads `docs/srd-loop-operating.md` first.

## Environment

- Python env: the `dungdra` pyenv environment (3.13). Dependencies: `pip install -e ".[dev,srd]"`.
- Python only: add a library to `pyproject.toml` extras, never mix in other languages.
- `python -m pytest -q` runs everything. `ruff check .` and `ruff format --check .` must be clean.
  `python -m scripts.srdloop dev-gate` runs the dev loop's quality checks.

## Layout

| Path | What |
|---|---|
| `dungdra/` | The engine. Its import layers are enforced in `pyproject.toml` (`[tool.importlinter]`) |
| `tests/unit/` | Unit tests for engine and harness components (coverage ratchet; seams in `tests/unit/SEAMS.md`) |
| `tests/srd/` | SRD-derived acceptance tests, one marker per test: `@pytest.mark.srd("<unit id>", clause=…, kind=…)` |
| `tests/scenarios/` | Golden scenarios from `docs/dnd-golden-scenarios-srd521.md` |
| `tests/support/` | Shared test helpers (`assert_refused_cleanly`, …) |
| `docs/SRD_CC_v5.2.1.pdf` | The rules source; `p.N` everywhere means a page of this PDF |
| `docs/srd/units.jsonl` | The SRD split into 1835 rule units, pinned by hash in `docs/srd/units.approved` |
| `scripts/srd/extract.py` | Builds `docs/srd/` from the PDF (`--check` validates) |
| `scripts/srdloop/`, `loop/` | The SRD rule loop: harness code and its state |

## Rules for every change

- **Rule text.** Only `docs/srd/units.jsonl` and the PDF count as rule text. Never edit
  `docs/srd/`. Re-extracting and `extract.py --approve` are a person's decision.
- **Rulings.** Where the SRD is silent or ambiguous, the README's register (R-01…) decides.
  Don't invent a reading: propose one and let a person decide. Only a person adds register rows.
- **Acceptance suites are append-only** (`tests/srd`, `tests/scenarios`). Never remove a test,
  drop an assertion or add a skip. A known-wrong engine result is marked
  `@pytest.mark.xfail(strict=True, reason="T-<n>: …")`, with the reason written out in the
  marker. Changing or removing an acceptance test needs a person's approval.
- **No suppressions:** no `noqa`, `type: ignore`, `pragma: no cover`, `fmt: skip`/`off`,
  lint ignore-list entries, skips, or xfails without a ticket. Fix the cause; `ruff format`
  fixes formatting.
- **Real engine in acceptance tests:** no mocks or monkeypatching. Dice are forced
  (`game.dice.force_str("d20=[12]")`) and every forced die must be rolled. Unit tests may
  replace only the seams listed in `tests/unit/SEAMS.md`.
- **Traceability.** Code that implements a rule carries `# SRD[<unit id>#<clause>]`. Log events
  and refusals carry `page=` and `rule="<unit id>#<clause>"`, plus `ruling="R-nn"` where a
  register ruling applies. Clause numbers come from the loop's stage-A analysis
  (`loop/runs/<unit id>/A.json`), not from the SRD's own labels.
- **Fix the rule, not the test case:** no special cases for a fixture, a monster name or a
  number from a test. Put a rule in the layer where it lives, and extend an existing mechanism
  rather than adding a second one.
- **Scope:** content the engine doesn't implement is refused with `OutOfScope`, not
  half-implemented. Don't write tests for it either.
