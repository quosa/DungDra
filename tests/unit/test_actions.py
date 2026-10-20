import pytest

from dungdra import actions
from dungdra.effects import AdvNext
from dungdra.rules import Refusal
from tests.support.helpers import pc


def test_help_check_refuses_the_helper_as_their_own_ally(game):
    lidda = pc(game, "LIDDA")
    with pytest.raises(Refusal) as e:
        actions.help_check(game, lidda, lidda, skill="perception")
    assert e.value.rule == "GLOSS.ally#1"
    assert e.value.ruling == "R-36"
    assert e.value.page == 176
    assert not lidda.find_effects(cls=AdvNext)
    assert game.log.last("help") is None


def test_help_check_gives_another_creature_advantage_on_the_check(game):
    lidda = pc(game, "LIDDA")
    brom = pc(game, "BROM", (5, 0))
    eff = actions.help_check(game, lidda, brom, skill="perception")
    assert eff in brom.effects
    assert eff.caster_id == lidda.id
    assert "LIDDA Helps BROM" in game.log.last("help").text
