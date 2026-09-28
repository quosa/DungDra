"""DMG, COND, REST, CLS-FTR-01, ORIG-02/03, EQP-05 (non-spell parts)."""
import pytest

from dungdra import Refusal
from dungdra import actions, combat as C, class_actions as CA, damage as D, rest as R, hazards as H
from dungdra.effects import Condition
from tests.helpers import pc, mon
from tests.test_combat import start, set_turn


# ---------------- DMG-01 ----------------
def test_dmg01a_drop_to_zero(game):
    m = pc(game, "MIALEE")
    m.take_damage(11, "slashing")
    assert m.hp == 0 and not m.dead and m.has("unconscious")


def test_dmg01b_death_saves_nat20(game):
    m = pc(game, "MIALEE")
    m.take_damage(8, "slashing")
    game.dice.force_str("d20=[12,3,20]")
    D.death_save(game, m); D.death_save(game, m)
    assert m.death_saves == {"success": 1, "failure": 1}
    D.death_save(game, m)
    assert m.hp == 1 and m.death_saves == {"success": 0, "failure": 0} and not m.has("unconscious")
    assert m.has("prone")


def test_dmg01c_death(game):
    m = pc(game, "MIALEE")
    m.take_damage(8, "slashing")
    game.dice.force_str("d20=[1,15,4]")
    D.death_save(game, m)
    assert m.death_saves["failure"] == 2
    D.death_save(game, m)
    assert m.death_saves["success"] == 1
    D.death_save(game, m)
    assert m.dead


def test_dmg01d_hit_at_zero_is_crit(game):
    m = pc(game, "MIALEE", (0, 0))
    m.take_damage(8, "slashing")
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[10,3]; d6=[1,1]; d4=[1,1]")
    r = C.attack(game, gob, m, attack_name="scimitar")
    assert r.crit and m.death_saves["failure"] == 2


def test_dmg01e_massive_damage(game):
    m = pc(game, "MIALEE")
    m.take_damage(16, "slashing")
    assert m.dead


def test_dmg01f_help_stabilize(game):
    m, j = pc(game, "MIALEE"), pc(game, "JOZAN", (5, 0))
    m.take_damage(8, "slashing")
    game.dice.force_str("d20=[5]; d4=[2]")
    r = D.first_aid(game, j, m)
    assert r.total == 10 and m.stable and m.hp == 0
    game.advance(2 * 3600)
    assert m.hp == 1


def test_dmg01h_knock_out(game):
    b = pc(game, "BROM")
    bandit = mon(game, "bandit")
    bandit.hp = 3
    game.answer("knock_out", True)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[15]; d8=[5]")
    C.attack(game, b, bandit, weapon="longsword")
    assert bandit.hp == 1 and bandit.has("unconscious") and not bandit.dead
    j = pc(game, "JOZAN", (5, 5))
    bandit.position = (5, 0)
    game.dice.force_str("d20=[10]")
    D.first_aid(game, j, bandit)
    assert not bandit.has("unconscious")


def test_dmg01_death_saves_at_turn_start(game):
    m = pc(game, "MIALEE")
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[20, 1]")
    start(game, m, gob)
    m.take_damage(8, "slashing")
    C.end_turn(game)
    game.dice.force_str("d20=[15]")
    C.end_turn(game)
    assert m.death_saves["success"] == 1


def test_eqp05_healers_kit(game):
    m, b = pc(game, "MIALEE"), pc(game, "BROM", (5, 0))
    m.take_damage(8, "slashing")
    D.healers_kit(game, b, m)
    assert m.stable and b.inventory.find("healer's kit").props["uses"] == 9
    assert not game.log.of_kind("check")


# ---------------- DMG-02 ----------------
def test_dmg02(game):
    j = pc(game, "JOZAN")
    sk = mon(game, "skeleton")
    game.dice.force_str("d20=[15]; d6=[4]")
    r = C.attack(game, j, sk, weapon="mace")
    assert r.damage == 12
    sk2 = mon(game, "skeleton", name="S2")
    assert sk2.take_damage(10, "poison") == 0
    from dungdra.creature import Creature
    x = game.add(Creature("Thing", max_hp=100))
    x.resist.add("all"); x.vuln.add("fire")
    assert x.take_damage(28, "fire", reduction=5) == 22
    y = game.add(Creature("Resister", max_hp=100))
    y.resist.add("fire"); y.resist.add("all")
    assert y.take_damage(12, "fire") == 6
    assert y.take_damage(1, "fire", reduction=5) == 0


# ---------------- DMG-03 ----------------
def test_dmg03_temp_hp(game):
    b = pc(game, "BROM")
    b.gain_temp_hp(5)
    game.answer("temp_hp", True)
    b.gain_temp_hp(12)
    assert b.temp_hp == 12
    b.take_damage(15, "slashing")
    assert b.temp_hp == 0 and b.hp == 10
    b.hp = 7
    assert b.heal(8) == 6 and b.hp == 13
    m = pc(game, "MIALEE")
    m.take_damage(8, "slashing")
    m.gain_temp_hp(5)
    assert m.has("unconscious")
    b.gain_temp_hp(4)
    R.long_rest(game, [b])
    assert b.temp_hp == 0


