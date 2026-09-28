"""Mounted combat (SRD p.15-16)."""
from __future__ import annotations

from .rules import Refusal, size_index

MOUNT_ACTIONS = ("dash", "disengage", "dodge")


def mount(game, rider, steed, controlled=True):
    if size_index(steed.size) - size_index(rider.size) < 1:
        raise Refusal(f"{steed.name} must be at least one size larger than {rider.name}", page=15)
    if rider.distance_to(steed) > 5:
        raise Refusal(f"{steed.name} must be within 5 ft to mount it", page=15)
    cost = rider.speed() // 2
    cb = game.combat
    if cb is not None and cb.is_turn(rider):
        if cb.turn.movement_left < cost:
            raise Refusal(f"Mounting costs {cost} ft of movement", page=15)
        cb.turn.movement_left -= cost
    rider.notes["mount"] = steed.id
    steed.notes["rider"] = rider.id
    steed.notes["controlled"] = controlled
    rider.position = steed.position
    steed.team = rider.team if controlled else steed.team
    game.log.player("mount", f"{rider.name} mounts {steed.name} (costs {cost} ft of movement)", page=15)
    if controlled and cb is not None:
        ini = cb.initiative_of(rider)
        cb.order = [(cid, v) for cid, v in cb.order if cid != steed.id]
        idx = next(i for i, (cid, _) in enumerate(cb.order) if cid == rider.id)
        cb.order.insert(idx + 1, (steed.id, ini))
        if cb.index > idx:
            cb.index += 1
        game.log.player("mount", f"{steed.name} is a controlled mount: it acts on {rider.name}'s Initiative ({ini}) "
                        f"and can only Dash, Disengage or Dodge", page=16)
    return cost


def dismount(game, rider):
    sid = rider.notes.pop("mount", None)
    if sid is None:
        raise Refusal(f"{rider.name} isn't mounted")
    steed = game.creatures[sid]
    steed.notes.pop("rider", None)
    cost = rider.speed() // 2
    cb = game.combat
    if cb is not None and cb.is_turn(rider):
        cb.turn.movement_left = max(0, cb.turn.movement_left - cost)
    rider.position = (steed.position[0] + 5, steed.position[1])
    game.log.player("mount", f"{rider.name} dismounts (costs {cost} ft)", page=15)


def mount_action(game, steed, action):
    if steed.notes.get("controlled") and action.lower() not in MOUNT_ACTIONS:
        raise Refusal("A controlled mount can only take the Dash, Disengage or Dodge action", page=16)
    from . import actions
    a = action.lower()
    return {"dash": actions.dash, "disengage": actions.disengage, "dodge": actions.dodge}[a](game, steed)


def fall_off_check(game, rider, why):
    """p.16: DC 10 Dex save or fall off, landing Prone within 5 ft of the mount."""
    sid = rider.notes.get("mount")
    if sid is None:
        return None
    r = rider.save("dex", 10, label=f"Dexterity save to stay mounted ({why})", page=16)
    if not r.success:
        steed = game.creatures[sid]
        rider.notes.pop("mount", None)
        steed.notes.pop("rider", None)
        rider.position = (steed.position[0] + 5, steed.position[1])
        rider.add_condition("prone", "fell off the mount")
        game.log.player("mount", f"{rider.name} falls off {steed.name} and lands Prone", page=16)
    return r
