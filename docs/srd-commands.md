# srdloop command


    status
    plan
    related
    report
    gate
    dev-gate
    run
    dev
    mutate
    prompt
    accept
    finish
    tickets         - lists all tickets
    ticket          - can be used to create tickets
    ruling
        list
        accept
        reject

## status
    python -m scripts.srdloop status
    1835 units; 641 to do; 4 finished; 4 with state

## list rulings to decide on
    python -m scripts.srdloop ruling list

    P-1   accepted  → R-05 GLOSS.grappled: A Tiny grappled creature never adds extra movement cost, whatever the grappler's size.
    P-2   accepted  → R-06 GLOSS.grappled: Attacks against any of your current grapplers have no Disadvantage from Grappled; attacks against anyone else have it.
    P-3   accepted  → R-07 GLOSS.grappled: Every Speed (Climb, Swim, Fly, including speeds gained after the grapple starts) is 0 and can't increase while Grappled.
    P-4   proposed  GLOSS.tremorsense: No. Pinpointing makes the location known (no guessing the space), but Tremorsense doesn't count as sight. Attacks against the target still have Disadvantage for an unseen target, and spells that need a target you can see stay unavailable.
    P-5   proposed  PLAY.combat.cover: Any other creature in the line between the origin and the target gives Half Cover, whatever its size. A creature never gives Three-Quarters or Total Cover, and several creatures in the line still give only Half.
    P-6   proposed  PLAY.combat.cover: 'Directly' limits the refusal to effects that select the creature (attack rolls, chosen spell targets, each target of a multi-target spell). An area spell isn't refused. Whether the area reaches a creature behind Total Cover is decided by GLOSS.area-of-effect (a line is blocked only by Total Cover), so with Total Cover from the origin it isn't affected. SPL-05 stays as is.
    P-7   proposed  PLAY.combat.cover: No. Cover is worked out per target and per origin: an obstacle that covers the target from an attacker gives the attacker no cover unless it also covers the attacker (a separate entry).
    P-8   proposed  SPELL.bless: Any roll the rules call a saving throw gets the 1d4, including Death Saving Throws and Concentration saves.
    P-9   proposed  SPELL.bless: The caster can bless themself as one of the targets.
    P-10  proposed  SPELL.bless: Range is checked only at casting. The benefit lasts until the spell ends, wherever the target goes.


These rulings are found in loop/rulings folder, see below for accepting or rejecting them.

### accept a ruling

    python -m scripts.srdloop ruling accept P-4
    P-4: accepted as R-08

Can have --note and --reason options:

    python -m scripts.srdloop ruling accept P-9 --note "this was confirmed on a 3d6 reddit thread"

