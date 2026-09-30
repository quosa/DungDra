---
name: srd-ticket
description: Work one SRD loop ticket (a red SRD test, a missing engine capability, a refactor) interactively with the loop's fixer and reviewer and the same gates as the headless dev loop. Use when asked to fix a loop ticket, e.g. "/srd-ticket T-3".
---

# One loop ticket, interactively

The headless dev loop is `python -m scripts.srdloop dev --budget <USD> --tickets <T-n>`. This
skill does the same in the current session.

1. Read the ticket: `loop/tickets/<T-n>.json` (`python -m scripts.srdloop tickets` lists them).
   Run its tests to see the failures: `python -m pytest <node ids> -q --runxfail`.
2. Delegate the fix to the `fixer` agent with the ticket, the failing output, and the rule
   unit's text (`python -m scripts.srdloop related <unit>` and `docs/srd/srd.md`). The fixer
   writes `dungdra/**` and `tests/unit/**` only.
3. If the fixer disputes the test or asks for a test change, stop and ask the user.
4. Remove the xfail markers naming the ticket from its tests, then check:
   - the ticket's tests pass: `python -m pytest <node ids> -q`;
   - nothing else broke: `python -m pytest -q`;
   - `python -m scripts.srdloop dev-gate` passes.
   On a failure, give the fixer the problems (at most three attempts in all), or restore the
   markers and stop.
5. Delegate a review of `git diff HEAD` to the `fix-reviewer` agent. On reject, back to step 2.
6. Show the user the diff summary, the gate output and the review. Commit only when the user
   says so, with the ticket id in the message, and set the ticket's status to "fixed".
