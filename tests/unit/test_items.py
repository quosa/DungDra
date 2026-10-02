"""Unit tests for dungdra.items: an item's value is Item.listed_cost(), which a `cost` prop overrides."""

import pytest

from dungdra.items import Item
from dungdra.rules import Refusal


def test_listed_cost_is_the_equipment_table_price_without_a_cost_prop():
    assert Item("longsword").listed_cost() == 1500
    assert Item("longsword").unit_cost() == 1500


def test_cost_prop_overrides_the_table_price():
    it = Item("dagger", title="Jeweled Dagger", cost=5000)
    assert it.listed_cost() == 5000 and it.unit_cost() == 5000


def test_unpriced_item_has_no_listed_cost_and_zero_unit_cost():
    it = Item("strange idol")
    assert it.listed_cost() is None and it.unit_cost() == 0


def test_sale_price_is_half_the_item_value_including_a_cost_prop():
    assert Item("longsword").sale_price() == 750
    assert Item("dagger", cost=5001).sale_price() == 2500  # rounds down


def test_sale_price_refuses_an_unpriced_item():
    with pytest.raises(Refusal, match="strange idol"):
        Item("strange idol").sale_price()


def test_sell_value_prop_replaces_the_half_price_sale():
    assert Item("dagger", cost=5000, sell_value=5000).sale_price() == 5000
    assert Item("strange idol", sell_value=300).sale_price() == 300  # no listed cost needed
