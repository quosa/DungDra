# SRD rule-by-rule audit + test loop for DungDra

## Context

The cc1 loop built DungDra scenario by scenario. The retrospective (`docs/cc1-loop-retrospective.md`) lists what went wrong:
- rules without a scenario were silently skipped (the Ready action, l.32);
- one agent built the code, wrote the tests and judged the result, so the loop overfit (l.45–47);
- increments were too big to bisect (l.48);
- assertions were edited without a note (l.59);
- progress was reported as "N tests pass" (l.29).

The `docs/loop-example/rulebook-audit` skeleton fixes most of these. It uses fresh-context agents with restricted tools, deterministic gates, verbatim evidence, an adversarial verifier, coverage gates and hooks. But it only audits.

**Goal:** adapt that skeleton so it walks the SRD 5.2.1 **one rule unit at a time**, and for each unit:
1. works out what it depends on and how it relates to other rules;
2. finds its ambiguities;
3. re-validates the existing scenarios and tests that touch it;
4. designs and writes as many tests for untested interactions and abuse cases as it can.

Failing tests go to a **separate** dev loop. That loop also keeps unit-test coverage high and the architecture clean and orthogonal. The whole thing must be resumable, including after the budget runs out. Parallel worktrees come later.

**Litmus test.** The loop must rediscover the known missing implementations and bugs, then fix them.

## Decisions (confirmed with user)

- **Dev loop:** auto-commits one ticket per commit on a loop branch. The user reviews the branch.
- **Scope:** core rules first (Glossary, Playing the Game, Toolbox), then implemented content. Unimplemented content only gets a refusal check and a `needs-content` row.
- **Rulings:** agents only *propose* rulings. Dependent tests stay `blocked` until the user accepts one.
- **Tooling is Python-only.** A dedicated virtualenv for DungDra; every dependency is listed in `pyproject.toml`. The orchestrator and hooks are Python too, not bash + jq. This also removes the example's GNU-only commands (`realpath -m`, `sha256sum`, `xargs -d`), which fail on macOS.
- **Two kinds of test, with different owners:**
  - **Unit tests**, written and maintained by the dev loop under a coverage ratchet.
  - **SRD rule / scenario / journey suites**, written only by the test-designer. The dev loop can't delete or weaken these without human approval.
- **Rule→code tracing:** greppable `SRD[...]` tags plus a `rule=` id on runtime events, not decorators.
- **Sandboxing:** a layered setup from the console for now; a container later, which is additive.

## Facts the design rests on

- **SRD PDF.** 364 pages, two columns. Heading levels can be told apart by font:

  | Font / size | Role |
  |---|---|
  | GillSans-SemiBold 26pt | chapter |
  | 18pt | section |
  | 14pt | subsection |
  | 12pt | entry |
  | Helvetica | body text |

  Rough unit counts:

  | Part | Pages | Units |
  |---|---|---|
  | Rules Glossary | 176–191 | 155 entries, 41 of them tagged |
  | Playing the Game | 5–18 | 38 subsections |
  | Gameplay Toolbox | 192–203 | about 30 |
- **Scenarios.** They live only in `docs/dnd-golden-scenarios-srd521.md`, as `#### ID · title` blocks with `Tests: ... p.N`, `Depends on`, forced-dice `Setup` and `[H]`/`[S]` bullets. Tests are tied to them only by name (`test_core02a_...`).
- **No rule→code map exists.** Traceability comes only from `page=` on `Event`/`Refusal` (422 uses) and `p.N` comments (159).
- **Registers.** Rulings R-01..R-04 (spec §1.3 and README). Scenario deviations in `docs/scenario-notes.md`.
- **Reusable test primitives:**
  - `game.dice.force_str()` and `game.dice.pending()` (`dungdra/dice.py:23-41`)
  - `game.answer()` (`dungdra/game.py:67`)
  - `pc()` and `mon()` (`tests/helpers.py`)
  - the fixtures in `dungdra/fixtures.py`
  - `game.log.*` (`dungdra/events.py:55-76`) and `Event(kind, text, visibility, page, ruling, data)` (`events.py:16-37`)
  - `pytest.raises(Refusal)`
  - `Play.say`, `session.execute`, `audit.reconcile` and `snapshot()`
- **Current suite.**
  - 150 tests, all scenario or journey tests, in flat `tests/test_*.py`. No real unit tests. Runs in under 1 s.
  - `pyproject.toml` declares no dependencies at all.
  - Plain `pytest` is broken in the current global environment because another project's `tests` package shadows this one. A fresh venv avoids that.
