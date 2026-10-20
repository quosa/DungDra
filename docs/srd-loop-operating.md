# Operating the SRD rule loop

How to run, steer and debug the loop. `docs/srd-loop-overview.pdf` shows it on one page
(rebuild it with `python -m scripts.docs.loop_overview`). Its design and rationale are in
`docs/srd-rule-loop-plan.md`, and `docs/srd-commands.md` has command notes. Read this before
running the loop or changing the harness (`scripts/srdloop/`, `.claude/agents/`, `loop/`).

## What it does

The **audit loop** works through the SRD one rule unit at a time (`docs/srd/units.jsonl`),
breadth-first, dependencies first. Each unit goes through four stages, each a fresh headless
`claude -p` run:

| Stage | Agent | Output |
|---|---|---|
| A | `rule-analyst` (Opus, no tools) | Clauses (numbered `<unit>#<n>`), relations, ambiguities |
| B | `scenario-auditor` (Sonnet, read-only) | A verdict on each existing scenario, test and code site |
| C | `test-designer` (Opus) | Tests in `tests/srd/`: positive, negative, boundary, abuse, journeys |
| D | `test-verifier` (Opus) | Tries to refute each test, including by mutating the engine |

Mechanical gates check each stage's output: verbatim quotes, clause×kind coverage, markers,
write zones, append-only, claimed outcomes and lint. Only output that passes is checkpointed.
At the end of a unit, the harness takes these steps:
- removes tests refuted with confidence ≥ 0.5;
- opens a **bug** ticket for each red test (`xfail(strict=True, reason="T-<n>: …")`);
- opens an **infra** ticket for each capability the engine is missing;
- files a **ruling proposal** P-n for each ambiguity a test depends on;
- commits.

The **dev loop** is separate. It takes one open ticket at a time:
1. The `fixer` writes code and unit tests.
2. The quality checks run: ruff, no suppressions, the coverage ratchet and ≥ 90% diff coverage,
   import layers, duplication, dead code, and the full suite.
3. The `fix-reviewer` approves or rejects the change. A problem in the diff, or a ticket whose
   own problem isn't solved, is a rejection: the boy scout rule happens inside the fix.
4. If approved, the harness removes the ticket's xfail marks and commits.

The reviewer may file **one follow-up** per bug or infra fix (none for a refactor or coverage
fix), only for a problem outside the diff that could lead to a wrong rule result. Follow-ups are
**parked**: the dev loop takes a parked ticket only when it is named (`dev --tickets T-n`), so
they are a menu to choose from, not the loop's to-do list. `ticket park T-n --reason "…"` parks
an open ticket, and `ticket reopen` puts a parked one back on the list.

A failed attempt is stashed and recorded. After three failed attempts the ticket is `stuck`.