# ---------------- COND ----------------
@pytest.mark.parametrize("cond", ["incapacitated", "paralyzed", "stunned", "unconscious", "petrified"])
def test_cond01_incapacitating(game, cond):
    j = pc(game, "JOZAN")
    j.concentrating = "Bless"
    gob = mon(game, "goblin warrior", (5, 0))
    j.add_condition(cond, "test")
    assert not j.can_act() and j.concentrating is None
    game.dice.force_str("d20=[1]")
    start(game, j, gob)
    set_turn(game, j)
    with pytest.raises(Refusal):
        game.combat.spend(j, "bonus")
    with pytest.raises(Refusal):
        game.combat.spend(j, "reaction")
    if cond != "incapacitated":
        assert j.save("str", 1).success is False and j.save("dex", 1).success is False
        set_turn(game, gob)
        game.dice.force_str("d20=[5,15]")
        r = C.attack(game, gob, j, attack_name="scimitar")
        assert r.roll.mode == "advantage"
        if cond in ("paralyzed", "unconscious"):
            assert r.crit
    if cond == "unconscious":
        assert j.has("prone") and j.speed() == 0
        j.remove_condition("unconscious")
    if cond == "petrified":
        assert j.take_damage(10, "slashing") == 5
        assert j.add_condition("poisoned") is None


def test_cond01_initiative_disadvantage(game):
    b = pc(game, "BROM")
    b.add_condition("incapacitated")
    game.dice.force_str("d20=[15,4]")
    assert C.initiative_roll(game, b).mode == "disadvantage"


def test_cond02(game):
    b = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.add_condition("restrained")
    assert gob.speed() == 0
    game.dice.force_str("d20=[5,5]")
    assert C.attack(game, gob, b, attack_name="scimitar").roll.mode == "disadvantage"
    game.dice.force_str("d20=[5,5]")
    assert gob.save("dex", 10).mode == "disadvantage"
    gob.remove_condition("restrained")
    gob.add_condition("prone")
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[5,5]")
    assert C.attack(game, b, gob, weapon="longsword").roll.mode == "advantage"
    l = pc(game, "LIDDA", (40, 0))
    game.dice.force_str("d20=[5,5]")
    assert C.attack(game, l, gob, weapon="shortbow").roll.mode == "disadvantage"
    b2 = pc(game, "BROM", (0, 20))
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, gob, b, b2)
    set_turn(game, gob)
    assert C.stand_up(game, gob) == 15 and game.combat.turn.movement_left == 15
    gob.add_condition("prone"); gob.add_condition("grappled", grappler=b.id)
    with pytest.raises(Refusal):
        C.stand_up(game, gob)
    # Frightened
    b2.add_condition("frightened", caster=gob)
    game.dice.force_str("d20=[5,5]")
    assert b2.check("athletics").mode == "disadvantage"
    set_turn(game, b2)
    with pytest.raises(Refusal, match="Frightened"):
        C.move(game, b2, to=(0, 10))


def test_cond03(game):
    b = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    b.add_condition("blinded")
    assert b.check("perception").success is False
    game.dice.force_str("d20=[5,5]")
    assert C.attack(game, gob, b, attack_name="scimitar").roll.mode == "advantage"
    b.remove_condition("blinded")
    b.add_condition("deafened")
    assert b.check("perception", tags={"hearing"}).success is False
    b.remove_condition("deafened")
    gob.add_condition("invisible")
    game.dice.force_str("d20=[5,5]")
    assert C.initiative_roll(game, gob).mode == "advantage"
    game.dice.force_str("d20=[5,5]")
    assert C.attack(game, gob, b, attack_name="scimitar").roll.mode == "advantage"
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[5,5]")
    assert C.attack(game, b, gob, weapon="longsword").roll.mode == "disadvantage"
    gob.remove_condition("invisible")
    b.add_condition("charmed", caster=gob)
    with pytest.raises(Refusal, match="Charmed"):
        C.attack(game, b, gob, weapon="longsword")
    game.dice.force_str("d20=[5,5]")
    assert gob.check("persuasion", target=b, tags={"social"}).mode == "advantage"
    b.remove_condition("charmed")
    b.add_condition("poisoned"); b.add_condition("poisoned")
    game.dice.force_str("d20=[5,5]")
    assert b.check("athletics").mode == "disadvantage"
    assert sorted(b.conditions()).count("poisoned") == 1


