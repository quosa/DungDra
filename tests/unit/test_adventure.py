"""Unit tests for dungdra.adventure: moving between places, both ways, and what each place keeps."""

import pytest

from dungdra.adventure import Adventure
from dungdra.combat import end_combat
from dungdra.play import Play
from dungdra.scenario import check

WORLD = {
    "title": "Test Hamlet",
    "start": "town",
    "places": {
        "town": {"name": "Town Square", "text": "A well.", "exits": [{"to": "yard"}]},
        "yard": {
            "name": "Mill Yard",
            "text": "Sacks.",
            "exits": [{"to": "cellar"}, {"to": "shed"}],
            "ground": [{"kind": "rubble", "rect": [10, 0, 20, 0]}],
        },
        "shed": {"name": "Tool Shed", "text": "Rakes."},
        "cellar": {
            "name": "Mill Cellar",
            "text": "Squeaking.",
            "encounter": {"monsters": ["giant rat"], "positions": [[30, 0]]},
            "loot": {"gp": 5},
            "exits": [{"to": "tunnel", "one_way": True}],
        },
        "tunnel": {"name": "Old Tunnel", "text": "Dark.", "ending": "You come out in the woods."},
        "island": {"name": "Lonely Island", "text": "Unreachable."},
    },
}


def play():
    check(WORLD)
    p = Play(seed=1, adventure=False, decider=lambda g, who, key, options, default, prompt: default)
    p.say("use the sample party")
    p.session.adventure = Adventure(p.session, WORLD)
    p.say("begin the adventure")
    return p


def at(p):
    return p.session.adventure.current


def clear_the_fight(p):
    for m in p.game.enemies_of(p.game.pcs()[0]):
        m.dead = True
    end_combat(p.game)


def test_a_place_with_one_way_on_says_continue():
    p = play()
    assert "(Say 'continue' or 'go to Mill Yard' to press on.)" in p.say("look")


def test_the_party_can_go_back_the_way_it_came():
    p = play()
    p.say("continue")
    assert at(p) == "yard"
    out = p.say("look")
    assert "Ways from here: Mill Cellar, Tool Shed, Town Square" in out
    assert "'continue' for Mill Cellar" in out and "'go back' for Town Square" in out
    p.say("go back")
    assert at(p) == "town"
    p.say("go to the mill yard")
    p.say("back")
    assert at(p) == "town"


def test_going_back_before_moving_is_refused():
    p = play()
    assert "nowhere to go back to" in p.say("go back")


def test_a_far_place_is_reached_one_place_at_a_time():
    p = play()
    out = p.say("go to the cellar")
    assert "toward Mill Cellar; the way leads through Mill Yard first" in out
    assert at(p) == "yard"


def test_a_place_with_no_way_on_of_its_own_refuses_continue_but_not_back():
    p = play()
    p.say("go to the mill yard")
    p.say("go to the tool shed")
    assert "There's no way on from here" in p.say("continue")
    p.say("go back")
    assert at(p) == "yard"


def test_a_fight_happens_only_the_first_time():
    p = play()
    p.say("continue")
    p.say("continue")
    assert at(p) == "cellar" and p.game.combat is not None
    clear_the_fight(p)
    p.say("go back")
    p.say("go to the cellar")
    assert at(p) == "cellar" and p.game.combat is None


def test_a_one_way_exit_has_no_way_back_and_the_end_ends():
    p = play()
    p.say("continue")
    p.say("continue")
    clear_the_fight(p)
    gp = p.game.pcs()[0].purse.gp
    p.say("continue")
    assert at(p) == "tunnel" and p.game.pcs()[0].purse.gp == gp + 5  # the loot goes with them
    assert "(This is the end of the road.)" in p.say("look")
    assert "no way back to Mill Cellar: it's behind you" in p.say("go to the cellar")
    assert "no way from here to Lonely Island" in p.say("go to the lonely island")
    assert "You come out in the woods." in p.say("continue")


def test_a_place_keeps_its_ground_and_only_its_own():
    p = play()
    assert p.game.scene.objects == {}
    p.say("continue")
    assert list(p.game.scene.objects) == ["rubble 1"]
    p.say("go back")
    assert p.game.scene.objects == {}
    p.say("continue")
    assert list(p.game.scene.objects) == ["rubble 1"]


def test_the_map_shows_where_the_party_has_been():
    p = play()
    p.say("continue")
    out = p.say("map")
    assert out.startswith("Map of Test Hamlet:")
    assert "  Town Square: ways to Mill Yard" in out
    assert "  Mill Yard (you are here): ways to Mill Cellar, Tool Shed, Town Square" in out
    assert "Lonely Island" not in out


@pytest.mark.parametrize("line", ["exits", "where am i", "where can we go"])
def test_asking_the_way_describes_the_place(line):
    p = play()
    assert p.say(line).startswith("Town Square\nA well.")


def test_the_map_needs_an_adventure():
    p = Play(seed=1, adventure=False)
    assert "no adventure loaded" in p.say("map")


# ---------------- the fallen and the fallen-over on the move ----------------
HALL = {
    "title": "Test Hall",
    "start": "hall",
    "places": {
        "hall": {
            "name": "Dusty Hall",
            "text": "Flagstones.",
            "traps": [{"kind": "hidden pit", "location": "the floor"}],
            "loot": {"gp": 7},
            "exits": [{"to": "yard"}],
        },
        "yard": {"name": "Back Yard", "text": "Weeds."},
    },
}


def in_the_hall():
    check(HALL)
    p = Play(seed=1, adventure=False, decider=lambda g, who, key, options, default, prompt: default)
    p.say("use the sample party")
    p.session.adventure = Adventure(p.session, HALL)
    p.say("begin the adventure")
    return p


def test_a_dead_character_doesnt_lead_the_way_into_a_pit():
    p = in_the_hall()
    brom, lidda = p.game.get("brom"), p.game.get("lidda")
    brom.dead = True
    p.say("continue")
    said = [e.text for e in p.game.log.of_kind("trap")]
    assert "LIDDA triggers the hidden pit!" in said and not any("BROM" in t for t in said)
    assert brom.hp == brom.max_hp and lidda.hp < lidda.max_hp


def test_the_treasure_goes_to_the_first_character_on_their_feet():
    p = in_the_hall()
    brom, lidda = p.game.get("brom"), p.game.get("lidda")
    brom.dead = True
    gp = lidda.purse.gp
    p.say("continue")  # the pit, then the treasure on the way out
    p.say("continue")
    assert lidda.purse.gp == gp + 7


def test_the_fallen_are_carried_at_the_back_of_the_line():
    p = in_the_hall()
    brom = p.game.get("brom")
    brom.hp = 0
    brom.add_condition("unconscious", "test")
    brom.stable = True
    p.session.adventure.enter("yard")
    assert [c.name for c in sorted(p.game.pcs(), key=lambda c: c.position[1])] == [
        "LIDDA",
        "MIALEE",
        "JOZAN",
        "BROM",
    ]


def test_nobody_on_their_feet_means_nobody_leads_the_way():
    p = in_the_hall()
    for c in p.game.pcs():
        c.hp, c.stable = 0, True
        c.add_condition("unconscious", "test")
    assert "Nobody in the party is awake to lead the way" in p.say("continue")


def test_a_prone_character_gets_up_before_the_party_moves_on():
    p = play()
    mialee = p.game.get("mialee")
    mialee.add_condition("prone", "knocked down")
    out = p.say("continue")
    assert "MIALEE gets back on their feet." in out and not mialee.has("prone")
