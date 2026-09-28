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


def _party(seed=5, adventure=False):
    p = Play(seed=seed, adventure=adventure)
    p.say("use the sample party")
    return p


def _turn_of(p, name):
    """Advance (ending turns) until it's `name`'s turn."""
    for _ in range(20):
        if p.game.combat.current.name == name:
            return
        p.say("end turn")
    raise AssertionError(f"never reached {name}'s turn")


def test_j2_deaths_door():
    p = _party()
    s = p.session
    s.auto_gm = False
    g = p.game
    for who, pos in (("mialee", [0, 0]), ("jozan", [70, 0]), ("brom", [10, 5]), ("lidda", [-5, 10])):
        s.execute({"cmd": "place", "actor": who, "position": pos})
    s.execute({"cmd": "spawn", "monsters": ["goblin warrior", "goblin warrior"], "positions": [[5, 0], [0, 15]]})
    s.execute({"cmd": "award_xp", "amount": 300})                  # level 2: LIDDA has Cunning Action
    g.get("mialee").take_damage(g.get("mialee").max_hp, "piercing", source="an arrow from the dark")
    # Initiative (BROM, LIDDA, MIALEE, JOZAN, goblins): MIALEE 21, goblins 16, JOZAN 11, LIDDA 10, BROM 4
    g.dice.force_str("d20=[2, 5, 20, 12, 14, 5]")
    s.execute({"cmd": "start_combat"})
    assert [g.creatures[i].name for i, _ in g.combat.order][:2] == ["MIALEE", "Goblin Warrior 1"]
    m = g.get("mialee")
    assert m.death_saves == {"success": 0, "failure": 1}          # she fails one Death Saving Throw
    p.say("end turn")                                               # MIALEE is unconscious
    # the goblins (GM) attack BROM and LIDDA
    g.dice.force_str("d20=[3]")
    assert s.execute({"cmd": "attack", "actor": "goblin_warrior_1", "target": "brom", "weapon": "scimitar"})["ok"]
    p.say("end turn")
    g.dice.force_str("d20=[3]")
    assert s.execute({"cmd": "attack", "actor": "goblin_warrior_2", "target": "lidda", "weapon": "scimitar"})["ok"]
    p.say("end turn")
    assert g.combat.current.name == "JOZAN"
    p.say("JOZAN moves 10 feet toward MIALEE")
    assert g.get("jozan").distance_to(m) == 60
    g.dice.force_str("d4=[2,3]")
    p.say("JOZAN casts healing word on MIALEE")
    assert m.hp == 8 and m.death_saves == {"success": 0, "failure": 0} and not m.has("unconscious")
    out = p.say("JOZAN casts guiding bolt at goblin warrior 1")
    assert "one spell slot" in out                                  # one slot per turn
    p.say("end turn")
    assert g.combat.current.name == "LIDDA"
    p.say("LIDDA uses cunning action to disengage")
    p.say("LIDDA moves 30 feet away from goblin warrior 2")
    p.say("end turn")
    p.say("BROM disengages")
    p.say("BROM moves 30 feet away from goblin warrior 1")
    p.say("end turn")
    # round 2: MIALEE stands and backs off; the goblin attacks her and she reacts with Shield
    p.say("MIALEE stands up")
    p.say("end turn")
    g.answer("shield", True, who="mialee")
    g.dice.force_str("d20=[9]")                                     # 9 + 4 = 13 vs AC 11 -> hit, Shield -> 16
    r = s.execute({"cmd": "attack", "actor": "goblin_warrior_1", "target": "mialee", "weapon": "scimitar"})
    assert r["result"]["hit"] is False and m.slots_left(1) == 2
    assert any("REACTION" in e.text for e in g.log.of_kind("offer"))
    assert not [e for e in g.log.of_kind("oa") if "makes an Opportunity Attack" in e.text]
    assert reconcile(g) == []
