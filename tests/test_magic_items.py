"""MI-01..05, EQP-05 (potion, torch)."""
import pytest

from dungdra import Refusal
from dungdra import combat as C, magic_items as MI, rest as R, spells as S, explore as X
from tests.helpers import pc, mon
from tests.test_combat import start, set_turn


def test_mi01_attunement(game):
    b = pc(game, "BROM")
    cloak = MI.make("cloak of protection")
    b.inventory.add(cloak)
    R.short_rest(game, [b], focus={b.id: ("identify", cloak)})
    assert cloak.props["identified"] and cloak not in b.attuned
    R.begin_rest(game, "short", [b], focus={b.id: ("attune", cloak)})
    R.interrupt_rest(game, "attacked")
    game.advance(3600)
    R.finish_short_rest(game, [b])
    assert cloak not in b.attuned
    R.short_rest(game, [b], focus={b.id: ("attune", cloak)})
    assert cloak in b.attuned and b.ac() == 20 and b.save_bonus_total("wis") == 0
    game.dice.force_str("d20=[10]")
    assert b.save("wis", 10).total == 11
    c2 = MI.make("cloak of protection")
    with pytest.raises(Refusal, match="copy"):
        MI.attune(game, b, c2)
    for _ in range(2):
        it = MI.make("cloak of protection"); it.name = f"ring {_}"; it.props["attunement"] = True
        MI.attune(game, b, it)
    x = MI.make("cloak of protection"); x.name = "amulet"
    with pytest.raises(Refusal, match="3"):
        MI.attune(game, b, x)
    MI.check_distance_attunements(game, b, {cloak.uid: 24})
    assert cloak not in b.attuned and b.ac() == 19
    it = b.attuned[0]
    R.short_rest(game, [b], focus={b.id: ("end_attunement", it)})
    assert it not in b.attuned


def test_mi02_eqp05_potions(game):
    l = pc(game, "LIDDA")
    ally = pc(game, "BROM", (5, 0))
    gob = mon(game, "goblin warrior", (60, 0))
    l.inventory.add(MI.make("potion of healing"))
    l.inventory.add(MI.make("potion of healing"))
    l.hp = 1
    ally.hp = 1
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, l, ally, gob)
    set_turn(game, l)
    game.dice.force_str("d4=[3,1]")
    MI.drink_potion(game, l)
    assert l.hp == 7 and game.combat.turn.bonus_used and l.inventory.count("potion of healing") == 1
    set_turn(game, l)
    MI.drink_potion(game, l, ally)
    assert ally.hp > 1 and game.combat.turn.bonus_used
    p = MI.make("potion of healing")
    MI.taste(game, l, p)
    assert p.props["identified"]


def test_eqp05_torch(game):
    b = pc(game, "BROM")
    n = b.inventory.count("torch")
    X.light_torch(game, b)
    assert b.light_sources() == [(20, 20)]
    game.advance(3600)
    assert b.light_sources() == [] and b.inventory.count("torch") == n - 1


def test_mi03_wand(game):
    l, m = pc(game, "LIDDA", (0, 0)), pc(game, "MIALEE", (0, 5))
    ogre = mon(game, "ogre", (30, 0))
    ogre.base_max_hp = ogre.hp = 500
    wand = MI.make("wand of magic missiles")
    l.inventory.add(wand)
    game.dice.force_str("d4=[1,1,1,1,1]")
    c = S.cast(game, l, "magic missile", ogre, item=wand, charges=3)
    assert c.level == 3 and ogre.hp == 500 - 10 and wand.props["charges"] == 4
    with pytest.raises(Refusal, match="3"):
        S.cast(game, l, "magic missile", ogre, item=wand, charges=4)
    l.inventory.items.remove(wand); m.inventory.items.append(wand)
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, m, l, ogre)
    set_turn(game, m)
    S.cast(game, m, "magic missile", ogre)
    game.combat.turn.actions += 1
    S.cast(game, m, "magic missile", ogre, item=wand, charges=1)
    C.end_combat(game)
    wand.props["charges"] = 1
    game.dice.force_str("d6=[3]")
    MI.dawn(game)
    assert wand.props["charges"] == 5
    wand.props["charges"] = 1
    game.dice.force_str("d20=[1]")
    S.cast(game, m, "magic missile", ogre, item=wand, charges=1)
    assert wand.props.get("destroyed") and m.inventory.find("wand of magic missiles") is None


def test_mi04_scroll(game):
    j, l, m = pc(game, "JOZAN"), pc(game, "LIDDA", (5, 0)), pc(game, "MIALEE", (0, 5))
    s = MI.make("spell scroll", spell="bless")
    j.inventory.add(s)
    for it in list(j.inventory):
        if it.name == "holy symbol":
            j.inventory.remove(it, it.qty)
    S.cast(game, j, "bless", [j], item=s, scroll=True)      # no components needed
    assert j.inventory.find("spell scroll") is None
    s2 = MI.make("spell scroll", spell="bless")
    l.inventory.add(s2)
    with pytest.raises(Refusal, match="unintelligible"):
        S.cast(game, l, "bless", [l], item=s2, scroll=True)
    web = MI.make("spell scroll", spell="web")
    m.inventory.add(web)
    gob = mon(game, "goblin warrior", (20, 0))
    game.dice.force_str("d20=[9]; d20=[20]")
    c = S.cast(game, m, "web", [gob], item=web, scroll=True)
    assert c.dc == 13 and "DC 13" in game.log.last("save").text
    web2 = MI.make("spell scroll", spell="web")
    m.inventory.add(web2)
    game.dice.force_str("d20=[5]")
    with pytest.raises(Refusal, match="lost"):
        S.cast(game, m, "web", [gob], item=web2, scroll=True)
    assert m.inventory.find("spell scroll") is None


def test_mi05_items(game):
    b = pc(game, "BROM")
    sword = MI.make("+1 longsword", base="longsword")
    b.inventory.add(sword)
    gob = mon(game, "ogre", (5, 0))
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]; d8=[4]")
    r = C.attack(game, b, gob, weapon=sword)
    assert r.roll.total == 16 and r.damage == 4 + 4
    mail = MI.make("+1 chain mail", base="chain mail")
    b.inventory.add(mail)
    b.armor = mail
    assert b.ac() == 20
    from dungdra import gear
    with pytest.raises(Refusal, match="one suit"):
        gear.don_armor(game, b, "chain mail")
    bag = MI.make("bag of holding")
    b.inventory.add(bag)
    w0 = b.load()
    MI.bag_put(game, b, bag, "glaive")
    assert b.load() == w0 - 6
    b.inventory.add("chest", 30)
    with pytest.raises(Refusal, match="500"):
        MI.bag_put(game, b, bag, "chest", 30)
    game.dice.force_str("d20=[20, 1]")
    start(game, b, gob)
    set_turn(game, b)
    MI.bag_take(game, b, bag, "glaive")
    assert not game.combat.turn.action_available()
    c1, c2 = MI.make("cloak of protection"), MI.make("cloak of protection")
    b.inventory.add(c1); b.inventory.add(c2)
    MI.wear(game, b, c1)
    with pytest.raises(Refusal, match="cloak"):
        MI.wear(game, b, c2)
