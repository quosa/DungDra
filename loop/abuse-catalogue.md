# Abuse catalogue

Ways a player could try to cheat the engine. The test designer checks each rule unit against
this list and adds new cheats as it finds them. A cheat is tested with
`assert_refused_cleanly`: the command is refused, cites a page, and changes nothing.

## Movement and position
- Moving through walls, closed doors or occupied spaces.
- Moving farther than Speed allows; Difficult Terrain for free; moving while Speed is 0.
- Standing up from Prone without spending movement; crawling at full speed.
- Standing up from Prone on another creature's turn, where no movement budget is checked.
- Moving while Prone with a Climb, Swim or Fly Speed instead of crawling, to dodge the crawl cost.
- Righting yourself with movement left over from before a Speed-0 condition, or by paying half
  your movement (after a Dash) instead of half your Speed.
- Teleporting or stepping to a position the rules don't allow.
- Dashing (or stacking a Speed bonus) to get movement while your Speed is 0 and can't increase.
- Spending movement left over from before you gained a Speed-0 condition mid-turn.
- Dragging a creature you aren't grappling, or one someone else is grappling, to move it for free.
- Dragging a grappled creature past what your Speed covers once the extra drag cost is counted.
- Escaping a Speed-0 condition with a special Speed (climbing, swimming or flying away while
  Grappled), using movement left over from before the condition started.

## Action economy
- Taking two actions, two Bonus Actions or two Reactions in one turn or round.
- Acting out of turn, or while Incapacitated, Paralyzed, Stunned or Unconscious.
- Reusing a once-per-turn benefit (Sneak Attack, Savage Attacker, a mastery property).
- Taking a readied Reaction and an Opportunity Attack in the same round, or keeping a readied
  action past the start of your next turn.
- Readying a Bonus Action, or an action plus movement, as one readied response; readying
  movement beyond your Speed.
- Readying out of turn, or after the turn's action is already spent.
- Casting two slot spells in one turn.
- Taking an action as a Bonus Action (Disengage, Hide, Dash) through a command flag without a
  feature that grants it (Nimble Escape, Cunning Action).
- An attack refused as out of reach or range that has already spent the Attack action.

## Resources
- Spending spell slots, Hit Dice, class-feature uses or ammunition that don't exist.
- Recovering resources without the rest that restores them; two Long Rests back to back.
- Negative, zero or huge quantities (buy −5 rations, move 1,000 feet, heal −3).

## Targets
- Targeting a hidden, invisible, unseen, dead or out-of-range creature.
- Naming yourself as "an ally" (Help on your own ability check, counting yourself as the ally
  next to the target for Sneak Attack), or naming an enemy as one (Help on a foe's check).
- Counting a creature on the other side, or one that is merely nearby, as an ally to switch on
  an ally-based benefit (Sneak Attack, Pack Tactics, Help on an attack roll).
- Targeting yourself, or an ally, where the rule says a creature you can see or an enemy.
- More targets than a spell or feature allows.
- Using a non-sight sense (Tremorsense, a sense that only pinpoints a location) as "a creature
  you can see": to cast a sight-targeted spell, to cancel the unseen-target Disadvantage, or to
  ignore Blinded.
- Attacking or casting a single-target spell at a creature behind Total Cover, or slipping it
  in as one of several targets of a multi-target spell (Magic Missile).
- Claiming cover against an attacker on the wrong side of it, or stacking two degrees of cover
  (Half + Half as +4, Half + Three-Quarters as +7).
- Using an obstruction that only covers a target from one attacker to protect it from all of them.
- Using a creature as Three-Quarters or Total Cover (a creature gives at most Half Cover).
- Shooting past a small creature (a Giant Rat in front of an Ogre) as if it gave no cover; or
  claiming a creature's Half Cover from one that stands behind the attacker, behind the target or
  off to the side instead of in the line between them.
- Keeping creature cover against every attacker once one attacker's line runs through a creature.
- Using the Sacred Flame exception (ignores Half and Three-Quarters Cover) to reach a target
  behind Total Cover.
- Using Tremorsense to detect a creature in the air (flying, jumping, falling), on a separate
  surface, or beyond its range.

## Spells and effects
- Casting while unable to speak (Verbal) or without a free hand (Somatic).
- Stacking the same effect twice; keeping Concentration on two spells.
- Dropping and recasting Concentration to reset a duration.
- Holding a readied spell while keeping Concentration on another spell.
- Readying a spell to get the slot back when the trigger never comes or Concentration breaks;
  readying a spell with no slot left; readying a Bonus Action or Reaction spell.
- Replacing a costed material component (Bless: a Holy Symbol worth 5+ GP) with a Component Pouch,
  a different focus, or the 2014 component (holy water).
- Meeting a costed component's minimum price with a cheaper copy of the item (a 4 GP Holy
  Symbol), by pooling several cheap copies, or by topping one up with a Component Pouch.
