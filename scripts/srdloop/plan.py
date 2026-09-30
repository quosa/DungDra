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
    """What a unit's result depends on: its own text, the scenarios and engine files related
    to it, and the status of the units it depends on. A change in any of them makes it stale."""
    rel = ctx.related(uid)
    scen = {s.id: s.text for s in ctx.scenarios}
    files = sorted({c["file"] for c in rel["code"]})
    deps = sorted({e.dst for e in ctx.edges if e.src == uid and e.kind in G.ORDERING})
    return {
        "text": _sha(ctx.by_id[uid]["text"]),
        "scenarios": _sha("".join(scen[s["id"]] for s in rel["scenarios"])),
        "code": _sha("".join("\n".join(ctx.engine[f]) for f in files)),
        "deps": _sha(json.dumps({d: ctx.state(d).get("status") for d in deps}, sort_keys=True)),
    }


def build(ctx: Context) -> list[dict]:
    """The queue: in-scope units that are pending, unfinished or stale, dependencies first."""
    include = {u["id"] for u in ctx.units if ctx.scope(u["id"]) != "content-out"}
    out = []
    for uid in G.queue(ctx.units, ctx.edges, include):
        st = ctx.state(uid)
        stale = S.is_stale(st, S.fingerprint(inputs(ctx, uid))) if st["status"] in S.TERMINAL else False
        if st["status"] not in S.TERMINAL or stale:
            out.append(
                {
                    "id": uid,
                    "scope": ctx.scope(uid),
                    "status": st["status"],
                    "stale": stale,
                    "next_stage": S.next_stage(st) if not stale else "A",
                }
            )
    return out


def write(queue: list[dict], path: Path = QUEUE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=1, ensure_ascii=False) + "\n")