# ---------------- REST-01 / REST-02 ----------------
def test_rest01(game):
    b = pc(game, "BROM")
    b.award_xp(300)
    b.hp = 5
    game.dice.force_str("d10=[6,2]")
    t0 = game.clock
    R.short_rest(game, [b])
    assert b.hp == 17 and game.clock - t0 == 3600 and b.hit_dice_left() == 0
    b.hp = 5
    R.begin_rest(game, "short", [b])
    game.dice.force_str("d20=[10]")
    gob = mon(game, "goblin warrior", (30, 0))
    C.roll_initiative(game, [b, gob])
    C.end_combat(game)
    assert R.finish_short_rest(game, [b]) is False
    b.hp = 0
    with pytest.raises(Refusal, match="1 Hit Point"):
        R.short_rest(game, [b])


def test_rest02(game):
    b, m = pc(game, "BROM"), pc(game, "MIALEE")
    b.award_xp(300)
    b.hit_dice_spent = 2
    b.hp = 3
    b.max_hp_reduction = 4
    b.gain_exhaustion(1)
    b.spend("second wind"); b.spend("action surge")
    R.long_rest(game, [b])
    assert b.hp == b.max_hp == 22 and b.hit_dice_left() == 2 and b.exhaustion == 0
    assert b.resource_left("second wind") == 2 and b.resource_left("action surge") == 1
    game.advance(10 * 3600)
    with pytest.raises(Refusal, match="16 hours"):
        R.long_rest(game, [b])
    game.advance(6 * 3600)
    b.hp = 10
    game.dice.force_str("d10=[5]")
    t0 = game.clock
    R.long_rest(game, [b], interrupt_after_hours=3)
    assert game.clock - t0 == (8 + 1) * 3600
    assert any("Short Rest benefits" in e.text for e in game.log.of_kind("rest"))
    game.advance(16 * 3600)
    t0 = game.clock
    m.slots_used = {1: 2}
    m.free_casts["thunderwave"]["available"] = False
    R.long_rest(game, [m])
    assert game.clock - t0 == 4 * 3600
    assert m.slots_left(1) == 2 and m.free_casts["thunderwave"]["available"]


# ---------------- CLS-FTR-01 ----------------
def test_cls_ftr01(game):
    b = pc(game, "BROM")
    b.award_xp(300)
    b.hp = 5
    gob = mon(game, "ogre", (5, 0))
    game.dice.force_str("d20=[20, 1]")
    start(game, b, gob)
    set_turn(game, b)
    game.dice.force_str("d10=[7]")
    CA.second_wind(game, b)
    assert b.hp == 14 and game.combat.turn.action_available()
    assert b.resources["second wind"]["max"] == 2
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[15]; d8=[2]")
    C.attack(game, b, gob, weapon="longsword")
    CA.action_surge(game, b)
    game.dice.force_str("d20=[15]; d8=[2]")
    C.attack(game, b, gob, weapon="longsword")
    with pytest.raises(Refusal):
        CA.action_surge(game, b)
    set_turn(game, b)
    b.resources["action surge"]["used"] = 0
    CA.action_surge(game, b)
    game.combat.spend(b, "action", "Attack")
    with pytest.raises(Refusal, match="Magic"):
        game.combat.spend(b, "action", "Magic")
    C.end_combat(game)
    game.dice.force_str("d20=[9]")
    r = b.check("athletics", dc=17)
    assert not r.success
    game.dice.force_str("d10=[2]")
    CA.tactical_mind(game, b, r)
    assert b.resource_left("second wind") == 1
    game.dice.force_str("d10=[6]")
    CA.tactical_mind(game, b, r)
    assert r.success and b.resource_left("second wind") == 0
    b.resources["action surge"]["used"] = 1
    game.dice.force_str("d10=[1,1]")
    R.short_rest(game, [b], hit_dice={b.id: 0})
    assert b.resource_left("second wind") == 1 and b.resource_left("action surge") == 1


# ---------------- ORIG-02 ----------------
def test_orig02a_serpent_venom(game):
    b = pc(game, "BROM")
    game.dice.force_str("d20=[5]; d6=[4,4,4]")
    H.expose(game, b, "serpent venom")
    assert b.hp == 13 - 6
    assert game.dice.pending("d20") == 0


def test_orig02b_poisoned_needle(game):
    from dungdra import traps
    b = pc(game, "BROM")
    t = traps.place(game, "poisoned needle")
    game.dice.force_str("d20=[3,15]; d10=[8]")
    traps.trigger(game, b, t)
    assert b.hp == 13 - 2 and not b.has("poisoned")


# ---------------- ORIG-03 ----------------
def test_orig03_human_inspiration(game):
    j, l = pc(game, "JOZAN"), pc(game, "LIDDA")
    R.long_rest(game, [j])
    assert j.heroic_inspiration
    l.heroic_inspiration = True
    R.grant_heroic_inspiration(game, j)
    assert "lost" in game.log.last("inspiration").text
    gob = mon(game, "ogre", (5, 0))
    game.answer("inspiration", None)
    game.answer("inspiration_damage", 0)
    game.dice.force_str("d20=[15]; d6=[1,5]")
    r = C.attack(game, j, gob, weapon="mace")
    assert r.damage == 5 + 2 and not j.heroic_inspiration
