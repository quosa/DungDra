"""Unit tests for the loop's deterministic core (scripts/srdloop): no SRD files, no model."""

import hashlib
import json

import pytest

from scripts.srdloop import graph as G
from scripts.srdloop import plan as P
from scripts.srdloop import related as R
from scripts.srdloop import state as S
from scripts.srdloop import units as U


def unit(
    uid,
    chapter="Rules Glossary",
    path=("Rules Definitions",),
    title=None,
    text="",
    pages=(176, 176),
    see_also=(),
):
    title = title or path[-1]
    heading_path = list(path) if path and path[-1] == title else [*path, title]  # includes its own heading
    return {
        "id": uid,
        "chapter": chapter,
        "heading_path": heading_path,
        "title": title,
        "tag": None,
        "pages": list(pages),
        "text": text,
        "see_also": list(see_also),
    }


CONTENT = {
    "classes": {"rogue"},
    "subclasses": {"thief"},
    "species": {"elf"},
    "backgrounds": {"sage"},
    "feats": {"alert"},
    "items": {"crowbar", "hooded lantern"},
    "spells": {"bless"},
    "monsters": {"goblin warrior"},
    "magic_items": {"potion of healing"},
    "max_level": {"3"},
}


# ---------------------------------------------------------------- units and scope
def test_load_refuses_unapproved_units(tmp_path):
    f, a = tmp_path / "units.jsonl", tmp_path / "units.approved"
    f.write_text(json.dumps(unit("GLOSS.ally")) + "\n")
    with pytest.raises(U.NotApproved):
        U.load(f, a)
    a.write_text(hashlib.sha256(f.read_bytes()).hexdigest() + "\n")
    assert [u["id"] for u in U.load(f, a)] == ["GLOSS.ally"]
    f.write_text(f.read_text() + json.dumps(unit("GLOSS.enemy")) + "\n")  # edited after approval
    with pytest.raises(U.NotApproved):
        U.load(f, a)


def test_norm_name_matches_engine_spelling():
    assert U.norm_name("Thieves’ Tools (25 GP)") == "thieves' tools"
    assert U.norm_name("Crowbar (2 gp)") == "crowbar"


@pytest.mark.parametrize(
    ("u", "expected"),
    [
        (unit("GLOSS.ally"), "core"),
        (unit("PLAY.x", "Playing the Game", ("Combat",)), "core"),
        (unit("C.a", "Classes", ("Rogue", "Rogue Class Features"), "Level 1: Sneak Attack"), "content-in"),
        (unit("C.b", "Classes", ("Rogue", "Rogue Class Features"), "Level 5: Cunning Strike"), "content-out"),
        (unit("C.c", "Classes", ("Monk", "Monk Class Features"), "Level 1: Martial Arts"), "content-out"),
        (
            unit("C.d", "Classes", ("Rogue", "Rogue Subclass: Assassin"), "Level 3: Assassinate"),
            "content-out",
        ),
        (unit("C.e", "Classes", ("Rogue", "Rogue Subclass: Thief"), "Level 3: Fast Hands"), "content-in"),
        (unit("E.a", "Equipment", ("Adventuring Gear",), "Crowbar (2 GP)"), "content-in"),
        (unit("E.b", "Equipment", ("Adventuring Gear",), "Lantern, Hooded (5 GP)"), "content-in"),
        (unit("E.c", "Equipment", ("Adventuring Gear",), "Basket (4 SP)"), "content-out"),
        (unit("E.d", "Equipment", ("Adventuring Gear",), "Potion of Healing (50 GP)"), "content-in"),
        (unit("E.e", "Equipment", ("Weapons",), "Properties"), "content-in"),
        (unit("S.a", "Spells", ("Spell Descriptions",), "Bless"), "content-in"),
        (unit("S.b", "Spells", ("Spell Descriptions",), "Fireball"), "content-out"),
        (unit("S.c", "Spells", ("Casting Spells",), "Components"), "content-in"),
        (unit("M.a", "Monsters A–Z", ("Goblins",), "Goblin Warrior"), "content-in"),
        (unit("M.b", "Animals", (), "Baboon"), "content-out"),
        (unit("I.a", "Magic Items", ("Magic Items A–Z",), "Potions of Healing"), "content-in"),
        (unit("I.b", "Magic Items", ("Magic Items A–Z",), "Deck of Illusions"), "content-out"),
        (
            unit("O.a", "Character Origins", ("Character Species", "Species Descriptions"), "Elf"),
            "content-in",
        ),
        (
            unit("O.b", "Character Origins", ("Character Species", "Species Descriptions"), "Orc"),
            "content-out",
        ),
        (unit("F.a", "Feats", ("Feat Descriptions", "Origin Feats"), "Alert"), "content-in"),
        (unit("F.b", "Feats", ("Feat Descriptions", "General Feats"), "Grappler"), "content-out"),
    ],
)
def test_scope(u, expected):
    assert U.scope(u, CONTENT) == expected


