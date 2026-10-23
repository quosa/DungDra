"""Unit tests for dungdra.town: shops, an inn, people to talk to and the quests they give."""

import copy

import pytest

from dungdra import gm
from dungdra.adventure import Adventure
from dungdra.play import Play
from dungdra.scenario import AdventureError, check

HAMLET = {
    "title": "Test Hamlet",
    "start": "square",
    "quests": {
        "rats": {
            "title": "Rats in the Cellar",
            "giver": "reeve",
            "offer": "Clear the rats out of the cellar and I'll pay you 40 gold.",
            "goal": {"defeat": "cellar"},
            "reward": {"gp": 40, "xp": 25},
            "done": "The reeve counts out the coins.",
        },
        "kit": {
            "title": "A Kit for the Herbalist",
            "giver": "herbalist",
            "offer": "Could you buy me a healer's kit?",
            "goal": {"bring": "healer's kit"},
            "reward": {"items": ["potion of healing"]},
        },
    },
    "places": {
        "square": {
            "name": "Village Square",
            "text": "A well.",
            "exits": [{"to": "cellar"}],
            "shop": {"name": "the general store", "sells": ["rope", "iron spikes", "healer's kit"]},
            "inn": {"name": "The Sleepy Ferret"},
            "people": [
                {"id": "reeve", "name": "Reeve Alda", "text": "The reeve.", "says": "Rats!", "quest": "rats"},
                {
                    "id": "herbalist",
                    "name": "Old Mags",
                    "text": "An herbalist.",
                    "quest": "kit",
                    "creature": "priest acolyte",
                    "attitude": "friendly",
                },
            ],
        },
        "cellar": {
            "name": "The Cellar",
            "text": "Squeaking.",
            "encounter": {"monsters": ["giant rat", "giant rat"], "positions": [[30, 0], [35, 5]]},
        },
    },
}


def play():
    check(HAMLET)
    p = Play(seed=1, adventure=False, decider=lambda g, who, key, options, default, prompt: default)
    p.say("use the sample party")
    p.session.adventure = Adventure(p.session, copy.deepcopy(HAMLET))
    p.say("begin the adventure")
    return p


def clear_the_cellar(p):
    p.say("go to the cellar")
    for m in p.game.party_foes():
        m.dead = True
    gm.finish_combat(p.game)


def test_a_place_says_who_is_here_and_what_it_offers():
    out = play().say("look")
    assert "Here: Reeve Alda, Old Mags (say 'talk to <name>')." in out
    assert "The general store is open (say 'shop' to see the wares)." in out
    assert "The Sleepy Ferret has rooms (say 'rent a room')." in out


def test_a_quest_is_offered_accepted_done_and_paid():
    p = play()
    out = p.say("talk to the reeve")
    assert out.startswith("Reeve Alda: Rats!") and "I'll pay you 40 gold" in out
    assert p.say("accept the quest").startswith("Quest accepted: “Rats in the Cellar”: defeat what lurks")
    assert "“Rats in the Cellar”: defeat what lurks in The Cellar" in p.say("quests")
    assert "isn't done yet" in p.say("talk to reeve alda")
    clear_the_cellar(p)
    assert "(done: go back to report)" in p.say("quests")
    gp = {c.id: c.purse.gp for c in p.game.pcs()}
    xp = {c.id: c.xp for c in p.game.pcs()}
    p.say("go back")
    out = p.say("talk to the reeve")
    assert "The reeve counts out the coins." in out and "Quest complete: “Rats in the Cellar”." in out
    assert sum(c.purse.gp - gp[c.id] for c in p.game.pcs()) == 40
    assert all(c.xp == xp[c.id] + 25 for c in p.game.pcs())
    assert "“Rats in the Cellar”: complete" in p.say("quests")


def test_monsters_defeated_for_a_quest_give_their_xp_too():
    p = play()
    p.say("talk to the reeve")
    p.say("accept the quest")
    clear_the_cellar(p)
    assert all(c.xp > 0 for c in p.game.pcs())  # R-02: the rats' XP, shared


def test_a_quest_is_turned_in_to_its_giver():
    p = play()
    p.say("talk to the reeve")
    p.say("accept the quest")
    assert "isn't done yet" in p.say("turn in the quest")
    clear_the_cellar(p)
    assert "nobody here waiting" in p.say("claim the reward")
    p.say("go back")
    assert "Quest complete" in p.say("turn in the quest")


