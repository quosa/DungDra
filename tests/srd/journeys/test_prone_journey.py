"""Journey: a PC knocked Prone fights from the ground, crawls, rights itself and fights on
(GLOSS.prone, SRD p.186)."""

import pytest

from dungdra import combat as C
from dungdra.api import Session
from tests.support.helpers import mon, pc

PR = "GLOSS.prone"


def set_turn(game, c):
    cb = game.combat
    if cb.current is not None:
        C._expire(game, "end", cb.current)
    cb.index = next(i for i, (cid, _) in enumerate(cb.order) if cid == c.id)
    C.start_turn(game)


@pytest.mark.srd(PR, clause=f"{PR}#2", kind="positive")
def test_prone_pc_fights_crawls_and_stands(game):
    s = Session(game)
    s.auto_gm = False
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 500  # the fight doesn't end mid-journey
    game.dice.force_str("d20=[20,1]")
    C.roll_initiative(game, [gob, brom])
    set_turn(game, gob)
    brom.add_condition("prone", "tripped")

    # the adjacent goblin attacks the Prone PC with Advantage (#5)
    game.dice.force_str("d20=[2,2]")
    assert C.attack(game, gob, brom, attack_name="scimitar").roll.mode == "advantage"

    set_turn(game, brom)
    assert game.combat.turn.movement_left == 30
    # BROM swings from the ground: Disadvantage (#4)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[2,2]")
    assert s.execute({"cmd": "attack", "actor": brom.id, "target": gob.id, "weapon": "longsword"})["ok"]
    assert "isadvantage" in game.log.last("attack").text
    # crawls 5 ft: 10 ft of movement, still Prone (#1)
    assert s.execute({"cmd": "move", "actor": brom.id, "to": [0, 5]})["ok"]
    assert game.combat.turn.movement_left == 20 and brom.has("prone")
    # rights himself for half his Speed (#2)
    assert s.execute({"cmd": "stand", "actor": brom.id})["ok"]
    assert game.combat.turn.movement_left == 5 and not brom.has("prone")
    # and walks the last 5 ft at normal cost
    assert s.execute({"cmd": "move", "actor": brom.id, "to": [0, 0]})["ok"]
    assert game.combat.turn.movement_left == 0

    # the goblin's next attack on the standing PC is a normal roll
    set_turn(game, gob)
    game.dice.force_str("d20=[2]")
    r = C.attack(game, gob, brom, attack_name="scimitar").roll
    assert r.mode == "normal"
    assert not any("Prone" in x for x in r.adv + r.dis)
