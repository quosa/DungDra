"""Journey: a Goblin Warrior hides with Nimble Escape, shoots from hiding with Advantage and the
extra 1d4, is revealed by the attack, then Disengages to slip away from a melee foe
(MONSTER.goblins.goblin-warrior, SRD p.290)."""

import pytest

from dungdra import class_actions as CA
from dungdra import combat as C
from tests.support.helpers import mon, pc

GW = "MONSTER.goblins.goblin-warrior"


def set_turn(game, c):
    cb = game.combat
    if cb.current is not None:
        C._expire(game, "end", cb.current)
    cb.index = next(i for i, (cid, _) in enumerate(cb.order) if cid == c.id)
    C.start_turn(game)


@pytest.mark.srd(GW, clause=f"{GW}#24", kind="positive")
def test_goblin_hides_shoots_from_hiding_then_disengages(game):
    li = pc(game, "LIDDA", (0, 0))
    li.hp = li.base_max_hp = 100
    gob = mon(game, "goblin warrior", (40, 0), name="Gob")
    game.dice.force_str("d20=[20,1]")
    C.roll_initiative(game, [gob, li])
    set_turn(game, gob)

    # turn 1: Nimble Escape (Hide) behind Three-Quarters Cover: 9 + Stealth 6 = 15 meets DC 15 (#12, #24)
    game.dice.force_str("d20=[9]")
    CA.nimble_escape(game, gob, "hide", cover="three-quarters")
    assert gob.has("invisible") and game.combat.turn.bonus_used

    # the hidden goblin's Shortbow attack has Advantage (LIDDA can't see it) and adds 1d4 (#21–#23)
    game.dice.force_str("d20=[4,17]; d6=[2]; d4=[3]")
    r = C.attack(game, gob, li, attack_name="shortbow")
    assert r.roll.mode == "advantage" and r.roll.total == 21
    assert r.hit and r.damage == 2 + 2 + 3 and li.hp == 93
    # making the attack roll ends hiding
    assert not gob.has("invisible")

    # turn 2: LIDDA closes in; the goblin Disengages with Nimble Escape and walks away unpunished
    set_turn(game, li)
    li.position = (35, 0)
    set_turn(game, gob)
    CA.nimble_escape(game, gob, "disengage")
    C.move(game, gob, to=(40, 30))
    assert game.combat.has_reaction(li) and gob.hp == 10
    # and it still has its action: a Shortbow shot without Advantage adds no 1d4 (#23)
    game.dice.force_str("d20=[19]; d6=[1]")
    r = C.attack(game, gob, li, attack_name="shortbow")
    assert r.roll.mode == "normal" and r.damage == 3