- **Lint baseline** (read-only run today):
  - Default `ruff`: 121 errors (F401 44, E741 33, E702 21, F841 14, F541 8, E731 1).
  - With `E,F,W,I,B,UP,SIM,C90` at line length 88: 1,543 errors. Of those, 1,339 are E501 and 30 are C901.
  - 3 existing `noqa` / `type: ignore` / `pragma` suppressions.
  - About 10k lines in `dungdra/`.
- **Claude Code facts that matter here.**
  - `claude -p` supports `--json-schema`, `--max-budget-usd`, `--output-format json` (gives `total_cost_usd` and `session_id`), `--resume <id>` and `--permission-mode dontAsk`.
  - **`--bare` skips hooks**, so the loop must not use it.
  - The built-in sandbox (`sandbox.enabled`, macOS Seatbelt) restricts **Bash and its child processes only**, for both filesystem and network. It does not cover Write/Edit.
- **Canaries the loop must rediscover** (`docs/cc1_architecture_review.md`):
  - the Ready action is missing;
  - casting spends the slot before its targets are validated (`spells.py:114-135`);
  - Hide always gets ¾ cover;
  - Shield and Opportunity Attacks use blocking-callback choices, so they can't be tested;
  - there is no map, so "move through walls" can't even be refused.

## Environment and dependencies

The user creates the venv (e.g. pyenv `dungdra`, Python 3.12) and runs `pip install -e ".[dev,srd]"`. `pyproject.toml` lists everything:

```toml
[project.optional-dependencies]
srd = ["pdfplumber>=0.11"]            # SRD extraction (MIT; per-char fontname/size)
dev = [
  "pytest>=8", "pytest-cov>=6", "hypothesis>=6",   # tests, coverage, property/abuse fuzzing
  "ruff>=0.14",                                     # lint + format, zero-violation policy
  "import-linter>=2",                               # layering contracts
  "pylint>=3",                                      # ONLY duplicate-code (R0801, symilar engine)
  "vulture>=2.11",                                  # dead code after refactors
  "mutmut>=3",                                      # mutation testing: anti "tests that assert nothing"
]
```

The engine keeps zero runtime dependencies. `claude` (Claude Code CLI) and `git` are the only non-Python tools. `tests/__init__.py` and the `__init__.py` files in each suite are needed because the suites reuse file basenames (e.g. `test_combat.py`).

## Sandboxing: enough for console runs now, container later

Running the loop from your console is fine for the pilot and for supervised runs, provided these layers are all in place. The loop still runs as you, so a container comes later, when it runs unattended for long stretches or in parallel. That step is additive: the orchestrator needs only `python`, `git` and `claude`.

1. **Claude Code sandbox for Bash.** Set `sandbox.enabled: true` in `.claude/settings.json`.
   - Filesystem writes are allowed only in the repo or worktree and the scratch directory.
   - **No network:** pytest, ruff and mutmut need none.
   - This matters most because the agents run `pytest` on code they wrote themselves. The sandbox confines that code, and any subprocess it spawns, at the OS level.
2. **Per-call tool scoping.** The orchestrator passes each role its own allowlist:
   - `--allowedTools "Write(tests/srd/**)" "Edit(tests/srd/**)" "Bash(pytest:*)"` and so on;
   - `--permission-mode dontAsk`, so anything not allowed is denied, not prompted.
   - It never uses `bypassPermissions`, `--dangerously-skip-permissions` or `--bare`.
3. **PreToolUse guard hook** (`.claude/hooks/guard_writes.py`). Role-based write zones as a second layer, because the OS sandbox doesn't cover Write/Edit.
4. **Deny rules** in `settings.json`: `git push`, `git reset --hard`, `rm -rf`, `curl`/`wget`, and reads of `.env*` and `~/.ssh`.
5. **Git as the undo button.**
   - The loop runs on a dedicated branch.
   - It refuses to start on a dirty tree.
   - It commits per unit (audit loop) and per ticket (dev loop).
   - The harness, not an agent, does all commits.

**Residual risk in console mode.** Write/Edit are limited by hooks and permissions, not by the OS. Agent-written test code can do damage only inside the allowed write paths. An API key (not a subscription login) is recommended so `total_cost_usd` maps to real spend.

## Test layout and ownership

The existing tests move once, in groundwork, with no assertion changes:

