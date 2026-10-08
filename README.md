# DungDra

An attempt to build D&amp;D SRD 5.2.1 (5.5e) autonomously using the ruleset and AI-derived test scenarios using loop engineering.

A rules-faithful, single-player game engine that is compatible with fifth edition. It's written in pure Python 3.10+ with no runtime dependencies.

## Play

```bash
python -m dungdra              # interactive adventure: "The Goblin Trail"
python -m dungdra --gm-log     # also show GM-only log lines (budgets, hidden DCs, rulings)
```

Type `use the sample party` (BROM, LIDDA, MIALEE, JOZAN) or describe your own characters, for example *"A dwarf fighter, ex-soldier, standard array with Str 15, Dex 14 ... Defense style. Chain mail, shield and longsword."* The game asks for any missing choices. Then type `begin the adventure`. Here are some example commands: `inventory`, `BROM inventory`, `MIALEE spells`, `JOZAN potions`, `BROM attacks the goblin with his longsword`, `MIALEE casts magic missile at goblin warrior 2`, `LIDDA uses cunning action to hide`, `end turn`, `continue`, `short rest`, `status`. In combat, a refused command (such as an out-of-range attack) doesn't cost anything. After each command the game shows what the active character can still do, and the turn ends on its own once no action or useful Bonus Action is left. Use `--manual-turns` to always type `end turn` yourself. Whenever the rules offer you a choice (a Reaction such as Shield, Halfling Luck, Heroic Inspiration or Savage Attacker), the game asks you.

Stuck on the goblin ambush? `docs/example-ambush.md` has a full winning session (`--seed 5`) with the commands used and some tactics.

## Architecture

| Module | Role |
|---|---|
| `dice.py`, `events.py` | Forced-dice injection over a seeded RNG, and an event log where every entry is player-visible or GM-only and carries SRD pages and ruling IDs |
| `d20.py`, `effects.py`, `creature.py` | D20 Tests, Advantage/Disadvantage, rerolls, and an effect-hook system that holds all 15 conditions, damage and healing |
| `character.py`, `creation.py`, `features.py`, `fixtures.py` | Player characters, the validating creation builder, levels 1–3, and the four scenario fixtures |
| `combat.py`, `actions.py`, `class_actions.py`, `mounted.py`, `damage.py` | Initiative, turn economy, attacks, weapon mastery, Opportunity Attacks, grappling, and death saves |
| `spells.py`, `spellcasting.py`, `magic_items.py` | Spellcasting rules, the 32 subset spells, and the 7 magic items |
| `monster.py`, `gm.py`, `encounters.py` | The 14 stat blocks, monster tactics, encounter budgets (R-03), and the XP split (R-02) |
| `rest.py`, `hazards.py`, `traps.py`, `explore.py`, `gear.py` | Rests, hazards, poisons, traps, travel, jumping, trade, lifestyle, and crafting |
| `api.py` | Structured command API: `Session().execute({"cmd": ..., ...})` |
| `nl.py`, `play.py`, `cli.py`, `adventure.py` | Natural-language interface, the campaign, and the terminal UI |
| `audit.py`, `snapshot.py` | JSON state snapshot and log reconciliation |

## Tests

```bash
pip install pytest && pytest       # pytest 7+; `python -m pytest` also works
```

Each test file maps to scenario IDs in `docs/dnd-golden-scenarios-srd521.md`. The journey tests (J1–J6) play through the natural-language interface. `docs/scenario-notes.md` lists where the engine follows the SRD over a scenario, plus the extra ruling R-04.

> **License note (CC-BY-4.0).** The SRD may be used freely, but the game and any repo that includes SRD text or data **must** include this attribution statement verbatim (SRD p.1):
> *"This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode."*
> Don't add any other attribution to Wizards. You may say "compatible with fifth edition" or "5E compatible".

## Scope and limitations

**Rules source:** System Reference Document 5.2.1 (SRD 5.2.1, the 2024 "5.5e" rules), 364 pages. All page references (`p.N`) point to that PDF (@docs/SRD_CC_v5.2.1.pdf).

**Purpose:** Success criteria for a loop-engineered, rules-faithful single-player D&D game built with Claude Code. An LLM plays, the engine resolves, assertions check.