# ---------------------------------------------------------------- graph
def test_seed_edges_see_also_and_longest_glossary_term_first():
    us = [
        unit("GLOSS.action", title="Action"),
        unit("GLOSS.bonus-action", title="Bonus Action"),
        unit("GLOSS.friendly", title="Friendly"),
        unit("PLAY.d20-tests", "Playing the Game", ("D20 Tests",)),
        unit(
            "GLOSS.x",
            title="X",
            text="You take a Bonus Action.",
            see_also=["Friendly,", "Playing the Game › D20 Tests"],
        ),
    ]
    edges = {(e.src, e.dst, e.kind) for e in G.seed_edges(us)}
    assert ("GLOSS.x", "GLOSS.bonus-action", "mentions") in edges
    assert ("GLOSS.x", "GLOSS.action", "mentions") not in edges  # "Bonus Action" wins at that position
    assert ("GLOSS.x", "GLOSS.friendly", "see_also") in edges
    assert ("GLOSS.x", "PLAY.d20-tests", "see_also") in edges


def test_resolve_see_also_chapter_section_and_unknown():
    us = [
        unit("SPELL.gaining", "Spells", ("Gaining Spells",)),
        unit("MAGIC.spells", "Magic Items", ("Crafting",), "Spells"),
    ]
    assert G.resolve_see_also("Spells", us, {}) == "SPELL.gaining"  # a chapter name beats a section title
    assert G.resolve_see_also("Crafting", us, {}) == "MAGIC.spells"
    assert G.resolve_see_also("NPC", us, {}) is None


def test_queue_puts_dependencies_first_and_breaks_cycles_by_document_order():
    us = [unit(i, title=i) for i in ("a", "b", "c", "d")]
    edges = [G.Edge("a", "c", "mentions"), G.Edge("b", "d", "requires"), G.Edge("d", "b", "mentions")]
    edges.append(G.Edge("c", "d", "interacts_with"))  # not an ordering edge
    # c has no dependencies, then a (needs c); b and d need each other: document order breaks the tie
    assert G.queue(us, edges, {"a", "b", "c", "d"}) == ["c", "a", "b", "d"]
    assert G.queue(us, edges, {"a", "b"}) == ["a", "b"]  # edges to excluded units are ignored


def test_analyst_edges_come_from_unit_state():
    states = {
        "a": {
            "relations": [
                {"type": "exception_to", "target": "b", "evidence": "q"},
                {"type": "bogus", "target": "c"},
            ]
        }
    }
    assert G.analyst_edges(states) == [G.Edge("a", "b", "exception_to", "q")]


# ---------------------------------------------------------------- state
def test_state_round_trip_next_stage_and_staleness(tmp_path):
    st = S.load("GLOSS.ally", tmp_path)
    assert st["status"] == "pending" and S.next_stage(st) == "A"
    st["stages"] = {"A": {}, "B": {}}
    st["status"], st["fingerprint"] = "green", "abc"
    S.save(st, tmp_path)
    assert S.load("GLOSS.ally", tmp_path)["stages"] == {"A": {}, "B": {}}
    assert S.next_stage(st) == "C"
    assert not list(tmp_path.glob("*.tmp"))
    assert S.is_stale(st, "xyz") and not S.is_stale(st, "abc")
    assert not S.is_stale({"status": "in-progress", "fingerprint": "abc"}, "xyz")
    assert S.fingerprint({"a": "1", "b": "2"}) == S.fingerprint({"b": "2", "a": "1"})


