"""The Ready action (GLOSS.ready, SRD p.186-187) as the SRD tests drive it.

The engine has no Ready command yet, so this module is the one place that fixes the shape the
tests use. If the dev loop settles on another shape, change it here, not in the tests.

- `ready(session, actor, trigger, response)` runs `{"cmd": "ready", ...}` on the actor's turn.
- A trigger is a perceivable circumstance in structured form. The tests only need one kind:
  `moves_within(creature, feet)`: "creature moves to within `feet` feet of me".
- A response is the command the actor will run with its Reaction, without the actor:
  `{"cmd": "attack", "target": ...}`, `{"cmd": "cast", "spell": ..., "targets": [...]}` or
  `{"cmd": "move", "to": [x, y]}` (movement up to Speed).
- When the trigger occurs the engine asks the readier `game.decide(actor, READIED, [True, False])`:
  True takes the Reaction right after the trigger, False ignores the trigger.
"""

from __future__ import annotations

from dungdra import combat as C
from dungdra.api import Session

READIED = "readied"


def moves_within(creature, feet: int = 5) -> dict:
    return {"event": "moves_within", "creature": creature.id, "feet": feet}


def ready(session: Session, actor, trigger: dict, response) -> dict:
    return session.execute({"cmd": "ready", "actor": actor.id, "trigger": trigger, "response": response})


def combat_session(game, first, *others) -> Session:
    """A session whose monster turns are driven by the test, with `first` acting first.

    Initiative is forced: 20 for `first`, then 10, 9, ... for the others in order. Identical
    monsters share one roll (p.13), so they get one forced die and keep the order given."""
    s = Session(game)
    s.auto_gm = False
    groups = []
    for c in others:
        key = getattr(c, "key", None) or c.id
        if key not in groups:
            groups.append(key)
    game.dice.force_str("d20=[" + ",".join(["20"] + [str(10 - i) for i in range(len(groups))]) + "]")
    C.roll_initiative(game, [first, *others])
    assert game.combat.current is first
    return s


def end_turn(session: Session) -> dict:
    out = session.execute({"cmd": "end_turn"})
    assert out["ok"], out
    return out


def move(session: Session, creature, to) -> dict:
    out = session.execute({"cmd": "move", "actor": creature.id, "to": list(to)})
    assert out["ok"], out
    return out


def reaction_used(game, creature) -> bool:
    return creature.id in game.combat.reaction_used
