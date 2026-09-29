# DungDra Engine Review

Sep 28, 2026 · @Jussi Kuosa

The rules kernel is sound, but the game on top isn't a campaign engine yet: no seed out of 40 finishes the Goblin Trail. Reviewed at `cc1` commit 03a4aef (10k lines of engine, 150 passing tests).

## Verdict

The scripted player in `tests/agent.py` played the whole Goblin Trail on seeds 1–40 and finished none: 10 runs wiped at the first ambush and 30 got permanently stuck at the watchtower.

- **Wipes are final.** A party wipe ends the game, yet the message says to "load an earlier game" (`gm.py:143`), and no save or load exists.
- **The watchtower is a dead end.** Once the hidden pit is detected, `Adventure.go()` refuses to continue until someone wedges it with an Iron Spike (`adventure.py:160`). The 2024 Dungeoneer's Pack has no spikes, nothing tells the player to buy them, and the adventure can't go back to the shop (`adventure.py:138`). So spotting the trap leaves you stuck, while missing it only costs HP.
- **J1 passes only by foreknowledge.** The test buys Iron Spikes in Millbrook, which a real player has no reason to do.

The existing retrospective covers the build process; this review covers the code.

## What's solid

The rules kernel is worth keeping as the foundation.

- **Dice and roll records.** Forced dice, and `D20Roll` records that keep every modifier with its source. The event log carries SRD pages and ruling IDs.
- **Effect hooks.** Conditions, spells and features all plug in through `Effect` hooks (`d20`, `as_target`, `ac_bonus`, `speed`, turn and damage events). That's the right core abstraction.
- **Fixtures.** All four match the spec's oracle values exactly.
- **Tests.** 150 tests run in about 3.5 s with about 87% line coverage.

## Confirmed defects

Each of these was reproduced in this session, not inferred.

| # | Problem | Evidence |
| --- | --- | --- |
| 1 | A refused command isn't free. `Session.execute` rolls back only `TurnState`, reactions and wielded weapons (`api.py:44`, `api.py:56`). `spells.cast` spends the slot, marks the free cast used, starts Concentration and logs the cast (`spells.py:114–131`) before the spell code runs its target checks (`spells.py:135`). | Bless on all four PCs is refused ("up to 3 creatures") but still uses a level 1 slot and leaves JOZAN concentrating on nothing. Magic Missile with no target also uses the slot. The audit can't catch it: the log does say "casts … with a level 1 slot". |
| 2 | Parser crashes end the game. Grapple, shove, stabilize, Healer's Kit, Divine Spark and help-an-enemy use `tg[0].id` with no check (`nl.py:383–446`), and `cli.py:62` catches nothing. | "BROM grapples", "JOZAN stabilizes" and "LIDDA shoves" each raise `IndexError`. |
| 3 | Target lookup falls back silently and leaks hidden information. | "LIDDA attacks goblin warrior 9" attacked Goblin Warrior 1, a hidden goblin she couldn't see. |
| 4 | The parser's first matching rule wins, whatever the sentence means. | "JOZAN heals BROM's hp" prints the party status. "walks 10 feet north" isn't understood; movement only works toward or away from a creature. |
| 5 | The engine takes the caller's word for spatial facts. Hide always gets `cover="three-quarters"` (`nl.py:388`), and the line-of-sight check only runs if the caller passes `seen_by`, which none does. Influence disposition is fixed at "hesitant" (`nl.py:474`). | Any character can hide anywhere. |
| 6 | The Ready action isn't implemented, though the `actions.py` docstring lists it. | Not found anywhere in the code. |
| 7 | The monster AI's random choices use the rules RNG (`gm.py:76`). | Changing a tactic changes every later roll for the same seed. |

## Architecture weaknesses

Six structural issues explain most of the defects above and will keep producing new ones.

