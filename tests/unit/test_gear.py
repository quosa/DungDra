"""Unit tests for dungdra.gear: selling values the owned item, so its `cost` prop sets the price."""

import pytest

from dungdra import gear
from dungdra.inventory_view import inventory_text
from dungdra.rules import Refusal
from tests.support.helpers import pc


def test_selling_an_item_with_a_cost_prop_pays_half_that_cost(game):
    b = pc(game, "BROM")
    b.inventory.add("dagger", title="Jeweled Dagger", cost=5000)
    cp0 = b.purse.total_cp()
    assert gear.sell(game, b, "jeweled dagger") == 2500
    assert b.purse.total_cp() - cp0 == 2500
    assert b.inventory.find("jeweled dagger") is None


def test_selling_a_plain_item_pays_half_the_table_price(game):
    b = pc(game, "BROM")
    cp0 = b.purse.total_cp()
    assert gear.sell(game, b, "longsword") == 750
    assert b.purse.total_cp() - cp0 == 750


def test_sell_value_prop_still_overrides_the_sale_price(game):
    b = pc(game, "BROM")
    b.inventory.add("dagger", title="Gem", cost=5000, sell_value=5000)
    assert gear.sell(game, b, "gem") == 5000


# ---------------- spares next to what's worn or wielded ----------------
def test_a_bought_shield_is_a_spare_next_to_the_worn_one(game):
    brom = pc(game, "BROM")
    gear.buy(game, brom, "shield")
    shields = brom.inventory.find_all("shield")
    assert len(shields) == 2 and all(s.qty == 1 for s in shields)
    assert "Carried armor: Shield" in inventory_text(brom)


def test_selling_a_shield_sells_the_spare_and_never_the_worn_one(game):
    brom = pc(game, "BROM")
    worn = brom.shield
    gear.buy(game, brom, "shield")
    gear.sell(game, brom, "shield")
    assert brom.shield is worn and brom.inventory.find_all("shield") == [worn]
    with pytest.raises(Refusal, match="Take off Shield"):
        gear.sell(game, brom, "shield")


def test_selling_one_of_a_stack_in_hand_keeps_the_rest_in_hand(game):
    brom = pc(game, "BROM")
    sword = brom.inventory.find("longsword")
    gear.buy(game, brom, "longsword")
    assert sword.qty == 2 and sword in brom.wielded
    gear.sell(game, brom, "longsword")
    assert sword.qty == 1 and sword in brom.wielded
    gear.sell(game, brom, "longsword")
    assert sword not in brom.wielded
