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
pip install pytest && python -m pytest
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