1. **Commands aren't transactions.** Validation, payment and effects are mixed together, so every new rule can repeat defect #1. Either split each command into `validate()` then `apply()`, or snapshot the whole state and roll back on any refusal. The second option comes free once state is serializable.
2. **State can't be saved.** State is spread across back-references (`creature.game`), a `notes` dict with about 30 unrelated keys (one holds a callable), effects matched by global counters and name strings, and a lambda in `EventLog.clock_fn` that breaks `pickle`. `snapshot()` exports effects as display strings, so it can't be loaded back. There is no save/load, undo or replay.
3. **The log's display text is also its data format.** `audit.py` reconciles state by regex over English sentences, and tests search log text. Typed event records (e.g. `SlotSpent(pc, level)`) that generate the text would make the audit and tests exact, and give a narrator clean input.
4. **Content is hard-coded in engine logic.** The spec says new content should be data entry, but the AI special-cases monster names (`m.key not in ("goblin boss", "ogre")`, `startswith("goblin")`), the adventure special-cases trap kinds in `go()` and `cmd_loot`, and spells are about 1,000 lines of one-off functions.
5. **Positions exist, but there's no map.** Walls, terrain, light and cover are entered by hand per pair of creatures (`scene.cover[(a, b)]`), so the engine can't check Hide, cover or line of sight, and players can't see where anything is. A small per-scene grid would fix both.
6. **Player choices are blocking callbacks.** `game.decide` works in a terminal, but a web or LLM front end needs the engine to pause on a pending choice and resume with the answer. That also makes reactions (Shield, Opportunity Attacks, Redirect Attack) testable through the API.

## Campaign readiness

The engine can't yet carry a meaningful campaign: most of what it implements is unreachable in play.

- **Content reach.** The adventure is five linear scenes using 2 of the 14 monsters. It awards 500 XP in total, 125 per PC, and level 2 needs 300. So level-ups, subclasses, level 2 spells, Channel Divinity, most magic items, Influence, crafting and lifestyle never come up. The reeve's promised reward is text only; no gold is paid.
- **Adventure format.** There are no NPCs or attitudes, no quest or flag state, no branching, no shops as places, no encounter tables and no rules for where it's safe to rest.
- **Losing.** A wipe ends the game for good, and there's no save to return to.
- **Narration.** There is no narrator. Scene text is fixed, and `--llm` crashes on import (`No module named 'dungdra.llm'`).

## Missing verification

These checks would have caught every defect above before a human did.

- [ ] **Refusals change nothing:** diff the full snapshot before and after every refused command. This alone catches defect #1.
- [ ] **Invariants after every command:** HP within bounds, slots within the maximum, at most one action, Bonus Action and Reaction per turn, and the log reconciling with state.
- [ ] **Campaign-completion sweep in CI:** N seeds × player styles (naive, tactical), asserting the completion rate, zero crashes and zero dead ends. The pit would have failed this.
- [ ] **Parser tests:** fuzz the parser, and require every `HELP` example and in-game hint to parse.
- [ ] **Save/load round-trips** and deterministic replay from a command log, once serialization exists.
- [ ] **Scenarios through both interfaces, plus a rule-to-scenario coverage map** (both also in the retrospective). The map would have flagged Ready.
- [ ] **CLI and tooling:** run `cli.py` under the tests (it never runs today), and add mypy and ruff.

## Recommended order of work

Fix what stops play first, then the foundations that later work depends on.

1. **Remove the dead end and the crashes.** Give the pit alternatives (jump, go around, go back to town), check the parser's target lookups, add a catch-all in the CLI, add the refusal-diff test, and move spell payment after target validation.
2. **Make commands transactional** (validate, then commit).
3. **Make state serializable and add save/load,** with typed events that generate the log text.
4. **Add a scene grid map** so the engine owns cover, light and line of sight, plus a `map` command for players.
5. **Adopt a data-driven adventure format** (location graph, NPCs, flags, triggers, rewards). Then write a level 1→3 campaign that reaches all 14 monsters and the magic items, tuned with the seed sweep.
6. **Add a pending-choice engine API,** then put an LLM narrator and interpreter behind it that can't change any numbers.
