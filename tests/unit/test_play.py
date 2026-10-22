"""Unit tests for dungdra.play: the natural-language play loop never ends the game on a bug."""

import random

import pytest

from dungdra.play import Play


class _BrokenInterpreter:
    """Stands in for the --llm interpreter (a constructor argument) and fails like a bug would."""

    def translate(self, play, text):
        raise RuntimeError("boom")


def _party(seed=1, **kw):
    p = Play(seed=seed, decider=lambda g, who, key, options, default, prompt: default, **kw)
    p.say("use the sample party")
    p.say("begin the adventure")
    return p


def test_a_bug_in_a_command_is_reported_and_the_game_goes_on():
    p = _party(llm=_BrokenInterpreter())
    out = p.say("BROM does something odd")
    assert "ran into a bug" in out
    assert len(p.errors) == 1 and "RuntimeError: boom" in p.errors[0]
    assert p.errors[0].startswith("> BROM does something odd")
    p.llm = None
    assert "BROM: HP" in p.say("status")


@pytest.mark.parametrize(
    "line",
    [
        "BROM grapples",
        "BROM shoves",
        "JOZAN stabilizes",
        "JOZAN uses divine spark",
        "LIDDA uses a healer's kit",
    ],
)
def test_a_command_that_needs_a_creature_asks_whom_when_it_names_none(line):
    p = _party()
    out = p.say(line)
    assert out.startswith("Whom do you want to")
    assert p.errors == []


def test_moving_on_when_the_last_dying_character_dies_on_the_way_ends_the_adventure():
    p = _party()
    brom, *others = p.game.pcs()
    for c in others:
        c.dead = True
    brom.hp = 0
    p.game.dice.force_str("d20=[1,1]")  # a 1 on a Death Saving Throw counts as two failures
    out = p.say("continue")
    assert brom.dead and p.game.defeated
    assert "The party has fallen" in out and "Goblin" not in out
    assert p.errors == []


def test_entering_a_place_after_the_party_has_fallen_starts_no_fight():
    p = _party()
    for c in p.game.pcs():
        c.dead = True
    p.session.adventure.enter("road")
    assert p.game.combat is None and p.game.defeated


def test_after_the_whole_party_falls_moving_on_is_refused():
    p = _party()
    for c in p.game.pcs():
        c.dead = True
    out = p.say("continue")
    assert "The party has fallen" in out
    assert p.errors == []


# The words the random sessions are built from: party names, targets, places, spells and items.
PCS = ["BROM", "LIDDA", "MIALEE", "JOZAN"]
WORDS = [
    *PCS,
    "goblin",
    "goblin warrior 1",
    "goblin warrior 2",
    "goblin boss",
    "the chest",
    "the floor",
    "longsword",
    "shortbow",
    "dagger",
    "fire bolt",
    "magic missile",
    "healing word",
    "sleep",
    "web",
    "burning hands",
    "thunderwave",
    "bless",
    "sacred flame",
    "potion",
    "torch",
    "spike",
    "pit",
    "lock",
    "Millbrook",
    "watchtower",
    "20 feet",
    "away",
]
VERBS = [
    "attacks",
    "casts",
    "casts {} at",
    "casts {} on",
    "moves toward",
    "moves 15 feet toward",
    "shoots",
    "throws a dagger at",
    "uses",
    "drinks a",
    "examines",
    "searches",
    "hides",
    "dashes",
    "disengages",
    "dodges",
    "helps",
    "grapples",
    "shoves",
    "readies",
    "gives a potion to",
    "goes to",
    "uses second wind",
    "uses divine spark on",
    "stabilizes",
    "wedges a spike into",
]
PLAIN = ["continue", "end turn", "short rest", "long rest", "status", "look", "leave the chest", "inventory"]


@pytest.mark.parametrize("seed", range(40))
def test_random_sessions_never_hit_a_bug(seed):
    rnd = random.Random(seed)
    p = _party(seed=seed, auto_end_turn=True)
    for _ in range(150):
        if rnd.random() < 0.3:
            line = rnd.choice(PLAIN)
        else:
            verb = rnd.choice(VERBS).replace("{}", rnd.choice(WORDS))
            line = f"{rnd.choice(PCS)} {verb} {rnd.choice(WORDS)}"
        p.say(line)
    assert p.errors == [], p.errors[0]
