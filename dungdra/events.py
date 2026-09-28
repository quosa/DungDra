"""Event log (harness contract §2.1.3).

Every entry is tagged player-visible or GM-only, and may carry an SRD page
reference, a ruling ID and structured data (state diffs, roll details).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
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

    def add(self, kind: str, text: str, visibility: str = PLAYER, page=None,
            ruling=None, **data) -> Event:
        ev = Event(kind, text, visibility, str(page) if page is not None else None,
                   ruling, data, len(self.events), self.clock_fn())
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

    def last(self, kind: str | None = None) -> Event | None:
        for e in reversed(self.events):
            if kind is None or e.kind == kind:
                return e
        return None

    def since(self, seq: int) -> list[Event]:
        return self.events[seq:]

    def text(self, visibility: str | None = PLAYER) -> str:
        return "\n".join(str(e) for e in self.events
                         if visibility is None or e.visibility == visibility)

    def __len__(self):
        return len(self.events)
