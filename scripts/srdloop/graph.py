"""The relation graph between rule units and the order the loop works through them.

Seed edges come from the SRD itself: "See also" references and mentions of glossary terms.
The rule analyst (stage A) adds typed edges with evidence; they are stored in each unit's
state and merged here. The queue puts a unit's `requires` dependencies (and, softer, the
units it references) before it; cycles are broken by document order.
"""

from __future__ import annotations

import heapq
import re
from dataclasses import dataclass

from . import units as U

EDGE_TYPES = (
    "requires",
    "modifies",
    "exception_to",
    "overrides",
    "excludes",
    "triggers",
    "interacts_with",
    "same_concept_as",
    "see_also",  # seed: an explicit SRD cross-reference
    "mentions",  # seed: the text uses a glossary term
)
ORDERING = {"requires", "see_also", "mentions"}  # edges that put the target before the source


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str
    evidence: str = ""


def _glossary_terms(units: list[dict]) -> dict[str, str]:
    """Glossary entry title -> unit id ("Grappled" -> GLOSS.grappled)."""
    return {
        u["title"]: u["id"] for u in units if u["chapter"] == "Rules Glossary" and len(u["heading_path"]) > 1
    }


def resolve_see_also(ref: str, units: list[dict], terms: dict[str, str]) -> str | None:
    """'Playing the Game › D20 Tests', a glossary entry, a section or a chapter name -> unit id.
    The SRD puts list commas inside the quotes ("Friendly,"), so trailing punctuation goes."""
    ref = ref.rstrip(",.;")
    if " › " in ref:
        chapter, section = (x.rstrip(",.;") for x in ref.split(" › ", 1))
        cands = [u for u in units if u["chapter"] == chapter]
    else:
        if ref in terms:
            return terms[ref]
        intro = next((u for u in units if u["chapter"] == ref), None)  # a whole chapter: its first unit
        if intro is not None:
            return intro["id"]
        section, cands = ref, units
    for u in cands:
        if u["title"] == section or u["heading_path"][:1] == [section]:
            return u["id"]
    return None


def seed_edges(units: list[dict]) -> list[Edge]:
    terms = _glossary_terms(units)
    # longest terms first so "Bonus Action" wins over "Action" at the same position
    names = sorted(terms, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b") if names else None
    edges: list[Edge] = []
    for u in units:
        for ref in u.get("see_also", []):
            dst = resolve_see_also(ref, units, terms)
            if dst and dst != u["id"]:
                edges.append(Edge(u["id"], dst, "see_also", ref))
        if pattern is not None:
            seen = set()
            for m in pattern.finditer(u["text"]):
                dst = terms[m.group(1)]
                if dst != u["id"] and dst not in seen:
                    seen.add(dst)
                    edges.append(Edge(u["id"], dst, "mentions", m.group(1)))
    return edges


def analyst_edges(states: dict[str, dict]) -> list[Edge]:
    out = []
    for uid, st in states.items():
        for r in st.get("relations", []):
            if r.get("type") in EDGE_TYPES and r.get("target"):
                out.append(Edge(uid, r["target"], r["type"], r.get("evidence", "")))
    return out


def queue(units: list[dict], edges: list[Edge], include: set[str]) -> list[str]:
    """Units in `include`, ordered so that each unit's ordering dependencies come first.
    Ties and cycles resolve by chapter order, then document order."""
    rank = {ch: i for i, ch in enumerate(U.CHAPTER_ORDER)}
    key = {u["id"]: (rank.get(u["chapter"], len(rank)), i) for i, u in enumerate(units)}
    deps: dict[str, set[str]] = {uid: set() for uid in include}
    for e in edges:
        if e.kind in ORDERING and e.src in include and e.dst in include and e.src != e.dst:
            deps[e.src].add(e.dst)
    users: dict[str, set[str]] = {uid: set() for uid in include}
    for src, ds in deps.items():
        for d in ds:
            users[d].add(src)
    waiting = {uid: len(ds) for uid, ds in deps.items()}
    ready = [(key[uid], uid) for uid, n in waiting.items() if n == 0]
    heapq.heapify(ready)
    order: list[str] = []
    done: set[str] = set()
    while len(order) < len(include):
        if not ready:  # a cycle: take the earliest remaining unit
            uid = min((u for u in include if u not in done), key=lambda u: key[u])
            heapq.heappush(ready, (key[uid], uid))
        _, uid = heapq.heappop(ready)
        if uid in done:
            continue
        done.add(uid)
        order.append(uid)
        for user in users[uid]:
            waiting[user] -= 1
            if waiting[user] == 0 and user not in done:
                heapq.heappush(ready, (key[user], user))
    return order
