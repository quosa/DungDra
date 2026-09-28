"""CORE: D20 Tests and core conventions (SRD p.5-9)."""
import pytest

from dungdra.creature import Creature
from dungdra.rules import ability_mod, div, mul


# CORE-01 · Ability modifiers and rounding
def test_core01_ability_modifiers():
    table = {1: -5, 2: -4, 3: -4, 8: -1, 9: -1, 10: 0, 11: 0, 16: 3, 17: 3, 20: 5, 21: 5, 30: 10}
    for score, m in table.items():
        assert ability_mod(score) == m
    for score in range(1, 31):
        assert ability_mod(score) == (score - 10) // 2


def test_core01_round_down():
    assert div(17, 2) == 8
    assert div(10, 3) == 3
    assert mul(7, 0.5) == 3


def _bob(game, **kw):
    return game.add(Creature("Bob", {"str": 10}, **kw), team="party")


# CORE-02 · Advantage, Disadvantage and rerolls
def test_core02a_one_advantage(game):
    bob = _bob(game)
    game.dice.force_str("d20=[18,3]")
    r = bob.check(ability="str", adv=["high ground"])
    assert r.dice == [18, 3] and r.chosen == 18
    assert "high ground" in game.log.last("check").text


def test_core02b_mixed_cancels(game):
    bob = _bob(game)
    game.dice.force_str("d20=[7]")
    r = bob.check(ability="str", adv=["a", "b"], dis=["c"])
    assert r.dice == [7] and r.mode == "normal"
    assert game.dice.pending("d20") == 0
    text = game.log.last("check").text
    assert all(s in text for s in ("a", "b", "c"))


def test_core02c_three_advantages_two_dice(game):
    bob = _bob(game)
    game.dice.force_str("d20=[4,15,9]")
    r = bob.check(ability="str", adv=["x", "y", "z"])
    assert r.dice == [4, 15] and r.chosen == 15
    assert game.dice.pending("d20") == 1


def test_core02d_heroic_inspiration_reroll_one_die(game):
    jozan = _bob(game)
    jozan.heroic_inspiration = True
    game.dice.force_str("d20=[3,18,11]")
    game.answer("inspiration", 0)            # player chooses to reroll the die showing 3
    r = jozan.check(ability="wis", adv=["Help"])
    assert r.dice == [11, 18] and r.chosen == 18
    assert jozan.heroic_inspiration is False
    assert any("Heroic Inspiration 3" in x for x in r.rerolls)


def test_core02d_inspiration_cannot_hold_two(game):
    from dungdra.rest import grant_heroic_inspiration
    a = _bob(game)
    b = game.add(Creature("Cy"), team="party")
    a.heroic_inspiration = True
    game.answer("give_inspiration", "cy")
    grant_heroic_inspiration(game, a)
    assert a.heroic_inspiration and b.heroic_inspiration
    grant_heroic_inspiration(game, a)          # nobody lacks it -> lost
    assert "lost" in game.log.last("inspiration").text


def test_core02e_halfling_luck_offered_not_automatic(game):
    lidda = _bob(game)
    lidda.traits.add("luck")
    game.dice.force_str("d20=[1,12]")
    r = lidda.check(ability="dex", dis=["Poisoned"])     # declines by default
    assert r.chosen == 1 and not r.rerolls
    game.dice.force_str("d20=[1,12,9]")
    game.answer("luck", True)
    r = lidda.check(ability="dex", dis=["Poisoned"])
    assert r.dice == [9, 12] and r.chosen == 9
    assert game.log.of_kind("offer")


def test_core05_save_rules(game):
    c = _bob(game)
    c.save_profs.add("con")
    c.abilities["con"] = 14
    game.dice.force_str("d20=[20]")
    r = c.save("con", 30)
    assert r.chosen == 20 and r.success is False       # no automatic success on saves
    game.dice.force_str("d20=[1]")
    r = c.save("con", 5)
    assert r.success is True                           # no automatic failure on saves
    r = c.save("dex", 5, choose_to_fail=True)
    assert r.success is False and r.dice == []
    c.abilities["str"] = None
    assert c.save("str", 1).success is False            # lacks the ability -> auto fail
