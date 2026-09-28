import pytest

from dungdra import Game


@pytest.fixture
def game():
    return Game(seed=12345)
