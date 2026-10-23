"""Journeys through the adventures that come with the game: each arena played from the start to
its quest's reward, through the natural-language interface, the way a player would."""

import pytest

from dungdra.audit import reconcile
from dungdra.play import Play
from tests.support.agent import fight


def start(name, seed=1):
    p = Play(
        seed=seed,
        adventure=name,
        decider=lambda g, who, key, options, default, prompt: default,
        auto_end_turn=True,
    )
    p.say("use the sample party")
    p.say("begin the adventure")
    return p


def say(p, line, dice=None):
    """One line from the player; any fight it starts is played out by the scripted agent."""
    if dice:
        p.game.dice.force_str(dice)
    out = p.say(line)
    if p.game.combat is not None:
        fight(p)
    return out


def coins(p):
    return sum(c.purse.total_cp() for c in p.game.pcs()) // 100


def finished(p):
    assert p.errors == [], p.errors[0]
    assert reconcile(p.game) == []
    assert all("budget" not in e.text.lower() for e in p.game.log.visible())  # R-03


def test_mill_rats_a_first_quest_from_offer_to_reward():
    p = start("mill-rats")
    assert "Here: Miller Hobb, Tamsin" in p.say("look")
    assert "Clear them out and I'll pay you 30 gold" in say(p, "talk to the miller")
    say(p, "accept the quest")
    say(p, "go to the cellar")  # through the mill, then the rats
    assert p.session.adventure.current == "mill"
    say(p, "continue")
    assert p.game.combat is None and all(c.xp == 18 for c in p.game.pcs())  # 75 XP shared (R-02)
    assert "(done: go back to report)" in say(p, "quests")
    gp, potions = coins(p), sum(c.inventory.count("potion of healing") for c in p.game.pcs())
    say(p, "go back")
    say(p, "go back")
    assert p.session.adventure.current == "green"
    out = say(p, "talk to the miller")
    assert "Quest complete: “Rats in the Mill”." in out
    assert coins(p) == gp + 5 + 30  # the cellar's 5 GP, picked up on the way out, and the reward
    assert sum(c.inventory.count("potion of healing") for c in p.game.pcs()) == potions + 1
    assert "Level 1, XP 18/300" in say(p, "status")
    finished(p)


def test_goblin_cellar_drive_the_goblins_out():
    p = start("goblin-cellar")
    say(p, "talk to edda")
    say(p, "accept the quest")
    say(p, "continue")
    say(p, "continue")  # the goblins fight
    assert p.game.combat is None and sum(not c.dead for c in p.game.pcs()) >= 1
    assert all(c.xp == 37 for c in p.game.pcs())  # 150 XP shared
    gp = coins(p)
    say(p, "go back")
    say(p, "go back")
    assert "Edda opens her strongbox" in say(p, "talk to edda")
    assert coins(p) >= gp + 50
    finished(p)


def test_trapped_hall_find_the_traps_and_bring_back_the_wand():
    p = start("trap-hall")
    say(p, "talk to wendel")
    say(p, "accept the quest")
    say(p, "BROM buys iron spikes")
    say(p, "continue")
    say(p, "MIALEE examines the floor for traps", "d20=[12]")
    say(p, "BROM wedges a spike into the pit lid")
    say(p, "continue")  # past the pit, into the vault and its skeletons
    assert p.session.adventure.current == "vault" and p.game.combat is None
    assert all(c.hp > 0 or c.stable or c.dead for c in p.game.pcs())
    say(p, "LIDDA searches the chest lock for traps", "d20=[18,18]")
    say(p, "LIDDA disarms the trap", "d20=[12,12]")
    say(p, "open the chest")
    assert any(c.inventory.find("wand of magic missiles") for c in p.game.pcs())
    say(p, "go back")
    say(p, "go back")
    gp = coins(p)
    assert "Quest complete: “The Scholar's Wand”." in say(p, "talk to wendel")
    assert coins(p) == gp + 60
    assert not any(c.inventory.find("wand of magic missiles") for c in p.game.pcs())
    finished(p)


def test_thornbury_shop_quests_temple_wolves_and_the_inn():
    p = start("town")
    assert "the market stocks the usual gear" in say(p, "shop").lower()
    say(p, "LIDDA buys a healer's kit")
    say(p, "go to the temple")
    say(p, "talk to sister maren")
    say(p, "accept the quest")
    assert "Sister Maren blesses you" in say(p, "talk to sister maren")
    say(p, "go back")
    say(p, "go to the gate")
    say(p, "talk to the captain")
    say(p, "accept the quest")
    t0 = p.game.clock
    say(p, "go to the woods")  # a mile of travel, then the wolves
    assert p.game.clock - t0 >= 20 * 60
    assert p.session.adventure.current == "woods" and p.game.combat is None
    say(p, "go back")
    assert "Quest complete: “Wolves at the Woods' Edge”." in say(p, "talk to the captain")
    say(p, "go back")
    assert "The party spends the night at The Thorn and Thistle." in say(p, "rent a room")
    assert all(c.hp == c.max_hp for c in p.game.pcs() if not c.dead)
    assert "“Wolves at the Woods' Edge”: complete" in say(p, "quests")
    finished(p)


@pytest.mark.parametrize("name", ["mill-rats", "goblin-cellar", "trap-hall", "town", "goblin-trail"])
def test_every_adventure_starts_and_names_itself(name):
    p = Play(seed=1, adventure=name)
    assert "This adventure: " in p.begin()
    p.say("use the sample party")
    assert p.say("begin the adventure").startswith("== ")
