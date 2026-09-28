"""Capstone journeys J1-J6 through the natural-language interface."""
import pytest

from dungdra import Game
from dungdra.audit import reconcile
from dungdra.fixtures import make
from dungdra.play import Play
from tests.agent import fight
from tests.conversations import create_party

KEYS = ["hp", "max_hp", "ac", "speed", "abilities", "skills", "tools", "languages", "cantrips", "prepared",
        "spellbook", "feats", "masteries", "coins", "slots", "resources", "features"]


def _fixture_state(name):
    g = Game(1)
    pc = make(g, name)
    return {k: v for k, v in g.snapshot()["creatures"][pc.id].items() if k in KEYS}


def test_cc01_all_four_by_conversation():
    p = Play(seed=1)
    create_party(p)
    snap = p.game.snapshot()["creatures"]
    for name in ("BROM", "LIDDA", "MIALEE", "JOZAN"):
        got = {k: v for k, v in snap[name.lower()].items() if k in KEYS}
        want = _fixture_state(name)
        for k in KEYS:
            if isinstance(want[k], list):
                assert sorted(map(str, got[k])) == sorted(map(str, want[k])), (name, k)
            else:
                assert got[k] == want[k], (name, k)


def test_j1_first_session():
    p = Play(seed=3)
    create_party(p)
    p.say("begin the adventure")
    out = p.say("BROM buys iron spikes")
    assert p.game.get("brom").purse.gp == 34
    t0 = p.game.clock
    p.game.dice.force_str("d20=[15,4, 15,4, 15,4, 15,4, 11,6]")
    out = p.say("continue")                           # forest road: 6 miles, then the ambush
    assert "2 hours" in out and "Roll Initiative" in out
    inits = dict(p.game.combat.order)
    assert inits["goblin_warrior_1"] == 13 and inits["brom"] == 6
    start_round_clock = p.game.clock
    fight(p)
    assert p.game.combat is None and not getattr(p.game, "defeated", False)
    rounds = p.game.log.last("combat").data["rounds"]
    assert all(pc.xp == 50 for pc in p.game.pcs())
    assert "R-02" in p.game.log.rulings()
    for pc in p.game.pcs():
        if pc.hp == 0 and not pc.dead:
            p.say(f"JOZAN casts healing word on {pc.name}")
    p.say("continue")                                 # the clearing
    out = p.say("short rest")
    assert "Hit Die" in out
    p.say("continue")                                 # the watchtower: hidden pit and chest
    p.game.dice.force_str("d20=[12]")
    p.say("MIALEE examines the floor for traps")
    pit = next(o["trap"] for o in p.game.scene.objects.values() if "trap" in o and o["trap"].kind == "hidden pit")
    assert pit.detected
    p.say("BROM wedges a spike into the pit lid")
    assert pit.disabled
    p.game.dice.force_str("d20=[18,18]")
    p.say("LIDDA searches the chest lock for traps")
    p.game.dice.force_str("d20=[12,12]")
    p.say("LIDDA disarms the trap")
    p.say("open the chest")
    brom = p.game.get("brom")
    assert brom.purse.gp == 34 + 30 and brom.inventory.find("potion of healing")
    base = 2 * 3600 + rounds * 6 + 3600          # travel + combat rounds + Short Rest
    assert base <= p.game.clock - t0 <= base + 120   # (+ any death-save rounds while someone was dying)
    assert reconcile(p.game) == []
    # budgets and R-03 flags never reach the player
    assert all("budget" not in e.text.lower() for e in p.game.log.visible())
