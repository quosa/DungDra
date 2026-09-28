# Golden Scenarios for an Autonomous D&D Play Harness

**Rules source:** System Reference Document 5.2.1 (SRD 5.2.1, the 2024 "5.5e" rules), 364 pages. All page references (`p.N`) point to that PDF.
**Purpose:** Success criteria for a loop-engineered, rules-faithful single-player D&D game built with Claude Code. An LLM plays, the engine resolves, assertions check.
**Version:** 2026-09-27 · supersedes the earlier Basic Rules (2014) draft.

> **License note (CC-BY-4.0).** The SRD may be used freely, but the game and any repo that includes SRD text or data **must** include this attribution statement verbatim (SRD p.1):
> *"This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode."*
> Don't add any other attribution to Wizards. You may say "compatible with fifth edition" or "5E compatible".

---

## 1. Scope restriction: the target subset (read first)

**Principle: implement all of the rules, but only a subset of the content.** The core rules and the Rules Glossary together are the engine. Implement them completely, because the rules are interlocked. Everything else is content, loaded as data. This subset is a thin vertical slice: it exercises every rule once and yields a playable game. Adding more content later should be data entry, not engine work.

### 1.1 In scope

| Area | In the first slice | SRD pages |
|---|---|---|
| **Core rules (all of them)** | Playing the Game: D20 Tests, Advantage/Disadvantage, Proficiency, Actions, Social Interaction, Exploration, Travel, Combat, Damage & Healing | p.5–18 |
| **Rules Glossary (all of it)** | Every definition, all 15 conditions, hazards, rests, areas of effect, Unarmed Strike (grapple/shove), Influence, Hide, etc. | p.176–191 |
| Levels | **1–3 only** (XP 0 / 300 / 900; Proficiency Bonus +2 throughout) | p.23 |
| Character creation | Standard Array, Point Cost, Random Generation; background ability adjustments; alignment; languages | p.19–23 |
| Classes | **Fighter** (Champion), **Rogue** (Thief), **Cleric** (Life Domain), **Wizard** (Evoker), features for levels 1–3 only | p.36–40, 47–49, 61–64, 77–82 |
| Species | **Human, Dwarf, Elf** (all three lineages), **Halfling** | p.83–86 |
| Backgrounds | **All four:** Acolyte, Criminal, Sage, Soldier | p.83 |
| Feats | **Origin:** Alert, Magic Initiate, Savage Attacker, Skilled. **Fighting Style:** Archery, Defense, Great Weapon Fighting, Two-Weapon Fighting | p.87–88 |
| Equipment | All weapons (incl. **mastery properties**), all armor and Shield, tools used by the fixtures, core gear (Healer's Kit, Potion of Healing, Torch, Rations, Iron Spikes, Component Pouch, Holy Symbol, packs), coins, lifestyle, crafting nonmagical items | p.89–103 |
| Spellcasting rules | All of "Spells" rules | p.104–106 |
| Spells (32) | **Cantrips (10):** Fire Bolt, Guidance, Light, Mage Hand, Minor Illusion, Prestidigitation, Ray of Frost, Sacred Flame, Spare the Dying, Thaumaturgy. **Level 1 (14):** Bless, Burning Hands, Command, Cure Wounds, Detect Magic, Guiding Bolt, Healing Word, Mage Armor, Magic Missile, Sanctuary, Shield, Shield of Faith, Sleep, Thunderwave. **Level 2 (8):** Aid, Hold Person, Invisibility, Lesser Restoration, Misty Step, Scorching Ray, Spiritual Weapon, Web | p.107–175 |
| Monsters (14) | Bandit, Cultist, Giant Rat, Goblin Minion, Goblin Warrior, Goblin Boss, Guard, Kobold Warrior, Ogre, Priest Acolyte, Riding Horse (mount), Skeleton, Wolf, Zombie | p.254–364 |
| Gameplay Toolbox | Travel Pace/terrain/extended travel, Poison (incl. Serpent Venom), Traps (Collapsing Roof, Falling Net, Hidden Pit, Poisoned Needle, Spiked Pit), Combat Encounter budget | p.192, 197–203 |
| Magic items (7) | Potion of Healing, Weapon +1, Armor +1, Spell Scroll (levels 0–2), Wand of Magic Missiles, Cloak of Protection (attunement), Bag of Holding | p.99, 204–253 |

### 1.2 Out of scope for now

- The other 8 classes and their subclasses.
- Levels 4 and above, including ASI feats, General and Epic Boon feats, and Extra Attack.
- Multiclassing.
- Dragonborn, Gnome, Goliath, Orc and Tiefling.
- Spells above level 2 and the other 76 spells of levels 0–2.
- The remaining monsters, including every creature with Legendary Actions or Legendary Resistance (all of them are far above CR 3).
- Curses and magical contagions, fear and mental stress, and environmental effects beyond the hazards in the glossary.
- Vehicles, hirelings, and scribing Spell Scrolls or brewing potions.
- The remaining magic items, and sentient or cursed items.

**Subset rules the engine must enforce.** XP keeps accruing past 900, but a character doesn't advance beyond level 3. The game reports "level 4+ is out of scope". Content outside the subset is refused with a clear message, never improvised.

### 1.3 Rulings register (gaps in the SRD)

The engine must implement each of these as an explicit, logged ruling. The judge treats them as correct only when the ruling ID appears in the event log.

| ID | Gap | Proposed ruling |
|---|---|---|
| R-01 | The SRD 5.2.1 has no rule for gaining the same proficiency twice. For example, the Rogue class and the Criminal background both grant Thieves' Tools. | The player picks a different tool proficiency instead. |
| R-02 | The SRD says XP is awarded for defeating or neutralizing a monster (p.255) but doesn't say how XP is shared. | Divide the total evenly among participating PCs, rounding down. |
| R-03 | The encounter rules build encounters to a budget (p.202). There's no label for an encounter whose XP exceeds the High budget. Such encounters can only come from authored content or GM improvisation, because generated encounters are built within budget. | The engine flags it as **"Over High budget"** in the **GM log only**, with the ruling ID, and never shows the flag to the player. If the GM improvises reinforcements, the engine blocks the over-budget addition or requires a logged justification. Danger is conveyed to the player **in the fiction** (SRD "Powerful Creatures" guidance, p.203), not as a number. |

---

## 2. How to read a scenario

- **ID** has the form `<SECTION>-<nn>`. Section IDs are listed in §3.
- **Tests** gives the sections and SRD pages this scenario exercises. A failure points there first.
- **Depends on** lists the sections that must be green before this scenario means anything. If a dependency is red, mark the scenario **blocked**, not failed.
- **Setup** gives fixtures, state and **forced dice**, written as `d20=[11,4]; d8=[5]`. Forced dice are consumed in order, then the seeded RNG takes over.
- **Journey** is what the player agent says or does, in plain language.
- **Pass** criteria come in two kinds. **[H]** is a hard assertion on state or the event log. **[S]** is a soft assertion scored by an LLM judge against the transcript.

### 2.1 Harness contract

1. **Dice injection.** Forced results can be queued per die type, then fall back to a seeded RNG.
2. **State snapshot.** State is exported as JSON: characters, monsters, initiative, conditions, resources (slots, uses, charges, Hit Dice, Heroic Inspiration), inventory, coins, clock, location and attunement.
3. **Event log.** Each roll lists all modifiers with their sources (`attack d20=10 +3 Str +2 PB = 15 vs AC 15 → hit`). The log also records state diffs, SRD page references and ruling IDs. Every entry is tagged **player-visible** or **GM-only**; GM tools such as encounter budgets and hidden DCs stay GM-only.
4. **Two interfaces.** There's a natural-language interface (what you play) and a structured command API (fast tests). A scenario is green only if it passes through both.
5. **Roles.** The **player agent** (an LLM) issues intents. The **engine** owns every number. An optional **narrator/GM** (an LLM) describes events and runs monsters and NPCs but can't change state. The **judge** (an LLM) scores [S] criteria only.
6. **Subset guard.** The engine refuses anything outside the subset in §1 with a clear message.

---

## 3. Section IDs and build order

| ID | Section | SRD pages | Depends on | Wave |
|---|---|---|---|---|
| CORE | D20 Tests, ability modifiers, Advantage/Disadvantage, Proficiency, Heroic Inspiration, round down, "exceptions supersede" | 5–9 | none | 1 |
| COND | Conditions (all 15) | 176–191 | CORE | 2 |
| ACT | Actions (Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize), Bonus Actions, Reactions | 9–10, 176–191 | CORE | 2 |
| ORIG | Backgrounds and species | 83–86 | CORE | 2 |
| FEAT | Origin and Fighting Style feats | 87–88 | CORE | 2 |
| EQP | Weapons, mastery, armor, tools, gear, coins, lifestyle, crafting | 89–103 | CORE | 2 |
| CLS-FTR / CLS-ROG / CLS-CLR / CLS-WIZ | The four classes, levels 1–3 | 36–82 | CORE, FEAT | 2 |
| CC | Character creation and level advancement | 19–24 | ORIG, FEAT, EQP, CLS-* | 3 |
| EXPL | Exploration, vision and light, hiding, objects, travel, jumping and climbing | 11–12, 192 | CC, COND | 4 |
| SOC | Social interaction, attitudes, Influence | 10–11, 184 | CC, ACT | 4 |
| CMB | Combat: initiative, turns, movement, attacks, cover, OA, grapple/shove, mounted, underwater | 13–16 | CC, ACT, COND, EQP | 4 |
| DMG | Damage, resistance, healing, dropping to 0, death saves, temp HP | 16–18 | CMB | 4 |
| REST | Short and Long Rest | 185, 187 | CC, DMG | 4 |
| HAZ | Burning, dehydration, falling, malnutrition, suffocation, exhaustion | 178–189 | COND, REST | 5 |
| SPL | Spellcasting rules | 104–106 | CLS-CLR, CLS-WIZ, CMB | 5 |
| MON | Monster stat blocks and traits | 254–364 | CMB, DMG, COND | 5 |
| SPELLS | The 32 subset spells | 107–175 | SPL, COND | 6 |
| ENC | Combat encounter budget | 202–203 | MON | 6 |
| TRAP | Traps | 199–201 | EXPL, CMB, DMG | 6 |
| POIS | Poisons | 197–198 | COND, DMG | 6 |
| MI | Magic items | 204–253 | REST, SPL, SPELLS | 7 |
| J | End-to-end journeys | all | everything | 8 |

---

## 4. Shared fixtures

Every fixture uses the **Standard Array by Class** (p.21) and background adjustments of +2/+1 (p.83). LIDDA, MIALEE and JOZAN take package A from their class and background. BROM takes the Fighter's gold option and buys his gear, because no Fighter package combines Chain Mail, a Shield and a one-handed weapon (p.47); the SRD allows spending starting coins on equipment immediately (p.20). All are level 1 with Proficiency Bonus +2. The expected values below are the oracle: if the engine derives anything different, CC, ORIG or CLS is broken.

| Fixture | Build | Expected values |
|---|---|---|
| **BROM** | Dwarf Fighter 1, Soldier. Base array Str 15, Dex 14, Con 13, Int 8, Wis 10, Cha 12; Soldier +2 Str, +1 Con → **Str 17, Dex 14, Con 14, Int 8, Wis 10, Cha 12**. Fighting Style: **Defense**. Savage Attacker (Soldier). Skills: Athletics, Intimidation (Soldier) + Perception, Survival (Fighter). Weapon Mastery: Longsword, Javelin, Glaive. **Starting equipment:** Fighter option C (155 GP), spent at list price on Chain Mail 75, Shield 10, Longsword 15, Glaive 20, 4 Javelins 2 (5 SP each), Dungeoneer's Pack 12 → 21 GP left; plus Soldier package A (Spear, Shortbow, 20 Arrows, gaming set, Healer's Kit, Quiver, Traveler's Clothes, 14 GP). | **HP 13** (10 + 2 Con + 1 Dwarven Toughness); level 2 = 22, level 3 = 31. **AC 19** (Chain Mail 16 + Shield 2 + Defense 1). Speed 30. Darkvision 120 ft. Initiative +2. Longsword **+5**, 1d8+3 Slashing (1d10+3 two-handed), mastery Sap. Str save +5, Con save +4. Athletics +5. **Passive Perception 12**. Grapple/Shove DC **13**. Disadvantage on Stealth (Chain Mail). **Coins: 35 GP.** |
| **LIDDA** | Halfling Rogue 1, Criminal. Base Str 12, Dex 15, Con 13, Int 14, Wis 10, Cha 8; Criminal +2 Dex, +1 Con → **Str 12, Dex 17, Con 14, Int 14, Wis 10, Cha 8**. Alert (Criminal). Skills: Sleight of Hand, Stealth (Criminal) + Acrobatics, Deception, Investigation, Perception (Rogue). Expertise: Stealth, Sleight of Hand. Thieves' Tools (+ R-01 replacement tool). Weapon Mastery: Shortsword (Vex), Dagger (Nick). Gear: Leather Armor, Shortsword, 2 Daggers, Shortbow, 20 Arrows, Thieves' Tools. | **HP 10**; level 2 = 17, level 3 = 24. **AC 14**. Small, Speed 30. **Initiative +5** (Dex 3 + Alert PB 2). Shortsword **+5**, 1d6+3 Piercing. Sneak Attack **1d6**. **Stealth +7**, Sleight of Hand +7. Passive Perception 12. Carry 180 lb, drag/lift/push 360 lb. |
| **MIALEE** | Elf (High Elf lineage, Int) Wizard 1, Sage. Base Str 8, Dex 12, Con 13, Int 15, Wis 14, Cha 10; Sage +2 Int, +1 Con → **Str 8, Dex 12, Con 14, Int 17, Wis 14, Cha 10**. Keen Senses: Perception. Cantrips: Fire Bolt, Mage Hand, Light (class); Prestidigitation (High Elf); Magic Initiate (Wizard, Int): Ray of Frost, Minor Illusion + **Thunderwave** (1 free cast per Long Rest). Spellbook (6): Magic Missile, Shield, Sleep, Burning Hands, Mage Armor, Detect Magic. Prepared (4): Magic Missile, Shield, Sleep, Mage Armor. Skills: Arcana, History (Sage) + Investigation, Medicine (Wizard). | **HP 8**; level 2 = 14, level 3 = 20. **AC 11** (14 with Mage Armor). Speed 30. Darkvision 60 ft. **Spell save DC 13, spell attack +5**. Slots: 2 × level 1. Int save +5, Wis save +4. **Passive Perception 14**. |
| **JOZAN** | Human (Medium) Cleric 1, Acolyte. Base Str 14, Dex 8, Con 13, Int 10, Wis 15, Cha 12; Acolyte +2 Wis, +1 Cha → **Str 14, Dex 8, Con 13, Int 10, Wis 17, Cha 13**. Divine Order: **Protector**. Magic Initiate (Cleric, Wis): Light, Thaumaturgy + **Command**. Versatile: Skilled (Athletics, Survival, Woodcarver's Tools). Skillful: Perception. Skills: Insight, Religion (Acolyte) + Medicine, Persuasion (Cleric). Cantrips: Sacred Flame, Guidance, Spare the Dying. Prepared (4): Bless, Cure Wounds, Healing Word, Guiding Bolt. Gear: Cleric package A (Chain Shirt, Shield, Mace, Holy Symbol, Priest's Pack, 7 GP). | **HP 9**; level 2 = 15, level 3 = 21. **AC 14** (Chain Shirt 13 − 1 Dex + Shield 2). Speed 30. Mace +4, 1d6+2 (no Weapon Mastery). **Spell save DC 13, spell attack +5**. Slots: 2 × level 1. Wis save +5, Cha save +3. Medicine +5. **Passive Perception 15**. Heroic Inspiration after each Long Rest. |

**Monster fixtures** (the numbers the scenarios rely on):

| Monster | Key values |
|---|---|
| Goblin Warrior | AC 15, HP 10, Initiative +2, Stealth +6, Dex save +2, Wis save −1. Scimitar +4, 1d6+2 (+1d4 if the attack had Advantage). **Nimble Escape** (Bonus Action: Disengage or Hide). CR 1/4, 50 XP. |
| Goblin Boss | AC 17, HP 21, Multiattack (2). **Redirect Attack** reaction (swaps places with a Small or Medium ally within 5 ft, which becomes the target). CR 1, 200 XP. |
| Goblin Minion | AC 12, HP 7. CR 1/8, 25 XP. |
| Wolf | AC 12, HP 11, **Pack Tactics**. Bite +4, 1d6+2; a Medium or smaller target gets the **Prone** condition (no save). CR 1/4, 50 XP. |
| Zombie | AC 8, HP 15, Con save +3. **Undead Fortitude** (DC 5 + damage; not vs Radiant damage or Critical Hits). Immune to Poison damage and to the Exhaustion and Poisoned conditions. CR 1/4, 50 XP. |
| Skeleton | AC 14, HP 13. **Vulnerable to Bludgeoning**. Immune to Poison damage and to Exhaustion and Poisoned. Shortsword +5, 1d6+3. CR 1/4, 50 XP. |
| Kobold Warrior | AC 14, HP 7, Pack Tactics, **Sunlight Sensitivity**. CR 1/8, 25 XP. |
| Giant Rat | AC 13, HP 7, Pack Tactics. Bite +5, 1d4+3. CR 1/8, 25 XP. |
| Bandit | AC 12, HP 11, Wis save +0. Humanoid. CR 1/8, 25 XP. |
| Cultist | AC 12, HP 9, Wis save +2. Ritual Sickle 1d4+1 Slashing + 1 Necrotic. CR 1/8, 25 XP. |
| Guard | AC 16, HP 11. CR 1/8, 25 XP. |
| Priest Acolyte | AC 13, HP 11. Divine Aid 1/Day (Bless, Healing Word or Sanctuary). CR 1/4, 50 XP. |
| Ogre | Large Giant, AC 11, HP 68, Int 5. Greatclub +6, 2d8+4. CR 2, 450 XP. |
| Riding Horse | Large Beast, AC 11, HP 13, Speed 60. Hooves +5, 1d8+3. CR 1/4, 50 XP. Used as a mount. |

Creature types matter: **goblins are Fey (Goblinoid)** in SRD 5.2.1 (p.290), not Humanoid. Only the Bandit, Cultist, Guard and Priest Acolyte are Humanoids here (relevant to Hold Person).

---

## 5. Scenarios by section

### CORE: D20 Tests and core conventions (p.5–9)

#### CORE-01 · Ability modifiers and rounding
- **Tests:** CORE (Ability Modifiers p.6; Round Down p.5)
- **Depends on:** none
- **Journey:** Query the modifier for every score from 1 to 30. Compute half of 17 and one third of 10.
- **Pass:**
  - [H] Modifiers follow the table: 1→−5, 2–3→−4, 8–9→−1, 10–11→+0, 16–17→+3, 20–21→+5, 30→+10 (equivalently, floor((score−10)/2)).
  - [H] Division **and multiplication** round down: 17/2 = 8 and 10/3 = 3.

#### CORE-02 · Advantage, Disadvantage and rerolls
- **Tests:** CORE (Advantage/Disadvantage p.7–8; Heroic Inspiration p.8), ORIG (Halfling Luck p.86)
- **Depends on:** CORE-01
- **Setup:** Forced d20s per case.
- **Journey:** (a) One source of Advantage, `d20=[18,3]`. (b) Two sources of Advantage and one of Disadvantage, `d20=[7]`. (c) Three Advantage sources, `d20=[4,15]`. (d) JOZAN, with Heroic Inspiration and Advantage on a check, rolls `d20=[3,18]` and spends Inspiration, `d20=[11]`. (e) LIDDA, with Disadvantage, rolls `d20=[1,12]`; she uses Luck, `d20=[9]`.
- **Pass:**
  - [H] (a) The roll uses 18.
  - [H] (b) Exactly one d20 is rolled; any mix of Advantage and Disadvantage cancels out.
  - [H] (c) Only two d20s are rolled, and the roll uses 15.
  - [H] (d) Only one die is rerolled, chosen by the player. Inspiration is consumed, and he can't hold two instances.
  - [H] (e) Only the die showing 1 is rerolled, so the dice become 9 and 12; with Disadvantage the result is 9. Luck is optional ("can reroll"): the engine offers it and doesn't auto-apply it.
  - [H] The event log names every source of Advantage and Disadvantage.

#### CORE-03 · Ability checks, proficiency, Expertise and tools
- **Tests:** CORE (Ability Checks p.6; Proficiency p.8–9; Tool proficiency p.9), EQP (Tools p.93–94), Glossary (Expertise p.182)
- **Depends on:** CC
- **Setup:** `d20=[10]` for each check.
- **Journey:** BROM makes an Athletics check. LIDDA makes a Stealth check. MIALEE makes an Athletics check. LIDDA picks a DC 15 lock with Thieves' Tools, which uses Dexterity and involves Sleight of Hand.
- **Pass:**
  - [H] BROM gets 15 (10 + 3 + 2).
  - [H] LIDDA's Stealth is 17 (10 + 3 + 4), with Expertise doubling PB only once.
  - [H] MIALEE gets 9 (10 − 1, no PB).
  - [H] On the lock, LIDDA adds her PB once (proficiency doesn't stack, p.8). Because she is proficient with both the tool and the relevant skill, she rolls **with Advantage**.
  - [H] Without Thieves' Tools the attempt is refused.

#### CORE-04 · Passive Perception
- **Tests:** CORE, CC (Passive Perception p.22), Glossary (p.186)
- **Depends on:** CC
- **Journey:** A creature has a Stealth total of 13. Compare it with each fixture's Passive Perception. Then repeat with MIALEE in Dim Light (Disadvantage on sight-based Perception).
- **Pass:**
  - [H] Passive Perception is 12 for BROM, 12 for LIDDA, 14 for MIALEE and 15 for JOZAN. Only MIALEE and JOZAN notice the creature.
  - [H] In Dim Light MIALEE's score drops to 9 (−5), and she no longer notices.

#### CORE-05 · Saving throws
- **Tests:** CORE (Saving Throws p.7), Glossary (Saving Throw p.187)
- **Depends on:** CC
- **Journey:** BROM makes a Con save (proficient) and a Wis save (not proficient). A save shows a natural 20, another a natural 1. A player chooses to fail a save.
- **Pass:**
  - [H] Proficiency is added only to proficient saves: BROM's Con save is +4 and his Wis save +0.
  - [H] Natural 20s and 1s have **no automatic effect** on saves; auto-hit and auto-miss apply only to attack rolls (p.7).
  - [H] A player may choose to fail a save without rolling.
  - [H] A creature that lacks the relevant ability score fails the save automatically (objects, p.178).

#### CORE-06 · The Help action
- **Tests:** ACT (Help p.182–183)
- **Depends on:** CORE-03
- **Journey:** (a) BROM, proficient in Athletics, Helps LIDDA's Athletics check. (b) BROM tries to Help LIDDA's Thieves' Tools check without that proficiency. (c) JOZAN Helps BROM's attack on a goblin within 5 ft of JOZAN. (d) JOZAN tries (c) against a goblin 10 ft away.
- **Pass:**
  - [H] (a) LIDDA has Advantage on her next Athletics check before the start of BROM's next turn.
  - [H] (b) Refused: a helper must choose a skill or tool they are proficient in.
  - [H] (c) The next ally attack against that enemy has Advantage and expires at the start of JOZAN's next turn.
  - [H] (d) Refused.

---

### CC: Character creation and advancement (p.19–24)

#### CC-01 · Create a character by conversation
- **Tests:** CC (Steps 1–5 p.19–23), ORIG, FEAT, CLS-FTR, EQP
- **Depends on:** ORIG, FEAT, EQP, CLS-FTR
- **Journey:** The player says: *"A dwarf fighter, ex-soldier, standard array with Str 15, Dex 14, Con 13, Wis 10, Cha 12, Int 8. Put +2 in Strength and +1 in Constitution. Defense style. Chain mail, shield and longsword."*
- **Pass:**
  - [H] The final sheet equals **BROM** field for field (§4).
  - [H] Because no Fighter package matches the request, the game offers option C (155 GP) and lets the player buy the gear at list prices (p.20, p.91–95). Purchases that exceed the remaining gold are refused.
  - [H] After the purchases and the Soldier package, BROM has **35 GP**.
  - [H] The game asks for any unanswered required choice (languages, skills, Weapon Mastery, gaming set).
  - [H] The sheet can't be finalized while a required step is missing.
  - [S] The game doesn't re-ask choices the player already made.

#### CC-02 · Ability score generation and background adjustments
- **Tests:** CC (Generate Your Scores; Adjust Ability Scores p.21), ORIG (Backgrounds p.83)
- **Depends on:** CORE
- **Setup:** `d6=[6,5,1,3]` for the first rolled score.
- **Journey:** (a) Random Generation. (b) A Point Cost build costing 28 points, then one with a score of 16. (c) Standard Array with 15 used twice. (d) A Soldier putting +2 into Wisdom. (e) A Soldier choosing +1/+1/+1. (f) A background increase that would push a score to 21.
- **Pass:**
  - [H] (a) The first score is 14 (drop the lowest die).
  - [H] (b) Both builds are rejected. The cost table is 8=0 … 13=5, 14=7, 15=9; the budget is 27 and the maximum is 15.
  - [H] (c) Rejected.
  - [H] (d) Rejected: a Soldier may only increase Str, Dex or Con.
  - [H] (e) Accepted.
  - [H] (f) Capped: no score can exceed 20.

#### CC-03 · Level advancement from 1 to 3 and the subset cap
- **Tests:** CC (Level Advancement p.23; Fixed Hit Points p.23), CLS-* (level 2–3 features)
- **Depends on:** CLS-FTR, CLS-ROG, CLS-CLR, CLS-WIZ
- **Journey:** Award each fixture 300 XP and then 900 XP, using fixed HP. Then award 2,700 XP.
- **Pass:**
  - [H] BROM's HP goes 13 → 22 → 31, LIDDA's 10 → 17 → 24, MIALEE's 8 → 14 → 20 and JOZAN's 9 → 15 → 21.
  - [H] PB stays +2.
  - [H] New features appear at the listed levels: Action Surge and Tactical Mind (Fighter 2), Cunning Action (Rogue 2), Channel Divinity (Cleric 2), Scholar (Wizard 2), and a subclass prompt at level 3.
  - [H] At level 2 the Wizard adds 2 spells to the spellbook (p.78).
  - [H] At 2,700 XP the XP is recorded, but the level stays 3 and the game reports that level 4+ is out of scope.

#### CC-04 · Languages
- **Tests:** CC (Choose Languages p.20), CLS-ROG (Thieves' Cant p.62)
- **Depends on:** CC-01
- **Pass:**
  - [H] Every PC knows Common plus two standard languages.
  - [H] LIDDA also knows Thieves' Cant and one extra language.
  - [H] Rare languages can't be picked at creation without a feature that grants them.

---

### ORIG: Species and backgrounds (p.83–86)

#### ORIG-01 · Species traits load correctly
- **Tests:** ORIG (Dwarf, Elf, Halfling, Human p.84–86)
- **Depends on:** CORE
- **Pass:**
  - [H] **Dwarf:** Speed 30, Darkvision 120, Resistance to Poison damage, Advantage on saves to avoid or end the Poisoned condition, +1 HP per level, Stonecunning (Bonus Action, Tremorsense 60 ft for 10 min, PB uses per Long Rest, only on stone).
  - [H] **Elf:** Darkvision 60 (120 for Drow), lineage cantrip, Keen Senses (Insight, Perception or Survival), Fey Ancestry (Advantage vs Charmed), Trance (Long Rest in 4 hours; immune to magical sleep). Lineage spells at levels 3 and 5 are always prepared and castable once per Long Rest without a slot.
  - [H] **Halfling:** Small, Speed 30, Brave, Nimbleness, Luck, Naturally Stealthy.
  - [H] **Human:** Small or Medium, Resourceful (Heroic Inspiration on each Long Rest), Skillful (+1 skill), Versatile (+1 Origin feat).

#### ORIG-02 · Dwarven Resilience: resistance always, Advantage only against the Poisoned condition
- **Tests:** ORIG (Dwarven Resilience p.84), POIS (Serpent Venom p.198), TRAP (Poisoned Needle p.200–201), DMG (Resistance p.17)
- **Depends on:** CORE-05, DMG
- **Journey:** (a) BROM is hit by a weapon coated in Serpent Venom (DC 11 Con, 3d6 Poison, half on success; no Poisoned condition). Dice: `d20=[5]; d6=[4,4,4]`. (b) BROM triggers a Poisoned Needle (DC 11 Con; 1d10 Poison and the Poisoned condition for 1 hour; half damage only on a success). Dice: `d20=[3,15]; d10=[8]`.
- **Pass:**
  - [H] (a) **No Advantage**: exactly one d20 is consumed, because this save doesn't avoid the Poisoned condition. 5 + 4 = 9 fails; 12 damage is halved by Resistance to **6**.
  - [H] (b) The save has Advantage and uses 15, so 15 + 4 = 19 succeeds. Damage is 8, halved for the save to 4, then halved by Resistance to **2**. BROM does **not** get the Poisoned condition.
  - [S] The narration doesn't claim a benefit the rules didn't grant.

#### ORIG-03 · Human Heroic Inspiration cycle
- **Tests:** ORIG (Resourceful p.86), CORE (Heroic Inspiration p.8)
- **Depends on:** REST
- **Journey:** JOZAN finishes a Long Rest, then gets awarded Inspiration by the GM while he still has it, then spends it on a damage die.
- **Pass:**
  - [H] He gains Heroic Inspiration on the Long Rest.
  - [H] The second instance is offered to a PC who lacks it, and is otherwise lost.
  - [H] He can reroll **any die**, including damage dice, and must use the new roll.

#### ORIG-04 · Background package and equipment choice
- **Tests:** ORIG (Parts of a Background p.83)
- **Depends on:** CC-02
- **Journey:** Create an Acolyte and choose equipment option B, then a Criminal and choose option A.
- **Pass:**
  - [H] The Acolyte gets Insight, Religion, Calligrapher's Supplies, Magic Initiate (Cleric) and **50 GP**.
  - [H] The Criminal gets Sleight of Hand, Stealth, Thieves' Tools, Alert, 2 Daggers, Thieves' Tools, a Crowbar, 2 Pouches, Traveler's Clothes and 16 GP.
  - [H] Only the background's three listed abilities can be increased.

---

### FEAT: Origin and Fighting Style feats (p.87–88)

#### FEAT-01 · Alert
- **Tests:** FEAT (Alert p.87), CMB (Initiative p.13)
- **Depends on:** CMB-01
- **Setup:** `d20=[8]` for LIDDA; BROM's Initiative is 17.
- **Pass:**
  - [H] LIDDA's Initiative is 13 (8 + 3 Dex + 2 PB).
  - [H] Immediately after rolling, she may swap Initiative with a willing ally; after the swap BROM is on 13 and LIDDA on 17.
  - [H] The swap is refused if either of them has the Incapacitated condition.

#### FEAT-02 · Savage Attacker
- **Tests:** FEAT (Savage Attacker p.87)
- **Depends on:** CMB-03
- **Setup:** BROM hits twice in one turn (e.g., an Action Surge attack). `d8=[2,7]` on the first hit, `d8=[3]` on the second.
- **Pass:**
  - [H] On the first hit he may roll the weapon's damage dice twice and use either result; choosing 7 deals 7 + 3.
  - [H] The second hit that turn gets no second roll (once per turn).
  - [H] Savage Attacker applies to weapon damage dice only, never to spells.

#### FEAT-03 · Magic Initiate and the one-slot-per-turn rule
- **Tests:** FEAT (Magic Initiate p.87), SPL (One Spell with a Spell Slot per Turn p.105)
- **Depends on:** SPL-01
- **Journey:** On one turn JOZAN casts Healing Word with a slot (Bonus Action) and then Command through Magic Initiate (Magic action, no slot). Next turn he casts Command again with a level 1 slot. After a Long Rest he casts it free again.
- **Pass:**
  - [H] The first turn is **allowed**, because only one slot was expended.
  - [H] The free cast recharges only on a Long Rest.
  - [H] The spell can also be cast with any slot.
  - [H] Magic Initiate spells use the ability chosen when the feat was taken (Wis for JOZAN, Int for MIALEE), so both have DC 13.

#### FEAT-04 · Defense and swapping a Fighting Style
- **Tests:** FEAT (Defense p.88), CLS-FTR (Fighting Style p.47)
- **Depends on:** EQP-01
- **Journey:** BROM removes his armor, then puts it back on. At Fighter level 2 he swaps Defense for Great Weapon Fighting.
- **Pass:**
  - [H] With no armor his AC is 14 (10 + 2 Dex + 2 Shield); Defense applies only while he wears armor.
  - [H] With armor his AC is 19.
  - [H] The swap is allowed on gaining a Fighter level.
  - [H] Great Weapon Fighting treats 1s and 2s as 3s only with Two-Handed or Versatile weapons held in two hands.

---

### CLS-FTR: Fighter levels 1–3 (p.47–49)

#### CLS-FTR-01 · Second Wind, Tactical Mind and Action Surge
- **Tests:** CLS-FTR (Second Wind, Tactical Mind, Action Surge p.48)
- **Depends on:** REST, CMB-02
- **Setup:** BROM at level 2 with 5/22 HP. `d10=[7]`.
- **Journey:** He uses Second Wind as a Bonus Action and attacks with his action. He uses Action Surge for a second Attack action, then tries to use Action Surge to take the Magic action. He fails an Athletics check by 3 and uses Tactical Mind (`d10=[2]`), then again (`d10=[6]`). He takes a Short Rest.
- **Pass:**
  - [H] Second Wind heals 9 (7 + 2), bringing him to 14 HP, and his action is still available.
  - [H] Second Wind has 2 uses.
  - [H] Action Surge gives an extra action other than Magic, so the Magic attempt is refused.
  - [H] Tactical Mind with 2 doesn't help, so that use of Second Wind is **not expended**. With 6 the check succeeds and the use is spent.
  - [H] The Short Rest regains one Second Wind use and Action Surge.

#### CLS-FTR-02 · Weapon Mastery gating and Champion features
- **Tests:** CLS-FTR (Weapon Mastery p.48; Champion p.49), EQP (Mastery Properties p.90)
- **Depends on:** EQP-03
- **Journey:** At level 3 (Champion) BROM attacks, `d20=[19]; d8=[4,6]`. He then tries to use a Mace's Sap mastery (he doesn't have Mace mastery). He rolls Initiative, `d20=[5,14]`.
- **Pass:**
  - [H] A roll of 19 is a **Critical Hit** (Improved Critical), dealing 4 + 6 + 3 = 13.
  - [H] After the crit he may move half his Speed without provoking Opportunity Attacks.
  - [H] The Mace's Sap doesn't apply, because mastery covers only the three chosen weapon kinds.
  - [H] Initiative has Advantage (Remarkable Athlete) and uses 14.
  - [H] Only one mastery choice can be changed per Long Rest.

---

### CLS-ROG: Rogue levels 1–3 (p.61–64)

#### CLS-ROG-01 · Sneak Attack eligibility
- **Tests:** CLS-ROG (Sneak Attack p.61–62)
- **Depends on:** CMB-03
- **Setup:** LIDDA attacks a Goblin Warrior (AC 15). Every hit uses `d20=[15]; d6=[4,5]`.
- **Journey:** (a) BROM is within 5 ft of the target and LIDDA has no Advantage or Disadvantage. (b) Nobody is adjacent and she has no Advantage. (c) She has Advantage but uses a Greatclub, which isn't a Finesse or Ranged weapon. (d) An ally is adjacent but she has Disadvantage. (e) The only adjacent ally is Incapacitated. (f) She hits twice in one turn using Light/Nick. (g) She scores a Critical Hit.
- **Pass:**
  - [H] (a) Damage is 4 + 3 + 5 = 12.
  - [H] (b), (c), (d) and (e) get no Sneak Attack.
  - [H] (f) Sneak Attack applies once per turn only.
  - [H] (g) The Sneak Attack dice are doubled too (p.16).
  - [H] At level 3 Sneak Attack is 2d6.

#### CLS-ROG-02 · Cunning Action, Steady Aim and the Thief
- **Tests:** CLS-ROG (Cunning Action, Steady Aim, Thief p.62–64), ACT (Hide p.183)
- **Depends on:** CMB-02, EXPL-03
- **Journey:** At level 3 (Thief) LIDDA, without moving, uses Steady Aim and fires her Shortbow. Next turn she moves 5 ft and tries Steady Aim. She takes Hide as a Bonus Action from behind Three-Quarters Cover. With Fast Hands she disarms a trap as a Bonus Action. She climbs a wall and makes a long jump using Dex.
- **Pass:**
  - [H] Steady Aim gives Advantage and sets her Speed to 0 for the turn; it's refused after she has moved.
  - [H] Cunning Action allows only Dash, Disengage or Hide.
  - [H] Fast Hands allows a Sleight of Hand check to disarm with Thieves' Tools, or the Utilize action, as a Bonus Action.
  - [H] She has a Climb Speed of 30, so climbing costs no extra movement.
  - [H] Her running Long Jump is 17 ft (Dex 17 in place of Str).

---

### CLS-CLR: Cleric levels 1–3 (p.36–40)

#### CLS-CLR-01 · Spellcasting counts and Divine Order
- **Tests:** CLS-CLR (Spellcasting, Divine Order p.36–37)
- **Depends on:** CC
- **Pass:**
  - [H] At level 1: 3 cantrips, 4 prepared spells, 2 level 1 slots. At level 3: 3 cantrips, 6 prepared spells, 4 level 1 and 2 level 2 slots.
  - [H] Protector grants Martial weapons and Heavy armor training. With Thaumaturge instead: +1 cantrip, and Int (Arcana/Religion) checks gain +Wis modifier (minimum +1).
  - [H] Prepared spells can be changed freely after a Long Rest.

#### CLS-CLR-02 · Channel Divinity at level 2
- **Tests:** CLS-CLR (Channel Divinity p.37), COND (Frightened, Incapacitated)
- **Depends on:** SPL, MON
- **Setup:** JOZAN at level 2. `d8=[5]`. The skeleton's Wis save is `d20=[6]` (6 − 1 = 5, which fails DC 13).
- **Journey:** He uses Divine Spark to heal BROM, then Turn Undead against a Skeleton and a Zombie within 30 ft. He hits the turned Skeleton. He takes a Short Rest.
- **Pass:**
  - [H] Divine Spark is a Magic action that heals 5 + 3 = 8. Alternatively it deals damage on a failed Con save and half on a success.
  - [H] The Skeleton gets **Frightened + Incapacitated** for 1 minute and moves away; the effect ends when it takes damage.
  - [H] Channel Divinity has 2 uses; a Short Rest regains 1 and a Long Rest regains all.

#### CLS-CLR-03 · Life Domain at level 3
- **Tests:** CLS-CLR (Life Domain p.40), SPELLS (Cure Wounds p.121; Healing Word p.139)
- **Depends on:** SPELLS-03
- **Setup:** JOZAN at level 3. `d8=[5,4]`.
- **Journey:** He casts Cure Wounds with a level 1 slot on BROM at 10/31 HP. He casts it with a level 2 slot. He casts it from a Spell Scroll (no slot). He uses Preserve Life on three Bloodied allies. He prepares 6 spells.
- **Pass:**
  - [H] The level 1 slot heals 5 + 4 + 3 + **3** (Disciple of Life: 2 + slot level) = 15, bringing BROM to 25.
  - [H] The level 2 slot heals 4d8 + 3 + 4.
  - [H] A cast without a slot gets no Disciple of Life bonus.
  - [H] Preserve Life divides 15 HP (5 × level) among Bloodied creatures within 30 ft, raising none above half its HP maximum, and uses one Channel Divinity.
  - [H] The domain spells Aid, Bless, Cure Wounds and Lesser Restoration are always prepared and **don't count** toward his 6.

---

### CLS-WIZ: Wizard levels 1–3 (p.77–82)

#### CLS-WIZ-01 · Spellbook, preparation and Arcane Recovery
- **Tests:** CLS-WIZ (Spellcasting, Spellbook, Arcane Recovery p.77–78)
- **Depends on:** SPL, REST
- **Journey:** MIALEE at level 1 uses both slots, takes a Short Rest and uses Arcane Recovery. She takes another Short Rest and tries again. She tries to prepare a 5th spell. At level 3 she spends both level 2 slots and uses Arcane Recovery.
- **Pass:**
  - [H] At level 1 she recovers one level 1 slot (ceil(1/2) = 1). The second attempt is refused until a Long Rest.
  - [H] The 5th preparation is refused (4 at level 1). Preparation is only from the spellbook, and changes are allowed after a Long Rest.
  - [H] At level 3 she recovers up to 2 slot levels: one level 2 slot or two level 1 slots.
  - [H] Her spellbook holds 6 spells at level 1, 8 at level 2 and 10 at level 3, plus 2 free Evocation spells at level 3.

#### CLS-WIZ-02 · Ritual Adept, Scholar and the Evoker
- **Tests:** CLS-WIZ (Ritual Adept, Scholar, Evocation Savant, Potent Cantrip p.78–82)
- **Depends on:** SPL-03
- **Setup:** MIALEE at level 3 (Evoker). She casts Ray of Frost at a Goblin Warrior and misses; then `d8=[6]`.
- **Journey:** She ritual-casts Detect Magic without having it prepared. She picks Arcana for Scholar at level 2. On the missed Ray of Frost, Potent Cantrip applies.
- **Pass:**
  - [H] The ritual works from the spellbook without preparation.
  - [H] Arcana gets Expertise (+3 + 4 = +7).
  - [H] Evocation Savant adds 2 Evocation spells of level 2 or lower for free.
  - [H] The miss deals half damage (3) with **no Speed reduction**.

#### CLS-WIZ-03 · Copying a scroll into the spellbook
- **Tests:** CLS-WIZ (Copying a Spell p.78), MI (Spell Scroll p.244)
- **Depends on:** MI-04
- **Journey:** At level 1 MIALEE finds a Scroll of Web (level 2) and a Scroll of Misty Step. At level 3 she copies Web.
- **Pass:**
  - [H] At level 1 she can't copy either, because they're above the spell levels she can prepare.
  - [H] At level 3 copying Web takes 4 hours and 100 GP; gold and the clock both change.
  - [H] After copying, the scroll isn't consumed.

---

### EQP: Equipment (p.89–103)

#### EQP-01 · Armor training, Strength requirement and Stealth
- **Tests:** EQP (Armor p.92), Glossary (Armor Training p.177), SPL (Casting in Armor p.104)
- **Depends on:** CC
- **Journey:** MIALEE puts on Leather Armor, attacks, tries to cast, then puts on Chain Mail. BROM wears Chain Mail and checks Stealth. JOZAN (Protector) wears Chain Mail. MIALEE holds a Shield.
- **Pass:**
  - [H] Untrained in armor, MIALEE has Disadvantage on every D20 Test involving Str or Dex and can't cast spells.
  - [H] In Chain Mail her Speed also drops by 10 ft, because her Str 8 is below 13.
  - [H] BROM has Disadvantage on Stealth.
  - [H] JOZAN is trained through Protector and meets Str 13.
  - [H] An untrained Shield gives no AC bonus.
  - [H] Don/doff times are enforced outside combat (Heavy armor 10/5 minutes), and a Shield takes the Utilize action.

#### EQP-02 · Weapon properties
- **Tests:** EQP (Properties p.89–90)
- **Depends on:** CMB-03
- **Journey:**
  - LIDDA attacks with a Dagger using Dex.
  - BROM uses his Longsword two-handed.
  - LIDDA throws a Dagger at 40 ft, then at 70 ft.
  - An attacker fires a Light Crossbow and tries a second shot with the same action.
  - LIDDA (Str 12) swings a Greatsword.
  - LIDDA fires 10 arrows, then spends 1 minute recovering them.
- **Pass:**
  - [H] Finesse uses the same modifier for attack and damage.
  - [H] The two-handed Longsword deals 1d10+3.
  - [H] The Dagger at 40 ft has Disadvantage; at 70 ft the attack is refused.
  - [H] Loading allows one shot per action, Bonus Action or Reaction.
  - [H] LIDDA has Disadvantage with the Greatsword **because her Str is below 13**, not because of her size.
  - [H] She recovers 5 arrows.
  - [H] Drawing ammunition or a thrown weapon is part of the attack.

#### EQP-03 · Mastery properties
- **Tests:** EQP (Mastery Properties p.90), CLS-FTR/ROG (Weapon Mastery)
- **Depends on:** EQP-02
- **Journey:**
  - BROM hits a goblin with his Longsword (Sap).
  - LIDDA hits with her Shortsword (Vex).
  - LIDDA takes the Attack action with her Shortsword and uses the Nick mastery on her Dagger.
  - BROM misses with his Glaive (Graze).
  - BROM hits with a Javelin (Slow), and a second Slow hit lands on the same target.
  - JOZAN hits with a Mace (Sap).
- **Pass:**
  - [H] **Sap:** the goblin has Disadvantage on its next attack before the start of BROM's next turn.
  - [H] **Vex:** LIDDA has Advantage on her next attack against that target before the end of her next turn.
  - [H] **Nick:** the extra Light attack happens as part of the Attack action, so her Bonus Action is still free. It's limited to once per turn, and the extra attack adds no ability modifier to damage unless the modifier is negative.
  - [H] **Graze:** the miss deals 3 Slashing damage.
  - [H] **Slow:** Speed drops by 10 ft, and repeat hits don't stack it past 10.
  - [H] JOZAN gets no Sap because he has no Weapon Mastery.

#### EQP-04 · Coins, carrying capacity and selling
- **Tests:** EQP (Coins p.89; Selling p.89), Glossary (Carrying Capacity p.178)
- **Depends on:** CC
- **Journey:** Pay 1 GP 7 SP with a 5 GP coin. LIDDA carries 190 lb, then drags a 300-lb crate. Sell a Longsword. Carry 500 coins.
- **Pass:**
  - [H] Change is 3 GP 3 SP (1 GP = 10 SP = 100 CP; 1 EP = ½ GP; 1 PP = 10 GP).
  - [H] 190 lb exceeds her 180-lb carrying capacity (Small uses Str × 15) and is refused.
  - [H] Dragging 300 lb (up to 360) sets her Speed to at most 5 ft.
  - [H] The Longsword sells for 7 GP 5 SP (half of 15 GP).
  - [H] 500 coins weigh 10 lb.

#### EQP-05 · Healer's Kit, Potion of Healing and Torch
- **Tests:** EQP (Healer's Kit p.97; Potion of Healing p.99; Torch p.100)
- **Depends on:** DMG-01
- **Setup:** `2d4=[3,1]`.
- **Journey:** BROM uses a Healer's Kit on an unconscious MIALEE. LIDDA drinks a Potion of Healing and then administers one to an ally 5 ft away. A Torch burns out.
- **Pass:**
  - [H] The Healer's Kit takes the Utilize action and stabilizes with **no Medicine check**, using 1 of its 10 uses.
  - [H] The potion is a **Bonus Action** and heals 3 + 1 + 2 = 6; administering to a creature within 5 ft is also a Bonus Action.
  - [H] The Torch gives Bright Light to 20 ft and Dim Light 20 ft further, and goes out after 1 hour of game time.

#### EQP-06 · Lifestyle and crafting
- **Tests:** EQP (Lifestyle Expenses p.101; Crafting Nonmagical Items p.103)
- **Depends on:** EQP-04
- **Journey:** JOZAN (proficient with Woodcarver's Tools) crafts a Shortbow (25 GP). LIDDA tries the same without the tool proficiency. The party lives a Modest lifestyle for 7 days.
- **Pass:**
  - [H] The Shortbow needs 12 GP of raw materials (half of 25, rounded down) and **3 days** (25/10, rounding a fraction **up** to a day).
  - [H] A helper with the proficiency halves the time.
  - [H] LIDDA is refused.
  - [H] Modest living costs 7 GP, and the game clock advances 7 days.

---

### EXPL: Exploration (p.11–12, 192, glossary)

#### EXPL-01 · Travel pace, terrain and extended travel
- **Tests:** EXPL (Travel Pace p.12), TBX (Travel Terrain, Good Roads, Extended Travel p.192–193), COND (Exhaustion)
- **Depends on:** HAZ-01
- **Setup:** Con saves `d20=[8,14]`.
- **Journey:**
  - The party travels 24 miles at Normal pace through Forest.
  - It asks for Fast pace in Forest, and then on a good road through Forest.
  - It travels 10 hours in one day.
- **Pass:**
  - [H] 24 miles takes 8 hours.
  - [H] **Normal pace imposes Disadvantage on Stealth.**
  - [H] Fast pace is refused in Forest (maximum Normal) but allowed on the road.
  - [H] Fast pace imposes Disadvantage on Perception, Survival and Stealth. Slow pace grants Advantage on Perception and Survival.
  - [H] Hour 9 calls for a DC 11 Con save: BROM's 8 + 4 = 12 succeeds.
  - [H] Hour 10 calls for a DC 12 save: MIALEE's 14 + 2 = 16 succeeds, and each failure adds 1 Exhaustion level.
  - [H] The clock advances correctly.

#### EXPL-02 · Vision, light and Darkvision
- **Tests:** EXPL (Vision and Light p.11), Glossary (Darkvision p.180; Heavily Obscured p.182)
- **Depends on:** COND-03
- **Journey:** The party enters an unlit cave. JOZAN (no Darkvision) looks around, BROM (Darkvision 120) looks around, then LIDDA lights a Torch.
- **Pass:**
  - [H] JOZAN effectively has the **Blinded** condition when trying to see in Darkness.
  - [H] For BROM, Darkness counts as Dim Light, so he has Disadvantage on sight-based Perception and sees no colors, only gray.
  - [H] Once the Torch is lit, everyone within 20 ft sees normally.
  - [S] The narration doesn't describe colors BROM couldn't see.

#### EXPL-03 · Hiding and being found
- **Tests:** ACT (Hide p.183), COND (Invisible p.184)
- **Depends on:** CORE-03
- **Setup:** LIDDA `d20=[9]` (9 + 7 = 16).
- **Journey:** LIDDA Hides behind a crate (Three-Quarters Cover, out of line of sight). A goblin with Passive Perception 9 walks by. Then she attacks, and on a separate run she whispers and then shouts.
- **Pass:**
  - [H] The Hide DC is 15, and 16 succeeds.
  - [H] While hidden LIDDA has the **Invisible** condition, and her check total of 16 becomes the DC to find her.
  - [H] Hiding is refused in plain view.
  - [H] The attack roll ends hiding, whether it hits or misses.
  - [H] A whisper doesn't end hiding; a shout does.
  - [H] Being Invisible gives her Advantage on the attack.

#### EXPL-04 · Jumping, climbing and searching
- **Tests:** Glossary (Long Jump, High Jump p.183–185; Climbing p.178), EXPL (Finding Hidden Objects p.12)
- **Depends on:** CC
- **Journey:** BROM (Str 17) jumps a 16-ft chasm with a run-up, then a 9-ft gap standing. He makes a running High Jump. MIALEE climbs 10 ft. The party searches the wrong room for a secret door.
- **Pass:**
  - [H] The running Long Jump reaches 17 ft, so 16 ft succeeds.
  - [H] The standing jump reaches 8 ft (½ × 17 rounded down), so 9 ft fails.
  - [H] The High Jump reaches 6 ft (3 + Str modifier).
  - [H] Each foot of jumping costs a foot of movement.
  - [H] Climbing costs 1 extra foot per foot (2 in Difficult Terrain).
  - [H] Searching away from the hidden object never reveals it, whatever the total.

---

### SOC: Social interaction (p.10–11, glossary)

#### SOC-01 · The Influence action
- **Tests:** SOC (Social Interaction p.10–11), ACT (Influence p.184), Glossary (Friendly/Indifferent/Hostile p.182–184)
- **Depends on:** CORE-03
- **Journey:** (a) JOZAN asks an Indifferent guard to open the gate after dark (hesitant); the guard has Int 10. (b) He asks a Hostile goblin boss to hand over its treasure (unwilling). (c) He asks a Friendly priest for a blessing it wants to give (willing). (d) He fails (a) and repeats the same request immediately.
- **Pass:**
  - [H] (a) Needs a check (Persuasion suggested) at **DC 15** (15 or the monster's Int, whichever is higher).
  - [H] Hostile imposes Disadvantage and Friendly grants Advantage.
  - [H] (b) Fails automatically with no roll.
  - [H] (c) Succeeds automatically with no roll.
  - [H] (d) Refused for 24 hours.
  - [S] The NPC acts consistently with its attitude and motives, and a single roll doesn't override its core nature.

#### SOC-02 · Search, Study and Insight
- **Tests:** ACT (Search p.187; Study p.189)
- **Depends on:** SOC-01
- **Journey:** JOZAN reads a merchant's body language, and MIALEE recalls lore about goblins.
- **Pass:**
  - [H] Reading the merchant is a **Search** action using Wis (Insight).
  - [H] Goblin lore is a **Study** action using Int (**Arcana**). In 2024 goblins are **Fey (Goblinoid)** (p.290), and Arcana covers Fey (Areas of Knowledge, p.189). Picking History, the 2014 answer, fails the test.
  - [H] The game refuses to Influence and Search in the same action.

---

### CMB: Combat (p.13–16)

#### CMB-01 · Surprise and Initiative
- **Tests:** CMB (Initiative, Surprise, Ties p.13), MON (Initiative p.254), FEAT (Alert)
- **Depends on:** EXPL-03, CC
- **Setup:** Four hidden Goblin Warriors (Hide totals of 16) ambush the party, who haven't noticed them. The goblins' single group roll is `d20=[11,6]`, which with Advantage gives 11 + 2 = 13. Each PC's roll is `d20=[15,4]`, which with Disadvantage gives 4 + Initiative modifier.
- **Pass:**
  - [H] Every unaware PC is **surprised**, meaning **Disadvantage on Initiative**. Nobody loses a turn (2024 rule).
  - [H] Identical monsters share a single roll, so all four goblins are on 13.
  - [H] The goblins are Invisible while hidden, so they have Advantage on Initiative.
  - [H] Ties are resolved by the GM between monsters, by the players between PCs, and by the GM between a monster and a PC.
  - [H] The order persists from round to round.

#### CMB-02 · Turn economy
- **Tests:** CMB (Your Turn p.13; Breaking Up Your Move p.14), ACT, Glossary (Attack: equipping p.177; Bonus Action; Reaction)
- **Depends on:** CMB-01
- **Journey:**
  - BROM moves 10 ft, draws a Javelin as part of an attack and attacks, then moves 20 ft.
  - He opens a door (a free interaction) and tries to pick up a Shield as well.
  - He tries to take a second action.
  - MIALEE tries to take a Bonus Action she has no feature for.
- **Pass:**
  - [H] Movement can be split around the action, up to his Speed of 30.
  - [H] He gets one action.
  - [H] The Attack action lets him equip **or** unequip one weapon.
  - [H] He gets one free object interaction; a second needs the Utilize action.
  - [H] A Bonus Action exists only when a feature grants one.
  - [H] He gets one Reaction per round, reset at the start of his own turn.
  - [H] Dropping Prone costs no movement.

#### CMB-03 · Attack resolution and Critical Hits
- **Tests:** CMB (Making an Attack p.14–15), CORE (Rolling 20 or 1 p.7), DMG (Critical Hits p.16), MON (Goblin Warrior)
- **Depends on:** CC, EQP
- **Setup:** BROM vs a Goblin Warrior (AC 15, HP 10). He declines Savage Attacker. Attack 1: `d20=[10]; d8=[4]`. Attack 2: `d20=[20]; d8=[3,5]`. Attack 3: `d20=[1]`.
- **Pass:**
  - [H] Attack 1: 10 + 5 = 15 meets AC and hits, dealing 4 + 3 = 7 and leaving the goblin at 3 HP.
  - [H] Attack 2: a natural 20 is a Critical Hit; the dice are rolled twice and the modifier added once (3 + 5 + 3 = 11). The goblin dies at 0, since monsters die at 0 HP (p.17).
  - [H] Attack 3: a natural 1 misses regardless of modifiers.
  - [H] The Critical Hit rolls every damage die twice, including extra dice such as Sneak Attack.

#### CMB-04 · Opportunity Attacks, Disengage, Nimble Escape and teleports
- **Tests:** CMB (Opportunity Attacks p.15), Glossary (Opportunity Attacks p.185; Teleportation p.190), MON (Nimble Escape)
- **Depends on:** CMB-02
- **Journey:** (a) LIDDA walks out of an Ogre's reach. (b) She Disengages first. (c) A goblin uses Nimble Escape. (d) BROM is shoved out of reach. (e) MIALEE Misty Steps away. (f) A goblin leaves the reach of a PC who already used their Reaction. (g) A Controlled mount moves away.
- **Pass:**
  - [H] (a) The Ogre may make one melee Opportunity Attack as its Reaction, just before she leaves.
  - [H] (b) No OA.
  - [H] (c) The goblin Disengages as a Bonus Action, provoking no OA, and still has its action.
  - [H] (d) No OA from forced movement.
  - [H] (e) No OA from a teleport.
  - [H] (f) No OA.
  - [H] (g) The mount provokes, because it's leaving using its own speed.

#### CMB-05 · Ranged attacks and cover
- **Tests:** CMB (Cover p.15; Ranged Attacks p.15)
- **Depends on:** CMB-03
- **Journey:** LIDDA fires her Shortbow (80/320) at a goblin 100 ft away, one behind a low wall, one behind an arrow slit, one behind a closed door, one at 400 ft, and one while a hostile, non-Incapacitated goblin stands next to her.
- **Pass:**
  - [H] At 100 ft she has Disadvantage.
  - [H] Half Cover gives +2 AC and Dex saves; Three-Quarters Cover gives +5.
  - [H] Total Cover can't be targeted.
  - [H] 400 ft is refused.
  - [H] The adjacent goblin imposes Disadvantage; an Incapacitated one wouldn't.
  - [H] Only the best degree of cover applies.

#### CMB-06 · Grapple and Shove (Unarmed Strike)
- **Tests:** Glossary (Unarmed Strike p.190; Grappling p.182; Grappled p.182), COND (Prone)
- **Depends on:** CMB-03, COND
- **Setup:** The goblin's Dex save is `d20=[9]` (9 + 2 = 11, which fails DC 13).
- **Journey:** BROM grapples a Goblin Warrior with his Shield hand free, then drags it 10 ft. LIDDA (Small) tries to grapple the Ogre (Large). BROM Shoves a Bandit Prone. The goblin uses its action to escape, `d20=[14]` with Acrobatics +2. BROM becomes Incapacitated.
- **Pass:**
  - [H] Grappling is an **Unarmed Strike option**: the target makes a Str or Dex **save** (its choice) against **DC 13**, rather than a contested check. It needs a free hand.
  - [H] The grappled goblin has Speed 0 and Disadvantage on attacks against anyone but BROM.
  - [H] Dragging costs 1 extra foot per foot (the Small goblin is only one size smaller than BROM, and the exemption needs Tiny or two sizes smaller), so 10 ft costs 20 ft of movement.
  - [H] LIDDA's grapple is refused (Large is more than one size larger).
  - [H] The Shove imposes Prone or pushes 5 ft.
  - [H] The escape roll of 16 meets DC 13, so the goblin is free.
  - [H] The grapple ends if BROM is Incapacitated.

#### CMB-07 · Light-weapon extra attack
- **Tests:** EQP (Light p.89), FEAT (Two-Weapon Fighting p.88)
- **Depends on:** EQP-03
- **Journey:** LIDDA, without Nick, attacks with her Shortsword and then her Dagger as a Bonus Action. She tries the same with a Rapier. BROM has the Two-Weapon Fighting feat in a variant fixture.
- **Pass:**
  - [H] The extra attack must use a **different** Light weapon and adds no ability modifier to damage unless it's negative.
  - [H] The Rapier (not Light) is refused.
  - [H] With the Two-Weapon Fighting feat, the modifier is added.

#### CMB-08 · Mounted and underwater combat
- **Tests:** CMB (Mounted Combat p.15–16; Underwater Combat p.16)
- **Depends on:** CMB-03
- **Journey:**
  - JOZAN mounts a Riding Horse and has it Dash.
  - BROM, who has no Swim Speed, fights underwater with a Longsword and then a Spear.
  - LIDDA shoots her Shortbow underwater at 60 ft and at 100 ft.
  - MIALEE casts Fire Bolt at a submerged target.
  - The horse is knocked Prone while JOZAN rides it; his Dex save is `d20=[4]`.
- **Pass:**
  - [H] Mounting costs 15 ft (half of 30).
  - [H] A Controlled mount acts on the rider's Initiative, with only Dash, Disengage or Dodge available.
  - [H] The Longsword (Slashing) attacks with Disadvantage; the Spear (Piercing) attacks normally.
  - [H] The Shortbow at 60 ft has Disadvantage; at 100 ft it automatically misses (beyond normal range).
  - [H] The submerged target has Resistance to Fire.
  - [H] JOZAN fails the DC 10 Dex save, falls off and lands Prone.

---

### DMG: Damage and healing (p.16–18)

#### DMG-01 · Dropping to 0 HP, Death Saving Throws and Massive Damage
- **Tests:** DMG (Dropping to 0 Hit Points p.17–18), COND (Unconscious p.191)
- **Depends on:** CMB-03
- **Setup:** MIALEE (8 max HP). Each case starts from full HP.
- **Journey:**
  - (a) She takes 11 damage.
  - (b) Her death saves are `d20=[12,3,20]`.
  - (c) Reset; saves `d20=[1,15,4]`.
  - (d) At 0 HP an adjacent goblin hits her.
  - (e) At 8 HP she takes 16.
  - (f) JOZAN takes the **Help** action to stabilize her, `d20=[5]` with Medicine +5.
  - (g) JOZAN casts Spare the Dying from 15 ft.
  - (h) BROM knocks out a Bandit with a melee attack.
- **Pass:**
  - [H] (a) She drops to 0 with 3 left over, below her max of 8: Unconscious, not dead.
  - [H] (b) Success, failure, then a 20: she regains 1 HP and her tallies reset.
  - [H] (c) The 1 counts as two failures; then a success; the 4 is the third failure, so she dies.
  - [H] (d) The hit is automatically a Critical Hit (Unconscious, within 5 ft), so it adds **2 failures**.
  - [H] (e) Remainder 8 ≥ 8, so she dies instantly.
  - [H] (f) 10 succeeds: she becomes Stable and regains 1 HP after 1d4 hours.
  - [H] (g) Stable.
  - [H] (h) The Bandit drops to **1 HP**, gets the Unconscious condition and starts a Short Rest; it wakes if healed or given first aid with a DC 10 Medicine check.
  - [H] Death saves happen at the start of each of her turns.

#### DMG-02 · Resistance, Vulnerability, Immunity and order of operations
- **Tests:** DMG (Resistance and Vulnerability; Order of Application p.17), MON (Skeleton, Zombie)
- **Depends on:** CMB-03
- **Journey:**
  - JOZAN hits a Skeleton with his Mace, `d6=[4]`.
  - Poison damage is dealt to the Skeleton.
  - A creature with Resistance to all damage and Vulnerability to Fire, inside a −5 damage aura, takes 28 Fire damage.
  - Burning Hands and a Fire Bolt both hit a fire-resistant target.
- **Pass:**
  - [H] The Mace deals 4 + 2 = 6, doubled by Bludgeoning Vulnerability to **12**.
  - [H] The Poison damage deals 0.
  - [H] In the aura case, 28 − 5 = 23, halved to 11, doubled to **22** (SRD worked example).
  - [H] Each instance of damage has Resistance applied at most once.
  - [H] Damage can't go below 0.

#### DMG-03 · Temporary Hit Points and healing limits
- **Tests:** DMG (Temporary Hit Points p.18; Healing p.17)
- **Depends on:** DMG-01
- **Journey:**
  - BROM has 5 temp HP and gains 12; he chooses 12.
  - He takes 15 damage.
  - He is healed for 8 while missing 6 HP.
  - A creature at 0 HP gains temp HP.
- **Pass:**
  - [H] Temp HP don't stack, so the player chooses which to keep.
  - [H] The 12 temp HP are lost first, and 3 HP comes off his real total.
  - [H] Healing doesn't restore temp HP and is capped at the maximum, so he regains 6.
  - [H] Temp HP don't restore consciousness.
  - [H] Temp HP expire after a Long Rest.

---

### REST: Short and Long Rests (glossary p.185, 187)

#### REST-01 · Short Rest and Hit Point Dice
- **Tests:** REST (Short Rest p.187), CLS (short-rest recharges)
- **Depends on:** DMG-01
- **Setup:** BROM at level 2, 5/22 HP, 2 Hit Dice. `d10=[6,2]`.
- **Journey:** He takes a Short Rest and spends his Hit Dice one at a time. A second Short Rest is interrupted when someone rolls Initiative. A Short Rest is attempted at 0 HP.
- **Pass:**
  - [H] The rest takes 1 hour. The first die heals 6 + 2 = 8 and the second 2 + 2 = 4, for **17 HP**; he decides after each roll whether to spend another.
  - [H] Rolling Initiative, casting a non-cantrip spell or taking damage interrupts the rest, and an interrupted Short Rest gives **no** benefit.
  - [H] A rest can't start at 0 HP.

#### REST-02 · Long Rest (2024 rules)
- **Tests:** REST (Long Rest p.185), COND (Exhaustion)
- **Depends on:** REST-01
- **Journey:** BROM, with spent Hit Dice, 1 Exhaustion level and a reduced HP maximum, takes a Long Rest. The party tries a second Long Rest 10 hours later. A Long Rest is interrupted by combat after 3 hours and then resumed. MIALEE rests in 4 hours through Trance.
- **Pass:**
  - [H] The Long Rest restores all HP and **all spent Hit Dice**, returns the HP maximum to normal and removes 1 Exhaustion level.
  - [H] The second rest is refused: he must wait at least **16 hours** after finishing one.
  - [H] The interrupted rest grants Short Rest benefits (at least 1 hour had passed). Resuming requires one extra hour.
  - [H] MIALEE's 4-hour Trance counts as a full Long Rest.
  - [H] Spell slots, Arcane Recovery, Second Wind, Channel Divinity, Magic Initiate free casts and "per day" features all reset.

---

### HAZ and COND: Hazards and conditions (glossary)

#### HAZ-01 · Exhaustion (2024)
- **Tests:** COND (Exhaustion p.181), REST
- **Depends on:** CORE
- **Journey:** A PC accumulates Exhaustion levels 1 through 6, making a d20 check at each level. It then takes Long Rests.
- **Pass:**
  - [H] Each level reduces D20 Tests by **2 × level** and Speed by **5 × level**.
  - [H] At level 6 the character dies.
  - [H] Each Long Rest removes 1 level.

#### HAZ-02 · Falling, suffocation, malnutrition, dehydration and burning
- **Tests:** HAZ (Falling p.182; Suffocation p.189; Malnutrition p.185; Dehydration p.181; Burning p.178)
- **Depends on:** HAZ-01
- **Journey:**
  - MIALEE falls 30 ft, `d6=[2,3,4]`. Separately, she falls 30 ft into water and uses her Reaction for a DC 15 Str (Athletics) or Dex (Acrobatics) check, `d20=[12]`.
  - MIALEE (Con +2) holds her breath underwater.
  - A PC eats nothing for 6 days.
  - A PC eats a quarter ration (Con save `d20=[7]`).
  - A PC drinks too little water.
  - A burning PC drops Prone and rolls.
- **Pass:**
  - [H] The fall deals 9 Bludgeoning damage and leaves her Prone. For the water check the engine picks her better option, Acrobatics (12 + 1 = 13); it fails, so the damage isn't halved.
  - [H] She can hold her breath for 3 minutes. After that she gains **1 Exhaustion level at the end of each of her turns**, and all of it is removed once she can breathe.
  - [H] Starvation gives 1 level at the end of day 5 and another at the end of day 6.
  - [H] The partial ration calls for a DC 10 Con save; 9 fails, adding 1 level.
  - [H] Too little water adds 1 level with no save, and it can't be removed until the character drinks a full day's water.
  - [H] Burning deals 1d4 Fire at the start of each turn, and the action to drop Prone and roll puts it out.

#### COND-01 · Incapacitating conditions
- **Tests:** COND (Incapacitated, Paralyzed, Stunned, Unconscious, Petrified p.184–191)
- **Depends on:** CMB-03
- **Pass:**
  - [H] Every one of these blocks actions, Bonus Actions and Reactions, and breaks Concentration.
  - [H] Paralyzed, Stunned, Unconscious and Petrified fail Str and Dex saves automatically, and attacks against them have Advantage.
  - [H] **Paralyzed and Unconscious:** any hit from within 5 ft is a Critical Hit.
  - [H] **Unconscious:** drops held items, is also Prone (and stays Prone after waking), and has Speed 0.
  - [H] **Petrified:** Resistance to all damage and immune to Poisoned.
  - [H] A creature that is Incapacitated when it rolls Initiative has Disadvantage.

#### COND-02 · Movement and attack conditions
- **Tests:** COND (Grappled, Restrained, Prone, Frightened p.182–187)
- **Depends on:** CMB-06
- **Pass:**
  - [H] **Restrained:** Speed 0, attacks against it have Advantage, its own attacks have Disadvantage, Disadvantage on Dex saves.
  - [H] **Prone:** crawling costs extra, standing costs half Speed (not possible at Speed 0), its attacks have Disadvantage, attacks from within 5 ft have Advantage and attacks from farther have Disadvantage.
  - [H] **Frightened:** Disadvantage on checks and attacks while the source is in line of sight, and it can't willingly move closer to the source.

#### COND-03 · Sensory and social conditions
- **Tests:** COND (Blinded, Deafened, Invisible, Charmed, Poisoned)
- **Depends on:** CMB-03
- **Pass:**
  - [H] **Blinded:** automatically fails sight checks, attacks against it have Advantage, its attacks have Disadvantage.
  - [H] **Deafened:** automatically fails hearing checks.
  - [H] **Invisible:** Advantage on Initiative, its attacks have Advantage and attacks against it have Disadvantage (neither applies against something that can see it), and it's immune to effects that require the target to be seen.
  - [H] **Charmed:** can't attack or target the charmer with harmful effects, and the charmer has Advantage on social checks against it.
  - [H] **Poisoned:** Disadvantage on attack rolls and ability checks.
  - [H] Conditions don't stack with themselves (Exhaustion excepted).

---

### SPL: Spellcasting rules (p.104–106)

#### SPL-01 · Slots, upcasting and one slot per turn
- **Tests:** SPL (Spell Slots, Using a Higher-Level Spell Slot, One Spell with a Spell Slot per Turn p.104–105)
- **Depends on:** CLS-CLR, CLS-WIZ
- **Journey:**
  - MIALEE casts Fire Bolt three times and Magic Missile twice, then tries a third Magic Missile.
  - At level 3 she casts Magic Missile with a level 2 slot.
  - JOZAN casts Healing Word with a slot and then Guiding Bolt with a slot on the same turn.
  - JOZAN casts Healing Word and then Sacred Flame.
- **Pass:**
  - [H] Cantrips cost no slots, and the third Magic Missile is refused.
  - [H] Upcast Magic Missile fires 4 darts at spell level 2.
  - [H] Healing Word followed by Guiding Bolt is **refused**, because only one slot can be spent per turn.
  - [H] Healing Word followed by Sacred Flame is allowed.
  - [H] Spell slots come back on a Long Rest.

#### SPL-02 · Concentration
- **Tests:** Glossary (Concentration p.179)
- **Depends on:** CORE-05
- **Setup:** JOZAN (Con +1, not proficient in Con saves) is concentrating on Bless.
- **Journey:** He takes 22 damage, `d20=[9]`. He recasts Bless and takes 7 damage, `d20=[9]`. He then casts Shield of Faith. He becomes Incapacitated.
- **Pass:**
  - [H] 22 damage sets the DC to 11; 9 + 1 = 10 fails and Bless ends.
  - [H] 7 damage sets the DC to 10 (the minimum); 10 succeeds.
  - [H] Starting another Concentration spell ends the first.
  - [H] Being Incapacitated ends Concentration.
  - [H] The DC is capped at 30.
  - [H] Bless expires after 10 rounds.

#### SPL-03 · Rituals and longer casting times
- **Tests:** SPL (Rituals p.104; Longer Casting Times p.105), Glossary (Ritual p.187), CLS-WIZ (Ritual Adept)
- **Depends on:** SPL-01
- **Journey:** JOZAN ritual-casts Detect Magic with and without it prepared. MIALEE ritual-casts it from her spellbook with no slots left. A ritual is attempted in combat. Someone tries to upcast a ritual.
- **Pass:**
  - [H] A ritual takes the normal casting time + **10 minutes**, uses no slot and advances the clock.
  - [H] JOZAN must have the spell prepared; MIALEE doesn't.
  - [H] While casting, the caster must take the Magic action each turn and hold Concentration. If Concentration breaks, the spell fails with no slot spent.
  - [H] A ritual can't be upcast.

#### SPL-04 · Components, foci and armor
- **Tests:** SPL (Components p.105–106), EQP (Component Pouch p.96; Holy Symbol p.97)
- **Depends on:** SPL-01, EQP-01
- **Journey:**
  - MIALEE, gagged, tries to cast Magic Missile (V).
  - Both her hands are full when she casts Burning Hands (S).
  - She casts Sleep with a Component Pouch.
  - JOZAN casts Bless (M: Holy Symbol worth 5+ GP) with and without his Holy Symbol.
  - An untrained caster casts while wearing armor.
- **Pass:**
  - [H] The gagged casting is refused.
  - [H] The full-hands casting is refused.
  - [H] The Pouch replaces free materials.
  - [H] Bless works with the Holy Symbol and is refused without it.
  - [H] Casting in untrained armor is refused.
  - [H] If a caster in an area of Silence casts a V spell, it's refused.

#### SPL-05 · Areas of effect and saving throws
- **Tests:** SPL (Areas of Effect p.106), Glossary (Cone p.179; Area of Effect p.177), DMG (Damage against Multiple Targets; Half Damage p.16), SPELLS (Burning Hands p.114)
- **Depends on:** SPL-01, CMB-05
- **Setup:** Three Goblin Warriors, two of them inside a 15-ft Cone from MIALEE and the third behind Total Cover inside the cone's area. `d6=[3,4,5]`; Dex saves `d20=[12]` and `d20=[9]`.
- **Pass:**
  - [H] Only the two exposed goblins are affected.
  - [H] Damage is rolled **once** for all targets: 12.
  - [H] DC 13: 12 + 2 = 14 succeeds and takes 6; 9 + 2 = 11 fails and takes 12, which kills that goblin.
  - [H] The cone's point of origin isn't included.
  - [H] Unattended flammable objects in the cone start burning.

#### SPL-06 · Targeting rules and combining effects
- **Tests:** SPL (Targets; Invalid Targets; Combining Spell Effects p.106), SPELLS (Hold Person, Bless)
- **Depends on:** SPL-01
- **Journey:** JOZAN casts Hold Person on a Wolf, which isn't a Humanoid. Two clerics bless the same fighter. Someone casts at a target behind Total Cover.
- **Pass:**
  - [H] The Wolf is an invalid target: the slot is spent and the wolf appears to succeed on its save.
  - [H] The fighter gets only one Bless bonus die while the effects overlap.
  - [H] The target behind Total Cover can't be targeted.

---

### SPELLS: The subset spells (p.107–175)

#### SPELLS-01 · Magic Missile vs Shield
- **Tests:** SPELLS (Magic Missile p.146; Shield p.161), ACT (Reactions)
- **Depends on:** SPL-01
- **Journey:** An enemy casts Magic Missile at MIALEE and she reacts with Shield. Later a Goblin Boss attacks her with a total of 12 (`d20=[8]` + 4) and she casts Shield.
- **Pass:**
  - [H] Magic Missile deals 0 damage while Shield is up.
  - [H] Her AC goes from 11 to 16, **including against the triggering attack**, so 12 misses.
  - [H] Shield lasts until the start of her next turn and uses her Reaction.
  - [H] Each Magic Missile dart deals 1d4+1 Force and hits automatically.

#### SPELLS-02 · Sleep (2024)
- **Tests:** SPELLS (Sleep p.163), COND (Incapacitated, Unconscious), ORIG (Elf Trance)
- **Depends on:** SPL-05
- **Setup:** A 5-ft-radius Sphere catches Goblin Warrior A, Goblin Warrior B, a Skeleton and an Elf NPC. The goblins' Wis saves (−1) are `d20=[10]` and `d20=[14]`. Goblin A's second save is `d20=[6]`.
- **Pass:**
  - [H] Goblin A's 9 fails DC 13, so it's **Incapacitated** until the end of its next turn and then repeats the save; its 5 fails, so it becomes **Unconscious** for the duration (Concentration, up to 1 minute).
  - [H] Goblin B's 13 succeeds, so it's unaffected.
  - [H] The Skeleton, immune to Exhaustion, and the Elf, who doesn't sleep, **automatically succeed**.
  - [H] The spell ends on a target that takes damage or is shaken awake by an action from within 5 ft.
  - [H] No hit-point pool is used; that was the 2014 rule.

#### SPELLS-03 · Healing spells
- **Tests:** SPELLS (Cure Wounds p.121; Healing Word p.139; Aid p.107; Spare the Dying p.163)
- **Depends on:** DMG-01
- **Setup:** JOZAN at level 1. `d8=[5,4]`, `d4=[2,3]`.
- **Journey:** He casts Cure Wounds on BROM at 2/13 HP. He casts Healing Word on MIALEE at 0 HP 50 ft away, then tries again at 70 ft. He casts Cure Wounds on a Zombie. At level 3 he casts Aid on three allies.
- **Pass:**
  - [H] Cure Wounds heals 5 + 4 + 3 = 12, capped so BROM reaches 13/13.
  - [H] Healing Word heals 2 + 3 + 3 = 8 and is a Bonus Action. MIALEE regains consciousness and her death saves reset.
  - [H] 70 ft is refused (range 60 ft).
  - [H] The Zombie is healed, because the 2024 spell text has **no Undead or Construct exclusion**.
  - [H] Aid adds +5 to both maximum and current HP for 8 hours, +5 more per slot level above 2.
  - [H] Cure Wounds heals +2d8 per slot level above 1; Healing Word +2d4.

#### SPELLS-04 · Hold Person, Command and Sanctuary
- **Tests:** SPELLS (Hold Person p.141; Command p.116; Sanctuary p.159), COND (Paralyzed, Prone)
- **Depends on:** SPL-02, COND-01
- **Journey:**
  - JOZAN at level 3 casts Hold Person on a Bandit (Wis +0), `d20=[7]`. BROM attacks it from 5 ft.
  - At the end of the Bandit's turn it repeats the save, `d20=[15]`.
  - JOZAN casts Command "Grovel" on a Cultist (Wis save +2) that rolls `d20=[8]`.
  - JOZAN casts Sanctuary on MIALEE, and a goblin attacks her (`d20=[11]` on its Wis save).
- **Pass:**
  - [H] The Bandit is Paralyzed, so BROM attacks with Advantage and any hit is a Critical Hit.
  - [H] On the repeat save 15 succeeds and the spell ends.
  - [H] The Cultist's 10 fails DC 13, so it becomes Prone and ends its turn.
  - [H] The goblin's Wis save of 10 fails, so it must choose a new target or lose the attack.
  - [H] Sanctuary ends if MIALEE attacks, casts a spell or deals damage, and it doesn't protect her from areas of effect.

#### SPELLS-05 · Cantrips: scaling, Sacred Flame and cover, burning
- **Tests:** SPELLS (Fire Bolt p.132; Sacred Flame p.159; Ray of Frost p.157)
- **Depends on:** CMB-05
- **Journey:** MIALEE casts Fire Bolt at a level 1 target and at an unattended wooden crate. JOZAN casts Sacred Flame at a goblin behind a low wall. MIALEE hits with Ray of Frost.
- **Pass:**
  - [H] Fire Bolt deals 1d10 until **character level 5**; its tier depends on character level.
  - [H] The crate starts burning.
  - [H] The goblin gets **no** Half or Three-Quarters Cover bonus on its Dex save.
  - [H] Ray of Frost reduces Speed by 10 ft until the start of MIALEE's next turn.

#### SPELLS-06 · Level 2 utility and control
- **Tests:** SPELLS (Misty Step p.150; Invisibility p.143; Web p.174; Spiritual Weapon p.165; Scorching Ray p.159; Lesser Restoration p.144)
- **Depends on:** SPELLS-01
- **Journey:**
  - Level 3 MIALEE uses Misty Step (Bonus Action).
  - She casts Invisibility on LIDDA, who then attacks.
  - She casts Web between two pillars; a goblin fails its Dex save and then makes an Athletics check to break free.
  - Someone sets the web on fire.
  - JOZAN casts Spiritual Weapon.
  - MIALEE casts Scorching Ray at two targets.
  - JOZAN casts Lesser Restoration on a Poisoned ally.
- **Pass:**
  - [H] Misty Step teleports up to 30 ft without provoking an OA.
  - [H] Invisibility ends right after LIDDA's attack roll.
  - [H] The web is Difficult Terrain and Lightly Obscured, and the goblin is Restrained. Breaking free is an Athletics check against DC 13.
  - [H] Fire burns a 5-ft cube of web away and deals 2d4 Fire.
  - [H] Spiritual Weapon is a Bonus Action and requires **Concentration** (2024). It makes a melee spell attack for 1d8 + 3 Force.
  - [H] Scorching Ray makes three separate attack rolls, 2d6 Fire each.
  - [H] Lesser Restoration ends Blinded, Deafened, Paralyzed or Poisoned as a Bonus Action.

---

### MON: Monsters (p.254–364)

#### MON-01 · Stat blocks load and run
- **Tests:** MON (Stat Block Overview p.254; the 14 subset stat blocks), Glossary (Stat Block p.188–189)
- **Depends on:** CMB-03
- **Pass:**
  - [H] All 14 subset monsters load with the §4 values: AC, Initiative modifier and score, HP (average and dice), speeds, ability modifiers and saves, skills, gear, senses, Passive Perception, languages, CR, XP and PB.
  - [H] Attacks resolve with the listed bonus and damage.
  - [H] Monsters are proficient with the gear in their stat block.
  - [H] The GM can use either fixed damage or dice, never both (p.189).

#### MON-02 · Monster traits
- **Tests:** MON (Pack Tactics, Nimble Escape, Undead Fortitude, Goblin Warrior bonus die, Redirect Attack, Wolf Bite, Sunlight Sensitivity)
- **Depends on:** MON-01, DMG-02
- **Journey:**
  - (a) A Wolf attacks BROM while another wolf is adjacent to him.
  - (b) The wolf hits LIDDA.
  - (c) A Goblin Warrior with Advantage hits.
  - (d) BROM hits a Zombie at 5 HP for 9 Slashing damage; its save is `d20=[12]`.
  - (e) BROM crits the Zombie instead.
  - (f) JOZAN hits it with Sacred Flame.
  - (g) BROM attacks the Goblin Boss while a goblin stands adjacent to it.
  - (h) Kobolds fight in sunlight.
- **Pass:**
  - [H] (a) The wolf has Advantage (Pack Tactics).
  - [H] (b) LIDDA is Prone (Medium or smaller, no save).
  - [H] (c) The goblin adds +1d4.
  - [H] (d) The DC is 5 + 9 = 14, and 12 + 3 = 15 succeeds, so the Zombie is left at **1 HP**.
  - [H] (e) and (f) No Undead Fortitude save.
  - [H] (g) The Boss may swap places with the goblin, making the goblin the target.
  - [H] (h) The kobolds have Disadvantage on attacks and checks.

#### MON-03 · Monster behavior (soft)
- **Tests:** MON (Running a Monster p.255)
- **Depends on:** MON-01
- **Pass:**
  - [S] Goblins use Nimble Escape to hide and snipe.
  - [S] Wolves flank to trigger Pack Tactics.
  - [S] Low-Int Ogres and Zombies don't use complex tactics.
  - [S] Monsters flee or surrender when it's plausible.
  - [S] The narrator never invents stat-block abilities.

---

### ENC, TRAP, POIS: Gameplay Toolbox (p.192–203)

#### ENC-01 · XP budget
- **Tests:** ENC (Combat Encounter Difficulty p.202), Ruling R-03
- **Depends on:** MON-01
- **Interface:** Budgets are a GM tool, so (a)–(e) run through the structured API in GM/debug mode, not as player dialogue. Only the in-fiction check in (c) is judged on the player-facing transcript.
- **Journey:** Rate or build: (a) 4 Goblin Warriors vs 4 level-1 PCs. (b) Goblin Boss + 2 Goblin Warriors vs 4 level-1 PCs. (c) 1 Ogre vs 4 level-1 PCs. (d) Ogre + Goblin Boss + 2 Wolves vs 4 level-3 PCs. (e) "Build a Moderate forest encounter for my level-1 party."
- **Pass:**
  - [H] A level-1 party of 4 has budgets **Low 200 / Moderate 300 / High 400**. (a) 200 fits Low. (b) 300 fits Moderate.
  - [H] (c) 450 exceeds High. The GM log flags it as "Over High budget" with ruling ID R-03 and notes that the Ogre's CR is above the party's level (p.203).
  - [H] (c) The player-facing output never shows budgets, XP totals or the flag.
  - [S] (c) Before combat, the narration signals the danger in the fiction (for example, the Ogre's size and club), so the player can choose to avoid the fight.
  - [H] If the GM tries to add reinforcements that would push an encounter over High, the engine blocks the addition or logs a justification under R-03.
  - [H] (d) A level-3 party of 4 has budgets 600 / 900 / 1,600, so 750 fits Moderate.
  - [H] (e) Total XP ≤ 300 using only subset monsters.
  - [H] There are **no multipliers** (2024 rule).
  - [S] The build includes terrain or a reason to move (p.202).

#### ENC-02 · XP award
- **Tests:** MON (Experience Points p.255), CC (Level Advancement), Ruling R-02
- **Depends on:** ENC-01
- **Journey:** The party defeats encounter (b) from ENC-01.
- **Pass:**
  - [H] 300 XP is split into **75 each** (R-02 logged).
  - [H] Neutralized foes (fled, surrendered or pacified) also award XP.

#### TRAP-01 · Hidden Pit (detection is Study/Investigation, not Perception)
- **Tests:** TRAP (Hidden Pit p.200), CORE (Exceptions Supersede General Rules p.5), HAZ (Falling)
- **Depends on:** EXPL-04, HAZ-02
- **Setup:** The marching order is BROM first. `d6=[3]`.
- **Journey:** Run 1: the party walks on without searching, and JOZAN's Passive Perception is 15. Run 2: MIALEE uses the Study action, Investigation +5, `d20=[10]`, then the party wedges the lid with Iron Spikes. Run 3: LIDDA (level 3 Thief) climbs out of the pit.
- **Pass:**
  - [H] Run 1: nobody detects the pit **passively**, because the trap specifies a DC 15 Int (Investigation) check through Study. The lead PC falls, takes 3 Bludgeoning and is Prone.
  - [H] Run 2: 15 detects the pit, and the spike makes it safe.
  - [H] Run 3: escaping requires a Climb Speed, gear or magic, and LIDDA's Climb Speed works.

#### TRAP-02 · Poisoned Needle
- **Tests:** TRAP (Poisoned Needle p.200–201), CORE-03 (tools + skill), ORIG-02
- **Depends on:** CORE-03, COND-03
- **Setup:** LIDDA disarms using Thieves' Tools: `d20=[4,9]`, with Sleight of Hand +7 and Advantage (tool + skill). In the failure run, `d20=[3,5]`; her Con save is `d20=[6]`; `d10=[8]`.
- **Journey:** A Search with DC 15 Perception finds the needle. LIDDA uses an action to disarm it. The failure run follows.
- **Pass:**
  - [H] The disarm check is 9 + 7 = 16 against DC 15, a success.
  - [H] Failure run: 5 + 7 = 12 fails and triggers the needle. Her Con save of 8 fails DC 11, so she takes 8 Poison and is **Poisoned for 1 hour**. On a success she'd take 4 and wouldn't be Poisoned.
  - [H] The disarm attempt uses Thieves' Tools (Utilize: disarm a trap, DC 15, p.94). Without tools, the engine must log which ruling it applies.

#### POIS-01 · Injury poison
- **Tests:** POIS (Poison types; Serpent Venom p.197–198)
- **Depends on:** DMG-02
- **Journey:** LIDDA coats her Shortsword with Serpent Venom as a Bonus Action, then hits a Bandit (Con +1), `d20=[6]; d6=[2,5,6]`. Later she tries to coat a Mace.
- **Pass:**
  - [H] Applying the venom takes a **Bonus Action**.
  - [H] It triggers when the target takes Piercing or Slashing damage from the coated weapon.
  - [H] The Bandit's 7 fails DC 11 and takes 13 Poison damage.
  - [H] The dose is then used up.
  - [H] The Mace deals Bludgeoning damage, so its coating never triggers.

---

### MI: Magic items (p.204–253, 102–103)

#### MI-01 · Identifying and attuning
- **Tests:** MI (Identifying, Attunement p.102–103; Attunement Prerequisites p.205)
- **Depends on:** REST-01
- **Journey:** BROM finds a Cloak of Protection, identifies it during one Short Rest and attunes during a second. He tries to attune to a second Cloak of Protection. He attunes to three items, then tries a fourth. He leaves an item behind for 24 hours. He ends an attunement voluntarily.
- **Pass:**
  - [H] Identifying and attuning need **separate** Short Rests; an interrupted rest fails the attunement.
  - [H] Once attuned, he gets +1 AC and +1 to saves.
  - [H] A duplicate item and a 4th item are both refused.
  - [H] Attunement ends when the item has been more than 100 ft away for 24 hours, or voluntarily through a Short Rest.

#### MI-02 · Potions and consumables
- **Tests:** MI (Potions p.204; Consumable Items p.206), EQP-05
- **Depends on:** DMG-01
- **Pass:**
  - [H] Drinking or administering a potion is a **Bonus Action**, takes effect immediately and uses the potion up.
  - [H] Tasting a potion identifies it.

#### MI-03 · Wand of Magic Missiles
- **Tests:** MI (Wand of Magic Missiles p.251; Charges; Spells Cast from Items p.206)
- **Depends on:** SPELLS-01
- **Setup:** 7 charges. At dawn `d6=[3]`. When the last charge is spent, `d20=[1]`.
- **Journey:** LIDDA, who isn't a caster, uses the wand for 3 charges and then tries 4. MIALEE casts Magic Missile with a slot and then uses the wand in the same turn. Dawn passes. The last charge is spent.
- **Pass:**
  - [H] 3 charges cast Magic Missile at level 3, firing 5 darts.
  - [H] 4 charges are refused (maximum 3).
  - [H] LIDDA can use the wand because it needs no attunement.
  - [H] Casting from an item spends no slot, so MIALEE's combination is allowed.
  - [H] At dawn the wand regains 1d6 + 1 = 4 charges, up to its maximum of 7.
  - [H] When the last charge is spent, a d20 of 1 destroys the wand.

#### MI-04 · Spell Scroll
- **Tests:** MI (Spell Scroll p.244)
- **Depends on:** SPL-01
- **Journey:**
  - JOZAN reads a Scroll of Bless.
  - LIDDA tries to read it.
  - MIALEE at level 1 reads a Scroll of Web (level 2), making an Int check of `d20=[9]` + 3.
  - A second reading has `d20=[5]`.
  - A casting from a scroll is interrupted.
- **Pass:**
  - [H] JOZAN casts Bless from the scroll with no components; the scroll crumbles.
  - [H] The scroll is unintelligible to LIDDA.
  - [H] Web is above the level MIALEE can cast, so she needs a DC 12 check; 12 succeeds, using the scroll's **DC 13**.
  - [H] The second reading gets 8, which fails: the spell vanishes from the scroll.
  - [H] An interrupted casting doesn't use up the scroll.

#### MI-05 · +1 weapon and armor, Bag of Holding
- **Tests:** MI (Weapon +1 p.253; Armor +1 p.210; Bag of Holding p.212)
- **Depends on:** CMB-03
- **Pass:**
  - [H] A +1 Longsword gives BROM +6 to hit and 1d8 + 4 damage.
  - [H] +1 Chain Mail gives BROM **AC 20** (16 + 1 + 2 Shield + 1 Defense).
  - [H] The Bag of Holding holds up to 500 lb and always weighs 5 lb, and taking an item out uses the Utilize action.
  - [H] He can't wear two suits of armor or two cloaks.

---

## 6. Capstone journeys (acceptance tests)

A loop is **done** when these pass through the **natural-language interface**, with a clean event-log audit: no rule violations, and every ruling ID logged.

#### J1 · First Session (goblin trail)
- **Tests:** CC, ORIG, FEAT, EQP, EXPL, CMB, DMG, MON, ENC, REST, TRAP, MI
- **Depends on:** waves 1–6
- **Journey:**
  1. Create all four fixtures by conversation.
  2. March 6 miles at Normal pace along a forest road.
  3. Four Goblin Warriors ambush the party, with the surprise dice from CMB-01, and the party fights to victory.
  4. Short Rest with Hit Dice.
  5. Hidden Pit, then a Poisoned-Needle chest.
  6. Loot: Potion of Healing and 30 GP.
  7. XP is awarded.
- **Pass:**
  - [H] The final snapshot matches: 200 XP split as 50 each (R-02).
  - [H] HP, Hit Dice, slots and uses reconcile with the log.
  - [H] The clock advanced 2 hours of travel + 1 hour of rest + combat rounds.
  - [H] The gold is correct.
  - [S] The judge rates the session transcript coherent and fun, at least 4/5.

#### J2 · Death's Door
- **Tests:** DMG, SPELLS, SPL, CMB, COND
- **Depends on:** DMG-01, SPELLS-01, SPELLS-03
- **Journey:** MIALEE drops to 0 and fails one death save. JOZAN, 70 ft away, moves into range and casts Healing Word. On the next goblin attack MIALEE casts Shield. The party retreats: LIDDA with Cunning Action Disengage, BROM with the Disengage action.
- **Pass:**
  - [H] Every state transition matches the rules.
  - [H] The one-slot-per-turn rule holds.
  - [S] The player agent is clearly prompted whenever a Reaction window opens.

#### J3 · The Long Road
- **Tests:** EXPL, HAZ, REST, ENC, EQP
- **Depends on:** EXPL-01, HAZ-02, ENC-01
- **Journey:** A 3-day overland trip. Rations are tracked, one ration is lost, and one day runs to 10 hours. Watches are kept during Long Rests. A generated Moderate encounter interrupts the second night's rest after 3 hours.
- **Pass:**
  - [H] Extended-travel saves are made and Exhaustion is applied and removed correctly.
  - [H] The interrupted rest grants Short Rest benefits, and the resumed rest takes +1 hour.
  - [H] The 16-hour spacing between Long Rests is respected.
  - [H] The encounter stays within the Moderate budget.

#### J4 · A Wizard's Day
- **Tests:** CLS-WIZ, SPL, SPELLS, MI, REST
- **Depends on:** CLS-WIZ-01..03, MI-03, MI-04
- **Journey:** MIALEE, at level 3, prepares spells. She ritual-casts Detect Magic, finds a Scroll of Web and copies it, fights two battles spending every slot, uses Arcane Recovery on a Short Rest, and uses a Wand of Magic Missiles until its last charge.
- **Pass:**
  - [H] Slots, spellbook contents, gold (−100 GP), the clock (+4 hours copying, +10 minutes ritual) and wand charges all reconcile.

#### J5 · The Goblin Boss's Lair (level 3 capstone)
- **Tests:** CMB, DMG, SPELLS, CLS-* level 3, MON, ENC, MI, COND
- **Depends on:** everything through wave 7
- **Journey:** A level-3 party fights a Goblin Boss, 2 Goblin Warriors and an Ogre (750 XP, Moderate). The fight includes a Hold Person attempt on the Boss (an **invalid target**: goblins are Fey, not Humanoid, so the slot is spent and the Boss appears to save), Hold Person on the Ogre (also invalid, since it's a Giant), Web, Sneak Attack with Steady Aim, a Champion critical on a 19, Preserve Life, Redirect Attack and a +1 weapon.
- **Pass:**
  - [H] All interactions resolve correctly: Paralyzed auto-crits, Redirect Attack, Concentration checks, Improved Critical and the Preserve Life cap.
  - [H] XP is 750, split as 187 each (R-02, rounded down).
  - [S] The fight feels climactic and fair.

#### J6 · Town Week
- **Tests:** SOC, EQP, CC, ORIG, MI
- **Depends on:** SOC-01, EQP-04, EQP-06, CC-03, MI-01
- **Journey:** The party sells loot at half price and pays a Modest lifestyle. It Influences an Indifferent guild master, including a failed attempt and the 24-hour wait. JOZAN crafts a Shortbow. The party reaches 900 XP and levels to 3 (subclass choices), then attunes to a Cloak of Protection.
- **Pass:**
  - [H] Money, time, proficiencies, level, HP, prepared spells and attunement are all consistent.
  - [S] NPC attitudes evolve believably.

---

## 7. Notes for the loop

- **Coverage metric.** Track the share of scenarios green per section ID. A section is green when all of its [H] assertions pass through both interfaces.
- **Triage rule.** When a scenario fails, check its "Depends on" sections first. If any is red, fix that section instead.
- **Regression goldens.** Every bug found in manual play becomes a new scenario with forced dice **before** the fix lands.
- **Traceability.** Every rule implementation carries an SRD page reference in code comments and in the event log. Rules text is referenced by page, not pasted into prompts.
- **2014 → 2024 traps.** Several scenarios exist mainly to catch an engine, or an LLM narrator, falling back to 2014 rules:
  - Surprise gives Disadvantage on Initiative; it doesn't skip a turn.
  - Sleep uses saves, not an HP pool.
  - Exhaustion is −2 per level to D20 Tests.
  - Long Rests restore all Hit Dice.
  - Potions take a Bonus Action.
  - Grappling uses a save.
  - The spell rule is one slot per turn.
  - Cure Wounds is 2d8.
  - Species don't raise ability scores.
  - Encounters have no multipliers.
  - Underwater melee exempts Piercing weapons, not a specific list.
  - Goblins are Fey, not Humanoid.
  - Dwarves have Speed 30 and Darkvision 120.
  - Heavy weapons key off Strength 13, not Small size.
