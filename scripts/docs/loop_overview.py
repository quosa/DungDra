"""Draws docs/srd-loop-overview.pdf: one tall page showing the SRD rule loop's audit stages A-D,
the dev loop, what each discovers (tickets, rulings, tests to review, disputes) and what a person
decides. The numbers at the bottom are read from loop/ when the page is built.

    python -m scripts.docs.loop_overview [--out docs/srd-loop-overview.pdf]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

W, H = 930, 2400
SANS, BOLD = "Helvetica", "Helvetica-Bold"
MONO = "Courier"
for path in ("/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
    if Path(path).exists():
        registerFont(TTFont("Mono", path, subfontIndex=0) if path.endswith(".ttc") else TTFont("Mono", path))
        MONO = "Mono"
        break

INK, MUTED, FAINT = HexColor("#1f2328"), HexColor("#59636e"), HexColor("#8b949e")
PAGE, LANE, EDGE = HexColor("#f7f8fa"), HexColor("#eceef2"), HexColor("#d0d7de")


@dataclass(frozen=True)
class Kind:
    edge: str
    fill: str
    title: str
    dashed: bool = False
    tag: str = ""


AGENT = Kind("#2f5bd3", "#ffffff", "#2f5bd3")
SCRIPT = Kind("#1f2328", "#ffffff", "#1f2328")
GATE = Kind("#d99a2b", "#fdf3dc", "#a8650a", tag="GATE")
YOU = Kind("#3a9a6a", "#e6f4ec", "#22774a", dashed=True)
FOUND = Kind("#8a4fd0", "#f3ecfb", "#6a35b0")
ARROW = HexColor("#57606a")


class Page:
    def __init__(self, out: Path):
        self.c = Canvas(str(out), pagesize=(W, H))
        self.c.setTitle("SRD rule loop")
        self.c.setFillColor(PAGE)
        self.c.rect(0, 0, W, H, stroke=0, fill=1)

    # top-down coordinates: y grows downwards from the top of the page
    def text(self, x, y, s, font=SANS, size=9, color=INK, anchor="left"):
        self.c.setFont(font, size)
        self.c.setFillColor(color)
        draw = {
            "left": self.c.drawString,
            "center": self.c.drawCentredString,
            "right": self.c.drawRightString,
        }
        draw[anchor](x, H - y, s)

    def wrap(self, s, font, size, width) -> list[str]:
        lines, cur = [], ""
        for word in s.split():
            trial = f"{cur} {word}".strip()
            if stringWidth(trial, font, size) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        return [*lines, cur] if cur else lines

    def para(self, x, y, s, width, font=SANS, size=9, color=MUTED, leading=None) -> float:
        leading = leading or size * 1.45
        for line in self.wrap(s, font, size, width):
            self.text(x, y, line, font, size, color)
            y += leading
        return y

    def rect(self, x, y, w, h, fill, edge=None, radius=6, dashed=False, width=1.0):
        c = self.c
        c.setFillColor(HexColor(fill) if isinstance(fill, str) else fill)
        if edge is not None:
            c.setStrokeColor(HexColor(edge) if isinstance(edge, str) else edge)
            c.setLineWidth(width)
        c.setDash(3, 2) if dashed else c.setDash()
        c.roundRect(x, H - y - h, w, h, radius, stroke=1 if edge is not None else 0, fill=1)
        c.setDash()

    def box(self, x, y, w, kind: Kind, title, sub="", h=None, tag=""):
        lines = self.wrap(sub, MONO, 6.6, w - 22) if sub else []
        h = h or 26 + 9.5 * max(len(lines), 1)
        self.rect(x, y, w, h, kind.fill, kind.edge, dashed=kind.dashed, width=1.2)
        self.text(x + 11, y + 16, title, SANS, 9.5, HexColor(kind.title))
        for i, line in enumerate(lines):
            self.text(x + 11, y + 29 + 9.5 * i, line, MONO, 6.6, MUTED)
        tag = tag or kind.tag
        if tag:
            self.text(x + w - 9, y + 12, tag, MONO, 5.6, HexColor(kind.title), anchor="right")
        return Box(x, y, w, h)

    def arrow(self, pts, label="", at=0, dashed=False, color=ARROW, side="above", head=True):
        c = self.c
        c.setStrokeColor(color)
        c.setLineWidth(0.9)
        c.setDash(3, 2) if dashed else c.setDash()
        p = c.beginPath()
        p.moveTo(pts[0][0], H - pts[0][1])
        for x, y in pts[1:]:
            p.lineTo(x, H - y)
        c.drawPath(p, stroke=1, fill=0)
        c.setDash()
        if head:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            dx, dy = (x1 - x0), (y1 - y0)
            n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            ux, uy = dx / n, dy / n
            a = c.beginPath()
            a.moveTo(x1, H - y1)
            a.lineTo(x1 - 6 * ux + 3 * uy, H - (y1 - 6 * uy - 3 * ux))
            a.lineTo(x1 - 6 * ux - 3 * uy, H - (y1 - 6 * uy + 3 * ux))
            a.close()
            c.setFillColor(color)
            c.drawPath(a, stroke=0, fill=1)
        if label:
            (x0, y0), (x1, y1) = pts[at], pts[at + 1]
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            if x0 == x1:  # vertical segment: label to the right
                self.label(mx + 5, my + 2, label, "left", color)
            else:
                self.label(mx, my - 4 if side == "above" else my + 9, label, "center", color)

    def label(self, x, y, s, anchor, color):
        w = stringWidth(s, MONO, 6.4)
        left = {"left": x, "center": x - w / 2, "right": x - w}[anchor]
        self.rect(left - 2, y - 7, w + 4, 9.5, PAGE, None, radius=2)
        self.text(x, y, s, MONO, 6.4, color, anchor)

    def lanes(self, top, bottom, titles):
        self.rect(36, top, W - 72, bottom - top, "#ffffff", EDGE, radius=8)
        for (x0, x1), (name, note) in zip(LANES, titles, strict=True):
            self.rect(x0, top + 12, x1 - x0, bottom - top - 24, LANE, None, radius=5)
            self.text(x0 + 12, top + 30, name, MONO, 6.8, INK)
            self.text(x0 + 12, top + 40, note, MONO, 6.2, MUTED)

    def section(self, y, title, sub):
        self.text(36, y, title, BOLD, 15, INK)
        self.para(36, y + 17, sub, 760, size=9)

    def card(self, x, y, w, h, title, items):
        self.rect(x, y, w, h, "#ffffff", EDGE, radius=8)
        self.text(x + 16, y + 26, title, BOLD, 11.5, INK)
        yy = y + 46
        for head, rest in items:
            lines = self.wrap(f"{head} {rest}".strip(), SANS, 8.2, w - 44)
            self.text(x + 18, yy, "•", SANS, 8.2, MUTED)
            first = True
            for line in lines:
                if first and head:
                    self.text(x + 28, yy, head, BOLD, 8.2, INK)
                    tail = line[len(head) :]
                    self.text(x + 28 + stringWidth(head, BOLD, 8.2), yy, tail, SANS, 8.2, MUTED)
                else:
                    self.text(x + 28, yy, line, SANS, 8.2, MUTED)
                first = False
                yy += 12.2
            yy += 4

    def save(self):
        self.c.showPage()
        self.c.save()


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def top(self):
        return (self.x + self.w / 2, self.y)

    @property
    def bottom(self):
        return (self.x + self.w / 2, self.y + self.h)

    @property
    def left(self):
        return (self.x, self.y + self.h / 2)

    @property
    def right(self):
        return (self.x + self.w, self.y + self.h / 2)

    def at(self, fx, fy=None):
        """A point on the box: fx across (0..1), fy down (0..1); fy None = the vertical middle."""
        return (self.x + self.w * fx, self.y + self.h * (0.5 if fy is None else fy))


LANES = ((48, 222), (236, 528), (542, 882))
YX, YW = 60, 150  # your boxes
AX, AW = 248, 268  # agent boxes
HX, HW = 554, 316  # harness boxes


def numbers(root: Path) -> dict:
    """What the loop has done so far, from its own files."""
    states = [json.loads(p.read_text()) for p in sorted((root / "loop/state").glob("*.json"))]
    tickets = [json.loads(p.read_text()) for p in sorted((root / "loop/tickets").glob("T-*.json"))]
    rulings = [json.loads(p.read_text()) for p in sorted((root / "loop/rulings").glob("P-*.json"))]
    costs = [json.loads(ln) for ln in (root / "loop/costs.jsonl").read_text().splitlines() if ln.strip()]
    units = {s["id"] for s in states if s.get("status") not in ("pending", "in-progress")}
    audit = sum(c["cost_usd"] for c in costs if c["about"] in units)
    tests = sum(len(s.get("tests", [])) for s in states)
    return {
        "units": len(units),
        "tests": tests,
        "tickets": Counter(t["kind"] for t in tickets),
        "ticket_status": Counter(t["status"] for t in tickets),
        "rulings": Counter(r["status"] for r in rulings),
        "audit_per_unit": audit / len(units) if units else 0.0,
        "dev": sum(c["cost_usd"] for c in costs if c["about"].startswith("T-")),
        "fixed": sum(t["status"] == "fixed" for t in tickets),
    }


def draw(out: Path, root: Path = Path(".")) -> None:
    pg = Page(out)
    t = pg.text

    # ------------------------------------------------------------------ header
    t(
        36,
        44,
        "CLAUDE CODE  ·  HEADLESS claude -p  ·  AGENTS, SCHEMAS, HOOKS, PYTHON HARNESS",
        MONO,
        7.2,
        MUTED,
    )
    t(36, 82, "SRD Rule Loop", BOLD, 30, INK)
    pg.para(
        36,
        104,
        "The DungDra engine is checked against the D&D SRD 5.2.1, one rule unit at a time and breadth-first. "
        "Four agents analyse the rule, audit what exists, write tests and try to refute them. A separate dev "
        "loop fixes what the tests find. Scripts check every agent's output before it counts, and what only "
        "a person can decide (readings of the rules, disputes, removals) waits for you.",
        560,
        size=9.6,
    )
    legend = [
        (AGENT, "Claude Code agent (fresh context, restricted tools)"),
        (SCRIPT, "Python harness"),
        (GATE, "Gate: rejects or retries"),
        (FOUND, "Discovery"),
        (YOU, "You"),
    ]
    x = 36
    for kind, name in legend:
        pg.rect(x, 172, 16, 9, kind.fill, kind.edge, radius=2, dashed=kind.dashed)
        t(x + 22, 180, name, SANS, 7.8, MUTED)
        x += 30 + stringWidth(name, SANS, 7.8)

    # ------------------------------------------------------------------ audit loop
    pg.section(222, "Audit loop: one rule unit, stages A to D", "")
    top = 236
    pg.lanes(
        top,
        1150,
        [
            ("YOU", "trigger, approve, decide"),
            ("CLAUDE CODE AGENTS", ".claude/agents/*.md · judgement"),
            ("PYTHON HARNESS", "scripts/srdloop · exact checks"),
        ],
    )
    approve = pg.box(YX, 290, YW, YOU, "Approve the SRD text", "extract.py --approve")
    plan = pg.box(
        HX, 290, HW, SCRIPT, "plan", "typed relation graph · dependencies first · content-out never queued"
    )
    pg.arrow([approve.right, (plan.x, approve.right[1])], "units.jsonl, pinned by hash", side="above")
    trigger = pg.box(YX, 356, YW, YOU, "run --budget USD", "--units ID … (optional)")
    run = pg.box(HX, 356, HW, SCRIPT, "run", "preflight: clean tree · green suite · breakers · next unit")
    pg.arrow([trigger.right, (run.x, trigger.right[1])])
    pg.arrow([plan.bottom, run.top])

    a = pg.box(
        AX,
        430,
        AW,
        AGENT,
        "A · rule-analyst",
        "Opus · no tools · clauses, relations, ambiguities, 2014 traps",
    )
    ga = pg.box(HX, 430, HW, GATE, "analysis gate", "verbatim quotes · relations name real units")
    b = pg.box(
        AX,
        520,
        AW,
        AGENT,
        "B · scenario-auditor",
        "Sonnet · read-only · gets related.py's scenarios, tests and code sites · a verdict on each",
    )
    gb = pg.box(HX, 520, HW, GATE, "verdict gate", "every related item judged · quotes from the SRD")
    cc = pg.box(
        AX,
        610,
        AW,
        AGENT,
        "C · test-designer",
        "Opus · writes tests/srd · positive, negative, boundary, abuse, journeys · red = xfail(T-new)",
    )
    gc = pg.box(
        HX,
        610,
        HW,
        GATE,
        "test gate",
        "clause × kind coverage · srd markers · no mocks · append-only · write zone · ruff · runs the tests: "
        "claimed green passes, claimed red fails",
    )
    d = pg.box(AX, 712, AW, AGENT, "D · test-verifier", "Opus · read + mutate · tries to refute every test")
    gd = pg.box(HX, 712, HW, GATE, "verification gate", "a verdict for every test")

    pg.arrow(
        [run.at(0.3, 1), (run.at(0.3)[0], 404), (a.top[0], 404), a.top], "unit text + linked units", at=1
    )
    for agent, gate, label in (
        (a, ga, "A.json"),
        (b, gb, "B.json"),
        (cc, gc, "C.json + tests"),
        (d, gd, "D.json"),
    ):
        pg.arrow([agent.at(1, 0.35), (gate.x, agent.at(1, 0.35)[1])], label)
        pg.arrow(
            [gate.at(0, 0.75), (agent.right[0] + 8, gate.at(0, 0.75)[1])],
            "retry once",
            dashed=True,
            color=HexColor("#a8650a"),
            side="below",
        )
    for gate, nxt in ((ga, b), (gb, cc), (gc, d)):
        pg.arrow([gate.bottom, (gate.bottom[0], nxt.y - 10), (nxt.top[0], nxt.y - 10), nxt.top])

    finish = pg.box(
        HX,
        800,
        HW,
        SCRIPT,
        "finish unit",
        "removes tests refuted with confidence ≥ 0.5 · numbers tickets and proposals · commits srd: <unit> "
        "— status",
    )
    pg.arrow([gd.bottom, finish.top])
    pg.text(AX, 830, "a gate failed twice → the unit is incomplete,", MONO, 6.2, HexColor("#a8650a"))
    pg.text(AX, 840, "its work set aside for the next run", MONO, 6.2, HexColor("#a8650a"))

    fy, fw = 920, 146
    found = []
    for i, (title, sub) in enumerate(
        (
            ("Bug ticket T-n", "a red test: the engine breaks the rule; xfail(strict, T-n)"),
            ("Infra ticket", "a capability the engine lacks (one per capability)"),
            ("Ruling proposal P-n", "a test needs one reading of an ambiguity; the unit is blocked"),
            ("Test to review", "refuted with confidence < 0.5: kept until you decide"),
        )
    ):
        found.append(pg.box(AX + i * (fw + 10), fy, fw, FOUND, title, sub, h=58))
    for f in found:
        pg.arrow([(f.top[0], 892), f.top], head=True)
    pg.arrow([finish.bottom, (finish.bottom[0], 892)], head=False)
    pg.arrow([(found[0].top[0], 892), (found[3].top[0], 892)], head=False)

    rul = pg.box(
        YX,
        1010,
        YW,
        YOU,
        "ruling accept | reject",
        "accept → R-nn in the README · reject → unit redone from C, its tickets void",
        h=66,
    )
    rev = pg.box(YX, 1088, YW, YOU, "review keep | remove", "numbers from review list · one commit", h=46)
    pg.arrow([found[2].bottom, (found[2].bottom[0], 1043), rul.right], at=1)
    pg.arrow([found[3].bottom, (found[3].bottom[0], 1111), rev.right], at=1)
    tickets_x = found[0].bottom[0]
    pg.arrow([found[0].bottom, (tickets_x, 1128)], head=False)
    pg.arrow([found[1].bottom, (found[1].bottom[0], 1128), (tickets_x, 1128)], head=False)
    pg.arrow([(tickets_x, 1128), (tickets_x, 1158)], head=True)
    pg.text(tickets_x + 6, 1144, "to the dev loop's backlog", MONO, 6.2, MUTED)

    # ------------------------------------------------------------------ dev loop
    pg.section(1200, "Dev loop: one ticket at a time", "")
    top = 1214
    pg.lanes(
        top,
        1980,
        [
            ("YOU", "trigger, settle, unstick"),
            ("CLAUDE CODE AGENTS", "fixer · fix-reviewer"),
            ("PYTHON HARNESS", "gates · commit"),
        ],
    )
    backlog = pg.box(
        HX,
        1262,
        HW,
        FOUND,
        "Open tickets",
        "bug and infra tickets from the audit loop · follow-ups from the reviewer",
    )
    dtrig = pg.box(YX, 1332, YW, YOU, "dev --budget USD", "--tickets T-n … (optional)")
    dev = pg.box(
        HX,
        1332,
        HW,
        SCRIPT,
        "dev",
        "preflight · next open ticket: bug → infra → refactor → coverage · skips tickets waiting for a "
        "ruling",
    )
    pg.arrow([backlog.bottom, dev.top])
    pg.arrow([dtrig.right, (dev.x, dtrig.right[1])])
    fixer = pg.box(
        AX,
        1410,
        AW,
        AGENT,
        "fixer",
        "Opus · writes dungdra/, tests/unit/, loop/requests/ · fixes the rule, not the test case · unit "
        "tests for what it changes",
    )
    pg.arrow(
        [dev.at(0.3, 1), (dev.at(0.3)[0], 1396), (fixer.top[0], 1396), fixer.top],
        "ticket + rule + failures",
        at=1,
    )
    g1 = pg.box(
        HX,
        1486,
        HW,
        GATE,
        "fix gates",
        "only the fixer's zone changed · harness drops the T-n xfail · the ticket's tests pass · nothing "
        "else turns red",
    )
    g2 = pg.box(
        HX,
        1566,
        HW,
        GATE,
        "dev-gate",
        "ruff clean · no suppressions · unit coverage ratchet · diff coverage ≥ 90% · import layers · "
        "duplication · dead code",
    )
    cx = g1.at(0.12)[0]
    pg.arrow([fixer.right, (cx, fixer.right[1]), (cx, g1.y)], "the change", at=0)
    pg.arrow([g1.bottom, g2.top])
    review = pg.box(
        AX,
        1650,
        AW,
        AGENT,
        "fix-reviewer",
        "Opus · read-only · hard-coding, layering, a second mechanism, meaningless tests, scope",
    )
    pg.arrow(
        [g2.bottom, (g2.bottom[0], 1638), (review.at(0.75)[0], 1638), review.at(0.75, 0)],
        "git diff + gate results",
        at=1,
    )
    commit = pg.box(
        HX,
        1730,
        HW,
        SCRIPT,
        "commit  fix: T-n",
        "co-fixed tickets closed · fixed infra → its unit revisits from C · coverage baseline ratchets up",
    )
    pg.arrow([review.at(1, 0.65), (commit.at(0.5)[0], review.at(1, 0.65)[1]), commit.top], "approve", at=0)

    dy = 1830
    disp = pg.box(
        AX,
        dy,
        128,
        FOUND,
        "Dispute",
        "the fixer thinks the test is wrong: code set aside, request filed",
        h=66,
    )
    fail = pg.box(
        AX + 140, dy, 128, FOUND, "Failed attempt", "stash + fix.attempt<n>.json · 3 failures → stuck", h=66
    )
    follow = pg.box(
        HX,
        dy,
        HW,
        FOUND,
        "Follow-up tickets",
        "refactor, infra, coverage, filed by the reviewer · one per problem",
        h=48,
    )
    pg.arrow([fixer.at(0, 0.8), (AX - 6, fixer.at(0, 0.8)[1]), (AX - 6, dy + 20), disp.at(0, 0.3)])
    orange = HexColor("#a8650a")
    lane = 535  # the gap between the agents' and the harness lanes carries every failure down
    for src in (g1.left, g2.left):
        pg.arrow([src, (lane, src[1])], dashed=True, color=orange, head=False)
    pg.arrow(
        [review.at(1, 0.35), (lane, review.at(1, 0.35)[1])], "reject", dashed=True, color=orange, head=False
    )
    pg.arrow(
        [(lane, g1.left[1]), (lane, dy - 14), (fail.top[0], dy - 14), fail.top], dashed=True, color=orange
    )
    pg.text(fail.top[0] + 6, dy - 18, "failed: set aside, retried with the problems", MONO, 6.2, orange)
    pg.arrow([commit.bottom, follow.top])
    pg.arrow(
        [follow.right, (HX + HW + 6, follow.right[1]), (HX + HW + 6, backlog.right[1]), backlog.right],
        "backlog",
        at=1,
    )

    settle = pg.box(
        YX,
        1830,
        YW,
        YOU,
        "settle a dispute",
        "fix the test or scenario · ticket reopen · stash pop · dev --recheck",
        h=66,
    )
    unstick = pg.box(YX, 1910, YW, YOU, "unstick a ticket", "ticket show · cap · reopen · void · waive", h=50)
    pg.arrow([(AX - 6, disp.at(0, 0.7)[1]), settle.at(1, 0.7)], head=True)
    pg.arrow([disp.at(0, 0.7), (AX - 6, disp.at(0, 0.7)[1])], head=False)
    pg.arrow([fail.bottom, (fail.bottom[0], unstick.right[1]), unstick.right], at=1)
    green = HexColor("#22774a")
    rx = YX + YW + 8
    pg.arrow(
        [
            settle.at(0.5, 0),
            (settle.at(0.5)[0], 1808),
            (rx, 1808),
            (rx, g1.at(0, 0.8)[1]),
            (lane - 4, g1.at(0, 0.8)[1]),
        ],
        "dev --recheck: gates and review, no fixer",
        at=3,
        dashed=True,
        color=green,
        head=False,
    )
    pg.arrow([(lane - 4, g1.at(0, 0.8)[1]), (g1.x, g1.at(0, 0.8)[1])], dashed=True, color=green)

    # ------------------------------------------------------------------ breakers
    y = 2006
    pg.rect(36, y, W - 72, 58, "#ffffff", EDGE, radius=8)
    t(52, y + 22, "Stops by itself", BOLD, 11, INK)
    pg.para(
        52,
        y + 38,
        "Exit 3, a circuit breaker: the suite was red before starting · more than 15 open tickets (run the "
        "dev loop "
        "first) · 3 units in a row failed their gates.   Exit 4, paused: budget, usage limit or a "
        "transient error; the "
        "same command resumes, a half-done retry included.   `status` lists everything waiting for you.",
        W - 110,
        size=8.2,
    )

    # ------------------------------------------------------------------ cards
    y, ch, cw = 2084, 150, (W - 72 - 24) / 3
    pg.card(
        36,
        y,
        cw,
        ch,
        "Always on, in every agent call",
        [
            ("Write zones", "per role: a PreToolUse hook (SRDLOOP_ROLE) and the gates block anything else."),
            ("settings.json", "denies git push, commit, reset, stash, rm, curl, pip; sandbox on."),
            ("--json-schema", "makes each stage's output checkable; --max-budget-usd caps each call."),
            ("CLAUDE.md", "carries the rules every role shares: append-only suites, no suppressions."),
        ],
    )
    pg.card(
        36 + cw + 12,
        y,
        cw,
        ch,
        "Only you decide",
        [
            ("Rulings:", "accept into the README register, or reject with a reason."),
            ("Disputes and stuck tickets:", "ticket show, reopen, void, cap, waive."),
            ("Tests:", "removing or weakening one; the verifier's doubts (review)."),
            ("Scope:", "the SRD text (extract --approve) and which infra to build."),
        ],
    )
    pg.card(
        36 + 2 * (cw + 12),
        y,
        cw,
        ch,
        "Traceability",
        [
            ("Code:", "# SRD[<unit>#<clause>] where a rule is implemented."),
            ("Events:", 'page=, rule="<unit>#<n>" and ruling="R-nn" in the log.'),
            ("Attempts:", "every stage and fix attempt kept in loop/runs/, with cost."),
            ("Commits:", "one per unit, fix and decision, with the reason."),
        ],
    )

    # ------------------------------------------------------------------ numbers
    n = numbers(root)
    y = 2250
    pg.rect(36, y, W - 72, 92, "#ffffff", EDGE, radius=8)
    t(52, y + 24, "So far", BOLD, 11, INK)
    stats = [
        (f"{n['units']}", "units audited"),
        (f"{n['tests']}", "SRD tests kept"),
        (
            f"{sum(n['tickets'].values())}",
            "tickets ({})".format(", ".join(f"{v} {k}" for k, v in n["tickets"].most_common())),
        ),
        (f"{n['fixed']}", "tickets fixed"),
        (f"{n['rulings']['accepted']}", "rulings accepted"),
        (f"${n['audit_per_unit']:.2f}", "per audited unit"),
    ]
    x = 52
    for big, small in stats:
        t(x, y + 58, big, BOLD, 18, INK)
        t(x, y + 74, small, SANS, 7.4, MUTED)
        x += max(110, stringWidth(small, SANS, 7.4) + 24)

    t(
        36,
        H - 40,
        "Generated by scripts/docs/loop_overview.py from loop/ · details in docs/srd-loop-operating.md",
        MONO,
        6.6,
        FAINT,
    )
    pg.save()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("docs/srd-loop-overview.pdf"))
    a = ap.parse_args()
    draw(a.out)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