## list all tickets

    python -m scripts.srdloop tickets

    T-1    fixed    bug      GLOSS.grappled: With two grapplers, attacking one grappler still has Disadvantage from the other grapple
    T-2    fixed    bug      GLOSS.grappled: move(drag=...) drags a creature the mover isn't grappling
    T-3    fixed    bug      GLOSS.grappled: move(drag=...) lets a non-grappler drag a creature someone else is grappling
    T-4    fixed    infra    GLOSS.grappled: GLOSS.grappled: Support carrying a grappled creature during non-walking movement (climb/fly), not just move(drag=...)
    T-5    open     refactor GLOSS.grappled: Pull the grappler lookup (`e.condition == "grappled" and e.data.get("grappler")`) into one helper, such as `grapplers_of(creature)`. The same scan appears in effects.py, combat.py (move-out-of-reach and release) and game.py (incapacitation).
    T-6    void     refactor GLOSS.grappled: Pull the 'is X grappled by Y' check (e.condition == 'grappled' and e.data.get('grappler') == id) into one helper; it's now repeated in combat.py (move drag check, the reach check around line 451, release_grapple), effects.py:172 and game.py:283
    T-7    open     refactor GLOSS.grappled: move(): replace the nested mode→speed ternary and the per-mode climb/swim/fly branches with a per-mode table (speed kind, fallback-to-walk allowed?, extra cost without the speed)
    T-8    open     infra    GLOSS.grappled: GLOSS.flying: a flying creature whose Fly Speed drops to 0 or who becomes Prone/Incapacitated falls (not modelled yet)
    T-9    fixed    infra    ENGINE: Traceability in the event log: every Event and Refusal carries the SRD rule it applies as rule="<unit id>#<clause>" (next to page=), matching the SRD[...] code tags; and wherever the engine applies a register ruling it logs ruling="R-<n>" (R-05..R-07 for Grappled are applied but not logged; check R-01..R-04 too). Game.log gets rules() and a test helper to assert a rule or ruling was applied. Backward compatible: page= stays.
    T-10   open     coverage ENGINE: Unit tests that assert_applied(ruling=...) for R-01 (creation tool proficiency), R-02 (XP split), R-03 (encounter budget GM-only / blocked reinforcements) and R-04 (disarm without Thieves' Tools); only R-05..R-07 are covered by the new traceability tests
    T-11   open     refactor ENGINE: add_condition logs ruling="R-07" on every Grappled condition, even for a creature with only a walking Speed; log R-07 only when the grappled creature has, or later gains, a non-walk Speed that the ruling zeroes
    T-12   open     infra    GLOSS.tremorsense: GLOSS.tremorsense: Awareness model: a query such as game.pinpoints(observer, target) / knows_location, kept separate from can_see. Tremorsense (and Blindsight) feed it within their range. Hide/Search and the combat help ('N hidden enemies somewhere nearby') use it, and Refusals and Events cite rule=GLOSS.tremorsense#<n>.
    T-13   open     infra    GLOSS.tremorsense: GLOSS.tremorsense: Surface/liquid contact model: each creature (and moving object) records the surface or body of liquid it touches: ground, wall, ceiling, a separate structure such as a boat, a creature it rides, a lake. Tremorsense detection requires a shared surface or liquid.
    T-14   open     infra    GLOSS.tremorsense: GLOSS.tremorsense: Airborne state: creatures that are flying, hovering, jumping or falling count as 'in the air' and touch no surface. Landing or clinging clears the state. Tremorsense excludes airborne creatures and objects.
    T-15   open     bug      PLAY.combat.cover: The Half/Three-Quarters Cover AC and save bonus is applied but no event carries rule=PLAY.combat.cover (T-9 traceability)
    T-16   open     bug      PLAY.combat.cover: A creature standing between attacker and target gives no Half Cover: cover comes only from scene.cover/cover_all labels
    T-17   open     infra    PLAY.combat.cover: PLAY.combat.cover: Obstacle geometry: scene objects with extent/height and a method that derives the cover degree (half / three-quarters / total) between an origin and a target from the objects and creatures in the line
    T-18   open     infra    PLAY.combat.cover: PLAY.combat.cover: Obstacle geometry: scene objects with extent/height and a method that derives the cover degree (half / three-quarters / total) between an origin and a target from the objects and creatures in the line
    T-19   open     infra    PLAY.combat.cover: PLAY.combat.cover: Cover lookup by point of origin (a position, not only a creature) for area effects and other effects that don't originate at the caster
    T-20   open     bug      SPELL.bless: Casting a V,S,M spell without its material component first stows the held weapon (free object interaction, log entry), then refuses
    T-21   open     bug      SPELL.bless: Bless's target cap is checked inside _bless, after the slot is spent and Concentration starts; the refusal also cites no page
    T-22   open     bug      SPELL.bless: Bless accepts a non-creature target and crashes instead of refusing it
    T-23   open     bug      SPELL.bless: death_save doesn't gather effects, so Bless adds no 1d4 to a Death Saving Throw

These tickets are (currently) found in loop/tickets folder, see below for accepting or rejecting them.


## report COVERAGE.md
    python -m scripts.srdloop report
    wrote loop/COVERAGE.md
