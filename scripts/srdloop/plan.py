"""The work plan: which units the loop still has to do, in what order, and which finished
units have gone stale because something they depend on changed."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from . import graph as G
from . import related as R
from . import state as S
from . import units as U

QUEUE = Path("loop/queue.json")


@dataclass
class Context:
    """Everything the planner reads, loaded once."""

    units: list[dict]
    by_id: dict[str, dict]
    content: dict[str, set[str]]
    scenarios: list[R.Scenario]
    srd: dict[str, list[str]]
    density: dict[int, int]
    engine: dict[str, list[str]]
    states: dict[str, dict]
    edges: list[G.Edge]
    fixtures: str = ""  # the scenarios' shared fixtures, quotable as scenario evidence

    @classmethod
    def load(cls, state_root: Path = S.STATE_DIR) -> Context:
        units = U.load()
        scenarios = R.parse_scenarios()
        R.index_tests(scenarios)
        states = S.all_states(state_root)
        return cls(
            units=units,
            by_id=U.by_id(units),
            content=U.engine_content(),
            scenarios=scenarios,
            srd=R.srd_tests(),
            density=R.page_density(units),
            engine=R.engine_lines(),
            states=states,
            edges=G.seed_edges(units) + G.analyst_edges(states),
            fixtures=R.shared_fixtures(),
        )

    def scope(self, uid: str) -> str:
        return U.scope(self.by_id[uid], self.content)

    def state(self, uid: str) -> dict:
        return self.states.get(uid) or S.load(uid, Path("/nonexistent"))

    def related(self, uid: str) -> dict:
        return R.related(self.by_id[uid], self.scenarios, self.srd, self.density, self.engine)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def inputs(ctx: Context, uid: str) -> dict[str, str]:
    """What makes a finished unit worth doing again: its own rule text, or its scope (content was
    implemented or removed). Engine changes don't: most come from fixing this very unit, and the
    loop works breadth-first across the rules rather than digging deeper into one."""
    return {"text": _sha(ctx.by_id[uid]["text"]), "scope": ctx.scope(uid)}


def build(ctx: Context) -> list[dict]:
    """The queue: in-scope units that are pending, unfinished or stale, dependencies first; then
    units to revisit (an infra ticket they opened was fixed, so stage C can test more) at the end,
    behind everything not yet done."""
    include = {u["id"] for u in ctx.units if ctx.scope(u["id"]) != "content-out"}
    first, revisit = [], []
    for uid in G.queue(ctx.units, ctx.edges, include):
        st = ctx.state(uid)
        current = S.fingerprint(inputs(ctx, uid))
        if st["status"] == "incomplete":  # resume at the failed stage, unless its text or scope changed
            stale = st.get("fingerprint") is not None and st["fingerprint"] != current
        else:
            stale = S.is_stale(st, current) if st["status"] in S.TERMINAL else False
        item = {"id": uid, "scope": ctx.scope(uid), "status": st["status"], "stale": stale, "revisit": False}
        if st["status"] in ("incomplete", *[s for s in S.STATUSES if s not in S.TERMINAL]) or stale:
            first.append({**item, "next_stage": S.next_stage(st) if not stale else "A"})
        elif st.get("revisit"):
            revisit.append({**item, "revisit": True, "next_stage": "C"})
    return first + revisit


def write(queue: list[dict], path: Path = QUEUE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=1, ensure_ascii=False) + "\n")
