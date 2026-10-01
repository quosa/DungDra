"""Unit tests for dungdra.gear: selling values the owned item, so its `cost` prop sets the price."""

from dungdra import gear
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