# ---------------------------------------------------------------- related
DOC = """# Spec

#### CORE-02 · Advantage and Disadvantage
- **Tests:** CORE (Advantage/Disadvantage p.7–8)
- **Pass:** [H] Roll twice.

#### CLS-ROG-01 · Sneak Attack
- **Tests:** CLS-ROG (Sneak Attack p.61)
- **Pass:** [H] Sneak Attack adds 1d6.
"""

TESTS = """
# ---- CORE-02 · Advantage ----
def test_core02a_one_advantage(game):
    assert True


def test_rog01a_ally_adjacent(game):
    assert True
"""


def test_parse_scenarios_and_index_tests_by_banner_and_name(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text(DOC)
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_x.py").write_text(TESTS)
    sc = R.parse_scenarios(doc)
    assert [(s.id, s.pages) for s in sc] == [("CORE-02", {7, 8}), ("CLS-ROG-01", {61})]
    R.index_tests(sc, tmp_path / "t")
    assert sc[0].tests == [f"{(tmp_path / 't' / 'test_x.py').as_posix()}::test_core02a_one_advantage"]
    assert sc[1].tests[0].endswith("::test_rog01a_ally_adjacent")


def test_shared_fixtures_is_the_fixtures_section_alone(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text(
        "## 3. Build order\n\nx\n\n## 4. Shared fixtures\n\n| Wolf | AC 12, HP 11 |\n\n"
        "## 5. Scenarios by section\n\n#### CORE-01 · A\n"
    )
    assert R.shared_fixtures(doc) == "## 4. Shared fixtures\n\n| Wolf | AC 12, HP 11 |\n\n"
    doc.write_text("## 5. Scenarios by section\n")
    assert R.shared_fixtures(doc) == ""


def test_term_strips_tags_levels_and_prices():
    assert R.term(unit("a", title="Grappled [Condition]")) == "Grappled"
    assert R.term(unit("a", title="Level 1: Sneak Attack")) == "Sneak Attack"
    assert R.term(unit("a", title="Crowbar (2 GP)")) == "Crowbar"


def test_related_uses_terms_and_only_uncrowded_pages(tmp_path):
    doc = tmp_path / "spec.md"
    doc.write_text(DOC)
    sc = R.parse_scenarios(doc)
    sneak = unit("CLASS.rogue.sneak", "Classes", ("Rogue",), "Level 1: Sneak Attack", pages=(61, 61))
    crowded = unit("GLOSS.x", title="Hide", pages=(7, 7))
    density = {61: 1, 7: 10}
    engine = {"dungdra/a.py": ["x = 1  # SRD[CLASS.rogue.sneak#2]", "raise Refusal('no', page=61)", "y = 2"]}
    r = R.related(sneak, sc, {"CLASS.rogue.sneak": ["tests/srd/t.py::t"]}, density, engine)
    assert [(s["id"], s["match"]) for s in r["scenarios"]] == [("CLS-ROG-01", ["pages", "term"])]
    assert [(c["line"], c["match"]) for c in r["code"]] == [(1, "tag"), (2, "page")]
    assert r["srd_tests"] == ["tests/srd/t.py::t"]
    assert R.related(crowded, sc, {}, density, {})["scenarios"] == []  # p.7 is shared by ten units


def test_srd_tests_reads_markers(tmp_path):
    (tmp_path / "test_gloss.py").write_text(
        "import pytest\n\n"
        '@pytest.mark.srd("GLOSS.prone", clause=1, kind="negative")\n'
        "def test_prone(game):\n    assert True\n"
    )
    assert R.srd_tests(tmp_path) == {
        "GLOSS.prone": [f"{(tmp_path / 'test_gloss.py').as_posix()}::test_prone"]
    }


# ---------------------------------------------------------------- plan
def _ctx(units, states=None, edges=None):
    return P.Context(
        units=units,
        by_id=U.by_id(units),
        content=CONTENT,
        scenarios=[],
        srd={},
        density={},
        engine={},
        states=states or {},
        edges=edges or [],
    )


def test_plan_queues_unfinished_and_stale_units_and_skips_done_and_out_of_scope():
    us = [unit("GLOSS.a", title="A"), unit("GLOSS.b", title="B"), unit("GLOSS.c", title="C")]
    us.append(unit("S.x", "Spells", ("Spell Descriptions",), "Fireball"))
    ctx = _ctx(us)
    fp_b = S.fingerprint(P.inputs(ctx, "GLOSS.b"))
    ctx.states = {
        "GLOSS.a": {"id": "GLOSS.a", "status": "in-progress", "stages": {"A": {}}},
        "GLOSS.b": {"id": "GLOSS.b", "status": "green", "stages": {}, "fingerprint": fp_b},
        "GLOSS.c": {"id": "GLOSS.c", "status": "green", "stages": {}, "fingerprint": "old"},
    }
    q = P.build(ctx)
    assert [(x["id"], x["next_stage"], x["stale"]) for x in q] == [
        ("GLOSS.a", "B", False),
        ("GLOSS.c", "A", True),
    ]


def test_an_incomplete_unit_resumes_at_the_failed_stage_unless_its_rule_changed():
    us = [unit("GLOSS.a", title="A"), unit("GLOSS.b", title="B"), unit("GLOSS.c", title="C")]
    ctx = _ctx(us)
    fp = S.fingerprint(P.inputs(ctx, "GLOSS.a"))
    abc = {"A": {}, "B": {}, "C": {}}
    ctx.states = {
        "GLOSS.a": {"id": "GLOSS.a", "status": "incomplete", "stages": abc, "fingerprint": fp},
        "GLOSS.b": {
            "id": "GLOSS.b",
            "status": "incomplete",
            "stages": {"A": {}},
        },  # failed before fingerprints
        "GLOSS.c": {"id": "GLOSS.c", "status": "incomplete", "stages": abc, "fingerprint": "old text"},
    }
    q = P.build(ctx)
    assert [(x["id"], x["next_stage"], x["stale"]) for x in q] == [
        ("GLOSS.a", "D", False),
        ("GLOSS.b", "B", False),
        ("GLOSS.c", "A", True),
    ]


def test_only_rule_text_or_scope_make_a_finished_unit_stale():
    us = [unit("GLOSS.a", title="A", text="old"), unit("GLOSS.b", title="B")]
    ctx = _ctx(us, edges=[G.Edge("GLOSS.a", "GLOSS.b", "requires")])
    before = S.fingerprint(P.inputs(ctx, "GLOSS.a"))
    ctx.states = {"GLOSS.b": {"id": "GLOSS.b", "status": "red"}}  # a dependency's status: no
    ctx.engine = {"dungdra/x.py": ["changed"]}  # engine code: no
    assert S.fingerprint(P.inputs(ctx, "GLOSS.a")) == before
    ctx.units[0]["text"] = "new"  # the rule text: yes
    assert S.fingerprint(P.inputs(ctx, "GLOSS.a")) != before


def test_revisits_go_to_the_end_of_the_queue_from_stage_c():
    us = [unit("GLOSS.a", title="A"), unit("GLOSS.b", title="B"), unit("GLOSS.c", title="C")]
    ctx = _ctx(us)
    fp = {i: S.fingerprint(P.inputs(ctx, i)) for i in ("GLOSS.a", "GLOSS.b")}
    ctx.states = {
        "GLOSS.a": {
            "id": "GLOSS.a",
            "status": "green",
            "stages": {},
            "fingerprint": fp["GLOSS.a"],
            "revisit": True,
        },
        "GLOSS.b": {"id": "GLOSS.b", "status": "green", "stages": {}, "fingerprint": fp["GLOSS.b"]},
    }
    q = P.build(ctx)
    assert [(x["id"], x["next_stage"], x["revisit"]) for x in q] == [
        ("GLOSS.c", "A", False),
        ("GLOSS.a", "C", True),
    ]
