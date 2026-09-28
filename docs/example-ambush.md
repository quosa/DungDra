# Example session: clearing the Forest Road ambush

This transcript was produced with `python -m dungdra --seed 5`, so you can replay it by typing the same commands. Whenever the game asks a question (Alert's Initiative swap, Savage Attacker, knocking a foe out instead of killing it), press Enter to accept the default. The `[choice]` lines in the transcript show where those questions come up. At level 1, four hidden goblin warriors are a deadly fight. Here's what wins it:

1. **Find them first.** The goblins start hidden (Invisible, Stealth 16) and attack with Advantage. `<PC> searches for hidden enemies` makes a Wisdom (Perception) check. On a 16 or higher, every goblin whose Stealth total it meets is revealed. A goblin also gives itself away when it attacks, though it may hide again.
2. **Focus fire.** Kill one goblin at a time (they have 10 HP). Target the most wounded one you can see.
   - MIALEE's `magic missile` never misses (3d4+3). Save `fire bolt` for finishing blows.
   - JOZAN's `sacred flame` forces a Dex save, so a goblin's AC 15 doesn't matter.
   - LIDDA's `shortbow` gets Sneak Attack once BROM stands next to the target.
3. **Keep everyone up.** `JOZAN casts healing word on <name>` is a Bonus Action, so JOZAN can still cast `sacred flame` the same turn. `BROM uses second wind` works when BROM is low. MIALEE's Shield is offered automatically when she's hit.
4. **Let BROM tank.** He has AC 19. `BROM moves 30 feet toward <goblin>` then `BROM attacks <goblin> with his longsword`, or `BROM throws a javelin at <goblin>` if he can't reach one.

The turn ends on its own once a character has nothing useful left to do. Otherwise, type `end turn`.

## Commands used

```
use the sample party
begin the adventure
go to the watchtower
LIDDA searches for hidden enemies
BROM searches for hidden enemies
MIALEE casts magic missile at Goblin Warrior 1
JOZAN casts sacred flame at Goblin Warrior 2
end turn
LIDDA shoots Goblin Warrior 2 with her shortbow
BROM moves 30 feet toward Goblin Warrior 2
BROM attacks Goblin Warrior 2 with his longsword
end turn
MIALEE casts magic missile at Goblin Warrior 3
JOZAN casts sacred flame at Goblin Warrior 4
end turn
LIDDA shoots Goblin Warrior 4 with her shortbow
BROM moves 30 feet toward Goblin Warrior 4
BROM attacks Goblin Warrior 4 with his longsword
end turn
MIALEE casts fire bolt at Goblin Warrior 4
JOZAN casts sacred flame at Goblin Warrior 4
end turn
LIDDA shoots Goblin Warrior 4 with her shortbow
```

## Full transcript

```
> use the sample party
The sample party joins you: BROM, LIDDA, MIALEE, JOZAN.
> begin the adventure
== Millbrook ==
Millbrook's square smells of bread and woodsmoke. The reeve has posted a notice: goblins have been raiding carts on the forest road east of the village, and whoever clears the old watchtower they use as a lair will be paid in coin. The general store is open if you need supplies.
(Say 'continue' or 'go to The Forest Road' to press on.)
> go to the watchtower
You set off toward The Ruined Watchtower; the way leads through The Forest Road first.
== The Forest Road ==
The road east narrows between old oaks. Six miles on, the trees crowd close and the birdsong stops. Broken cart wheels lie in the ditch.
The party travels 6 miles at a Normal pace through forest on a good road (2 hours)  [p.12]
2 hours of travel pass
Goblin Warrior 1 has the Invisible condition (Hide (Stealth 16))  [p.176-191]
Goblin Warrior 2 has the Invisible condition (Hide (Stealth 16))  [p.176-191]
Goblin Warrior 3 has the Invisible condition (Hide (Stealth 16))  [p.176-191]
Goblin Warrior 4 has the Invisible condition (Hide (Stealth 16))  [p.176-191]
Arrows hiss out of the undergrowth: goblins, hidden in the ferns!
Roll Initiative!  [p.13]
BROM Initiative (Dex check): d20=9 (disadvantage: 20/9) +2 Dex = 11; Disadvantage from surprised  [p.13]
LIDDA Initiative (Dex check): d20=12 (disadvantage: 12/17) +3 Dex +2 Alert (PB) = 17; Disadvantage from surprised  [p.13]
MIALEE Initiative (Dex check): d20=1 (disadvantage: 1/15) +1 Dex = 2; Disadvantage from surprised  [p.13]
JOZAN Initiative (Dex check): d20=2 (disadvantage: 8/2) −1 Dex = 1; Disadvantage from surprised  [p.13]
Goblin Warrior 1 Initiative (Dex check): d20=6 (advantage: 6/4) +2 Initiative = 8; Advantage from Invisible  [p.13]
Goblin Warrior 2 shares its group's Initiative 8  [p.13]
Goblin Warrior 3 shares its group's Initiative 8  [p.13]
Goblin Warrior 4 shares its group's Initiative 8  [p.13]
Tie at 8 between Goblin Warrior 1, Goblin Warrior 2, Goblin Warrior 3, Goblin Warrior 4; order decided by the GM (monsters)  [p.13]
[choice] LIDDA (Alert): swap Initiative with a willing ally? → None
Initiative order: LIDDA 17, BROM 11, Goblin Warrior 1 8, Goblin Warrior 2 8, Goblin Warrior 3 8, Goblin Warrior 4 8, MIALEE 2, JOZAN 1  [p.13]
Round 1: LIDDA's turn  [p.13]
→ It's LIDDA's turn (action available; 30 ft of movement left).
> LIDDA searches for hidden enemies
LIDDA Search: Wisdom (Perception) — LIDDA searches for hidden enemies: d20=12 +0 Wis +2 PB (Perception) = 14  [p.6]
LIDDA doesn't spot anyone hidden  [p.183]
(LIDDA has nothing more to do this turn, so the turn ends.)
Round 1: BROM's turn  [p.13]
→ It's BROM's turn (action available; 30 ft of movement left).
> BROM searches for hidden enemies
BROM Search: Wisdom (Perception) — BROM searches for hidden enemies: d20=16 +0 Wis +2 PB (Perception) = 18  [p.6]
Goblin Warrior 1: Hide (Stealth 16) ends (found by BROM)  [p.176-191]
Goblin Warrior 2: Hide (Stealth 16) ends (found by BROM)  [p.176-191]
Goblin Warrior 3: Hide (Stealth 16) ends (found by BROM)  [p.176-191]
Goblin Warrior 4: Hide (Stealth 16) ends (found by BROM)  [p.176-191]
BROM spots Goblin Warrior 1, Goblin Warrior 2, Goblin Warrior 3, Goblin Warrior 4  [p.183]
(BROM has nothing more to do this turn, so the turn ends.)
Round 1: Goblin Warrior 1's turn  [p.13]
Goblin Warrior 1 attack on BROM (Shortbow): d20=8 +4 Shortbow (stat block) = 12 vs AC 19 → miss  [p.14-15]
Goblin Warrior 1 Dexterity (Stealth) check to Hide: d20=4 +6 Stealth (stat block) = 10 vs DC 15 → failure  [p.183]
Round 1: Goblin Warrior 2's turn  [p.13]
Goblin Warrior 2 attack on BROM (Shortbow): d20=19 +4 Shortbow (stat block) = 23 vs AC 19 → hit  [p.14-15]
Goblin Warrior 2 deals 4 Piercing damage: 1d6+2: [2]  [p.16]
BROM takes 4 Piercing damage from Goblin Warrior 2's attack  [p.16-17]
Round 1: Goblin Warrior 3's turn  [p.13]
Goblin Warrior 3 attack on BROM (Shortbow): d20=1 +4 Shortbow (stat block) = 5 vs AC 19 → miss  [p.14-15]
Round 1: Goblin Warrior 4's turn  [p.13]
Goblin Warrior 4 attack on BROM (Shortbow): d20=14 +4 Shortbow (stat block) = 18 vs AC 19 → miss  [p.14-15]
Round 1: MIALEE's turn  [p.13]
→ It's MIALEE's turn (action available; 30 ft of movement left).
> MIALEE casts magic missile at Goblin Warrior 1
MIALEE casts Magic Missile with a level 1 slot [Wizard]  [p.146]
3 darts of magical force strike automatically  [p.146]
Goblin Warrior 1 takes 12 Force damage from Magic Missile  [p.16-17]
Goblin Warrior 1 dies (reduced to 0 HP)  [p.17]
(MIALEE has nothing more to do this turn, so the turn ends.)
Round 1: JOZAN's turn  [p.13]
→ It's JOZAN's turn (action available; Bonus Action: cast Healing Word; 30 ft of movement left).
> JOZAN casts sacred flame at Goblin Warrior 2
JOZAN stows the Mace to free a hand for the spell's gestures  [p.13]
JOZAN casts Sacred Flame (no slot) [Cleric]  [p.159]
Goblin Warrior 2 Dex save vs Sacred Flame (DC 13): d20=6 +2 Dex save (stat block) = 8 vs DC 13 → failure  [p.159]
Goblin Warrior 2 takes 2 Radiant damage from Sacred Flame  [p.16-17]
→ It's JOZAN's turn (action used; Bonus Action: cast Healing Word; 30 ft of movement left).
> end turn
Round 2: LIDDA's turn  [p.13]
→ It's LIDDA's turn (action available; 30 ft of movement left).
> LIDDA shoots Goblin Warrior 2 with her shortbow
LIDDA draws the Shortbow as part of the attack  [p.177]
LIDDA attack on Goblin Warrior 2 with Shortbow: d20=5 +3 Dex +2 PB = 10 vs AC 15 → miss  [p.14-15]
(LIDDA has nothing more to do this turn, so the turn ends.)
Round 2: BROM's turn  [p.13]
→ It's BROM's turn (action available; Bonus Action: Second Wind; 30 ft of movement left).
> BROM moves 30 feet toward Goblin Warrior 2
BROM moves 30 ft; 0 ft left  [p.14]
→ It's BROM's turn (action available; Bonus Action: Second Wind).
> BROM attacks Goblin Warrior 2 with his longsword
BROM attack on Goblin Warrior 2 with Longsword: d20=20 +3 Str +2 PB = 25 vs AC 15 → CRITICAL HIT  [p.14-15]
[choice] Use Savage Attacker (once per turn)? → True
[choice] Savage Attacker: use [8, 3] or [3, 1]? → [8, 3]
Savage Attacker: rolled [8, 3] and [3, 1]; uses [8, 3]  [p.87]
BROM deals 14 Slashing damage (CRITICAL): 1d8x2=[8, 3]; +3 Str  [p.16]
Goblin Warrior 2 takes 14 Slashing damage from BROM's attack  [p.16-17]
[choice] Knock Goblin Warrior 2 out instead of killing it? → False
Goblin Warrior 2 dies (reduced to 0 HP)  [p.17]
→ It's BROM's turn (action used; Bonus Action: Second Wind).
> end turn
Round 2: Goblin Warrior 3's turn  [p.13]
Goblin Warrior 3 attack on BROM (Shortbow): d20=1 +4 Shortbow (stat block) = 5 vs AC 19 → miss  [p.14-15]
Goblin Warrior 3 Dexterity (Stealth) check to Hide: d20=7 +6 Stealth (stat block) = 13 vs DC 15 → failure  [p.183]
Round 2: Goblin Warrior 4's turn  [p.13]
Goblin Warrior 4 attack on BROM (Shortbow): d20=6 +4 Shortbow (stat block) = 10 vs AC 19 → miss  [p.14-15]
Round 2: MIALEE's turn  [p.13]
→ It's MIALEE's turn (action available; 30 ft of movement left).
> MIALEE casts magic missile at Goblin Warrior 3
MIALEE casts Magic Missile with a level 1 slot [Wizard]  [p.146]
3 darts of magical force strike automatically  [p.146]
Goblin Warrior 3 takes 11 Force damage from Magic Missile  [p.16-17]
Goblin Warrior 3 dies (reduced to 0 HP)  [p.17]
(MIALEE has nothing more to do this turn, so the turn ends.)
Round 2: JOZAN's turn  [p.13]
→ It's JOZAN's turn (action available; Bonus Action: cast Healing Word; 30 ft of movement left).
> JOZAN casts sacred flame at Goblin Warrior 4
JOZAN casts Sacred Flame (no slot) [Cleric]  [p.159]
Goblin Warrior 4 Dex save vs Sacred Flame (DC 13): d20=7 +2 Dex save (stat block) = 9 vs DC 13 → failure  [p.159]
Goblin Warrior 4 takes 4 Radiant damage from Sacred Flame  [p.16-17]
→ It's JOZAN's turn (action used; Bonus Action: cast Healing Word; 30 ft of movement left).
> end turn
Round 3: LIDDA's turn  [p.13]
→ It's LIDDA's turn (action available; 30 ft of movement left).
> LIDDA shoots Goblin Warrior 4 with her shortbow
LIDDA attack on Goblin Warrior 4 with Shortbow: d20=6 +3 Dex +2 PB = 11 vs AC 15 → miss  [p.14-15]
(LIDDA has nothing more to do this turn, so the turn ends.)
Round 3: BROM's turn  [p.13]
→ It's BROM's turn (action available; Bonus Action: Second Wind; 30 ft of movement left).
> BROM moves 30 feet toward Goblin Warrior 4
BROM moves 10 ft; 20 ft left  [p.14]
→ It's BROM's turn (action available; Bonus Action: Second Wind; 20 ft of movement left).
> BROM attacks Goblin Warrior 4 with his longsword
BROM attack on Goblin Warrior 4 with Longsword: d20=7 +3 Str +2 PB = 12 vs AC 15 → miss  [p.14-15]
→ It's BROM's turn (action used; Bonus Action: Second Wind; 20 ft of movement left).
> end turn
Round 3: Goblin Warrior 4's turn  [p.13]
Goblin Warrior 4 attack on BROM (Scimitar): d20=13 +4 Scimitar (stat block) = 17 vs AC 19 → miss  [p.14-15]
Round 3: MIALEE's turn  [p.13]
→ It's MIALEE's turn (action available; 30 ft of movement left).
> MIALEE casts fire bolt at Goblin Warrior 4
MIALEE casts Fire Bolt (no slot) [Wizard]  [p.132]
MIALEE spell attack (Fire Bolt) on Goblin Warrior 4: d20=10 +5 spell attack bonus = 15 vs AC 15 → hit  [p.106]
Goblin Warrior 4 takes 1 Fire damage from Fire Bolt  [p.16-17]
(MIALEE has nothing more to do this turn, so the turn ends.)
Round 3: JOZAN's turn  [p.13]
→ It's JOZAN's turn (action available; Bonus Action: cast Healing Word; 30 ft of movement left).
> JOZAN casts sacred flame at Goblin Warrior 4
JOZAN casts Sacred Flame (no slot) [Cleric]  [p.159]
Goblin Warrior 4 Dex save vs Sacred Flame (DC 13): d20=12 +2 Dex save (stat block) = 14 vs DC 13 → success  [p.159]
→ It's JOZAN's turn (action used; Bonus Action: cast Healing Word; 30 ft of movement left).
> end turn
Round 4: LIDDA's turn  [p.13]
→ It's LIDDA's turn (action available; 30 ft of movement left).
> LIDDA shoots Goblin Warrior 4 with her shortbow
LIDDA attack on Goblin Warrior 4 with Shortbow: d20=14 +3 Dex +2 PB = 19 vs AC 15 → hit  [p.14-15]
Sneak Attack (BROM is within 5 ft of Goblin Warrior 4): 1d6 = [2]  [p.61]
LIDDA deals 7 Piercing damage: 1d6=[2]; +3 Dex; +2 Sneak Attack  [p.16]
Goblin Warrior 4 takes 7 Piercing damage from LIDDA's attack  [p.16-17]
Goblin Warrior 4 dies (reduced to 0 HP)  [p.17]
Combat ends after 4 rounds (the fight is over)  [p.14]
200 XP for defeating or neutralizing foes, divided among 4 PCs: 50 each  [p.255, R-02]
BROM gains 50 XP (total 50) — defeating or neutralizing foes  [p.23, R-02]
LIDDA gains 50 XP (total 50) — defeating or neutralizing foes  [p.23, R-02]
MIALEE gains 50 XP (total 50) — defeating or neutralizing foes  [p.23, R-02]
JOZAN gains 50 XP (total 50) — defeating or neutralizing foes  [p.23, R-02]
```
