# Abuse catalogue

Ways a player could try to cheat the engine. The test designer checks each rule unit against
this list and adds new cheats as it finds them. A cheat is tested with
`assert_refused_cleanly`: the command is refused, cites a page, and changes nothing.

## Movement and position
- Moving through walls, closed doors or occupied spaces.
- Moving farther than Speed allows; Difficult Terrain for free; moving while Speed is 0.
- Standing up from Prone without spending movement; crawling at full speed.
- Teleporting or stepping to a position the rules don't allow.
- Dashing (or stacking a Speed bonus) to get movement while your Speed is 0 and can't increase.
- Spending movement left over from before you gained a Speed-0 condition mid-turn.
- Dragging a creature you aren't grappling, or one someone else is grappling, to move it for free.
- Dragging a grappled creature past what your Speed covers once the extra drag cost is counted.

## Action economy
- Taking two actions, two Bonus Actions or two Reactions in one turn or round.
- Acting out of turn, or while Incapacitated, Paralyzed, Stunned or Unconscious.
- Reusing a once-per-turn benefit (Sneak Attack, Savage Attacker, a mastery property).
- Casting two slot spells in one turn.

## Resources
- Spending spell slots, Hit Dice, class-feature uses or ammunition that don't exist.
- Recovering resources without the rest that restores them; two Long Rests back to back.
- Negative, zero or huge quantities (buy −5 rations, move 1,000 feet, heal −3).

## Targets
- Targeting a hidden, invisible, unseen, dead or out-of-range creature.
- Targeting yourself, or an ally, where the rule says a creature you can see or an enemy.
- More targets than a spell or feature allows.
- Using a non-sight sense (Tremorsense, a sense that only pinpoints a location) as "a creature
  you can see": to cast a sight-targeted spell, to cancel the unseen-target Disadvantage, or to
  ignore Blinded.
- Using Tremorsense to detect a creature in the air (flying, jumping, falling), on a separate
  surface, or beyond its range.

## Spells and effects
- Casting while unable to speak (Verbal) or without a free hand (Somatic).
- Stacking the same effect twice; keeping Concentration on two spells.
- Dropping and recasting Concentration to reset a duration.

## Equipment
- Two shields; armor you lack training in with no penalty; wielding more weapons than hands.
- Attuning to more than three items.

## The interface
- Chained commands in one sentence ("attack the goblin twice", "cast and move").
- Naming a creature that doesn't exist, or matching one you can't see.
- A refused command that still costs the turn, a slot or a log entry.
