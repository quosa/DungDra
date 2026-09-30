"""Event log (harness contract §2.1.3).

Every entry is tagged player-visible or GM-only, and may carry an SRD page
reference, the SRD rule it applies (`rule`: the id of a unit in docs/srd/units.jsonl with an
optional "#<clause>", as in the code's SRD tags), the ID of the register ruling that decided
it (`ruling`, "R-<n>") and structured data (state diffs, roll details).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PLAYER = "player"
GM = "gm"


@dataclass
class Event:
    kind: str
    text: str
    visibility: str = PLAYER
    page: str | None = None
    ruling: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    time: int = 0  # game clock (seconds) when logged
    rule: str | None = None  # "<unit id>" or "<unit id>#<clause>"

    def applies(self, rule: str) -> bool:
        """True if this event applies `rule`: a whole unit ("GLOSS.grappled") matches any of
        its clauses; a clause ("GLOSS.grappled#2") matches only itself."""
        if not self.rule:
            return False
        return self.rule == rule or ("#" not in rule and self.rule.partition("#")[0] == rule)

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        ref = []
        if self.page:
            ref.append(f"p.{self.page}")
        if self.ruling:
            ref.append(self.ruling)
        suffix = f"  [{', '.join(ref)}]" if ref else ""
        tag = "" if self.visibility == PLAYER else "(GM) "
        return f"{tag}{self.text}{suffix}"


class EventLog:
    def __init__(self):
        self.events: list[Event] = []
        self.clock_fn = lambda: 0
        self.listeners: list = []

    def add(
        self, kind: str, text: str, visibility: str = PLAYER, page=None, ruling=None, rule=None, **data
    ) -> Event:
        ev = Event(
            kind,
            text,
            visibility,
            page=str(page) if page is not None else None,
            ruling=ruling,
            data=data,
            seq=len(self.events),
            time=self.clock_fn(),
            rule=rule,
        )
        self.events.append(ev)
        for fn in self.listeners:
            fn(ev)
        return ev

    def player(self, kind, text, **kw) -> Event:
        return self.add(kind, text, PLAYER, **kw)

    def gm(self, kind, text, **kw) -> Event:
        return self.add(kind, text, GM, **kw)

    # -- queries ---------------------------------------------------------
    def visible(self) -> list[Event]:
        return [e for e in self.events if e.visibility == PLAYER]

    def of_kind(self, kind: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind]

    def rulings(self) -> set[str]:
        return {e.ruling for e in self.events if e.ruling}

    def rules(self) -> set[str]:
        """The SRD rules the logged events applied, as "<unit id>[#<clause>]"."""
        return {e.rule for e in self.events if e.rule}

    def applied(self, rule: str | None = None, ruling: str | None = None) -> list[Event]:
        """The events that applied `rule` (a unit matches its clauses) and/or `ruling`."""
        return [
            e
            for e in self.events
            if (rule is None or e.applies(rule)) and (ruling is None or e.ruling == ruling)
        ]

    def assert_applied(self, rule: str | None = None, ruling: str | None = None) -> list[Event]:
        """Test helper: fail unless some event applied `rule` and/or `ruling`; returns them."""
        if rule is None and ruling is None:
            raise ValueError("assert_applied needs a rule or a ruling")
        found = self.applied(rule, ruling)
        if not found:
            want = " and ".join(x for x in (rule and f"rule {rule}", ruling and f"ruling {ruling}") if x)
            raise AssertionError(
                f"no event applied {want}; rules applied: {sorted(self.rules())}, "
                f"rulings applied: {sorted(self.rulings())}"
            )
        return found

    def last(self, kind: str | None = None) -> Event | None:
        for e in reversed(self.events):
            if kind is None or e.kind == kind:
                return e
        return None

    def since(self, seq: int) -> list[Event]:
        return self.events[seq:]

    def text(self, visibility: str | None = PLAYER) -> str:
        return "\n".join(str(e) for e in self.events if visibility is None or e.visibility == visibility)

    def __len__(self):
        return len(self.events)
