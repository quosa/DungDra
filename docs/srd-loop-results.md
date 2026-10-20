# loop results


...skipped many early loop development bugs...

Already exercised for real: all four audit stages, a gate retry, a paused run and its resume, the verifier refuting tests, red tests turning into tickets, an infra ticket, the dev loop's fix and review, a dispute, one fix closing two tickets, a recheck, a waiver, and accepting rulings (though I filed those proposals by hand).


## first hand-selected test round:

### expectations

Not yet exercised for real:
- a missing feature (GLOSS.ready, a canary);
- a bug where a refusal still changes state (spell slot spent on a refused cast, the other canary);
- a unit that turns out to be out of scope;
- a ruling proposed during a live run (not filed by hand), and rejecting one;
- a revisit (Grappled now has one waiting, for carrying);
- a long Playing the Game section;
- content units: a spell and a monster;
- the circuit breakers (red suite, too many open tickets), checked only in unit tests.

What I'd run, about 8 units chosen to hit those paths:

    ┌──────────────────────────────────────────────────┬────────────────────────────────────────────┐
    │                       Unit                       │               Expected path                │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ GLOSS.ready                                      │ missing action: a red test or infra ticket │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ Spellcasting "one slot spell per turn / targets" │ the slot-spent-on-refusal canary: red      │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ GLOSS.tremorsense (or Burrow Speed)              │ likely out of scope                        │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ PLAY.combat.cover                                │ long section, many related scenarios       │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ SPELL.bless                                      │ content unit, touches the slot canary      │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ MONSTER.goblins.goblin-warrior                   │ stat-block unit                            │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ GLOSS.prone                                      │ likely ambiguities: a live ruling proposal │
    ├──────────────────────────────────────────────────┼────────────────────────────────────────────┤
    │ GLOSS.grappled                                   │ the revisit, stages C and D only           │
    └──────────────────────────────────────────────────┴────────────────────────────────────────────┘

Then the dev loop on whatever tickets result.

### results

Results so far:

    ┌───────────────────┬─────────────────────┬───────┬─────────────────┬───────┐
    │       Unit        │       Status        │ Tests │     Tickets     │ Cost  │
    ├───────────────────┼─────────────────────┼───────┼─────────────────┼───────┤
    │ GLOSS.tremorsense │ blocked (1 ruling)  │ 7     │ 3 infra         │ $1.26 │
    ├───────────────────┼─────────────────────┼───────┼─────────────────┼───────┤
    │ PLAY.combat.cover │ blocked (3 rulings) │ 38    │ 2 bugs, 3 infra │ $2.96 │
    ├───────────────────┼─────────────────────┼───────┼─────────────────┼───────┤
    │ SPELL.bless       │ blocked (3 rulings) │ 44    │ 4 bugs          │ $2.73 │
    └───────────────────┴─────────────────────┴───────┴─────────────────┴───────┘

- The second canary was found on its own: T-21, "Bless's target cap is checked after the slot is spent and Concentration starts; the refusal cites no page".
- Other real bugs:
  - T-16: creatures standing in the way give no cover;
  - T-20: a refused spell still stows your weapon;
  - T-22: targeting an object with Bless crashes;
  - T-23: Bless doesn't add to Death Saving Throws;
  - T-15: cover isn't logged with its rule.
- Cost: about $2.30 per unit on average, against my estimate of $1.50. Longer units like Cover cost twice as much as short glossary entries. I'll recalibrate the estimate once the trial is finished.

## Resist the temptation

I need to resist the temptation to go directly into fixing things, and let the loop do it.

I need to wait for the loop to finish/break so that I don't accidentally trip the verifiers with false positive edits outside teh loop.