def test_a_bring_quest_takes_the_item_and_gives_the_reward():
    p = play()
    p.say("talk to old mags")
    p.say("accept the quest")
    p.say("LIDDA buys a healer's kit")
    brom = p.game.get("brom")
    kits = sum(c.inventory.count("healer's kit") for c in p.game.pcs())
    potions = brom.inventory.count("potion of healing")
    out = p.say("talk to mags")
    assert "Quest complete: “A Kit for the Herbalist”." in out
    assert sum(c.inventory.count("healer's kit") for c in p.game.pcs()) == kits - 1
    assert brom.inventory.count("potion of healing") == potions + 1


def test_accepting_without_an_offer_and_talking_to_nobody_are_refused():
    p = play()
    assert "Nobody has offered you a quest" in p.say("accept the quest")
    assert "nobody called 'the mayor' here" in p.say("talk to the mayor")
    assert "no quests yet" in play().say("quests")


def test_a_person_can_stand_in_the_place_as_a_creature():
    p = play()
    mags = next(c for c in p.game.creatures.values() if c.name == "Old Mags")
    assert mags.team == "neutral" and mags.attitude == "friendly"
    assert p.game.is_ally(p.game.get("brom"), mags)  # R-37: Friendly
    mags.dead = True
    assert "Old Mags is dead." in p.say("talk to mags")
    assert "Old Mags" not in p.say("look")


def test_the_shop_lists_and_sells_its_wares_only():
    p = play()
    out = p.say("shop")
    assert out.startswith("The general store sells:") and "  Rope: 1 GP" in out
    p.say("BROM buys rope")
    assert p.game.get("brom").inventory.find("rope")
    assert "doesn't sell longsword" in p.say("BROM buys a longsword")
    p.say("go to the cellar")
    for m in p.game.party_foes():
        m.dead = True
    gm.finish_combat(p.game)
    assert "no shop in The Cellar" in p.say("BROM buys rope")
    assert "no shop in The Cellar" in p.say("shop")


def test_a_shop_that_doesnt_buy_refuses_to_buy():
    world = copy.deepcopy(HAMLET)
    world["places"]["square"]["shop"]["buys"] = False
    p = Play(seed=1, adventure=False)
    p.say("use the sample party")
    p.session.adventure = Adventure(p.session, world)
    p.say("begin the adventure")
    assert "doesn't buy anything" in p.say("BROM sells his longsword")


def test_a_night_at_the_inn_is_a_long_rest_paid_for_at_the_rooms_price():
    p = play()
    brom = p.game.get("brom")
    brom.hp = 3
    gp = {c.id: c.purse.total_cp() for c in p.game.pcs()}
    t0 = p.game.clock
    assert p.say("rent a room").endswith("The party spends the night at The Sleepy Ferret.")
    assert brom.hp == brom.max_hp
    assert all(gp[c.id] - c.purse.total_cp() == 100 for c in p.game.pcs())  # Modest: 1 GP (p.101)
    assert 8 * 3600 <= p.game.clock - t0 < 24 * 3600


def test_status_shows_level_xp_and_coins():
    out = play().say("status")
    assert "BROM: HP 13/13, AC 19, Speed 30, conditions: none; Level 1, XP 0/300, 35 GP" in out


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (lambda w: w["quests"]["rats"].update(giver="mayor"), "nobody in the adventure has the id 'mayor'"),
        (lambda w: w["quests"]["rats"].update(goal={"defeat": "square"}), "has no encounter or ambush"),
        (lambda w: w["quests"]["rats"].update(goal={"defeat": "cellar", "bring": "rope"}), "one of defeat"),
        (lambda w: w["quests"]["kit"]["goal"].update(bring="holy grail"), "no item 'holy grail'"),
        (lambda w: w["places"]["square"]["shop"].update(sells=["dragon egg"]), "no item 'dragon egg'"),
        (lambda w: w["places"]["square"]["inn"].update(room="palatial"), "inn.room: 'palatial'"),
        (lambda w: w["places"]["square"]["people"][1].update(creature="dragon"), "no monster 'dragon'"),
        (lambda w: w["places"]["square"]["people"][1].update(attitude="grumpy"), "attitude: 'grumpy'"),
        (lambda w: w["places"]["square"]["people"][1].update(side="pirates"), "side: 'pirates'"),
        (lambda w: w["places"]["square"]["people"][0].update(quest="dragons"), "there's no quest 'dragons'"),
    ],
)
def test_a_mistake_in_a_town_is_named(change, says):
    world = copy.deepcopy(HAMLET)
    change(world)
    with pytest.raises(AdventureError) as e:
        check(world)
    assert says in str(e.value)
