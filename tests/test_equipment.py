"""EQP (non-combat parts) and FEAT-04."""
import pytest

from dungdra import Refusal
from dungdra.fixtures import make, party
from dungdra import gear
from dungdra.items import make_change


@pytest.fixture
def pcs(game):
    return {pc.name: pc for pc in party(game)}


# EQP-01 · Armor training, Strength requirement and Stealth
def test_eqp01_armor_training(pcs, game):
    m, b, j = pcs["MIALEE"], pcs["BROM"], pcs["JOZAN"]
    m.inventory.add("leather armor")
    t0 = game.clock
    gear.don_armor(game, m, "leather armor")
    assert game.clock - t0 == 60                       # light armor: 1 minute
    game.dice.force_str("d20=[5,15]")
    r = m.check("athletics")
    assert r.mode == "disadvantage"
    game.dice.force_str("d20=[5,15]")
    assert m.save("dex", 10).mode == "disadvantage"
    game.dice.force_str("d20=[5]")
    assert m.save("wis", 10).mode == "normal"
    gear.doff_armor(game, m)
    m.inventory.add("chain mail")
    t0 = game.clock
    gear.don_armor(game, m, "chain mail")
    assert game.clock - t0 == 600                      # heavy: 10 minutes
    assert m.speed() == 20                             # Str 8 < 13
    game.dice.force_str("d20=[5,15]")
    assert b.check("stealth").mode == "disadvantage"
    assert j.trained_in("heavy") and j.score("str") >= 13
    j.armor = None
    j.inventory.add("chain mail")
    gear.don_armor(game, j, "chain mail")
    assert j.speed() == 30 and j.ac() == 18
    gear.doff_armor(game, m)
    m.inventory.add("shield")
    gear.equip_shield(game, m)
    assert m.ac() == 11                                # untrained Shield: no AC bonus


def test_eqp01_no_armor_changes_in_combat(pcs, game):
    m = pcs["MIALEE"]
    m.inventory.add("leather armor")
    game.combat = object()
    with pytest.raises(Refusal, match="minute"):
        gear.don_armor(game, m, "leather armor")
    game.combat = None


# EQP-04 · Coins, carrying capacity and selling
def test_eqp04(pcs, game):
    l, b = pcs["LIDDA"], pcs["BROM"]
    assert make_change(500, 170) == {"gp": 3, "sp": 3, "cp": 0}
    for it in list(l.inventory):
        l.inventory.remove(it, it.qty)
    l.purse.coins = {k: 0 for k in l.purse.coins}
    with pytest.raises(Refusal, match="180"):
        gear.pick_up(game, l, "crate", weight=190)
    gear.drag(game, l, 300)
    assert l.speed() <= 5
    gp0 = b.purse.total_cp()
    gear.sell(game, b, "longsword")
    assert b.purse.total_cp() - gp0 == 750
    l.purse.coins["gp"] = 500
    assert l.purse.weight() == 10


# EQP-06 · Lifestyle and crafting
def test_eqp06(pcs, game):
    j, l = pcs["JOZAN"], pcs["LIDDA"]
    plan = gear.craft_plan("shortbow")
    assert plan["materials_cp"] == 1200 and plan["days"] == 3
    assert gear.craft_plan("shortbow", helpers=1)["work_days"] == 1.5
    with pytest.raises(Refusal, match="Woodcarver"):
        gear.craft(game, l, "shortbow")
    cp0, t0 = j.purse.total_cp(), game.clock
    gear.craft(game, j, "shortbow")
    assert cp0 - j.purse.total_cp() == 1200 and game.clock - t0 == 3 * 86400
    j.purse.add(gp=20)
    before = {p.name: p.purse.total_cp() for p in pcs.values()}
    t0 = game.clock
    gear.live(game, list(pcs.values()), "modest", 7)
    assert all(before[p.name] - p.purse.total_cp() == 700 for p in pcs.values())
    assert game.clock - t0 == 7 * 86400


# FEAT-04 · Defense
def test_feat04_defense(pcs, game):
    b = pcs["BROM"]
    assert b.ac() == 19
    gear.doff_armor(game, b)
    assert b.ac() == 14
    gear.don_armor(game, b, "chain mail")
    assert b.ac() == 19
    game.answer("fighting_style_swap", "great weapon fighting")
    b.award_xp(300)
    assert b.fighting_style == "great weapon fighting" and b.ac() == 18