Units are not re-queued when code changes, only when their SRD text or scope does. An `incomplete`
unit resumes at the stage that failed (a resume at D first brings back C's set-aside test files;
if they're gone, C runs again). A fixed infra
ticket marks the unit that opened it for a **revisit**, queued last and starting at stage C.

## A session, step by step

`python -m scripts.srdloop --help` lists every command; `<command> --help` gives its details
(`ticket --help`, `ticket create --help`).

```
python -m scripts.srdloop status                    # units, ticket backlog, what waits for you
python -m scripts.srdloop run --budget 20 [--units ID ...]   # audit loop
python -m scripts.srdloop ruling list              # proposals to decide (below)
python -m scripts.srdloop ticket list              # what the units found (--all: fixed too)
python -m scripts.srdloop dev --budget 15 [--tickets T-n ...] # dev loop
python -m scripts.srdloop report                    # loop/COVERAGE.md
```

- **Before a run:** commit your own work. `preflight` refuses to start on a tree with changes
  that belong to no agent zone. Don't edit the working tree while a run is going: the zone check
  counts your files as the agent's, fails the attempt and stashes your edit with it.
- **Failed calls:** an agent call that exits non-zero never counts as a result. If it cost
  nothing or names a limit (usage, rate, overload), the run pauses (exit 4) instead of spending an
  attempt; the attempt record keeps the CLI's exit code, subtype and message (`error`). A call
  that runs 60 minutes is stopped and the run pauses.
- **Budget:** `--budget` is a cap per run in USD; whatever isn't used isn't spent. Exit 4 means
  paused (budget, usage limit or a transient error); the same command resumes, including a
  half-done retry. Each run's budget starts at $0. A budget pause prints a hint: run the same command again, or a
  `--budget` big enough for the next call (a ticket's `ticket cap` is that call's worst case, not its cost).
- **Login:** the loop runs on the claude.ai login, so `cost_usd` in `loop/costs.jsonl` is
  Claude Code's estimate, not a bill.

Typical cost from the trial:

| Item | Cost |
|---|---|
| Glossary entry | ≈ $1.30 |
| Bigger unit (Cover, Bless) | ≈ $2.70–3.00 |
| Bug fix with review | ≈ $1 |
| Review alone | ≈ $0.20 |
| A large infra change (T-9, traceability) | ≈ $11.60 |

The plan's estimate is ≈ $5.40 per unit, so far an overestimate.

## Exit codes and circuit breakers

| Exit | Meaning |
|---|---|
| 0 | Done, or nothing left in the queue or the ticket list |
| 1 | `dev --recheck`: the ticket wasn't fixed |
| 2 | `docs/srd/units.jsonl` doesn't match its approved hash |
| 3 | Stopped by a circuit breaker: the suite was red before starting; more than 15 open **bugs** ("run the dev loop first"; infra, refactor and coverage tickets don't count); or 3 units in a row failed their gates (`incomplete`) |
| 4 | Paused; run the same command again |

## What only a person decides

| Decision | How |
|---|---|
| A ruling proposal P-n | `ruling accept P-n --note "…"` adds the next R-nn to the README register and updates the markers. `ruling reject P-n --reason "…"` re-queues the unit from stage C with your reason, and the tickets that depended on the proposal become void. While a proposal is pending, its unit is `blocked` and the dev loop skips tickets whose tests depend on it |
| A dispute (the fixer thinks a test or scenario is wrong) | Read the ticket's `why:` and `loop/requests/`. Change the test yourself or reject the dispute, `ticket reopen T-n --reason "…"`, then bring the stashed code back (below) or let the fixer redo it. The fixer and the reviewer see every reopen reason, and it overrides the ticket's title where the two differ |
| A `stuck` ticket | Read `loop/runs/T-n/fix.attempt*.json`. Then do one of these: `ticket cap T-n 9` (a bigger fixer budget) and `ticket reopen T-n --reason "…"`; `ticket void T-n --reason "…"`; or fix it yourself and `dev --recheck T-n` |
| Waiving a check for one ticket | `ticket waive T-n diff_coverage --reason "…"` (only `diff_coverage` can be waived) |
| A test the verifier doubted ("Tests to review" in `loop/COVERAGE.md`) | `review list` numbers them; then `review keep 1 3 --reason "…"` or `review remove 2 --reason "…"` (numbers or node ids; one commit; the harness removes the tests). Evidence: `mutate dungdra/<file> <line> <old> <new> <node id>` shows whether the test catches a broken engine |
| Removing or weakening any other acceptance test | By hand, in a commit of its own |
| Changing a golden scenario | By hand, together with `docs/dnd-golden-scenarios-srd521.md` |
| Which infra tickets to build | They are large engine features (geometry, awareness, surfaces); pick them deliberately. Park the ones you won't build soon (`ticket park`), and name the ones you will (`dev --tickets`). `/srd-triage` helps choose |
| Re-extracting or approving the SRD text | `python scripts/srd/extract.py`, review, `--approve` |

## Investigating a ticket

The dev loop prints the result, the reason, the first problems, where the code went and the
attempt record. To dig deeper:

```
python -m scripts.srdloop ticket show T-16     # status, tests, history, each attempt
cat loop/runs/T-16/fix.attempt1.json            # fixer + reviewer output in full
git stash list                                  # "srdloop: T-16 dispute", "… attempt 2"
git stash show -p --include-untracked 'stash@{0}'   # the code that was set aside
ls loop/requests/                               # the fixer's notes for a person
grep '"T-16"' loop/costs.jsonl                  # every agent call, with its cost
python -m pytest <node id> --runxfail -q        # what the red test says today
```

Headless sessions aren't persisted (`--no-session-persistence`), so the JSON outputs above are
the record. Each audit stage keeps `loop/runs/<unit>/<stage>.attempt<n>.json` the same way.

**Bringing set-aside code back** (after a dispute, or to finish a fix by hand):

```
git stash pop 'stash@{0}'          # restore the fixer's work
# edit as needed, make the ticket's tests pass with --runxfail
python -m scripts.srdloop dev-gate # the same checks the loop runs; free
python -m scripts.srdloop dev --recheck T-16 --budget 4   # checks, review, commit (no fixer)
```

The harness itself removes the xfail marks. Leave them in when you recheck; if a stash carries a
test file with its mark already removed, `git checkout` that file first.

Example, T-16 in the trial:
1. The fixer made creatures give Half Cover on attacks. It saw that doing the same for saves
   would break SPL-05, so it disputed instead of changing the scenario.
2. A person agreed the scenario was wrong, rewrote SPL-05 and added it to T-16.
3. The person popped the stash, extended the change to saves, and ran `--recheck`, which
   committed the fix.

## Where things live

| Path | Content |
|---|---|
| `loop/state/<unit>.json` | A unit's stages, status, tests, tickets, relations, for_review, out_of_scope |
| `loop/runs/<unit>/` | Stage checkpoints `A.json`…`D.json`, `<stage>.attempt<n>.json`, `<stage>.pending.json` |
| `loop/runs/<T-n>/` | `fix.attempt<n>.json` per dev-loop attempt |
| `loop/tickets/T-n.json` | Kinds bug, infra, refactor, coverage; statuses open, parked, fixed, stuck, dispute, void |
| `loop/rulings/P-n.json` | Proposals; the accepted ones are rows R-nn in `README.md` |
| `loop/requests/` | The fixer's notes to a person (disputes, test-change requests) |
| `loop/costs.jsonl` | One line per agent call |
| `loop/COVERAGE.md` | `report`: states per chapter, queue, rulings waiting, tests to review, tickets waiting, out of scope |
| `loop/quality-baseline.json` | The ratchet (unit coverage %, duplication, dead code) |
| `loop/abuse-catalogue.md` | Abuse cases the designer reuses across units |
| `loop/queue.json` | `plan` output (gitignored) |
| `scripts/srdloop/settings.json` | Agents' permissions, sandbox, write-guard hook |
| `scripts/srdloop/schemas/` | Each stage's JSON output schema |
| `.claude/agents/*.md` | Each role's system prompt |
| `.claude/skills/srd-rule`, `srd-ticket` | Run a stage or a ticket interactively with the same gates |

## Changing the harness

- Tests:
  - `tests/unit/test_srdloop_core.py`: units, graph, plan.
  - `test_srdloop_gates.py`.
  - `test_srdloop_runtime.py`: runner, tickets, dev loop, report.
  - `test_srdloop_rulings.py`.
  - `test_srdloop_adversarial.py`: one bad-agent case per gate.
- Every gap found in a real run gets a test that fails without the fix. A bad-agent case belongs
  in the adversarial file.
- Run the full suite, `ruff check .`, `ruff format --check .` and `dev-gate` before committing.
  A harness change doesn't re-queue units.
- **Agents read the top-level `CLAUDE.md`** (`--setting-sources project`). Keep it to rules that
  hold for every role. Operator material goes here, not there and not in `loop/CLAUDE.md`, which
  would load for any agent reading `loop/`.
- The guard hook (`hooks/guard_writes.py`) enforces write zones only when `SRDLOOP_ROLE` is set,
  so interactive sessions aren't affected.

## State as of 2026-10-20 (`loop-v1`)

**The trial is over.** Every path has run for real: audit stages A–D, the dev loop, rulings,
reviews, disputes, parked follow-ups, pauses on budget and usage limits, resumes of failed units,
and revisits after an infra fix. The last five units (Cylinder, Emanation, Line, Ally, Creature
Type) ran with no harness change, at ≈ $1.23 a unit.

- **Audited:** 17 units. Green or red only on fixed bugs: Grappled, Tremorsense, Cover, Bless,
  Ready, Targets, the Goblin Warrior, Prone, Cone, Cube, Sphere, Area of Effect, Ally, Creature
  Type. Out of scope (no in-scope content uses them): Cylinder, Emanation, Line. `status` still
  calls some units red after their last bug is fixed: the dev loop doesn't update a unit's status.
- **Rulings:** R-05…R-39 in the README register (R-35 decided by hand for T-79).
- **Tickets:** 0 open, 15 parked. The suite: 1093 passed. The last dev round (6 bugs from Ally and
  Creature Type, $2.64) filed one parked follow-up, T-93: the ally rule is still decided by team
  equality in a few places beside `Game.is_ally`.
- **Features built along the way:** the Ready action (T-41), area targeting from positions with
  `point=` (T-56, T-59, T-19, T-57, T-58), cover from a point of origin.
- **Parked (the feature menu):** T-93 (the ally rule in one place) is small and worth building
  soon; obstacle geometry (T-17, T-84), area choices (T-67, T-78), senses and surfaces
  (T-12–T-14), in the air (T-8), creature spaces (T-46), GM tools (T-76, T-90), and odds and
  ends (T-42, T-47, T-63). `/srd-triage` groups and ranks them.

**How a session goes now:**
1. `srdloop run --budget <n> --units …` (or without `--units` for the queue's order).
2. `/srd-triage`: one sheet in `loop/triage/` with every decision, a recommendation and the
   command for it.
3. Decide the rulings and reviews, then `srdloop dev --budget <n> --tickets <the ready bugs>`.
   Always name the tickets: open infra tickets would otherwise be built too.

**Harness changes since the trial** (each with tests in `tests/unit/test_srdloop_*.py`):
- Scenario evidence may quote the shared fixtures; assertion helpers must be named `assert_*`.
- Follow-ups are parked, at most one per bug or infra fix, none for refactor or coverage fixes; the
  reviewer rejects problems in the diff and unsolved tickets instead of filing them.
- The breaker counts open bugs only.
- A stat value's negative or boundary test may be waived with a reason (`kind_waivers`).
- A person's reopen reasons reach the fixer and the reviewer; the fixer disputes a fix that needs an
  unruled reading.
- A budget pause says how to resume; a failed call never counts as a result; a call that didn't
  run (cost 0, or a usage/session limit) pauses; one call may run 60 minutes.
- A failed unit resumes at its failed stage; a revisit counts the unit's committed tests.

**Open questions for the person:**
- **Infra from the audit loop** still starts open. Park what you won't build soon.
- **Edits during a run** are still treated as the agent's: don't edit while a run is going.
- **Stale unit status** (above): a small harness fix, not done yet.
- **`ticket reopen` on a fixed ticket** is allowed (T-79 was reopened twice by accident); a guard is
  proposed, not done yet.
