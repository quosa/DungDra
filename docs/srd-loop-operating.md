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
3. The `fix-reviewer` approves or rejects the change.
4. If approved, the harness removes the ticket's xfail marks and commits.

A failed attempt is stashed and recorded. After three failed attempts the ticket is `stuck`.

Units are not re-queued when code changes, only when their SRD text or scope does. A fixed infra
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
- **Budget:** `--budget` is a cap per run in USD; whatever isn't used isn't spent. Exit 4 means
  paused (budget, usage limit or a transient error); the same command resumes, including a
  half-done retry.
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
| 3 | Stopped by a circuit breaker: the suite was red before starting; more than 15 open tickets ("run the dev loop first"); or 3 units in a row failed their gates (`incomplete`) |
| 4 | Paused; run the same command again |

## What only a person decides

| Decision | How |
|---|---|
| A ruling proposal P-n | `ruling accept P-n --note "…"` adds the next R-nn to the README register and updates the markers. `ruling reject P-n --reason "…"` re-queues the unit from stage C with your reason, and the tickets that depended on the proposal become void. While a proposal is pending, its unit is `blocked` and the dev loop skips tickets whose tests depend on it |
| A dispute (the fixer thinks a test or scenario is wrong) | Read the ticket's `why:` and `loop/requests/`. Change the test yourself or reject the dispute, `ticket reopen T-n --reason "…"`, then bring the stashed code back (below) |
| A `stuck` ticket | Read `loop/runs/T-n/fix.attempt*.json`. Then do one of these: `ticket cap T-n 9` (a bigger fixer budget) and `ticket reopen T-n --reason "…"`; `ticket void T-n --reason "…"`; or fix it yourself and `dev --recheck T-n` |
| Waiving a check for one ticket | `ticket waive T-n diff_coverage --reason "…"` (only `diff_coverage` can be waived) |
| A test the verifier doubted ("Tests to review" in `loop/COVERAGE.md`) | `review list` numbers them; then `review keep 1 3 --reason "…"` or `review remove 2 --reason "…"` (numbers or node ids; one commit; the harness removes the tests). Evidence: `mutate dungdra/<file> <line> <old> <new> <node id>` shows whether the test catches a broken engine |
| Removing or weakening any other acceptance test | By hand, in a commit of its own |
| Changing a golden scenario | By hand, together with `docs/dnd-golden-scenarios-srd521.md` |
| Which infra tickets to build | They are large engine features (geometry, awareness, surfaces); pick them deliberately (see open questions) |
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
| `loop/tickets/T-n.json` | Kinds bug, infra, refactor, coverage; statuses open, fixed, stuck, dispute, void |
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

## State as of 2026-10-01

**Trial run** (8 units, before tagging `loop-v1`):
- **Done:**
  - `GLOSS.grappled`: green, after T-1…T-4.
  - `GLOSS.tremorsense`: red; infra T-12…T-14 are open.
  - `PLAY.combat.cover`: red; T-16 is fixed, T-15 and infra T-17/T-19 are open.
  - `SPELL.bless`: red; bugs T-20…T-23.
- **Rulings:** R-05…R-14 accepted; none pending.
- **Still to run:**
  - `GLOSS.ready`: a canary; the engine is known to lack this capability, and the loop should
    find that by itself.
  - `SPELL.casting-spells.effects.targets`.
  - `MONSTER.goblins.goblin-warrior`.
  - `GLOSS.prone`.
  - The `GLOSS.grappled` revisit.

The suite: 501 passed, 7 xfailed.

**Before resuming:** 16 tickets are open, so the audit loop stops at once (more than 15). Run
the dev loop on the bugs first:

```
python -m scripts.srdloop dev --budget 15 --tickets T-15 T-20 T-21 T-22 T-23
```

Then resume:

```
python -m scripts.srdloop run --budget 20 --units GLOSS.ready SPELL.casting-spells.effects.targets MONSTER.goblins.goblin-warrior GLOSS.prone GLOSS.grappled
```

**Open questions for the person:**
- **Infra approval:** should infra tickets start as `proposed` and wait for an approval before
  the dev loop builds them? Should the circuit breaker count only open bugs? Without this the
  dev loop will start building geometry and awareness models depth-first.
- **Tests to review:** the four Cover tests the verifier doubted were written before T-16. Each
  now fails when creature cover is broken (checked with `mutate`), so they can be kept.
- **Edits during a run:** a person's edit made during a run is still treated as the agent's.
  The plan is to snapshot the dirty files at start and leave later non-agent edits alone, or
  just keep the rule "don't edit during a run".

**Tagging `loop-v1`:** every path has run for real, the last 4–5 units ran without harness
changes, and cost stays within the estimate.
