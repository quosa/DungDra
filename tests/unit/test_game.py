"""Unit tests for dungdra.game: cover between an attacker and a target, its bonus, and choices."""

import pytest

from dungdra import class_actions as CA
from dungdra import combat as C
from dungdra import spells as S
from tests.support.helpers import mon, pc


def setup(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    return lidda, gob


def test_a_creature_in_the_line_gives_half_cover(game):
    lidda, gob = setup(game)
    screen = mon(game, "goblin warrior", (15, 0), name="Screen")
    assert game.creatures_in_the_way(lidda, gob) == [screen]
    assert game.cover_between(lidda, gob) == "half"


def test_several_creatures_still_give_only_half(game):
    lidda, gob = setup(game)
    mon(game, "goblin warrior", (10, 0), name="A")
    mon(game, "goblin warrior", (20, 0), name="B")
    assert game.cover_between(lidda, gob) == "half"


def test_a_scene_label_beats_creature_cover(game):
    lidda, gob = setup(game)
    mon(game, "goblin warrior", (15, 0), name="Screen")
    game.scene.cover[(lidda.id, gob.id)] = "three-quarters"
    assert game.cover_between(lidda, gob) == "three-quarters"


def test_creatures_off_the_line_behind_or_dead_give_none(game):
    lidda, gob = setup(game)
    mon(game, "goblin warrior", (15, 30), name="Aside")
    mon(game, "goblin warrior", (45, 0), name="Behind")
    corpse = mon(game, "goblin warrior", (15, 0), name="Corpse")
    corpse.dead = True
    assert game.cover_between(lidda, gob) is None


def test_a_creature_sharing_the_targets_space_is_not_in_the_way(game):
    lidda, gob = setup(game)
    pc(game, "BROM", (30, 0))
    assert game.cover_between(lidda, gob) is None


def test_a_dead_creature_is_not_in_the_way(game):
    lidda, gob = setup(game)
    screen = mon(game, "goblin warrior", (15, 0), name="Screen")
    screen.dead = True
    assert game.cover_between(lidda, gob) is None


def test_cover_bonus_is_plus_two_for_half_and_logged_with_its_clause(game):
    lidda, gob = setup(game)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    assert game.cover_bonus(lidda, gob, "AC") == [(2, "Half Cover")]
    (ev,) = game.log.applied(rule="PLAY.combat.cover")
    assert ev.rule == "PLAY.combat.cover#5" and ev.page == "15"


def test_cover_bonus_is_plus_five_for_three_quarters(game):
    lidda, gob = setup(game)
    game.scene.cover_all[gob.id] = "three-quarters"
    assert game.cover_bonus(lidda, gob, "AC") == [(5, "Three-Quarters Cover")]
    assert [e.rule for e in game.log.applied(rule="PLAY.combat.cover")] == ["PLAY.combat.cover#7"]


def test_no_or_total_cover_gives_no_bonus_and_logs_nothing(game):
    lidda, gob = setup(game)
    assert game.cover_bonus(lidda, gob, "AC") == []
    game.scene.cover[(lidda.id, gob.id)] = "total"
    assert game.cover_bonus(lidda, gob, "AC") == []
    assert game.log.applied(rule="PLAY.combat.cover") == []


def test_cover_from_a_point_of_origin_reads_the_scene_label_for_that_point(game):
    lidda, gob = setup(game)
    game.scene.cover[((40, 0), gob.id)] = "total"
    assert game.cover_between((40, 0), gob) == "total"
    # the label is for that point only, not for the caster nor another point
    assert game.cover_between(lidda, gob) is None
    assert game.cover_between((20, 0), gob) is None


def test_labelled_cover_reads_an_objects_labels_by_name_and_keeps_the_most_protective(game):
    lidda, _ = setup(game)
    assert game.labelled_cover(lidda, "hay") is None
    game.scene.cover_all["hay"] = "half"
    game.scene.cover[((40, 0), "hay")] = "total"
    assert game.labelled_cover((40, 0), "hay") == "total"
    assert game.labelled_cover(lidda, "hay") == "half"
    assert game.labelled_cover(None, "hay") == "half"


def test_a_creature_between_a_point_of_origin_and_the_target_gives_half_cover(game):
    _, gob = setup(game)
    mon(game, "goblin warrior", (50, 0), name="SHIELD")
    assert game.cover_between((70, 2.5), gob) == "half"
    # the same creature is behind the target as seen from the caster's side
    assert game.cover_between((0, 2.5), gob) is None


def test_cover_bonus_against_a_point_names_the_point_in_the_log(game):
    _, gob = setup(game)
    game.scene.cover[((40, 0), gob.id)] = "half"
    assert game.cover_bonus([40, 0], gob, "the Dexterity saving throw") == [(2, "Half Cover")]
    (ev,) = game.log.applied(rule="PLAY.combat.cover")
    assert "point of origin at [40, 0]" in ev.text and ev.rule == "PLAY.combat.cover#5"


def guard(game, attitude):
    g = mon(game, "guard", (10, 0), name="WATCHMAN")
    g.team = "neutral"
    g.attitude = attitude
    return g


def test_a_friendly_creature_off_both_sides_is_an_ally_of_the_party_and_back(game):
    lidda = pc(game, "LIDDA", (0, 0))
    g = guard(game, "friendly")
    assert g in game.allies_of(lidda)
    assert lidda in game.allies_of(g)


def test_an_indifferent_or_hostile_creature_off_both_sides_is_no_ally(game):
    lidda = pc(game, "LIDDA", (0, 0))
    g = guard(game, "indifferent")
    assert g not in game.allies_of(lidda)
    g.attitude = "hostile"
    assert g not in game.allies_of(lidda)


def test_a_friendly_creature_is_no_ally_of_the_enemy_side(game):
    gob = mon(game, "goblin warrior", (30, 0))
    g = guard(game, "friendly")
    assert g not in game.allies_of(gob)


def test_a_creature_is_never_its_own_ally(game):
    lidda = pc(game, "LIDDA", (0, 0))
    assert not game.is_ally(lidda, lidda)
    assert lidda not in game.allies_of(lidda)


def test_creatures_on_the_same_side_are_allies_and_the_other_side_is_not(game):
    lidda = pc(game, "LIDDA", (0, 0))
    brom = pc(game, "BROM", (5, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    assert game.is_ally(lidda, brom)
    assert brom in game.allies_of(lidda)
    assert gob not in game.allies_of(lidda)


def test_a_monster_added_to_the_party_side_is_an_ally_but_not_on_the_pc_roster(game):
    lidda = pc(game, "LIDDA", (0, 0))
    g = mon(game, "guard", (10, 0))
    game.remove(g)
    game.add(g, team="party", position=(10, 0))
    assert g in game.allies_of(lidda)
    assert lidda in game.allies_of(g)
    assert game.pcs() == [lidda]


def test_a_queued_answer_among_the_options_is_taken(game):
    game.answer("pick", "b")
    assert game.decide(None, "pick", ["a", "b", None], default="a") == "b"


def test_a_named_option_matches_whatever_its_case_and_the_option_itself_is_returned(game):
    game.answer("subclass", "Life-Domain")
    assert game.decide(None, "subclass", ["life domain"], default="life domain") == "life domain"


def test_an_answer_outside_the_options_declines_where_declining_is_offered(game):
    game.answer("pick", "ogre")
    assert game.decide(None, "pick", ["a", "b", None], default="a") is None
    assert "'ogre' doesn't fit the options for pick" in game.log.last("decide").text
    assert game.log.last("decide").visibility != "player"


def test_an_answer_outside_the_options_takes_the_default_where_declining_isnt_offered(game):
    game.answer("swap", "maybe")
    assert game.decide(None, "swap", [True, False], default=False) is False


def test_a_number_doesnt_answer_a_yes_or_no_choice_nor_a_yes_pick_a_die(game):
    game.answer("swap", 1)
    assert game.decide(None, "swap", [True, False], default=False) is False
    game.answer("reroll", True)
    assert game.decide(None, "reroll", [None, 0, 1], default=None) is None


def test_the_players_answer_is_checked_like_a_queued_one(game):
    game.decider = lambda g, who, key, options, default, prompt: "nobody"
    lidda = pc(game, "LIDDA", (0, 0))
    assert game.decide(lidda, "give", ["x", None], default="x", prompt="Give?") is None


def test_a_multi_pick_answer_takes_any_picks_from_the_pool(game):
    game.answer("learn", ["Sleep", "shield"])
    pool = ["magic missile", "shield", "sleep"]
    assert game.decide(None, "learn", pool, default=pool[:2], many=True) == ["sleep", "shield"]


def test_a_lone_option_answers_a_multi_pick_as_a_list_of_one(game):
    game.answer("learn", "sleep")
    assert game.decide(None, "learn", ["shield", "sleep"], default=["shield"], many=True) == ["sleep"]


def test_a_multi_pick_uses_each_option_only_as_often_as_it_is_offered(game):
    game.answer("recover", [1])
    assert game.decide(None, "recover", [1, 1, 2], default=[2], many=True) == [1]
    game.answer("recover", [2, 2])
    assert game.decide(None, "recover", [1, 1, 2], default=[2], many=True) == [2]


def test_a_multi_pick_naming_anything_outside_the_pool_takes_the_default(game):
    game.answer("learn", ["shield", "wish"])
    assert game.decide(None, "learn", ["shield", "sleep"], default=["shield"], many=True) == ["shield"]


def test_without_options_the_answer_is_left_to_the_caller(game):
    game.answer("free", 42)
    assert game.decide(None, "free", None, default=0) == 42


# ---------------- enemies by deed (p.181, R-45, R-46) ----------------
def bystander(game, pos=(5, 0), attitude="indifferent"):
    g = mon(game, "guard", pos, name="WATCHMAN")
    g.team, g.attitude = "neutral", attitude
    return g


def test_creatures_on_no_side_have_no_enemies_until_someone_acts(game):
    lidda = pc(game, "LIDDA", (0, 0))
    w = bystander(game)
    assert not game.is_enemy(lidda, w) and not game.is_enemy(w, lidda)
    assert game.enemies_of(w) == []


def test_an_attack_makes_the_attacker_its_victims_enemy_and_says_so_once(game):
    lidda = pc(game, "LIDDA", (0, 0))
    w = bystander(game)
    game.dice.force_str("d20=[2,2]")
    for _ in range(2):
        C.attack(game, w, lidda, attack_name="spear")
    assert game.is_enemy(lidda, w) and w in game.enemies_of(lidda)
    assert not game.is_enemy(w, lidda)  # LIDDA did nothing to the watchman
    said = game.log.of_kind("enemy")
    assert len(said) == 1
    assert said[0].text == "WATCHMAN works to harm LIDDA with an attack and is now LIDDA's enemy"
    assert (said[0].page, said[0].rule, said[0].ruling) == ("181", "GLOSS.enemy#2", "R-45")


def test_a_foe_already_fighting_you_isnt_announced_again(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[2]")
    C.attack(game, gob, lidda, attack_name="scimitar")
    assert game.is_enemy(lidda, gob) and game.log.of_kind("enemy") == []


def test_a_friendly_npc_fighting_on_the_other_side_is_an_enemy_and_no_ally(game):
    lidda = pc(game, "LIDDA", (0, 0))
    turncoat = mon(game, "guard", (5, 0))
    turncoat.attitude = "friendly"
    assert game.is_enemy(lidda, turncoat) and not game.is_ally(lidda, turncoat)
    turncoat.team = "neutral"
    assert game.is_ally(lidda, turncoat)


def test_a_spell_aimed_at_a_creature_is_working_to_harm_it(game):
    jozan = pc(game, "JOZAN", (0, 0))
    w = bystander(game, pos=(30, 0))
    S.cast(game, jozan, "sacred flame", [w])
    assert game.is_enemy(w, jozan) and not game.is_enemy(jozan, w)
    said = game.log.last("enemy")
    assert said.text == "JOZAN works to harm WATCHMAN with Sacred Flame and is now WATCHMAN's enemy"
    assert said.ruling == "R-45"


@pytest.mark.parametrize(
    ("act", "what"),
    [
        (lambda game, w, lidda: C.grapple(game, w, lidda), "grapple"),
        (lambda game, w, lidda: C.shove(game, w, lidda), "shove"),
    ],
)
def test_grappling_or_shoving_a_creature_is_working_to_harm_it(game, act, what):
    lidda = pc(game, "LIDDA", (0, 0))
    w = bystander(game)
    act(game, w, lidda)
    assert game.is_enemy(lidda, w)
    assert game.log.last("enemy").text == f"WATCHMAN works to harm LIDDA with {what} and is now LIDDA's enemy"


def test_divine_spark_that_harms_is_working_to_harm_but_one_that_heals_isnt(game):
    jozan = pc(game, "JOZAN", (0, 0))
    jozan.award_xp(300)  # level 2: Channel Divinity
    w = bystander(game, pos=(10, 0))
    lidda = pc(game, "LIDDA", (5, 0))
    CA.divine_spark(game, jozan, lidda, mode="heal")
    assert not game.is_enemy(lidda, jozan)
    CA.divine_spark(game, jozan, w, mode="harm")
    assert game.is_enemy(w, jozan)


def test_a_spell_that_only_deals_damage_is_working_to_harm_its_target(game):
    mialee = pc(game, "MIALEE", (0, 0))
    w = bystander(game, pos=(30, 0))
    S.cast(game, mialee, "magic missile", [w])
    assert game.is_enemy(w, mialee)


def test_a_bystander_who_catches_you_in_an_area_spell_is_your_enemy(game):
    lidda = pc(game, "LIDDA", (5, 0))
    mage = pc(game, "MIALEE", (0, 0))
    mage.team = "neutral"  # a spellcaster who isn't on the party's side
    game.party.remove(mage.id)
    S.cast(game, mage, "thunderwave", [lidda])
    assert game.is_enemy(lidda, mage)
    said = game.log.last("enemy")
    assert said.text == "MIALEE works to harm LIDDA with Thunderwave and is now LIDDA's enemy"
    assert said.ruling == "R-52"


def test_catching_a_companion_in_an_area_spell_doesnt_make_you_its_enemy(game):
    mialee = pc(game, "MIALEE", (0, 0))
    lidda = pc(game, "LIDDA", (5, 0))
    gob = mon(game, "goblin warrior", (5, 5))
    S.cast(game, mialee, "thunderwave", [lidda])
    assert not game.is_enemy(lidda, mialee) and game.is_ally(lidda, mialee)  # R-52: her ally
    assert game.is_enemy(gob, mialee)  # the goblin she caught too


def test_creatures_on_no_side_are_not_each_others_allies(game):
    w = bystander(game)
    porter = bystander(game, pos=(10, 0))
    assert not game.is_ally(w, porter) and not game.is_ally(porter, w)
    assert game.allies_of(w) == []


def test_a_bystanders_area_spell_harms_another_bystander_it_catches(game):
    mage = pc(game, "MIALEE", (0, 0))
    mage.team = "neutral"
    game.party.remove(mage.id)
    porter = bystander(game, pos=(5, 0))
    S.cast(game, mage, "thunderwave", [porter])
    assert game.is_enemy(porter, mage)  # R-52: not the caster's ally, so it's harmed


def test_harm_lasts_until_the_combat_ends(game):
    lidda = pc(game, "LIDDA", (0, 0))
    w = bystander(game)
    game.works_to_harm(w, lidda, "an attack")
    C.roll_initiative(game, [lidda, w])
    assert game.is_enemy(lidda, w)
    C.end_combat(game)
    assert not game.is_enemy(lidda, w) and w.harming == set()


def test_in_a_combat_the_harmed_and_the_harmers_side_fight_each_other(game):
    lidda, brom = pc(game, "LIDDA", (0, 0)), pc(game, "BROM", (10, 0))
    w = bystander(game)
    game.works_to_harm(brom, w, "an attack")
    assert game.is_enemy(w, brom) and not game.is_enemy(w, lidda)  # outside a combat: BROM only
    C.roll_initiative(game, [lidda, brom, w])
    assert game.is_enemy(w, lidda) and game.is_enemy(lidda, w)  # R-54: both ways, the whole side
    assert game.is_ally(lidda, brom)  # the party's own alliance is untouched


def test_harming_a_creature_on_your_own_side_doesnt_turn_the_rest_of_it(game):
    lidda, brom, mialee = pc(game, "LIDDA", (0, 0)), pc(game, "BROM", (10, 0)), pc(game, "MIALEE", (5, 5))
    C.roll_initiative(game, [lidda, brom, mialee])
    game.works_to_harm(mialee, lidda, "an attack")
    assert game.is_enemy(lidda, mialee)  # the one who harmed her
    assert not game.is_enemy(lidda, brom) and game.is_ally(lidda, brom)