| Suite | Path | Purpose | Writer |
|---|---|---|---|
| **Unit** | `tests/unit/test_<module>.py` | Per-component behaviour of `dungdra/*`. Fast and isolated. | **Dev loop** (fixer, unit-test writer) |
| **Support** | `tests/support/` (helpers, scripted player agent, NL conversations) | Shared builders used by the scenario and SRD suites | **test-designer** |
| **Scenario** | `tests/scenarios/` (today's `test_*.py`) | Golden scenarios, journeys J1–J6 | **test-designer**, only on a scenario-auditor verdict, with a `scenario-notes.md` row |
| **SRD rule** | `tests/srd/test_<chapter>.py` | Per-clause rule, interaction and abuse tests, `@pytest.mark.srd("<unit-id>", clause=..., kind=positive\|negative\|boundary\|abuse)` | **test-designer** |
| **SRD journeys** | `tests/srd/journeys/test_<topic>.py` | Long multi-step chains ("if this, and this, and that, then…") through `Play.say` / `Session.execute`, with checkpoint assertions after each step | **test-designer** |

**Enforcement.** Write zones are enforced by per-role `--allowedTools`, the guard hook, and a `git diff` check in the harness.

**Acceptance tests are append-only.** For `tests/srd/**` and `tests/scenarios/**`, the gate compares the set of collected test ids and the per-test assertion count (by AST) against HEAD. Any removal, skip or xfail without a ticket, or reduction in assertions fails the gate. The only exceptions are:
- the test-designer acting on a logged scenario verdict;
- a **human-approved test-change request.** During a major refactor, the fixer files `loop/requests/<ticket>.md` listing the test ids, the reason, and the proposed replacements. That ticket pauses (others continue). The user approves it (hash-pinned in `loop/approvals/`). The **test-designer**, not the fixer, then migrates the tests.

**Unit tests** can be rewritten or deleted by the dev loop, as long as the coverage and mutation ratchets hold.

## Rule→code tracing: tags + runtime ids, not decorators

- **Why not decorators.** Rules usually live in *branches*, not whole functions, and one function often applies several rules. A decorator would say "rule applied" even when the branch wasn't taken. It would also couple the engine to the loop's tooling.
- **Static: greppable tags.** A comment at each implementation site, in the form `# SRD[GLOSS.grappled#2]` or `# SRD[PLAY.combat.oa]` (unit id plus optional clause). `rg 'SRD\[GLOSS\.grappled'` finds every site.
- **Runtime: rule ids on events.** Extend `Event` and `Refusal` with `rule="<unit-id>#clause"`, next to the existing `page=`.
  - Tests can then assert that *this rule* was applied, which is stronger than matching log text.
  - A small pytest plugin in `tests/conftest.py` records which rule ids fired in each test.
- **`srdloop.py map`** combines tags, fired rule ids and `srd` markers into `loop/RULEMAP.md`: unit → code sites → tests that assert it → tests in which it actually fired.
- **Gates:**
  - every `SRD[...]` tag and `rule=` id must exist in `units.jsonl`, so there are no stale tags;
  - a dev-loop fix must tag the code it adds for the ticket's unit.
- **Migration.** Moving existing `page=` uses to `rule=` is a gradual `refactor` ticket. Until then `srdloop.py related` also uses page hits.

## Architecture

```
SRD PDF ─ extract.py (pdfplumber) ─► docs/srd/units.jsonl ─ check-units ─► HUMAN APPROVE (hash-pinned)
                                    │
     srdloop.py plan: typed relation graph (analyst edges + See also + term mentions + scenario deps)
                                    │
 ┌──────── AUDIT LOOP  (srdloop.py run) · per unit · fresh headless context per stage ────────┐
 │ A rule-analyst     (Read; SRD only)  → relations, clauses, ambiguities, traps              │
 │ B scenario-auditor (Read/Grep)       → verdicts on related scenarios/tests                 │
 │ C test-designer    (tests/srd/**, scenarios on verdict) → interaction + abuse matrix       │
 │                    → positive/negative/boundary/abuse tests, journeys, SRD-derived oracles │
 │ gates: schema · verbatim quotes · clause×kind coverage · dice consumed · no mocks          │
 │        · refusal-has-no-side-effects · append-only acceptance tests · diff zones           │
 │ D test-verifier    (fresh) → refute oracles; mutation-check each test in scratch copy      │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
      pass → GREEN · fail → xfail(strict, T-n) + ticket · after each chapter: journey pass
                                    ▼
 DEV LOOP (srdloop.py dev) · tickets: bug · infra · refactor · coverage · lint
   fixer (dungdra/** + tests/unit/**) | unit-test-writer (tests/unit/** only)
   → gates: target xpasses · all suites green · ruff clean (0, no new suppressions)
     · unit coverage ratchet + diff coverage · mutation ratchet on touched modules
     · duplication & dead-code ratchets · import-linter · anti-mock checks · rule tags
     · fix-reviewer (fresh; hard-coding, layering, orthogonality, test meaningfulness)
   → harness removes xfail marker and commits
```

### Stage 0: extraction (deterministic, run once)

`scripts/srd/extract.py` (pdfplumber) does the extraction:
- Crops each page into two columns and groups characters into lines.
- Marks GillSans-SemiBold lines as headings, with the level taken from the font size.
- Rejoins hyphenated words, strips footers, and keeps tables as raw text.
- Writes `docs/srd/units.jsonl`, one unit per line: `id`, `chapter`, `heading_path`, `pages`, `tag`, `text` (verbatim), `see_also`.
- Ids are deterministic slugs, e.g. `GLOSS.grappled` or `PLAY.combat.opportunity-attacks`.
- Units are split at these levels:
  - Glossary: 12pt;
  - Playing the Game and the Toolbox: 14pt;
  - class features: 12pt;
  - one unit per spell, monster or item.
- Adds the CC-BY-4.0 attribution to `docs/srd/`.

**Gate: `check-units`.**
- Ids are unique.
- Every page is covered.
- No unit is empty.
- Counts roughly match (155 glossary entries, 38 Playing the Game subsections).
- A sample of units is found verbatim in `extract_text()`.

Then the human approves.

**Scope tags.** Each unit is `core`, `content-in` or `content-out`. Content-out units (spells, monsters, class features and items the engine doesn't implement) are left out of the queue: the loop improves the accuracy of what exists and doesn't test absent features. When a piece of content is implemented, its unit becomes content-in and is queued automatically.

### Plan: a typed relation graph

Seed edges come from `see_also` links, glossary-term mentions and scenario `Depends on`. **Stage A extends and types the graph.** Each edge carries a type and verbatim evidence from either unit:

| Type | Meaning |
|---|---|
| `requires` | needs the other rule to function |
| `modifies` | changes how the other rule works |
| `exception_to` / `overrides` | carves out or replaces part of the other rule |
| `excludes` | the two can't both apply, e.g. no stacking the same effect |
| `triggers` | this rule sets the other one off |
| `interacts_with` | they combine in some case |
| `same_concept_as` | they describe the same thing |

- Edges are stored in the unit's state and merged by `srdloop.py plan`.
- The queue is topological over `requires` edges.
- A new edge that points at an already-finished unit marks it `stale-interactions`, so only stage C re-runs for it. This happens at most once per pass, to prevent thrash.
- Per-unit state lives in `loop/state/<id>.json`, one file per unit, so worktrees don't conflict.

### Stage A: rule-analyst

- **Tools:** Read only. It sees the unit, the units it relates to, and the rulings register, never the code.
- **Output:**
  - `relations`, as above;
  - `clauses`, each an atomic obligation quoted verbatim, e.g. `PLAY.combat.oa#2`;
  - `ambiguities`: a quote, reading A vs reading B, a proposed ruling, and a confidence;
  - `conflicts` and `gaps`;
  - `traps` (2014→2024 changes).

### Stage B: scenario-auditor

- **Tools:** Read and Grep.
- **Input:** `srdloop.py related <id>` finds the scenarios that cite the unit's pages or terms. It maps them to tests through names, `page=`/`rule=` hits and `SRD[...]` tags.
- **Verdicts:** `consistent`, `contradicts-srd`, `under-asserts` or `affected-by-ambiguity`, each with verbatim evidence.
- **Gate:** every related item has a verdict.

### Stage C: test-designer

The aim is **at least one, and preferably many, tests per clause**.

1. **Interaction and abuse matrix.** The designer crosses each clause with its related units, the conditions, the in-scope equipment, spells, monsters and class features, and the ambiguities. Then it adds an **abuse pass** using `loop/abuse-catalogue.md`, which is seeded and grows as agents add to it:
   - moving through walls, occupied spaces or difficult terrain for free, or beyond speed;
   - acting twice, reusing a Reaction or Bonus Action, or acting out of turn;
   - spending resources that don't exist (slots, Hit Dice, uses, ammunition);
   - targeting hidden, dead, out-of-range, invisible or unseen creatures, or self where that isn't allowed;
   - negative, zero or huge numbers;
   - casting while Incapacitated, without a free hand, or without components;
   - equipment violations (two shields, armor without proficiency);
   - repeated rests;
   - stacking the same effect, and concentration juggling;
   - order exploits within a turn;
   - NL parser tricks ("attack goblin twice", chained commands);
   - refused commands that still change state.
2. **Required test kinds.** Each clause needs ≥1 **positive** and ≥1 **negative** test, plus **boundary** tests wherever a threshold exists. Each unit needs its abuse list either implemented or justified. A negative or abuse test uses a helper `assert_refused_cleanly(game, cmd)`, which checks four things:
   - `Refusal` is raised with a page or rule id;
   - `snapshot()` is unchanged;
   - no resource was consumed;
   - the turn was not spent.
3. **Oracle first.** Each expected outcome is written from the SRD, with `rule_quote` and page, before the test is run. The designer may not change it after seeing a failure; only the verifier or the human can dispute it.
4. **Journeys.** Multi-step chains go in `tests/srd/journeys/`. Each one:
   - cites ≥2 units;
   - uses forced dice;
   - runs through `Session.execute` or `Play.say`;
   - asserts at checkpoints after each step.

   Journeys are optional per unit. They are *required* in a **chapter journey pass** that runs after every unit in a chapter is done, and that pass focuses on edges typed `modifies`, `exception_to`, `excludes` and `triggers`.
5. **Invariant properties.** The designer may add Hypothesis properties: random legal and illegal command sequences through `Session.execute` must never break invariants. The invariants are:
   - HP stays within its bounds;
   - one action, Bonus Action and Reaction per turn;
   - slots stay ≤ maximum;
   - positions stay legal;
   - the log matches the state;
   - refusals are free.

   CI uses a short Hypothesis profile; `srdloop.py nightly` uses a long one.
6. **Scenario fixes.** For `under-asserts`, the designer adds assertions. For `contradicts-srd`, it fixes the test to match the SRD and logs a `scenario-notes.md` row.
7. **Outcomes.**
   - Pass: the test is kept.
   - Fail: marked `xfail(strict=True, reason="T-n")` and a `bug` ticket is opened.
   - Can't be tested because a hook is missing (map, callbacks, validate/apply split): an `infra` ticket is opened.

**Gates after stage C** (`srdloop.py gate <id>`):
- Output is schema-valid.
- Every clause has tests of each required kind, or a `not_testable` reason.
- `rule_quote` is verbatim.
- Every new test has the `srd` marker.
- Forced dice are fully consumed (an autouse `game.dice.pending()==0` fixture).
- **No mocks** in `tests/srd`/`tests/scenarios`. The gate greps for `unittest.mock`, `MagicMock`, `patch(`, `monkeypatch` and `mocker`. Only the real engine is used: randomness comes from forced dice and choices from `game.answer`.
- Tests claimed green pass, and tests claimed red fail.
- Acceptance tests stay append-only.
- The diff touches only allowed zones.

### Stage D: test-verifier

A fresh agent tries to refute each test:
- **Wrong oracle:** the test misreads the SRD, or silently picks one reading of an ambiguity.
- **Wrong reason:** it passes for the wrong reason. The verifier mutates the relevant branch or constant in a scratch copy and the test must fail.
- **Duplicate:** it repeats an existing test.

The harness removes refuted tests and logs them. Low-confidence refutations go to the human.

### Dev loop

`srdloop.py dev [ticket]`. Tickets are worked in this priority order:

| Priority | Kind | Source | Done when |
|---|---|---|---|
| 1 | `bug` | xfail SRD or scenario test | the test xpasses; the harness removes the marker |
| 2 | `infra` | an untestable clause | the blocked tests can be written; the unit is requeued |
| 3 | `lint` | groundwork, or any gate failure on HEAD | 0 violations |
| 4 | `refactor` | fix-reviewer findings, architecture-review debt, metric triggers (complexity, module size, duplication, import-contract exceptions) | acceptance suites untouched and green, and the metric improved |
| 5 | `coverage` | unit coverage below target, or a module below its floor | the floor is reached, with the mutation score held |

**Agents:**
- **fixer.** Writes `dungdra/**` and `tests/unit/**`. Every behaviour change gets unit tests for the component it touches. It adds `SRD[...]` tags and `rule=` ids for the unit. If it thinks an acceptance test is wrong, it files a `dispute`; a major refactor goes through a test-change request.
- **unit-test-writer.** For `coverage` tickets. It writes `tests/unit/**` only, so a coverage ticket can't change behaviour.
- **fix-reviewer.** Fresh context, read-only. It checks for:
  - hard-coding, such as fixture or monster names from the test;
  - the change sitting in the wrong layer;
  - parallel mechanisms or special cases where data-driven code would do;
  - unit tests that mock the component under test, or only execute lines without asserting anything.

  It can reject a change, or pass it and file a follow-up `refactor` ticket.

**Gates for a dev-loop commit** (`srdloop.py dev-gate`):
1. The target test xpasses, or the metric improved. All suites are green, and plain `pytest` works.
2. **Clean lint.** `ruff check` and `ruff format --check` report **0 violations** on the configured rule set, `E,F,W,I,B,UP,SIM,C90`. The line length is set once in groundwork, e.g. 110 with `ruff format`. The C901 limit starts at the current worst function (84 today) and is ratcheted down to 10 by refactor tickets. Changing that limit is config, not a suppression.
3. **No suppressions.** The diff must not add any of:
   - `noqa`, `type: ignore`, `pragma: no cover`, `pylint: disable`;
   - `per-file-ignores`, `extend-ignore`, `ignore_imports`;
   - `skip` or `xfail` without a ticket.

   These are allowed only with a human approval file. The 3 existing suppressions are reviewed in groundwork.
4. **Unit coverage.** Measured by `pytest tests/unit --cov=dungdra --cov-branch`, from unit tests only.
   - The total must not drop below `loop/coverage-baseline.json`, and the baseline rises after each commit.
   - Changed lines need ≥90% branch coverage, computed by `srdloop.py` from coverage JSON plus the git diff.
5. **Mutation testing.** mutmut runs on the modules the ticket touched; this is feasible because the suite runs in under 1 s. The per-module mutation score must not drop. Surviving mutants in changed lines go to the reviewer. The full run is nightly.
6. **Duplication.** Checked by `pylint --disable=all --enable=duplicate-code`, with min-similarity-lines 6 and imports and docstrings ignored. `dungdra/` and `tests/` are checked separately, and tests get a higher threshold. The count must not increase. **Dead code:** `vulture --min-confidence 80`, and the count must not increase.
7. **Anti-mock rules for unit tests.**
   - Mocking is allowed only at declared seams: dice RNG, choice callbacks and IO, listed in `tests/unit/SEAMS.md` and provided as fixtures.
   - An AST check rejects patch targets inside the module under test.
   - Tests with no `assert` or `pytest.raises` are rejected.
8. **Architecture.** `lint-imports` enforces these layers (bottom to top):
   1. `rules` and `dice`
   2. `data`
   3. the model
   4. mechanics
   5. game and session
   6. `api`, `nl`, `cli`, `play`

   Today's violations are recorded as `refactor` tickets and ratcheted down. `SRD[...]` tags and `rule=` ids must be valid.
9. `audit.reconcile` is clean on the journeys, and the fix-reviewer approved.

### Stop and verification rules

**Per stage.**
- Output is schema-enforced.
- Each call has a budget cap (`--max-budget-usd`).
- One retry at 1.5× the cap; after that the unit is marked `incomplete` with the reason.

**A unit is DONE** when stages A–D have run, all clause × kind coverage is met or justified, every related scenario has a verdict, every ambiguity has an accepted or proposed ruling, and the verifier has run. It ends in one of four states:
- `green`: all its tests pass;
- `red`: tickets are open;
- `blocked`: a `requires` dependency is red, it has an `infra` ticket, or it waits on an unaccepted ruling;
- `incomplete`: it failed its gates twice.

**Staleness.** A unit is requeued when any of these change:
- its own text;
- the statuses of units it relates to;
- the text of its related scenarios;
- the data files it touches;
- a new edge pointing at it.

This covers content added later, accepted rulings and landed fixes.

**The audit loop stops when:**
- no units are pending or stale; **or**
- the budget is paused (see below); **or**
- a circuit breaker trips:
  - the suite is red on entry with no ticket;
  - 3 stages fail in a row;
  - more than 15 tickets are open (the dev loop catches up first);
  - the same file is churned by more than K consecutive units.

**The dev loop stops when:**
- no `bug`, `infra` or `lint` tickets are open **and** the coverage and architecture targets are met, or the last N refactor/coverage tickets improved the metrics by less than ε; **or**
- a ticket fails 3 times, so it becomes `stuck` and goes to the human; **or**
- a regression appears, so the change is reverted and the ticket marked `stuck`; **or**
- the budget is paused.

**Human gates:**
- approving `units.jsonl`;
- accepting rulings;
- disputes and test-change requests;
- `stuck` tickets;
- raising targets.

**Reporting.** `loop/COVERAGE.md` never shows raw test counts. It shows:
- unit states per chapter;
- clause × kind coverage;
- tickets by kind;
- rulings;
- scenario verdicts;
- unit and branch coverage and mutation score per module;
- lint, duplication, dead-code and import-contract status;
- spend so far and projected.

### Budget and resume

- **Checkpoints on disk.** Each stage's output is saved to `loop/runs/<unit>/<stage>.json` as soon as it passes its gate. Per-unit state files record the last completed stage. Everything is committed at the end of each unit or ticket.
- **Cost ledger.** `loop/costs.jsonl` gets one row per call: unit or ticket, stage, model, `total_cost_usd`, `session_id` and timestamp.
- **Run budget.** `srdloop.py run --budget 200`. Before each call, if `remaining < per-call cap` the loop **stops cleanly between calls**: state `paused(budget)`, exit code 4. It never kills a stage midway.
- **Resume** is `srdloop.py run --budget <more>` or `srdloop.py dev --budget <more>`. It is idempotent:
  1. It restores any uncommitted changes in loop write zones left by an interrupted stage to HEAD.
  2. It resumes the in-flight unit from its last completed stage, without re-running the stages already done.
  3. It continues the queue.
- **Transient stops** are rate limits, subscription usage limits, network errors and CLI failures. Each is treated as `paused(transient)` with the same resume path, so a cron job, `/loop` or `/schedule` can resume automatically later.
- **Fresh contexts on resume.** Resuming reruns the stage from its checkpoint in a fresh context rather than continuing the old session with `--resume <session_id>`, so every stage stays reproducible.

## Cost estimate (rough; calibrate with the pilot)

**Prices.** Per MTok, input / output / cache read:

| Model | Input | Output | Cache read |
|---|---|---|---|
| Opus 5.5 | $4 | $20 | $0.20 |
| Sonnet 5.5 | $2 | $10 | $0.20 |

Cache writes cost about 1.25× input. Claude Code caches its system prompt and each growing context.

**Models:** Opus for A, C, D, fixer and reviewer; Sonnet for B and the unit-test writer.

| Per full unit | Turns | Main cost drivers | ≈ $ |
|---|---|---|---|
| A rule-analyst (Opus) | ~5 | ~30k ctx, ~8k out incl. thinking | 0.35 |
| B scenario-auditor (Sonnet) | ~15 | ~0.6M mostly cached input | 0.45 |
| C test-designer (Opus) | ~40 | ~3.5M cached reads, ~200k cache writes, ~40k out | 2.50 |
| D test-verifier (Opus) | ~20 | ~1.2M cached reads, mutation checks | 1.20 |
| Retries / gate failures (~20%) | | | 0.90 |
| **Total per unit** | | | **≈ $5.4** (range $3–10) |

| Item | Count | ≈ $ |
|---|---|---|
| Core units: Glossary 155 + Playing the Game 38 + Toolbox 30 | ~225 | 1,200 |
| Content-in units: 4 classes at levels 1–3, origins and feats, the equipment chapter, spellcasting rules plus 32 spells, monster rules plus 14 monsters, magic item rules plus 7 items | ~175 | 950 |
| Chapter journey passes | ~10 | 100 |
| Content-out units (not queued until the content is implemented) | ~1,190 | 0 |
| **Audit loop subtotal** | | **≈ $2,250** |
| Dev loop: ~130 bug tickets at ~$6 (fixer, reviewer, retries) | | 800 |
| Dev loop: ~8 large infra tickets (map/geometry, validate/apply split, reaction choices, rule-id events) at ~$40 | | 320 |
| Dev loop: ~60 refactor, coverage and lint tickets at ~$4 | | 240 |
| **Total first full pass** | | **≈ $3,600** (plausible range $2k–6k) |

**Ways to reduce this, if needed:**
- Run B and D on Sonnet (about −25%).
- Merge tiny glossary entries (e.g. "Bonus Action", "Action") into one unit with their Playing the Game subsection (about −15% units).
- Lower the effort on stage A.

**The pilot gives real numbers.** `srdloop.py report` projects $/unit × remaining units, so the estimate is replaced after 3 units. On a subscription plan the "cost" is usage-window time rather than dollars. The loop then mostly pauses and resumes on limits.

## Files to create or change

- **`pyproject.toml`:**
  - the dependencies above;
  - `[tool.ruff]` (rules, line length, C901 limit);
  - `[tool.coverage]`;
  - `[tool.importlinter]` contracts;
  - `[tool.pylint]` duplicate-code settings;
  - `[tool.mutmut]`;
  - pytest markers (`srd`) and the Hypothesis profiles.
- **Extraction:** `scripts/srd/extract.py`, which writes `docs/srd/units.jsonl`, plus the attribution.
- **Orchestrator:** `scripts/srdloop/` holds `srdloop.py` (CLI) and the package modules:
  - `units`, `plan`, `related`, `gates`, `devgates`, `quality` (ruff, coverage, mutmut, pylint, vulture and import-linter wrappers with ratchets), `tickets`, `budget`, `report`, `map`;
  - `claude.py`, which wraps `claude -p` with a per-role `--allowedTools`, `--json-schema`, `--max-budget-usd` and `--permission-mode dontAsk`.

  It reuses the patterns from `docs/loop-example/.../audit.py` (`norm`, `fingerprint`, coverage).
- **Schemas:** `schemas/*.json` for analysis, scenario-verdicts, test-plan, verification, fix-result and review.
- **Agents:** `.claude/agents/` holds `rule-analyst`, `scenario-auditor`, `test-designer`, `test-verifier`, `fixer`, `unit-test-writer` and `fix-reviewer`.
- **Hooks:** `.claude/hooks/guard_writes.py` and `stop_gate.py`. `.claude/settings.json` holds the sandbox, deny rules and hooks.
- **Skills:** `.claude/skills/srd-rule/SKILL.md` and `srd-ticket/SKILL.md`, the interactive single-unit and single-ticket modes.
- **Engine:** add `rule=` to `Event`/`Refusal` in `dungdra/events.py` and `dungdra/rules.py`, which is the first `infra` change and is backward compatible.
- **Tests:**
  - `tests/__init__.py`;
  - `tests/unit/` with `SEAMS.md`, `tests/scenarios/` and `tests/srd/` (conftest with the dice-consumed fixture, `assert_refused_cleanly`, no-mock check), `tests/srd/journeys/`;
  - the rule-firing plugin in `tests/conftest.py`.
- **Loop state:**
  - `loop/state/`, `loop/runs/`, `loop/tickets/`, `loop/requests/`, `loop/approvals/`;
  - `loop/rulings-proposed.md`, `loop/abuse-catalogue.md`;
  - `loop/coverage-baseline.json`, `loop/quality-baseline.json`, `loop/costs.jsonl`;
  - the generated `loop/COVERAGE.md` and `loop/RULEMAP.md`.

## Build order

1. **Groundwork** (hand-driven with you, not by the loop):
   - `pyproject` dependencies and tool config, and the venv.
   - Move the tests into `tests/scenarios/`: 150 tests before and after, no assertion changes.
   - Lint to zero: `ruff --fix`, `ruff format`, and manual fixes for E741, E702 and F841. Review the 3 existing suppressions.
   - Record the baselines: unit coverage (≈0), duplication, dead code, mutation score, import-contract exceptions.
2. **Extractor.** Write `extract.py` and `check-units`, then hand-review the Glossary and Playing the Game output and approve it.
3. **Orchestrator.** The `srdloop` package, with its own unit tests in `tests/unit/test_srdloop_*.py`. Add the `rule=` event field and the tracing plugin.
4. **Agents, schemas, hooks and skills.** Include hook tests: fake PreToolUse JSON for each forbidden role × path must be blocked.
5. **Pilot on 3 canary units** in interactive mode (`/srd-rule`), then headless:
   - `PLAY.actions.ready`: expected red or infra;
   - `GLOSS.grappled`: expected mostly green, with abuse cases;
   - the spellcasting slot/target clause: expected red.

   Then run `srdloop.py dev` on the resulting tickets. Calibrate the cost. **Litmus test:** the loop finds and fixes the canaries without being told about them.
6. **Headless audit.** The Glossary first, then Playing the Game and the Toolbox, with a chapter journey pass after each chapter. The dev loop runs between batches.
7. **Quality lanes.** Coverage, refactor and architecture tickets.
8. **Later:** a container, then parallel worktrees (one unit per worktree, with per-unit state merges).

## Verification of the loop itself

- **srdloop's own unit tests:** quote gate, clause × kind coverage, append-only check, suppression detector, anti-mock AST check, diff-coverage arithmetic, ratchets, budget pause/resume, staleness hashing and plan ordering.
- **Resume test.** Kill the run between stages C and D (simulating `--budget` exhaustion), then resume. Stages A–C must not re-run, and the tree must be clean.
- **Canary pilot.** A missed canary is a defect in the loop.
- **End to end.** Run `srdloop.py run --units GLOSS.prone,GLOSS.grappled --budget 30`, then `srdloop.py dev --budget 30`. Then check:
  - `COVERAGE.md` and `RULEMAP.md` are updated;
  - git log shows the chain xfail → fix + unit tests → marker removed → commit;
  - ruff reports 0;
  - no ratchet regressed;
  - plain `pytest` is green in a fresh venv after `pip install -e ".[dev,srd]"`.
