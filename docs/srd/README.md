# SRD 5.2.1 rule units

This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode.

The files here are generated from `docs/SRD_CC_v5.2.1.pdf` by `scripts/srd/extract.py`. Don't edit them by hand.

| File | What it is |
|---|---|
| `units.jsonl` | One rule unit per line, the input to the rule-audit loop (`docs/srd-rule-loop-plan.md`) |
| `srd.md` | The same units as one readable Markdown file, for review and grep |
| `units.approved` | sha256 of the reviewed `units.jsonl`; the loop refuses to run on unapproved units |

## Unit fields

- `id`: a deterministic slug, e.g. `GLOSS.grappled` or `PLAY.combat.cover`.
- `chapter`, `heading_path` and `title`: where the unit sits in the SRD.
- `tag`: the glossary tag (`Condition`, `Action`, …) or null.
- `pages`: first and last PDF page.
- `text`: the verbatim rule text.
  - Running prose is joined into paragraphs.
  - Paragraphs are separated by a blank line. Each numbered step (`1:`), bullet (`•`), bold run-in label ("Speed 0.") and stat-block line is its own paragraph.
  - Sidebars are moved after the unit's running text. A table laid out mid-sentence follows its paragraph.
  - Sub-headings are `####` lines.
  - A table without a header whose rows start with a bold label (the Core Traits tables) has two columns and an empty header row.
  - Table footnotes ("*Primordial includes …") are paragraphs after the table.
  - A table that runs over two pages is joined into one (the Trinkets table).
  - A stat block's ability grid is a table with one row per ability (`| Str | 8 | −1 | −1 |`). Values stay as printed: the Young White Dragon's Intelligence save is "2" in the SRD.
  - Tables are Markdown, headed by `Table: <title>`. A table printed as side-by-side strips ("Item | Cost | Item | Cost") is stacked into one list, and one continued in the next column is merged back together.
- `see_also`: cross-references, either `Chapter › Section` or a glossary entry name.

## Where units split

Each chapter is split at a fixed heading size:

| Heading size | Chapters |
|---|---|
| 14pt subsection | Playing the Game, Character Creation, Gameplay Toolbox, the Monsters introduction |
| 12pt entry | Classes (one unit per class feature), Origins, Feats, Equipment, Spells, Rules Glossary, Magic Items |
| 15pt stat block | Monsters A–Z, Animals |

Stat blocks inside a spell or magic item stay part of that entry. You can change the split sizes in `CHAPTERS` in the script.

## Pipeline

1. Read the PDF and put the lines in reading order.
2. Cut the text into chapters and units.
3. Assemble each unit's text, including its tables.
4. Move each table to the unit that names it.
5. Apply the fix-ups (`fixups()`): deterministic clean-ups such as turning ability grids into tables.
6. Run the gate.

`srd.md` is rendered from `units.jsonl` and never edited by hand. Any correction goes into the script, so that a rerun reproduces it and the gate re-checks it.

## Regenerate, check, approve

```bash
python scripts/srd/extract.py            # writes units.jsonl + srd.md, then runs the gate
python scripts/srd/extract.py --check    # re-runs the gate on the existing units.jsonl
python scripts/srd/extract.py --approve  # after review: pins units.jsonl by hash
```

The gate checks four things:
- ids are unique;
- no unit is empty;
- every page from 5 to 364 is covered;
- there are about 155 glossary entries.

It checks the structure too:
- no stray numbers sit outside tables (the sign of a table row that got detached);
- every table with a `Level` column runs 1, 2, 3 … without gaps, and to 20 when it starts at 1;
- every die-roll table (`1d100`, `1d8`, …) covers 1 to N in order, with `00` counting as 100;
- no table has many rows with text only in the first cell (the sign of a table cut down the middle);
- no table sits in the middle of a sentence;
- every class spell-list entry matches the level and class line of that spell's own description, and every class a
  description names lists the spell. The four omissions that are in the SRD itself (Phantasmal Force for Bard,
  Sorcerer and Wizard; Mind Spike for Sorcerer) are allowlisted in `SRD_LIST_OMISSIONS`;
- unit start pages follow document order within each chapter.

It also checks the output against the PDF:
- every PDF heading survives as a unit title, a `####` line or text;
- every prose line of the PDF appears verbatim in some unit (ignoring whitespace and hyphens);
- because tables are rearranged into rows, all remaining text is compared by character counts, so no character may be missing (table header words are exempt, since repeated headers are kept once).

## Text-layer quirks handled

- Bounding boxes of bold-italic run-in labels are about 20pt too high, so lines are found by text baseline.
- A few space characters inside words have no visual gap ("Short|sword", "spell|casters"). They are ignored.
- Small-caps headings ("Acid Splash") get their letter case from glyph size, because the text layer's case is wrong.
- The ½ glyph is stored as the text "1/2"; it becomes "½" ("1½ pints").
- The outline's chapter pages are off by one in places, so chapters start at their 26pt title line.

## Known limitations

- A line-end hyphen is kept only if the same hyphenated word appears elsewhere in the SRD. A compound that is hyphenated only at a line break loses its hyphen.
- Table columns come from the header cells. Each boundary sits in the widest vertical strip that no cell text touches.
  Tables without a header row are kept as plain lines.
- A table is recognised as page-wide when its header row has cells on both sides of the column gutter. A
  page-wide table with no header row would be read as two half-tables (none are known in the SRD).