**Principle: implement all of the rules, but only a subset of the content.** The core rules and the Rules Glossary together are the engine. Implement them completely, because the rules are interlocked. Everything else is content, loaded as data. This subset is a thin vertical slice: it exercises every rule once and yields a playable game. Adding more content later should be data entry, not engine work.

### In scope

| Area | In the first slice | SRD pages |
|---|---|---|
| **Core rules (all of them)** | Playing the Game: D20 Tests, Advantage/Disadvantage, Proficiency, Actions, Social Interaction, Exploration, Travel, Combat, Damage & Healing | p.5–18 |
| **Rules Glossary (all of it)** | Every definition, all 15 conditions, hazards, rests, areas of effect, Unarmed Strike (grapple/shove), Influence, Hide, etc. | p.176–191 |
| Levels | **1–3 only** (XP 0 / 300 / 900; Proficiency Bonus +2 throughout) | p.23 |
| Character creation | Standard Array, Point Cost, Random Generation; background ability adjustments; alignment; languages | p.19–23 |
| Classes | **Fighter** (Champion), **Rogue** (Thief), **Cleric** (Life Domain), **Wizard** (Evoker), features for levels 1–3 only | p.36–40, 47–49, 61–64, 77–82 |
| Species | **Human, Dwarf, Elf** (all three lineages), **Halfling** | p.83–86 |
| Backgrounds | **All four:** Acolyte, Criminal, Sage, Soldier | p.83 |
| Feats | **Origin:** Alert, Magic Initiate, Savage Attacker, Skilled.<br>**Fighting Style:** Archery, Defense, Great Weapon Fighting, Two-Weapon Fighting | p.87–88 |
| Equipment | All weapons (incl. **mastery properties**), all armor and Shield, tools used by the fixtures, core gear (Healer's Kit, Potion of Healing, Torch, Rations, Iron Spikes, Component Pouch, Holy Symbol, packs), coins, lifestyle, crafting nonmagical items | p.89–103 |
| Spellcasting rules | All of "Spells" rules | p.104–106 |
| Spells (32) | **Cantrips (10):** Fire Bolt, Guidance, Light, Mage Hand, Minor Illusion, Prestidigitation, Ray of Frost, Sacred Flame, Spare the Dying, Thaumaturgy.<br>**Level 1 (14):** Bless, Burning Hands, Command, Cure Wounds, Detect Magic, Guiding Bolt, Healing Word, Mage Armor, Magic Missile, Sanctuary, Shield, Shield of Faith, Sleep, Thunderwave.<br>**Level 2 (8):** Aid, Hold Person, Invisibility, Lesser Restoration, Misty Step, Scorching Ray, Spiritual Weapon, Web | p.107–175 |
| Monsters (14) | Bandit, Cultist, Giant Rat, Goblin Minion, Goblin Warrior, Goblin Boss, Guard, Kobold Warrior, Ogre, Priest Acolyte, Riding Horse (mount), Skeleton, Wolf, Zombie | p.254–364 |
| Gameplay Toolbox | Travel Pace/terrain/extended travel, Poison (incl. Serpent Venom), Traps (Collapsing Roof, Falling Net, Hidden Pit, Poisoned Needle, Spiked Pit), Combat Encounter budget | p.192, 197–203 |
| Magic items (7) | Potion of Healing, Weapon +1, Armor +1, Spell Scroll (levels 0–2), Wand of Magic Missiles, Cloak of Protection (attunement), Bag of Holding | p.99, 204–253 |

### Out of scope for now

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

### Rulings register (gaps in the SRD)

The engine must implement each of these as an explicit, logged ruling. The judge treats them as correct only when the ruling ID appears in the event log.

| ID | Gap | Proposed ruling |
|---|---|---|
| R-01 | The SRD 5.2.1 has no rule for gaining the same proficiency twice. For example, the Rogue class and the Criminal background both grant Thieves' Tools. | The player picks a different tool proficiency instead. |
| R-02 | The SRD says XP is awarded for defeating or neutralizing a monster (p.255) but doesn't say how XP is shared. | Divide the total evenly among participating PCs, rounding down. |
| R-03 | The encounter rules build encounters to a budget (p.202). There's no label for an encounter whose XP exceeds the High budget. Such encounters can only come from authored content or GM improvisation, because generated encounters are built within budget. | The engine flags it as **"Over High budget"** in the **GM log only**, with the ruling ID, and never shows the flag to the player. If the GM improvises reinforcements, the engine blocks the over-budget addition or requires a logged justification. Danger is conveyed to the player **in the fiction** (SRD "Powerful Creatures" guidance, p.203), not as a number. |
| R-04 | Disarming a trap (Poisoned Needle) without Thieves' Tools isn't covered; the tool's Utilize entry assumes the tool. | Allowed as a plain Dexterity (Sleight of Hand) check with no tool proficiency or tool+skill Advantage; logged GM-only. |
| R-05 | GLOSS.grappled: “unless you are Tiny or two or more sizes smaller than it”: does a Tiny creature dragged by a Tiny grappler cost extra movement? | A Tiny grappled creature never adds extra movement cost, whatever the grappler's size. *Note: As the reviewer reads the rule.* |
| R-06 | GLOSS.grappled: “any target other than the grappler” when two creatures grapple you. | Attacks against any of your current grapplers have no Disadvantage from Grappled; attacks against anyone else have it. *Note: The rule's intent; the reviewer doesn't fully agree with the rule itself.* |
| R-07 | GLOSS.grappled: “Your Speed is 0 and can’t increase”: does it cover special speeds, and speeds gained later? | Every Speed (Climb, Swim, Fly, including speeds gained after the grapple starts) is 0 and can't increase while Grappled. *Note: For now. A grappled flyer might rather inherit the grappler's movement than stop; a swimmer stopping (0) is fine.* |
| R-08 | GLOSS.tremorsense: “pinpoint the location”: does pinpointing cancel the unseen-target rules (Disadvantage on attacks, 'a creature you can see')? | No. Pinpointing makes the location known (no guessing the space), but Tremorsense doesn't count as sight. Attacks against the target still have Disadvantage for an unseen target, and spells that need a target you can see stay unavailable. |
| R-09 | PLAY.combat.cover: “Another creature or an object that covers at least half of the target”: does a creature's size matter, and can creatures give more than Half Cover? | Any other creature in the line between the origin and the target gives Half Cover, whatever its size. A creature never gives Three-Quarters or Total Cover, and several creatures in the line still give only Half. |
| R-10 | PLAY.combat.cover: “Can’t be targeted directly”: does Total Cover stop area effects? | 'Directly' limits the refusal to effects that select the creature (attack rolls, chosen spell targets, each target of a multi-target spell). An area spell isn't refused. Whether the area reaches a creature behind Total Cover is decided by GLOSS.area-of-effect (a line is blocked only by Total Cover), so with Total Cover from the origin it isn't affected. SPL-05 stays as is. |
| R-11 | PLAY.combat.cover: “originates on the opposite side of the cover”: does an obstacle that covers the target from an attacker also cover the attacker from the target? | No. Cover is worked out per target and per origin: an obstacle that covers the target from an attacker gives the attacker no cover unless it also covers the attacker (a separate entry). |
| R-12 | SPELL.bless: “Whenever a target makes an attack roll or a saving throw” — do Death Saving Throws and Concentration saves get the d4? | Any roll the rules call a saving throw gets the 1d4, including Death Saving Throws and Concentration saves. |
| R-13 | SPELL.bless: “You bless up to three creatures within range.” — can the caster be a target? | The caster can bless themself as one of the targets. *Note: this was confirmed on a 3d6 reddit thread* |
| R-14 | SPELL.bless: “within range” — is range checked only at casting? | Range is checked only at casting. The benefit lasts until the spell ends, wherever the target goes. |
| R-15 | SPELL.casting-spells.effects.targets: 'If you cast a spell on someone or something that can't be affected by it, nothing happens to that target': does this cover restrictions the caster can see, such as Mage Armor's 'who isn't wearing armor', or does the engine refuse those? | Reading A, applied to every target restriction in a spell's description except the positional ones the targeting rules name (range, clear path, sight). If a target fails a restriction such as creature type, wearing armor, or 0 HP, the spell is cast: the slot (and action) are spent, nothing happens to that target, and the caster either sees an apparent successful save (spells with a save) or a player-visible note that the spell did nothing (no save). The half-refusal abuse tests accept either a clean refusal or this resolution, so they don't depend on this ruling. *Note: Target kind (creature vs object, from the spell's description) is part of choosing a target and stays a refusal, like range, clear path and sight (T-26, T-37). Every other restriction (creature type, armor, 0 HP, …) is an invalid target: cast, slot spent, nothing happens.* |
| R-16 | SPELL.casting-spells.effects.targets: 'The area determines what the spell targets': for an area spell that affects 'each creature' in the area (Thunderwave), does the engine work out who is in the area, or does it rely on a list the caller supplies? | The engine works out the creatures in the area from the scene, using the shape, point of origin and direction. A caller's list can only narrow the choice where the spell says 'of your choice' (Sleep). It never adds creatures outside the area or drops creatures inside an 'each creature' area. *Note: The engine selects creatures in the area from positions, shape, origin and direction; a caller list only narrows 'of your choice' spells.* |
| R-17 | GLOSS.ready: GLOSS.ready ambiguity 1: 'holding on to the spell’s magic requires Concentration'. Does holding a spell that isn't a Concentration spell end an existing Concentration? | Reading A. Holding any readied spell is an effect that requires Concentration, so readying one ends Concentration on an earlier spell such as Bless. *Note: you can only concentrate on one thing at a time* |
| R-18 | GLOSS.ready: GLOSS.ready ambiguity 2: does an ignored trigger use up the readied action? | Reading A. Ignoring the trigger keeps the readied action and the Reaction for a later occurrence of the same circumstance, until the start of your next turn. *Note: nothing says it wouldn't last until the start of the next turn if the trigger is ignored* |
| R-19 | GLOSS.ready: GLOSS.ready gap: what happens to a held spell that isn't released before the start of your next turn? | The Concentration that holds it ends at the start of your next turn. The spell dissipates without effect, and the spent slot isn't refunded. *Note: the unreleased spell is gone* |
| R-20 | GLOSS.ready: GLOSS.ready #4: is the readied response checked when you ready it, or only when the trigger occurs? | It is checked when you ready it. A response that isn't one action, or one move up to your Speed, is refused cleanly on your turn before the action is spent. *Note: when you ready it, not when the trigger occurs* |
| R-21 | GLOSS.prone: GLOSS.prone ambiguity 1: 'half your Speed (round down)' — current Speed after modifiers, or base Speed? | Use the creature's current Speed after all modifiers, halved and rounded down (Speed 25 costs 12; Speed 5 costs 2). *Note: Current Speed after modifiers, as in 'If your Speed is 0' in the same sentence.* |
| R-22 | GLOSS.prone: GLOSS.prone gap: righting yourself with less movement left than half your Speed. | Refuse it cleanly. Righting yourself needs at least the full cost in remaining movement, and no partial cost carries over. *Note: You can't spend movement you don't have; refused before anything changes.* |
| R-23 | MONSTER.goblins.goblin-warrior: 'if the attack roll had Advantage' when Advantage and Disadvantage cancel | Reading A. The extra 1d4 applies only when the roll is made with Advantage. If Advantage and Disadvantage cancel, the roll has neither, so the 1d4 isn't added. *Note: Cancelled Advantage is no Advantage: 'the roll has neither of them'.* |
| R-24 | MONSTER.goblins.goblin-warrior: is the conditional 1d4 doubled on a Critical Hit? | Reading A. The 1d4 is a damage die of the attack, so a Critical Hit rolls it twice like the 1d6. *Note: The 1d4 is one of the attack's damage dice; a Critical Hit rolls them all twice.* |
| R-25 | MONSTER.goblins.goblin-warrior: Gear lists a Shield and a Two-Handed Shortbow with no arrows. Does the goblin lose its Shield AC when it shoots, and does it use up ammunition? | Stat-block actions and AC are used exactly as printed. The goblin keeps AC 15 while using the Shortbow, and a monster's stat-block ranged attacks don't track ammunition. *Note: Stat-block actions and AC are used as printed; monsters don't track ammunition.* |
| R-26 | GLOSS.cone: GLOSS.cone ambiguity 2: is 'width' the full width across the Cone, or the width from the axis out to each side? | Full width, centred on the chosen direction: a point may be at most half its distance along the axis away from the axis (about 53°). The 15-ft-at-15-ft example then covers three 5-ft squares. |
| R-27 | GLOSS.cone: GLOSS.cone gap: on a grid, is a creature in the Cone when any part of its square is, or only when the centre of its square is? | A creature is in the Cone when the centre of its space (its position) lies inside the Cone, so the 15-ft width at 15 ft covers exactly three squares. *Note: A centre exactly on the edge is inside. Revisit when creature spaces (T-46) give Large creatures several squares.* |
