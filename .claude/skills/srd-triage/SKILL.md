---
name: srd-triage
description: After an SRD loop run (audit or dev), gather everything that waits for a person (ruling proposals, tests to review, incomplete units, new and stuck tickets, set-aside stashes) into one decision sheet with context, a recommendation and the exact command for each item. Read-only; the person runs the commands. Use when asked to triage, review or "look at" a loop run, e.g. "/srd-triage" or "/srd-triage since c8dc8e3".
---

# Triage a loop run

The person runs the loop by hand (`python -m scripts.srdloop run|dev …`). Your job is the
chain of checks after it: find each item that needs a person, work out what it means, recommend
a decision and write the command for it. The person decides; you never do.

Argument (optional): `since <ref>`, the commit before the run. Without it, take the commits
since the last commit that isn't the loop's own (`srd:`, `dev:`, `fix:`, `ticket:`, `ruling:`,
`review:`), and say which range you used.

## Ground rules

- **Read-only.** Never run `ruling accept|reject`, `review keep|remove`, `ticket void|reopen|cap|waive`,
  `git stash drop`, or anything else that decides or commits, unless the person says so for that
  item. Running tests, `--runxfail`, `related`, `mutate` and `dev-gate` is fine.
- **A run may be going.** Check `pgrep -fl "scripts.srdloop (run|dev)"`. While one runs, write
  nothing in the repo except the sheet (its folder is gitignored, so the zone check ignores it).
- Only the person adds register rows, edits acceptance tests or changes the harness. You may
  recommend any of these; for a hand edit of a test or the harness, describe the change and
  offer to make it after the run, in a commit of its own.
- Quote the SRD from `docs/srd/units.jsonl` only. Cite tests and code as `path:line`.

## 1. Gather

```
python -m scripts.srdloop status          # the "Waiting for you" list is the checklist
git log --format='%h %ad %s' --date=format:%H:%M <range>
python -m scripts.srdloop ruling list
python -m scripts.srdloop review list
python -m scripts.srdloop ticket list
git stash list
```

Run cost: sum `cost_usd` in `loop/costs.jsonl` for the run's units and tickets, and compare it
with the table in `docs/srd-loop-operating.md` (≈ $1.30 a glossary entry, ≈ $3 a bigger unit,
≈ $1 a bug fix).

## 2. Work out each item

**Ruling proposal `P-n`** (`loop/rulings/P-n.json`):
- Read the ambiguity, the proposed reading, the unit's text and the tests that depend on it.
- Look for conflicts: a register row (`README.md`, R-nn) that says otherwise, or a ticket or test
  that already asserts the opposite (`grep` tests/srd and `loop/tickets` for the same spell,
  condition or behaviour). A proposal worded more broadly than the tests need is a conflict too.
- Say what accepting costs: which tickets it unblocks (`status` lists the tickets waiting on a
  ruling) and whether they turn from bug fixes into larger engine work.
- Recommend accept, accept with a narrowing note, or reject with a reason that tells stage C which
  reading to write instead. Use these lenses, which settled earlier rulings, and name the one you use:
  1. Follow the SRD's literal words where they settle it.
  2. The engine never leaks hidden information (a refusal must not reveal what the player can't know).
  3. One mechanism, not two (prefer the reading that extends an existing rule path).
  4. Check a declaration when it is made, before resources are spent.
  5. Agree with the existing register and with the tests already accepted.
  These guide your recommendation; they are not rulings.

**Test to review** (`review list`): read the test and stage D's reason
(`loop/runs/<unit>/D.json`). Check that it fails for the right reason (`--runxfail` on an xfail),
that its preconditions are true in the fixtures, that it checks intermediate steps and not only the
end state, and that every queued answer and forced die is used. If in doubt, show evidence with
`python -m scripts.srdloop mutate <file> <line> <old> <new> <node id>`. Recommend keep, remove, or
keep after strengthening (write the stronger version out).

**Incomplete unit** (`loop/state/<unit>.json` → `problems`; each attempt in
`loop/runs/<unit>/<stage>.attempt<n>.json`). Compare the attempts:
- The same gate failure on both attempts, or a rejected quote that exists elsewhere in the same
  document → probably a **harness gap**. Find the gate in `scripts/srdloop/` and propose the fix
  plus a bad-agent test (`tests/unit/test_srdloop_adversarial.py`). Re-running before the fix
  wastes the money.
- Different, real mistakes (missing kinds, missing markers, invented quotes) → the **agent's**;
  recommend a re-run (`run --budget <n> --units <unit>`; an incomplete unit re-queues itself).
- A set-aside attempt is in `git stash list` (`srdloop: <unit> incomplete at stage <X>`).

**New tickets**: one line each. A bug ticket with more than about five tests, or one that says a
command or action doesn't exist, is a feature: flag it so it is kept out of `dev` runs and planned
deliberately. A ticket whose tests depend on a pending ruling waits for it.

**Stuck or disputed ticket**: summarise `loop/runs/<T-n>/fix.attempt*.json` (what the fixer
tried, why the gate or reviewer refused) and recommend `ticket cap` + `reopen`, `void`, a test
change, or fixing it by hand followed by `dev --recheck`.

**Housekeeping**: a set-aside stash whose unit or ticket has since succeeded is safe to drop; a
unit whose bug tickets are all fixed but whose state still says red is stale (note it, no command).

## 3. Write the sheet

Write `loop/triage/<YYYY-MM-DD-HHMM>.md`:

```
# Triage <date>: <range>, <n> units, $<cost>

## Summary
<3-5 lines: what the run found, what blocks what, the one decision that matters most>

## Decisions
### P-11 · <one-line ambiguity>            ← unblocking items first: rulings, then reviews
<context: SRD quote, the tests, conflicts, cost of accepting>
**Recommend:** accept with note. <one-line reason, naming the lens>
    python -m scripts.srdloop ruling accept P-11 --note "…"

### <unit> · incomplete at stage B
…

## Tickets
<table: id, kind, one line, ready / waits for P-n / feature: keep out of dev>

## Next commands
<every recommended command in the order to run them: decisions, then dev on the ready bugs
(always with --tickets), then re-runs; then the stashes that are safe to drop>
```

Keep each item short: a tired reader should be able to agree or disagree without opening a file.

## 4. Report

In chat: the summary, the path of the sheet, and the items where your recommendation is least
certain. Then wait. When the person says "do it" for some items, run exactly those commands
and report what each one committed.
