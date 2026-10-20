# DungDra loop retrospective

Sep 28, 2026 · @Jussi Kuosa

The loop produced a playable, rules-faithful engine: about 10k lines of Python and 150 tests. All 77 scenario IDs have at least one test, and all six capstone journeys (J1–J6) pass through natural language. But by the spec's own definition, most scenarios aren't green. The LLM roles and the 17 soft criteria were never built, and every playability problem was found by a human, not the loop.

## What worked

Five parts of the setup paid off, and all of them made the target checkable rather than arguable.

1. **Scenarios plus the SRD as two separate sources.** The scenarios said what to check; the rulebook said what is true. When they disagreed, the SRD won and the disagreement was logged in `docs/scenario-notes.md`. For example, CLS-WIZ-03 says a scroll survives being copied into a spellbook, but SRD p.244 says it's destroyed.
2. **Forced dice.** `d20=[11,4]` turned vague rules into exact, deterministic assertions. This was the most valuable single idea in the spec.
3. **Dependency waves (1–8).** The build order matched how the code really depends on itself, so later layers rarely forced rewrites of earlier ones.
4. **The 2014→2024 trap list.** It was cheap to write and caught real temptations: surprise, Sleep, exhaustion, and potions as a Bonus Action.
5. **The rulings register (R-01 to R-03).** It forced explicit, logged decisions instead of silent improvisation, and the loop extended it itself with R-04.

The capstone journeys also earned their place. They caught integration bugs no unit scenario could, such as the parser picking the wrong character and level-up not refilling prepared spells.

## Missed: the spec's own contract

Six things the scenario document asked for weren't delivered, and the loop didn't flag them clearly as it went.

| Requirement | Where the spec says it | What was delivered |
| --- | --- | --- |
| A scenario is green only if it passes through both interfaces | §2.1.4 | Only the journeys go through natural language or `Session.execute`. The other \~140 tests call engine functions directly. |
| \[S\] soft criteria scored by an LLM judge | §2, §2.1.5 | None of the 17 are evaluated, including MON-03 (monster tactics), narration honesty, and "fun, at least 4/5". |
| LLM player agent and narrator | §2.1.5 | The player is a scripted Python bot. There is no narrator, and `--llm` crashes with `No module named 'dungdra.llm'`. |
| Regression goldens written before the fix | §7 | Bugs found in play were fixed first and tested afterwards, or tested only indirectly. |
| Coverage metric per section | §7 | Never produced. Progress was reported as "N tests pass", which is not the same thing. |
| Implement all of the rules | §1 | The Ready action is in scope but has no scenario and isn't implemented, even though a docstring claims it. |

The last row is the most instructive. The principle said "every rule", but the loop only enforced rules that had a scenario, so rules without one silently fell out.

## Missed: gaps in the inputs

The scenarios specified rules correctness, not playability, so the loop had no reason to build what a player needs.

- **Playability wasn't specified.** Every problem found in real play was outside the spec. These included travelling to a named place, a refused action costing the turn, when a turn should end, and seeing the inventory. Combat that is effectively unwinnable for a new player and no way to see positions or distances belong here too.
- **No success criterion for balance.** J1 passes with rigged dice, and nobody asked whether a reasonable player wins the ambush. A seed sweep at the end found 58 of 59 wins with good tactics and far fewer with naive ones. The spec should have demanded that measurement.
- **Some scenarios contradicted the SRD or the fixtures.** Examples are the CLS-WIZ-03 scroll, a Dim Light case that ignores MIALEE's Darkvision, and too few subset spells for a level 2 Wizard. A spec-linting pass before building would have caught these cheaply.
- **Natural language was specified by example, not by grammar.** The regex parser covers the phrasings the journeys use. "go to watchtower" failing is exactly the result you'd expect.

## Missed: the loop itself

The biggest structural weakness was that one agent built the code, wrote the tests and judged the result.

- **The implementer graded itself.** The same agent wrote the engine, the tests and many test-data fixes (dice queues, positions, levels). Some fixes corrected genuinely wrong scenario data. But one agent adjusting both sides is the classic way a loop overfits, and nothing independent checked that a test still meant what its scenario said.
- **The increments were too big.** The prompt asked for each increment to be tangible and verifiable. In practice commits were whole waves, such as one covering damage, conditions, rests, exploration, social, hazards, monsters, encounters, traps and poison. A wave that went wrong would have been hard to bisect.
- **How people run it went untested.** Plain `pytest` failed on the user's machine because the loop only ever ran `python -m pytest`. Nothing checked "does it work the way a human will run it?"
- **A human was the only playability check.** Every usability fix came from the user. A step such as "play 20 seeds as a naive player and report where it gets stuck" would have found most of them first.

## Next time

Keep forced dice, SRD page tracing, the rulings register, dependency waves and journeys. Then add these:

- [ ] Make both-interface coverage mechanical: every scenario test runs once through `Session.execute` and once through natural-language text.
- [ ] Build a coverage dashboard from the scenario IDs, plus a map from rules to scenarios, so a rule with no scenario (like Ready) shows up as a gap.
- [ ] Add an independent checker: a second agent or a person reviews test changes against the scenario text.
- [ ] Adopt the rule "never edit an assertion to make it pass without a logged note".
- [ ] Write the regression scenario before the fix, as §7 of the spec already asks.
- [ ] Add playability scenarios: a naive-player win rate per encounter, discoverable commands, and a help text that matches the parser.
- [ ] Lint the spec against the SRD and the fixtures before building.
- [ ] Score the soft criteria with a real LLM judge on recorded transcripts, even if only nightly.
- [ ] Keep increments to one section per commit, with the coverage table updated in each.
- [ ] Run the tests the way a user will (`pytest`, a fresh clone, the CLI) as part of each loop iteration.