- Upcasting with a slot level the caster doesn't have, to buy extra targets.
- Naming the same creature twice in a multi-target spell to double its benefit (two Bless d4s).
- Pointing a creature-targeting spell at an object or a name that isn't a creature.
- Going over a spell's target cap, hoping the refusal only comes after the slot is spent and
  Concentration has started.
- Pointing an object-targeting spell (Light) at a creature.
- Naming yourself as the target of an object-targeting spell (Light on the caster), on the strength
  of "you can choose yourself", which covers only spells that target a creature.
- Probing a creature's type or immunities by casting at it and reading the refusal or the log
  (an invalid target must look like a successful save, with no save rolled).
- Getting the slot back by casting at an invalid target (the slot is still expended).
- Naming creatures for an area spell that the area can't hold: far from the point of origin,
  or on both sides of the caster for one Cone or Cube. Leaving creatures that are in the area
  off the list to spare them from a spell that hits every creature in it.
- Stretching an area by aiming it at a far point, or by upcasting a spell whose higher levels
  add only damage (a 15-foot Cone stays 15 feet long).
- Widening a Cone into a quarter-circle (width measured from the axis out to each side) by
  naming two creatures on its flanks, or aiming between them.
- Naming yourself for an area that starts from you, to aim it or to be in it.
- Aiming a Cube diagonally so a rotated Cube takes in more squares than its side allows on the
  grid (ten instead of 3×3 for 15 feet).
- Reading a Sphere's radius as its diameter or stretching it with a higher slot (Sleep's 5-foot
  radius reaching 10 feet), or using its "origin is included" rule to put the caster in a
  Sphere placed elsewhere, as if it were an Emanation from them.
- Naming a creature that is walled off (Total Cover) from an area's point of origin, so that the
  caller's list puts it in the area anyway.
- Judging an area's blocked lines from the wrong place: cover from the caster used against a
  Sphere placed elsewhere, or cover from a Cone's aim point used against a Cone that starts at the
  caster.
- Using a column of creatures, or a Three-Quarters obstruction (an arrow slit), as a wall that
  keeps an area out (only Total Cover blocks a line).
- Placing an area at an unseen point behind a wall so it erupts on the far side, instead of on
  the near side of the obstruction.
- Naming a far-off creature for an area spell that takes the caller's list instead of working out
  the area (Web's 20-foot Cube catching a creature 100 feet away).
- Claiming an "if the attack roll had Advantage" rider (a Goblin's extra 1d4) when Advantage and
  Disadvantage cancelled, or dropping it when the GM uses static damage numbers.
- A monster using an action its stat block doesn't list (a weapon from its Gear line it has no
  attack for, a trait like Nimble Escape that another monster has).

## Equipment
- Two shields; armor you lack training in with no penalty; wielding more weapons than hands.
- Attuning to more than three items.

## The interface
- Chained commands in one sentence ("attack the goblin twice", "cast and move").
- Naming a creature that doesn't exist, or matching one you can't see.
- A refused command that still costs the turn, a slot or a log entry.
- A refused command that still has a side effect on the way to the refusal (stowing a weapon
  to free a hand, using the free object interaction, ending Concentration on another spell).
