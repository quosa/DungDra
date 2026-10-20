"""Split the SRD 5.2.1 PDF into rule units for the rule-audit loop.

    python scripts/srd/extract.py            # writes docs/srd/units.jsonl and docs/srd/srd.md
    python scripts/srd/extract.py --check    # validates units.jsonl against the PDF
    python scripts/srd/extract.py --approve  # pins the reviewed units.jsonl by hash

The PDF is two-column. Headings are GillSans-SemiBold (26pt chapter, 18pt section,
15pt stat block, 14pt subsection, 12pt entry); body text is Cambria. Footers sit
below y=730. Chapters come from the PDF outline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PDF = Path("docs/SRD_CC_v5.2.1.pdf")
OUT = Path("docs/srd")
UNITS = OUT / "units.jsonl"
APPROVED = OUT / "units.approved"

MID = 297.0  # column gutter (page width 594)
FOOTER_TOP = 730.0
HEADING_FONT = "GillSans-SemiBold"
RANK = {26: 0, 18: 1, 15: 2, 14: 2, 12: 3}  # heading size -> depth

# chapter title -> (id prefix, smallest heading size that starts a unit)
CHAPTERS = {
    "Playing the Game": ("PLAY", 14),
    "Character Creation": ("CREATE", 14),
    "Classes": ("CLASS", 12),
    "Character Origins": ("ORIGIN", 12),
    "Feats": ("FEAT", 12),
    "Equipment": ("EQUIP", 12),
    "Spells": ("SPELL", 12),
    "Rules Glossary": ("GLOSS", 12),
    "Gameplay Toolbox": ("TOOLBOX", 14),
    "Magic Items": ("MAGIC", 12),
    "Monsters": ("MONSTER", 14),
    "Monsters A–Z": ("MONSTER", 15),
    "Animals": ("ANIMAL", 15),
}
# headings that only group entries; left out of unit ids
ID_SKIP = re.compile(r"^(rules-definitions|spell-descriptions|magic-items-a-z|.*-class-features)$")
TAG = re.compile(r"^(?P<name>.*?)\s*\[(?P<tag>[^\]]+)\]$")
SEE_ALSO = re.compile(r"See also\s+")
QUOTED = re.compile(r"“([^”]+?)\.?”(?:\s*\((.*?)\))?")


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    font: str
    size: float


def words_text(words: list[Word]) -> str:
    """Words joined by a space unless they touch (a font change inside a word, "Healing" + ",").
    A large negative gap means the next word is on a new line (a merged heading): a space."""
    if not words:
        return ""
    out = words[0].text
    for prev, w in zip(words, words[1:], strict=False):
        out += ("" if -2 < w.x0 - prev.x1 < 1.0 else " ") + w.text
    return out


@dataclass
class Line:
    words: list[Word]
    page: int

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> float:
        return max(w.bottom for w in self.words)

    @property
    def size(self) -> float:
        return max(w.size for w in self.words)

    @property
    def text(self) -> str:
        return words_text(self.words)

    @property
    def heading_size(self) -> int | None:
        """Rounded size if this line is a unit-level heading, else None."""
        if all(HEADING_FONT in w.font for w in self.words):
            s = round(self.size)
            if s in RANK:
                return s
        return None

    @property
    def body(self) -> bool:
        """Running prose: body text, stat blocks and sidebars (joined into paragraphs)."""
        return all(_prose(w) for w in self.words)

    @property
    def run_in(self) -> bool:
        """Starts with a bold run-in label ("Speed 0.", "Scimitar.", "AC 15")."""
        return "Bold" in self.words[0].font

    @property
    def table_start(self) -> bool:
        w = self.words[0]
        return HEADING_FONT in w.font and "SC700" not in w.font and round(w.size, 2) in (10.5, 9.25)

    @property
    def sidebar_text(self) -> bool:
        w = self.words[0]
        return "GillSans" in w.font and abs(w.size - 9.0) < 0.2 and "SemiBold" not in w.font

    @property
    def sidebar_title(self) -> bool:
        return "SC700" in self.words[0].font and "SemiBold" not in self.words[0].font


def _prose(w: Word) -> bool:
    f = w.font
    return (
        "Cambria" in f
        or "Optima" in f
        or "ScalaSans" in f
        or ("GillSans" in f and abs(w.size - 9.0) < 0.2 and "SemiBold" not in f)  # sidebar text
        or ("GillSans" in f and w.size < 8.8)  # table footnotes ("*Primordial includes …")
    )


# ---------------------------------------------------------------- page layout
def _rows(words: list[Word], tol: float = 3.0) -> list[list[Word]]:
    rows: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        if rows and abs(rows[-1][0].top - w.top) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w.x0) for r in rows]


def _lines_in(words: list[Word], page: int) -> list[Line]:
    """Split a set of same-column words into lines, breaking on large horizontal gaps too."""
    out = []
    for row in _rows(words):
        cur = [row[0]]
        for w in row[1:]:
            if w.x0 - cur[-1].x1 > 25:  # table cells in the same column
                out.append(Line(cur, page))
                cur = [w]
            else:
                cur.append(w)
        out.append(Line(cur, page))
    return out


def _crosses_gutter(row: list[Word]) -> bool:
    """A word straddles the gutter, or text runs across it with ordinary word spacing
    (real columns are ~25pt apart; a wide table row can break exactly at the midline)."""
    row = sorted(row, key=lambda w: w.x0)
    return any(w.x0 < MID - 5 and w.x1 > MID + 5 for w in row) or any(
        a.x0 < MID <= b.x0 and b.x0 - a.x1 < 8 for a, b in zip(row, row[1:], strict=False)
    )


def _spanning_header(row: list[Word]) -> bool:
    if not all(HEADING_FONT in w.font and w.size < 10 for w in row):
        return False
    left = [w.text for w in row if w.x0 < MID]
    right = [w.text for w in row if w.x0 >= MID]
    return bool(left) and bool(right) and left != right


def reading_order(words: list[Word], page: int) -> list[Line]:
    """Two-column reading order; rows with a word across the gutter are full-width."""
    words = [w for w in words if w.top < FOOTER_TOP]
    bands: list[tuple[list[Word], list[Word]]] = [([], [])]
    wide_rows: list[list[Word]] = []
    order: list[tuple[str, int]] = []  # ("band", i) / ("wide", i)
    rows = _rows(words)
    # full-width: a word straddles the gutter, or text runs across it with ordinary word spacing
    # (real columns are ~25pt apart; a wide table row can break exactly at the midline)
    wide = [_crosses_gutter(r) for r in rows]
    # A full-width table's header or short rows may not cross the gutter themselves:
    # table-font rows adjacent to a wide table row belong to the same full-width block.
    tabular = [all("GillSans" in w.font and not _prose(w) and w.size < 11 for w in r) for r in rows]

    # a table printed across both page columns: its header row has different cells on the two sides
    # of the gutter (two tables side by side each have their own, identical header: "Spell | School")
    # ... unless a table title also sits above it in the right column: then they are two tables
    # ("Level 8 Warlock Spells" beside "Fiend Spells")
    def titled_right(i: int) -> bool:
        above = [r for r in rows[max(0, i - 2) : i] if 0 < rows[i][0].top - r[0].top < 30]
        return any(
            HEADING_FONT in w.font and round(w.size, 2) == 10.5 and w.x0 >= MID for r in above for w in r
        )

    wide = [
        wd or (_spanning_header(r) and not titled_right(i))
        for i, (wd, r) in enumerate(zip(wide, rows, strict=True))
    ]
    changed = True
    while changed:
        changed = False
        for i, r in enumerate(rows):
            if wide[i] or not tabular[i]:
                continue
            for j in (i - 1, i + 1):
                if 0 <= j < len(rows) and wide[j] and tabular[j] and abs(rows[j][0].top - r[0].top) < 20:
                    wide[i] = changed = True
                    break
    for row, is_wide in zip(rows, wide, strict=True):
        if is_wide:
            order.append(("band", len(bands) - 1))
            wide_rows.append(row)
            order.append(("wide", len(wide_rows) - 1))
            bands.append(([], []))
        else:
            left, right = bands[-1]
            for w in row:
                (left if w.x0 < MID else right).append(w)
    order.append(("band", len(bands) - 1))
    out: list[Line] = []
    seen = set()
    for kind, i in order:
        if (kind, i) in seen:
            continue
        seen.add((kind, i))
        if kind == "wide":
            out.append(Line(wide_rows[i], page))
        else:
            left, right = bands[i]
            out += _lines_in(left, page) + _lines_in(right, page)
    return out


# ---------------------------------------------------------------- text assembly
HYPHEN_END = re.compile(r"([A-Za-z]+)-$")
HYPHEN_WORD = re.compile(r"\b[A-Za-z]+-[A-Za-z]+\b")


ITEM_START = re.compile(r"^(•|\d+:|[*†‡]\S)")  # bullets, numbered steps, footnotes
FORMULA_CONT = re.compile(r"^[+=×−-] ")


SENTENCE_END = re.compile(r"[.!?:”)]$")


def join_lines(lines: list[Line], hyphenated: set[str]) -> str:
    """Rebuild paragraphs. A line either continues the current paragraph (running prose, a
    hyphenated word, a formula's "+ …" line) or starts a new one after a blank line: bold
    run-in labels, numbered steps ("1:"), bullets, stat-block lines, sub-headings (as ####).
    Tables become Markdown tables; one laid out in the middle of a sentence is held back until
    the paragraph ends. A line-end hyphen is kept only if the hyphenated word occurs elsewhere
    in the SRD."""
    lines = _sidebars_last(lines)
    parts: list[str] = []  # finished blocks
    para = ""  # the paragraph being built
    held: list[str] = []  # tables waiting for the current sentence to end
    prev: Line | None = None
    resume = False  # the next line continues a sentence interrupted by a held table

    def new_block(block: str) -> None:
        nonlocal para
        if para:
            parts.append(para)
        parts.extend(held)
        held.clear()
        para = block

    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.table_start:
            j = i + 1
            while j < len(lines) and _table_body(lines[j]):
                j += 1
            if j == i + 1 and round(ln.words[0].size, 2) == 10.5:  # a minor heading, not a table
                new_block("#### " + ln.text)
                prev = None
            else:
                table = render_table(lines[i:j], hyphenated)
                nxt = lines[j] if j < len(lines) else None
                mid_sentence = (
                    prev is not None
                    and prev.body
                    and para
                    and not SENTENCE_END.search(para.rstrip())
                    and nxt is not None
                    and nxt.body
                    and nxt.text[:1].islower()
                )
                if mid_sentence:
                    held.append(table)
                    resume = True
                else:
                    new_block(table)
                    prev = None
            i = j
            continue
        t = ln.text
        if prev is None:
            new_block(("#### " if ln.heading_size is not None and (parts or para) else "") + t)
        else:
            gap = ln.top - prev.bottom
            m = HYPHEN_END.search(para)
            label_wraps = ln.run_in and "Bold" in prev.words[-1].font  # "…What Their Characters" / "Do."
            new_item = (ln.run_in and not label_wraps) or ITEM_START.match(t) is not None
            # prose continues across a column or page break (negative gap), or past a held table,
            # when it resumes mid-sentence
            flows = 0 <= gap < 6 or ((gap < 0 or resume) and t[:1].islower())
            if m and t[:1].islower() and prev.body and ln.body and flows:
                nxt = re.match(r"[A-Za-z]+", t).group(0)
                keep = f"{m.group(1)}-{nxt}".lower() in hyphenated
                para = para[:-1] + ("-" if keep else "") + t
            elif (prev.body and ln.body and flows and not new_item) or (
                not prev.body and not ln.body and FORMULA_CONT.match(t) and 0 <= gap < 6
            ):
                para += " " + t
            elif ln.heading_size is not None:
                new_block("#### " + t)
            else:
                new_block(t)
        resume = False
        prev = ln
        i += 1
    new_block("")
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(p for p in parts if p)).strip()


def _sidebars_last(lines: list[Line]) -> list[Line]:
    """Sidebars (small-caps title + GillSans 9pt text) sit wherever the layout put them, often
    mid-sentence; move each one after the unit's running text."""
    main: list[Line] = []
    boxes: list[Line] = []
    in_box = False
    for ln in lines:
        if ln.sidebar_title:
            in_box = True
        elif in_box and not ln.sidebar_text:
            in_box = False
        (boxes if in_box else main).append(ln)
    return main + boxes


def _table_body(ln: Line) -> bool:
    w = ln.words[0]
    return (
        ln.heading_size is None
        and not ln.body
        and not ln.sidebar_title
        and "GillSans" in w.font
        and (not ln.table_start or round(w.size, 2) == 9.25)
    )


def render_table(lines: list[Line], hyphenated: frozenset[str] | set[str] = frozenset()) -> str:
    """Markdown table from a title line, SemiBold header row(s) and body rows.
    Columns come from the header cells; a row starts when the first column has text.
    A table whose header spans the page is read row by row across both columns; otherwise
    each page column is read separately (a table that flows on in the next column)."""
    title = lines[0].text if round(lines[0].words[0].size, 2) == 10.5 else None
    rest = lines[1:] if title else lines
    if not rest:
        return title or ""
    # a table may run over pages; rows are only ever formed within one page
    parts: list[list[list[Word]]] = []
    for pno in dict.fromkeys(ln.page for ln in rest):
        words = [w for ln in rest if ln.page == pno for w in ln.words]
        rows = _rows(words, tol=2.0)
        lead = [w for r in rows[: _header_count(rows)] for w in r]
        left = [w.text for w in sorted(lead, key=lambda w: (w.top, w.x0)) if w.x0 < MID]
        right = [w.text for w in sorted(lead, key=lambda w: (w.top, w.x0)) if w.x0 >= MID]
        # the header crosses the gutter and isn't one header repeated per column: a page-wide table
        page_wide = (bool(left) and bool(right) and left != right) or any(_crosses_gutter(r) for r in rows)
        if page_wide or all(w.x0 < MID for w in words) or all(w.x0 >= MID for w in words):
            parts.append(rows)
        else:
            parts += [
                _rows([w for w in words if w.x0 < MID], 2.0),
                _rows([w for w in words if w.x0 >= MID], 2.0),
            ]
    md: list[str] = []
    header: list[str] | None = None
    cols: list[float] | None = None
    for part in parts:
        head = part[: _header_count(part)]  # the header may wrap over several rows
        if head:
            # header cells come from the last (most detailed) header row; words of upper rows
            # add a column only where they sit above no existing cell ("Pace" over nothing,
            # but "Distance Traveled Per …" over "Minute Hour Day")
            spans = _spans(head[-1])
            phrases = [(r[0].top, ph) for r in head[:-1] for ph in _phrases(r)]
            spans = sorted(
                spans
                + [
                    [ph[0].x0, ph[-1].x1]
                    for _, ph in phrases
                    if not any(ph[0].x0 < b and ph[-1].x1 > a for a, b in spans)
                ]
            )
            # label rows ("Simple Ranged Weapons") are one phrase that may run across columns
            body_words = [w for r in part[len(head) :] if len(_phrases(r)) > 1 for w in r]
            cols = [spans[0][0]] + [
                _boundary(p, q, body_words) for p, q in zip(spans, spans[1:], strict=False)
            ]
        elif cols is not None:  # continuation without its own header: shift the known columns
            shift = min(w.x0 for r in part for w in r) - cols[0]
            cols = [x + shift for x in cols]
        elif HEADING_FONT in part[0][0].font:
            md += _label_value_table(part, hyphenated)
            continue
        else:
            md += [" ".join(w.text for w in r) for r in part]
            continue
        part_header = [""] * len(cols)
        for r in head[:-1]:  # upper rows: each phrase labels the first column it sits over
            for ph in _phrases(r):
                k = max((i for i, x in enumerate(cols) if x <= ph[0].x0 + 1), default=0)
                part_header[k] = (part_header[k] + " " + " ".join(w.text for w in ph)).strip()
        if head:
            part_header = [
                (a + " " + b).strip() for a, b in zip(part_header, _cells(head[-1], cols), strict=True)
            ]
        if head and part_header != header:  # a repeated header: the table continues in the next column
            md += ([""] if md else []) + ["| " + " | ".join(part_header) + " |", "|" + " --- |" * len(cols)]
            header = part_header
        elif header is None:
            md += ["|" + " |" * len(cols), "|" + " --- |" * len(cols)]
            header = []
        body: list[list[str]] = []
        prev_top = None
        for r in part[len(head) :]:
            c = _cells(r, cols)
            # a wrapped line of the first cell: only that cell has text and it sits a line (~12pt)
            # below the previous one; table rows are ~15pt apart
            wrapped = prev_top is not None and not any(c[1:]) and r[0].top - prev_top < 13.5
            prev_top = r[0].top
            if not body or (c[0] and not body[-1][0].endswith("-") and not wrapped):
                body.append(c)
            else:
                body[-1] = [_join_cell(a, b, hyphenated) for a, b in zip(body[-1], c, strict=True)]
        if head and body:
            part_header, body = _unfold(part_header, body)
            if len(part_header) != len(cols):  # replace the header just written
                md[-2:] = ["| " + " | ".join(part_header) + " |", "|" + " --- |" * len(part_header)]
                header = part_header
        md += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(([f"Table: {title}"] if title else []) + md)


def _unfold(header: list[str], body: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """A header that repeats one column group side by side ("Item | Cost | Item | Cost") is one
    list printed in several strips: stack the strips, left strip first, dropping empty rows."""
    n = len(header)
    for size in range(1, n // 2 + 1):
        if n % size == 0 and header == header[:size] * (n // size):
            rows = [r[k : k + size] for k in range(0, n, size) for r in body]
            return header[:size], [r for r in rows if any(r)]
    return header, body


def _header_count(rows: list[list[Word]]) -> int:
    """How many leading rows form the header. Header rows are SemiBold; the first may be only
    partly so (Travel Terrain sets half its header in the regular face) if it holds no numbers
    and the row after it starts in the regular face. In a label/value table ("Primary Ability |
    Strength") every row starts with a SemiBold label, so no row is a header."""
    n = 0
    for i, r in enumerate(rows):
        if all(HEADING_FONT in w.font for w in r):
            n += 1
            continue
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if (
            n == 0
            and any(HEADING_FONT in w.font for w in r)
            and not any(c.isdigit() for w in r for c in w.text)
            and nxt is not None
            and HEADING_FONT not in nxt[0].font
        ):
            n += 1
        break
    return n


def _join_cell(a: str, b: str, hyphenated: frozenset[str] | set[str]) -> str:
    """Join a cell's wrapped lines; a line-end hyphen follows the same rule as in prose."""
    if not a or not b:
        return (a + b).strip()
    m = HYPHEN_END.search(a)
    if m:
        nxt = re.match(r"[A-Za-z]*", b).group(0)
        keep = not b[:1].islower() or f"{m.group(1)}-{nxt}".lower() in hyphenated
        return a[:-1] + ("-" if keep else "") + b
    return a + " " + b


def _label_value_table(rows: list[list[Word]], hyphenated: frozenset[str] | set[str]) -> list[str]:
    """A headerless table whose rows start with a SemiBold label: two columns, label and value."""
    body: list[list[str]] = []
    prev_top = None
    for r in rows:
        k = 0
        while k < len(r) and HEADING_FONT in r[k].font:
            k += 1
        label, value = words_text(r[:k]), words_text(r[k:])
        wrapped = prev_top is not None and r[0].top - prev_top < 13.5
        prev_top = r[0].top
        if body and wrapped and label and not value:  # "Saving Throw" / "Proficiencies"
            body[-1][0] = _join_cell(body[-1][0], label, hyphenated)
        elif label or not body:
            body.append([label, value])
        else:  # a wrapped line of the value
            body[-1][1] = _join_cell(body[-1][1], value, hyphenated)
    return ["| | |", "| --- | --- |", *("| " + " | ".join(c) + " |" for c in body)]


def _phrases(row: list[Word]) -> list[list[Word]]:
    """Words of one header row grouped where they nearly touch."""
    out: list[list[Word]] = []
    for hw in sorted(row, key=lambda w: w.x0):
        if out and hw.x0 - out[-1][-1].x1 <= 6:
            out[-1].append(hw)
        else:
            out.append([hw])
    return out


def _spans(words: list[Word]) -> list[list[float]]:
    """Header cells: words merged where they nearly touch."""
    spans: list[list[float]] = []
    for hw in sorted(words, key=lambda w: w.x0):
        if spans and hw.x0 - spans[-1][1] <= 6:
            spans[-1][1] = max(spans[-1][1], hw.x1)
        else:
            spans.append([hw.x0, hw.x1])
    return spans


def _boundary(p: list[float], q: list[float], body: list[Word]) -> float:
    """Where column q starts: the middle of the widest strip between header cells p and q that no
    body word touches (cells overflow their headers; numbers are often right-aligned).
    Without such a strip, halfway between the two header cells."""
    lo, hi = int(p[1]) + 1, int(q[0])
    covered = [False] * max(0, hi - lo)
    for w in body:
        for x in range(max(lo, int(w.x0)), min(hi, int(w.x1) + 1)):
            covered[x - lo] = True
    best, start = (0, 0.0), None
    for i, c in enumerate([*covered, True]):
        if not c and start is None:
            start = i
        elif c and start is not None:
            if i - start > best[0]:
                best = (i - start, lo + (start + i) / 2)
            start = None
    return best[1] if best[0] >= 3 else (p[1] + q[0]) / 2


def _cells(row: list[Word], cols: list[float]) -> list[str]:
    """Each phrase (words that nearly touch) goes to the column where it starts."""
    out = [""] * len(cols)
    for ph in _phrases(row):
        k = max((i for i, x in enumerate(cols) if x <= ph[0].x0 + 1), default=0)
        text = words_text(ph)
        sep = "" if not out[k] or out[k].endswith("-") else " "
        out[k] += sep + text
    return out


def see_also(text: str) -> list[str]:
    """Cross-references from 'See also' sentences, as 'Chapter › Section' or a glossary entry name."""
    refs: list[str] = []
    for m in SEE_ALSO.finditer(text):
        rest = text[m.end() :]
        end, depth, quoted = len(rest), 0, False
        for i, ch in enumerate(rest):  # the sentence ends at the first period outside quotes/parens
            quoted = True if ch == "“" else False if ch == "”" else quoted
            depth += (ch == "(") - (ch == ")")
            if ch == "." and not quoted and depth == 0:
                end = i
                break
        for q in QUOTED.finditer(rest[:end]):
            target, inner = q.group(1), q.group(2)
            if inner:
                refs += [f"{target} › {x.rstrip('.')}" for x in re.findall(r"“([^”]+?)”", inner)]
            else:
                refs.append(target)
    return list(dict.fromkeys(refs))


def slug(s: str) -> str:
    s = s.lower().replace("’", "").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# ---------------------------------------------------------------- units
@dataclass
class Node:
    heading: str
    size: int
    path: list[str]
    lines: list[Line] = field(default_factory=list)


def unit_id(prefix: str, path: list[str]) -> str:
    parts: list[str] = []
    for k, h in enumerate(path):
        s = slug(TAG.sub(r"\g<name>", h))
        if (ID_SKIP.match(s) and k < len(path) - 1) or (parts and parts[-1] == s):
            continue
        parts.append(s)
    return ".".join([prefix, *parts]) if parts else prefix


STAT_LINE = re.compile(r"^(Tiny|Small|Medium|Large|Huge|Gargantuan)\b[^.]*,")
# chapters whose stat blocks are part of another entry (a spell's summoned creature, an item's avatar)
INLINE_STAT_BLOCKS = {"Spells", "Magic Items", "Classes"}


def merge_wrapped_headings(lines: list[Line]) -> list[Line]:
    out: list[Line] = []
    for ln in lines:
        prev = out[-1] if out else None
        hs = ln.heading_size
        if (
            prev is not None
            and hs is not None
            and hs == prev.heading_size
            and prev.page == ln.page
            and (
                0 <= ln.top - prev.bottom < hs * 0.6
                or prev.text.count("(")
                > prev.text.count(")")  # "Spell Scroll (Cantrip, 30 GP;" / "Level 1 …"
                or ln.text[:1].islower()  # "Amulet of Proof against Detection" / "and Location"
            )
        ):
            out[-1] = Line(prev.words + ln.words, prev.page)
        else:
            out.append(ln)
    return out


def make_unit(prefix: str, chapter: str, node: Node, hyphenated: set[str]) -> list[dict]:
    """The unit for a finished node, or nothing if it has no text of its own."""
    text = join_lines(node.lines, hyphenated)
    if not text:
        return []
    m = TAG.match(node.heading)
    pages = sorted({ln.page for ln in node.lines})
    return [
        {
            "id": unit_id(prefix, node.path),
            "chapter": chapter,
            "heading_path": node.path,
            "title": m.group("name") if m else node.heading,
            "tag": m.group("tag") if m else None,
            "pages": [pages[0], pages[-1]],
            "text": text,
            "see_also": see_also(text),
        }
    ]


def build_units(chapter_lines: dict[str, list[Line]], hyphenated: set[str]) -> list[dict]:
    units: list[dict] = []
    for chapter, raw in chapter_lines.items():
        prefix, split = CHAPTERS[chapter]
        lines = merge_wrapped_headings(raw)
        stack: list[tuple[int, str]] = []
        node = Node(chapter, 26, [])

        for i, ln in enumerate(lines):
            hs = ln.heading_size
            if hs == 26:  # chapter title
                continue
            if hs is None:
                node.lines.append(ln)
                continue
            nxt = lines[i + 1].text if i + 1 < len(lines) else ""
            if chapter in INLINE_STAT_BLOCKS and hs in (14, 15, 18) and STAT_LINE.match(nxt):
                node.lines.append(ln)  # stat block inside the current entry
                continue
            _open(ln, stack)
            if hs >= split:
                units += make_unit(prefix, chapter, node, hyphenated)
                node = Node(ln.text, hs, [h for _, h in stack])
            else:
                node.lines.append(ln)
        units += make_unit(prefix, chapter, node, hyphenated)
    return fixups(relocate_tables(_dedupe(units)))


TABLE_BLOCK = re.compile(r"^(Table: (?P<title>[^\n]+)\n(?:\|[^\n]*(?:\n|$))+)", re.M)


def relocate_tables(units: list[dict]) -> list[dict]:
    """A full-width table is laid out wherever it fits, often inside an unrelated entry.
    Move it to the unit of the same chapter that is titled after it or refers to "the X table"."""
    for u in units:
        for m in list(TABLE_BLOCK.finditer(u["text"])):
            title = m.group("title").strip()
            own = u["text"].replace(m.group(1), "")
            if u["title"] == title or re.search(rf"\b{re.escape(title)} table", own, re.I) or not own.strip():
                continue  # it belongs here, or it is all this unit has
            same = [v for v in units if v["chapter"] == u["chapter"] and v is not u]
            home = next((v for v in same if v["title"] == title), None) or next(
                (v for v in same if re.search(rf"\b{re.escape(title)} table", v["text"], re.I)), None
            )
            if home is None:
                continue
            u["text"] = re.sub(r"\n{3,}", "\n\n", u["text"].replace(m.group(1), "")).strip()
            home["text"] += "\n\n" + m.group(1).strip()
            home["pages"] = [min(home["pages"][0], u["pages"][0]), max(home["pages"][1], u["pages"][1])]
    return units


# ---------------------------------------------------------------- fix-ups
ABILITY_GRID = re.compile(r"(?:MOD SAVE\n\n){2}MOD SAVE\n\n(?P<a>[^\n]+)\n\n(?P<b>[^\n]+)")
ABILITY_CELL = re.compile(
    r"\b(Str|Dex|Con|Int|Wis|Cha)\s*(\d+) ([+−-]\d+) ([+−-]?\d+)", re.I
)  # sic: one save is unsigned


def ability_table(m: re.Match) -> str:
    """A stat block's ability grid (three "MOD SAVE" labels over two rows of three abilities)
    as a Markdown table, one ability per row."""
    cells = ABILITY_CELL.findall(m.group("a") + " " + m.group("b"))
    if [c[0].lower() for c in cells] != ["str", "dex", "con", "int", "wis", "cha"]:
        return m.group(0)
    rows = [f"| {a.title()} | {score} | {mod} | {save} |" for a, score, mod, save in cells]
    return "\n".join(["| Ability | Score | Mod | Save |", "| --- | --- | --- | --- |", *rows])


def fixups(units: list[dict]) -> list[dict]:
    """Deterministic clean-ups of layout artefacts that survive assembly."""
    for u in units:
        u["text"] = ABILITY_GRID.sub(ability_table, u["text"])
    return units


def _open(ln: Line, stack: list[tuple[int, str]]) -> None:
    r = RANK[ln.heading_size]
    while stack and RANK[stack[-1][0]] >= r:
        stack.pop()
    stack.append((ln.heading_size, ln.text))


def _dedupe(units: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    for u in units:
        n = seen.get(u["id"], 0)
        seen[u["id"]] = n + 1
        if n:
            u["id"] = f"{u['id']}-{n + 1}"
    return units


# ---------------------------------------------------------------- PDF access
def chapters(pdf) -> list[tuple[str, int, int]]:
    from pdfminer.pdftypes import resolve1

    ids = {p.page_obj.pageid: i + 1 for i, p in enumerate(pdf.pages)}
    starts = []
    for level, title, dest, action, _se in pdf.doc.get_outlines():
        if level == 2 and title in CHAPTERS:
            target = resolve1(dest) if dest else resolve1(resolve1(action)["D"])
            ref = resolve1(target["D"] if isinstance(target, dict) else target)[0]
            starts.append((title, ids[ref.objid]))
    out = []
    for i, (title, start) in enumerate(starts):
        end = starts[i + 1][1] - 1 if i + 1 < len(starts) else len(pdf.pages)
        out.append((title, start, end))
    return out


FRACTIONS = {"1/2": "½", "1/4": "¼", "3/4": "¾"}  # single fraction glyphs whose text layer reads "1/2"


def page_words(page) -> list[Word]:
    """Words built from characters grouped by text baseline.

    Bounding-box tops are unreliable in this PDF (the bold-italic run-in labels
    report tops ~20pt too high), so lines are found from the text matrix baseline."""
    chars = []
    for c in page.chars:
        base = page.height - c["matrix"][5]
        chars.append((round(base * 2) / 2, c))
    chars.sort(key=lambda t: (t[0], t[1]["x0"]))
    words: list[Word] = []
    cur: list[dict] = []
    cur_base = None

    def close() -> None:
        if cur:
            base, size = cur_base, max(c["size"] for c in cur)
            if "SC700" in cur[0]["fontname"]:
                # small caps: the text layer's letter case is unreliable ("SplASh");
                # full-size glyphs are capitals, small ones lowercase
                text = "".join(
                    c["text"].upper() if c["size"] > 0.85 * size else c["text"].lower() for c in cur
                )
            else:
                text = "".join(FRACTIONS.get(c["text"], c["text"]) for c in cur)
            words.append(
                Word(
                    text,
                    cur[0]["x0"],
                    cur[-1]["x1"],
                    base - 0.8 * size,
                    base + 0.2 * size,
                    cur[0]["fontname"],
                    size,
                )
            )
            cur.clear()

    spaced = False  # a space char since the last glyph
    for base, c in chars:
        if c["text"].isspace():
            spaced = True
            continue
        gap = c["x0"] - cur[-1]["x1"] if cur else 0.0
        # a space char followed by no visual gap is a text-layer artefact inside a word
        # ("Short|sword", "spell|casters", "Meta|magic", "re|appears"), not a word break
        if cur and (
            abs(base - cur_base) > 1.0
            or gap > 1.5
            or (spaced and gap >= 0.8)
            or c["x0"] < cur[-1]["x0"]
            or c["fontname"] != cur[-1]["fontname"]
        ):
            close()
        spaced = False
        if not cur:
            cur_base = base
        cur.append(c)
    close()
    return words


def read_lines() -> dict[str, list[Line]]:
    import pdfplumber

    with pdfplumber.open(PDF) as pdf:
        chaps = chapters(pdf)
        first = chaps[0][1]
        flat = [
            ln
            for pno in range(first, len(pdf.pages) + 1)
            for ln in reading_order(page_words(pdf.pages[pno - 1]), pno)
        ]
    # A chapter starts at its 26pt title line; the outline page is only a hint (it is off by one for some).
    cuts = []
    for title, start, _end in chaps:
        near = [i for i, ln in enumerate(flat) if start - 1 <= ln.page <= start + 1]
        titled = [i for i in near if flat[i].heading_size == 26 and norm(flat[i].text) == title]
        cuts.append(titled[0] if titled else next(i for i, ln in enumerate(flat) if ln.page == start))
    chapter_lines = {
        title: flat[cut : cuts[k + 1] if k + 1 < len(cuts) else len(flat)]
        for k, ((title, _s, _e), cut) in enumerate(zip(chaps, cuts, strict=True))
    }
    return chapter_lines


def extract(chapter_lines: dict[str, list[Line]]) -> list[dict]:
    hyphenated = {
        m.group(0).lower()
        for ls in chapter_lines.values()
        for ln in ls
        for m in HYPHEN_WORD.finditer(ln.text)
    }
    return build_units(chapter_lines, hyphenated)


def write_markdown(units: list[dict], path: Path) -> None:
    out = ["# SRD 5.2.1 rule units", "", "Generated by `scripts/srd/extract.py`; do not edit.", ""]
    chapter = None
    for u in units:
        if u["chapter"] != chapter:
            chapter = u["chapter"]
            out += [f"## {chapter}", ""]
        tag = f" [{u['tag']}]" if u["tag"] else ""
        where = " › ".join(u["heading_path"][:-1])
        out += [
            f"### {u['title']}{tag}",
            f"`{u['id']}` · p.{u['pages'][0]}"
            + (f"–{u['pages'][1]}" if u["pages"][1] != u["pages"][0] else "")
            + (f" · {where}" if where else ""),
            "",
            u["text"],
            "",
        ]
    path.write_text("\n".join(out))


# ---------------------------------------------------------------- gate
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _squash(s: str) -> str:
    return re.sub(r"[\s#|\-]", "", s)


ORPHAN = re.compile(r"^[+−-]?\d+(?:[–-]\d+)?$", re.M)


SPELL_LIST = re.compile(r"^Table: (?:Level (\d) |Cantrips \(Level 0 )(\w+) Spells\)?$", re.M)
SPELL_LINE = re.compile(r"^(?:Level (\d) \w+|\w+ Cantrip) \(([^)]*)\)")
# spells whose description names a class whose spell list, in the SRD itself, doesn't include them
SRD_LIST_OMISSIONS = {
    ("Bard", "Phantasmal Force"),
    ("Sorcerer", "Phantasmal Force"),
    ("Wizard", "Phantasmal Force"),
    ("Sorcerer", "Mind Spike"),
}


def spell_lists(units: list[dict]) -> list[str]:
    """Every class spell list entry agrees with the level/class line of the spell's own
    description, and every class a description names lists the spell."""
    spells = {
        u["title"]: u
        for u in units
        if u["chapter"] == "Spells" and u["heading_path"][:1] == ["Spell Descriptions"]
    }
    problems, listed = [], set()
    for u in units:
        for m in SPELL_LIST.finditer(u["text"]):
            level, cls = int(m.group(1) or 0), m.group(2)
            block = u["text"][m.end() :].split("\n\n", 1)[0]
            for row in block.strip().split("\n")[2:]:
                name = row.strip("|").split("|")[0].strip()
                listed.add((cls, name))
                sp = spells.get(name)
                head = SPELL_LINE.match(sp["text"]) if sp else None
                if head is None:
                    problems.append(f"{u['id']}: {name!r} in the {cls} list has no spell description")
                elif int(head.group(1) or 0) != level or cls not in head.group(2):
                    problems.append(
                        f"{u['id']}: {name!r} listed as {cls} level {level}, described as {head.group(0)!r}"
                    )
    for name, sp in spells.items():
        head = SPELL_LINE.match(sp["text"])
        for cls in [c.strip() for c in head.group(2).split(",")] if head else []:
            if (cls, name) not in listed and (cls, name) not in SRD_LIST_OMISSIONS:
                problems.append(f"{sp['id']}: {cls} spell {name!r} is missing from the {cls} spell list")
    return problems


def structure(units: list[dict]) -> list[str]:
    """Structural checks on the rebuilt text: layout errors that lose relationships, not words."""
    problems = spell_lists(units)
    for u in units:
        prose = "\n".join(p for p in u["text"].split("\n") if not p.startswith("|"))
        for m in ORPHAN.finditer(prose):
            problems.append(f"{u['id']}: stray number {m.group(0)!r} outside a table")
        paras = u["text"].split("\n\n")
        for k in range(1, len(paras) - 1):
            before, block, after = paras[k - 1], paras[k], paras[k + 1]
            if (
                block.startswith(("Table: ", "|"))
                and before
                and not before.startswith("|")
                and not SENTENCE_END.search(before.strip())
                and after[:1].islower()
            ):
                problems.append(f"{u['id']}: table interrupts the sentence {before[-40:]!r} … {after[:20]!r}")
        if "MOD SAVE" in u["text"]:
            problems.append(f"{u['id']}: ability grid not converted to a table")
        for block in re.findall(r"(?:^\|[^\n]*\n?)+", u["text"], re.M):
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in block.strip().split("\n")]
            body = rows[2:]
            first_only = sum(1 for r in body if r[0] and not any(r[1:])) if len(rows[0]) > 1 else 0
            if first_only >= 3 and first_only > len(body) / 4:
                # the sign of a table cut down the middle: the right-hand text ends up as extra rows
                problems.append(
                    f"{u['id']}: {first_only} of {len(body)} table rows have text only in the first cell"
                )
            die = re.fullmatch(r"\d*d(\d+)", rows[0][0]) if rows else None
            if die:
                gaps = _die_gaps([r[0] for r in body], int(die.group(1)))
                if gaps:
                    problems.append(f"{u['id']}: {rows[0][0]} table {gaps}")
            if not rows or rows[0][0] != "Level":
                continue
            levels = [int(r[0]) for r in rows[2:] if r[0].isdigit()]
            if levels and (
                levels != list(range(levels[0], levels[0] + len(levels)))
                or (levels[0] == 1 and levels[-1] != 20)
            ):
                problems.append(f"{u['id']}: Level column is not 1..20 in order: {levels}")
    by_chapter: dict[str, list[dict]] = {}
    for u in units:
        by_chapter.setdefault(u["chapter"], []).append(u)
    for ch, us in by_chapter.items():
        for a, b in zip(us, us[1:], strict=False):
            if b["pages"][0] < a["pages"][0] - 1:
                problems.append(f"{ch}: {b['id']} (p.{b['pages'][0]}) follows {a['id']} (p.{a['pages'][0]})")
    return problems


def _die_gaps(cells: list[str], sides: int) -> str | None:
    """A die-roll table's first column ("01", "82–84", "00") must cover 1..sides in order."""
    expect = 1
    for c in cells:
        m = re.fullmatch(r"(\d+)(?:[–-](\d+))?", c.strip())
        if not m:
            continue  # a sub-heading row
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        lo, hi = (sides if lo == 0 else lo), (sides if hi == 0 else hi)  # "00" is 100 on a d100
        if lo != expect:
            return f"expected {expect}, found {c!r}"
        expect = hi + 1
    return None if expect == sides + 1 else f"ends at {expect - 1}, not {sides}"


def check(units: list[dict], chapter_lines: dict[str, list[Line]] | None = None) -> list[str]:
    """Deterministic gate before human approval. With the PDF's lines, also checks that
    every prose/table line of the PDF survives verbatim (whitespace-, hyphen- and
    table-markup-insensitive) in some unit."""
    problems = structure(units)
    if chapter_lines is not None:
        corpus = _squash("".join(u["text"] for u in units))
        names = _squash("".join(u["text"] + u["title"] + "".join(u["heading_path"]) for u in units))
        lost_headings = [
            f"p.{ln.page}: {ln.text!r}"
            for ls in chapter_lines.values()
            for ln in merge_wrapped_headings(ls)
            if ln.heading_size not in (None, 26) and _squash(ln.text) not in names
        ]
        if lost_headings:
            problems.append(f"{len(lost_headings)} headings missing from units, e.g. {lost_headings[:3]}")
        lines = [ln for ls in chapter_lines.values() for ln in ls]
        lost = [
            f"p.{ln.page}: {ln.text[:60]!r}"
            for ln in lines
            if ln.body and len(_squash(ln.text)) > 25 and _squash(ln.text) not in corpus
        ]
        if lost:
            problems.append(f"{len(lost)} prose lines missing from units, e.g. {lost[:3]}")
        # tables are rearranged into rows, so for everything else compare character counts
        # markup ("Table: ", "#### ") isn't source text; table header words are exempt because a
        # header repeated per strip ("Item | Cost | Item | Cost") is kept once when unfolded
        have: Counter[str] = Counter()
        for u in units:
            text = re.sub(r"^(Table: |#### )", "", u["text"], flags=re.M)
            have.update(_squash(" ".join([text, u["title"], *u["heading_path"]])).casefold())
        need = Counter(
            _squash(
                "".join(
                    w.text
                    for ln in lines
                    if ln.heading_size != 26
                    for w in ln.words
                    if not (HEADING_FONT in w.font and w.size < 10)
                    and not (w.text in ("MOD", "SAVE") and w.size < 7)  # ability-grid labels
                )
            ).casefold()
        )
        short = need - have
        if short:
            problems.append(
                f"{sum(short.values())} PDF characters missing from units: {short.most_common(8)}"
            )
    ids = [u["id"] for u in units]
    problems += [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    problems += [f"{u['id']}: empty text" for u in units if not u["text"].strip()]
    covered = {p for u in units for p in range(u["pages"][0], u["pages"][1] + 1)}
    missing = sorted(set(range(5, 365)) - covered)
    if missing:
        problems.append(f"pages without any unit: {missing}")
    gloss = sum(
        u["chapter"] == "Rules Glossary" and u["heading_path"][-1:] != ["Rules Glossary"] for u in units
    )
    if not 150 <= gloss <= 160:
        problems.append(f"expected ~155 glossary entries, got {gloss}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate the existing units.jsonl")
    ap.add_argument("--approve", action="store_true", help="pin the current units.jsonl by hash")
    a = ap.parse_args()
    if a.approve:
        APPROVED.write_text(hashlib.sha256(UNITS.read_bytes()).hexdigest() + "\n")
        print(f"approved {UNITS} ({APPROVED.read_text().strip()[:16]})")
        return 0
    chapter_lines = read_lines()
    if a.check:
        units = [json.loads(line) for line in UNITS.read_text().splitlines()]
    else:
        units = extract(chapter_lines)
        OUT.mkdir(parents=True, exist_ok=True)
        UNITS.write_text("".join(json.dumps(u, ensure_ascii=False) + "\n" for u in units))
        write_markdown(units, OUT / "srd.md")
    problems = check(units, chapter_lines)
    by_chapter: dict[str, int] = {}
    for u in units:
        by_chapter[u["chapter"]] = by_chapter.get(u["chapter"], 0) + 1
    for ch, n in by_chapter.items():
        print(f"  {n:4d}  {ch}")
    print(f"{len(units)} units, {len(problems)} problems")
    for p in problems:
        print("  !", p)
    approved = (
        APPROVED.exists() and APPROVED.read_text().strip() == hashlib.sha256(UNITS.read_bytes()).hexdigest()
    )
    print("approved" if approved else "NOT approved: review docs/srd/srd.md, then run with --approve")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
