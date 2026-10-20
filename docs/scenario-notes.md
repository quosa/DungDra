# Scenario notes

Places where the golden scenarios and the SRD 5.2.1 text disagree, or where the
engine had to make an explicit ruling beyond the register in the README.

| Scenario | Issue | What the engine does |
|---|---|---|
| CLS-WIZ-03 | The scenario says the scroll isn't consumed after copying. SRD p.244 ("Copying a Scroll into a Spellbook") says the copier makes an Int (Arcana) check (DC 10 + spell level) and the scroll is destroyed whether the check succeeds or fails. | Follows the SRD: Arcana check, 2 h + 50 GP per level (p.78), scroll destroyed. |
| CC-03 / CLS-WIZ-01 | Only 7 level 1 Wizard spells are in the subset, so a level 2 Wizard can't add two new subset spells. | Spellbooks may hold other SRD Wizard spells (levels 1–2) as named placeholders. Casting them is refused as out of scope. |
| CORE-04 | MIALEE has Darkvision, so Dim Light near her counts as Bright Light. | The scenario's Dim Light case is modelled as looking into a Lightly Obscured area (`dim_light` tag), which gives −5. |
| TRAP-02 | Disarming without Thieves' Tools needs a logged ruling. | **R-04**: the attempt is allowed as a plain Dexterity (Sleight of Hand) check without tool proficiency or the tool+skill Advantage; logged GM-only. |
