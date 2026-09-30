"""Unit tests for dungdra.creature: conditions, saves and damage log the rule they apply."""

from tests.support.helpers import mon, pc


def test_the_grappled_condition_logs_its_rule_and_ruling_r07(game):
    gob = mon(game, "goblin warrior")
    gob.add_condition("grappled", "grappled by Brom", grappler="brom")
    ev = game.log.last("condition")
    assert (ev.rule, ev.ruling) == ("GLOSS.grappled", "R-07")


def test_other_conditions_log_their_glossary_entry_and_no_ruling(game):
    gob = mon(game, "goblin warrior")
    gob.add_condition("prone", "shoved")
    ev = game.log.last("condition")
    assert (ev.rule, ev.ruling) == ("GLOSS.prone", None)
    gob.remove_condition("prone")
    assert game.log.last("condition_end").rule == "GLOSS.prone"


def test_a_condition_immunity_cites_immunity(game):
    gob = mon(game, "goblin warrior")
    gob.cond_immune.add("poisoned")
    gob.add_condition("poisoned")
    assert game.log.last("immune").rule == "PLAY.damage-and-healing.immunity"


def test_a_save_carries_the_callers_rule(game):
    brom = pc(game, "BROM")
    game.dice.force_str("d20=[15]")
    brom.save("con", 10, rule="GLOSS.concentration")
    assert game.log.last("save").rule == "GLOSS.concentration"


def test_a_save_without_a_rule_cites_saving_throws(game):
    brom = pc(game, "BROM")
    game.dice.force_str("d20=[15]")
    brom.save("con", 10)
    assert game.log.last("save").rule == "PLAY.d20-tests.saving-throws"


def test_damage_and_healing_log_their_rules(game):
    brom = pc(game, "BROM")
    brom.take_damage(3, "fire", source="a trap", rule="TOOLBOX.traps.example-traps")
    assert game.log.last("damage").rule == "TOOLBOX.traps.example-traps"
    brom.take_damage(1, "fire")
    assert game.log.last("damage").rule == "PLAY.damage-and-healing"
    brom.heal(2)
    assert game.log.last("heal").rule == "PLAY.damage-and-healing.healing"


def test_exhaustion_cites_its_cause_when_given(game):
    brom = pc(game, "BROM")
    brom.gain_exhaustion(1, "suffocation", page=189, rule="GLOSS.suffocation")
    assert game.log.last("exhaustion").rule == "GLOSS.suffocation"
    brom.lose_exhaustion(1)
    assert game.log.last("exhaustion").rule == "GLOSS.exhaustion"
