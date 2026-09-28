"""Dropping to 0 HP, Death Saving Throws, stabilizing (SRD p.17-18)."""
from __future__ import annotations

from .d20 import D20Roll, roll_d20_test
from .data.equipment import canonical
from .rules import HOUR, Refusal


def pc_drop_to_zero(pc, remainder: int, crit: bool):
    g = pc.game
    if remainder >= pc.max_hp:
        pc.die(f"Massive Damage: {remainder} damage remained, ≥ HP maximum {pc.max_hp}")
        return
    pc.hp = 0
    pc.stable = False
    pc.death_saves = {"success": 0, "failure": 0}
    pc.notes["dying"] = True
    if g:
        g.log.player("down", f"{pc.name} drops to 0 HP ({remainder} damage left over, below the HP maximum of "
                     f"{pc.max_hp}) and is Unconscious", page=17)
    if not pc.has("unconscious"):
        pc.add_condition("unconscious", "0 Hit Points")


def pc_damage_at_zero(pc, amount: int, crit: bool):
    g = pc.game
    if amount >= pc.max_hp:
        pc.die(f"took {amount} damage at 0 HP, ≥ HP maximum")
        return
    if pc.stable:
        pc.stable = False
        if g:
            g.log.player("death_save", f"{pc.name} is no longer Stable", page=18)
    n = 2 if crit else 1
    add_failures(pc, n, "Critical Hit at 0 HP" if crit else "damage at 0 HP")


def add_failures(pc, n, why):
    pc.death_saves["failure"] += n
    g = pc.game
    if g:
        g.log.player("death_save", f"{pc.name} suffers {n} Death Saving Throw failure{'s' if n > 1 else ''} ({why}); "
                     f"successes {pc.death_saves['success']}, failures {pc.death_saves['failure']}", page=18)
    if pc.death_saves["failure"] >= 3:
        pc.die("three Death Saving Throw failures")


def death_save(game, pc) -> D20Roll:
    """p.17-18: at the start of the turn with 0 HP. 10+ succeeds; 1 = two failures; 20 = regain 1 HP."""
    roll = D20Roll("death save", "Death Saving Throw", pc.name, target=10)
    roll_d20_test(game, pc, roll, page=17)
    d = roll.chosen + roll.modifier
    if roll.chosen == 20:
        game.log.player("death_save", f"{pc.name} rolls a 20 on the Death Saving Throw and regains 1 HP", page=18)
        pc.heal(1, "natural 20 on a Death Saving Throw", page=18)
        return roll
    if roll.chosen == 1:
        add_failures(pc, 2, "rolled a 1")
        return roll
    if d >= 10:
        pc.death_saves["success"] += 1
        game.log.player("death_save", f"{pc.name}: success ({pc.death_saves['success']} successes, "
                        f"{pc.death_saves['failure']} failures)", page=17)
        if pc.death_saves["success"] >= 3:
            make_stable(game, pc, "three successes")
    else:
        add_failures(pc, 1, f"rolled {d}")
    return roll


def make_stable(game, pc, how: str):
    if pc.dead:
        raise Refusal(f"{pc.name} is dead")
    if pc.hp > 0:
        raise Refusal(f"{pc.name} isn't at 0 HP")
    pc.stable = True
    pc.death_saves = {"success": 0, "failure": 0}
    pc.notes["stable_since"] = game.clock
    wake = game.dice.roll(4)
    pc.notes["stable_wake_at"] = game.clock + wake * HOUR
    game.log.player("stable", f"{pc.name} is Stable ({how}); still Unconscious, regains 1 HP after 1d4={wake} "
                    f"hours if not healed", page=18)


def first_aid(game, helper, patient, dc=10):
    """Help action to stabilize (p.18) / first aid on a knocked-out creature (p.183): DC 10 Wis (Medicine)."""
    if helper.distance_to(patient) > 5:
        raise Refusal(f"{helper.name} must be within 5 ft of {patient.name}")
    if game.combat is not None:
        game.combat.spend(helper, "action", "Help (first aid)")
    r = helper.check("medicine", dc=dc, label=f"Wisdom (Medicine) check to stabilize {patient.name}", page=18)
    if r.success:
        if patient.notes.get("knocked_out"):
            patient.remove_condition("unconscious", reason="first aid")
            patient.notes.pop("knocked_out", None)
        elif patient.hp == 0 and not patient.dead:
            make_stable(game, patient, f"first aid from {helper.name}")
    return r


def healers_kit(game, helper, patient):
    """p.97: Utilize action, expend one use, stabilize with no Medicine check."""
    kit = helper.inventory.find("healer's kit") if hasattr(helper, "inventory") else None
    if kit is None or kit.props.get("uses", 0) <= 0:
        raise Refusal(f"{helper.name} has no Healer's Kit with uses left")
    if helper.distance_to(patient) > 5:
        raise Refusal(f"{helper.name} must be within 5 ft of {patient.name}")
    if not (patient.hp == 0 and patient.has("unconscious")):
        raise Refusal("A Healer's Kit stabilizes an Unconscious creature that has 0 Hit Points")
    if game.combat is not None:
        game.combat.spend(helper, "action", "Utilize (Healer's Kit)")
    kit.props["uses"] -= 1
    make_stable(game, patient, f"{helper.name}'s Healer's Kit ({kit.props['uses']} uses left), no Medicine check")


def on_time_passed(game, c, start, end):
    if c.is_pc() and c.stable and c.hp == 0 and not c.dead:
        at = c.notes.get("stable_wake_at")
        if at is not None and end >= at:
            c.notes.pop("stable_wake_at", None)
            c.heal(1, "Stable for 1d4 hours", page=18)
    if c.notes.get("knocked_out") and end - c.notes.get("ko_at", start) >= HOUR:
        c.notes.pop("knocked_out", None)
        c.remove_condition("unconscious", reason="finished its Short Rest")
