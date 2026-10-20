from dungdra.fixtures import make
from dungdra.monster import Monster


def pc(game, name, pos=(0, 0)):
    return make(game, name, position=pos)


def mon(game, key, pos=(5, 0), name=None, **kw):
    m = Monster(key, name=name, **kw)
    return game.add(m, team="enemy", position=pos)
