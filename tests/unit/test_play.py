"""Unit tests for dungdra.play: the natural-language play loop never ends the game on a bug."""

import random

import pytest

from dungdra import nl
from dungdra.encounters import spawn
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


# ---------------- what playing by hand turned up ----------------
def _at_the_ambush(seed=3):
    p = _party(seed=seed)
    p.say("continue")  # the Forest Road: four goblin warriors
    assert p.game.combat is not None
    return p


@pytest.mark.parametrize(
    ("line", "actor", "feet"),
    [
        ("move toward goblin warrior 1", None, None),
        ("move towards goblin warrior 1", None, None),
        ("move to goblin warrior 1", None, None),
        ("BROM moves toward goblin warrior 1", "brom", None),
        ("BROM moves 25 feet toward goblin warrior 1", "brom", 25),
    ],
)
def test_a_move_toward_a_creature_needs_no_distance(line, actor, feet):
    p = _at_the_ambush()
    cmds = nl.parse(p.session, line)
    assert cmds[0]["cmd"] == "move" and cmds[0]["toward"] == "goblin_warrior_1"
    assert cmds[0].get("feet") == feet
    assert actor is None or cmds[0]["actor"] == actor


def test_a_move_toward_nothing_it_knows_asks_whom():
    p = _at_the_ambush()
    assert p.say("move toward the door").startswith("Move toward whom?")


@pytest.mark.parametrize("line", ["use sample party", "Use the sample party.", "sample party", "quickstart"])
def test_the_sample_party_is_found_by_any_close_wording(line):
    p = Play(seed=1)
    assert p.say(line).startswith("The sample party joins you")


@pytest.mark.parametrize("line", ["begin adventure", "start the adventure", "let's begin", "Begin!"])
def test_the_adventure_begins_by_any_close_wording(line):
    p = Play(seed=1)
    p.say("use the sample party")
    assert p.say(line).startswith("== Millbrook ==")


def test_a_typo_is_offered_back_and_yes_does_it():
    p = Play(seed=1)
    p.say("use the sample party")
    assert p.say("begin hte adventure") == (
        "I didn't catch that. Did you mean 'begin the adventure'? Say 'yes' to do that."
    )
    assert p.say("yes").startswith("== Millbrook ==")


def test_a_typo_offered_back_can_be_declined_and_is_then_forgotten():
    p = _party()
    assert "Did you mean 'status'?" in p.say("stauts")
    assert p.say("no") == "OK."
    assert "Did you mean" not in p.say("yes")  # nothing is waiting any more


def test_a_line_like_no_known_command_gets_no_guess():
    p = _party()
    assert "Did you mean" not in p.say("xyzzy")


def test_going_to_something_in_this_place_says_its_here():
    p = _party()
    out = p.say("go to the general store")
    assert "The general store is part of Millbrook, where you are now." in out
    assert "'BROM buys iron spikes'" in out
    assert "I don't know a place called" in p.say("go to waterdeep")


# ---------------- "Are you sure?" before harming someone who isn't an enemy ----------------
def _with_a_watchman():
    p = Play(seed=3, adventure=False, decider=lambda g, who, key, options, default, prompt: default)
    p.say("use the sample party")
    for c, pos in zip(p.game.pcs(), [(0, 0), (0, 5), (0, 10), (0, 15)], strict=True):
        c.position = pos
    w = spawn(p.game, ["guard"], [(5, 0)])[0]
    w.team, w.name = "neutral", "WATCHMAN"
    return p, w


def test_attacking_someone_who_isnt_fighting_you_asks_first():
    p, w = _with_a_watchman()
    assert p.say("BROM attacks watchman") == (
        "That would harm WATCHMAN, who isn't your enemy. Do it anyway? Say 'yes' or 'no'."
    )
    assert p.say("no") == "OK." and w.hp == w.max_hp and not p.game.log.of_kind("attack")


def test_yes_carries_out_the_harm_it_asked_about():
    p, w = _with_a_watchman()
    out = p.say("MIALEE casts thunderwave at watchman")
    assert "would harm WATCHMAN, BROM and LIDDA, who aren't your enemies" in out
    p.say("yes")
    assert p.game.is_enemy(w, p.game.get("mialee"))


def test_an_enemy_is_attacked_without_asking():
    p, w = _with_a_watchman()
    spawn(p.game, ["goblin warrior"], [(5, 5)])
    assert "Do it anyway" not in p.say("BROM attacks goblin warrior")


def test_a_creature_the_actor_cant_see_isnt_mentioned():
    p, w = _with_a_watchman()
    w.add_condition("invisible", "test")
    out = p.say("MIALEE casts thunderwave at BROM")
    assert "would harm BROM and LIDDA" in out and "WATCHMAN" not in out


def test_a_climbing_move_keeps_its_mode():
    p = _at_the_ambush()
    cmds = nl.parse(p.session, "BROM moves 10 feet toward goblin warrior 1, climbing the bank")
    assert cmds[0]["mode"] == "climb" and cmds[0]["feet"] == 10


def test_an_unnamed_creature_is_one_the_actor_can_see():
    p = _at_the_ambush()
    g = p.game
    actor = g.combat.current
    unseen = [e for e in g.enemies_of(actor) if not g.can_see(actor, e)]
    assert unseen  # the ambushers still hidden at this seed
    cmds = nl.parse(p.session, "move toward goblin warrior")
    assert g.can_see(actor, g.get(cmds[0]["toward"]))


# ---------------- naming a creature that has died ----------------
def _two_rats():
    p = Play(seed=1, adventure=False, decider=lambda g, who, key, options, default, prompt: default)
    p.say("use the sample party")
    return p, spawn(p.game, ["giant rat", "giant rat"], [(5, 0), (5, 5)])


def test_attacking_a_dead_creature_by_name_is_refused_not_turned_on_another():
    p, (rat1, rat2) = _two_rats()
    rat1.dead = True
    assert p.say("BROM attacks giant rat 1") == "(Refused) Giant Rat 1 is already dead"
    assert rat2.hp == rat2.max_hp


def test_a_name_a_later_fight_reused_finds_the_living_creature():
    p, (rat1, _) = _two_rats()
    rat1.dead = True
    again = spawn(p.game, ["giant rat"], [(5, 10)])[0]
    again.name = "Giant Rat 1"
    assert nl.parse(p.session, "BROM attacks giant rat 1")[0]["target"] == again.id


def test_status_marks_the_dead_in_the_initiative_order():
    p = _at_the_ambush()
    gob = p.game.get("goblin_warrior_1")
    gob.dead = True
    line = next(x for x in p.say("status").splitlines() if x.startswith("  Goblin Warrior 1: "))
    assert line.endswith(" (dead)")
