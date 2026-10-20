---
name: srd-rule
description: Run the SRD rule loop's four stages (analyse, audit scenarios, write tests, verify) on one SRD 5.2.1 rule unit interactively, with the same gates as the headless loop. Use when asked to check, test or pilot one rule, e.g. "/srd-rule GLOSS.grappled".
---

# One SRD rule unit, interactively

The headless loop is `python -m scripts.srdloop run --budget <USD> --units <unit id>`. This
skill does the same in the current session: you route the work to the loop's agents and let
the harness's gates decide; you don't judge results yourself.

Argument: a unit id (`python -m scripts.srdloop related <id>` shows what exists for it; ids are
in `docs/srd/srd.md` under each heading).

For each stage that `loop/state/<unit id>.json` doesn't show as done, in order A, B, C, D:

1. Get the prompt: `python -m scripts.srdloop prompt <stage> <unit id>`.
2. Delegate it to the stage's agent, with the prompt verbatim:
   A `rule-analyst`, B `scenario-auditor`, C `test-designer`, D `test-verifier`.
   Ask it to return only the JSON its schema describes
   (`scripts/srdloop/schemas/`: analysis, verdicts, test-plan, verification).
3. Save the JSON to `loop/runs/<unit id>/<stage>.draft.json` and gate it:
   `python -m scripts.srdloop accept <stage> <unit id> loop/runs/<unit id>/<stage>.draft.json`.
4. On FAIL, give the agent the listed problems and try once more; on a second FAIL, stop and
   show the user the problems.

After D passes: `python -m scripts.srdloop finish <unit id>`. The harness removes refuted
tests, opens tickets for red tests and missing capabilities, and commits the unit. Report the
unit's status, its tests (by kind), the tickets, and any proposed rulings, quoting the
harness output rather than re-summarising the agents.

Invariants:
- The test designer writes only `tests/srd/**`, `tests/scenarios/**` (on a stage B verdict),
  `tests/support/**` and the notes files. It never edits `dungdra/`.
- Never edit an expected value to make a test pass, and never delete a test; the harness
  removes refuted ones.
- A proposed ruling is only a proposal: tell the user, who accepts or rejects it.
