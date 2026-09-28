"""SPL, SPELLS, CLS-CLR, CLS-WIZ, FEAT-03."""
import pytest

from dungdra import Refusal, OutOfScope
from dungdra import combat as C, class_actions as CA, rest as R, spells as S, magic_items as MI
from dungdra.creation import prepare_spells
from tests.helpers import pc, mon
from tests.test_combat import start, set_turn


# ---------------- SPL-01 ----------------
def test_spl01_slots(game):
    m = pc(game, "MIALEE")
    gob = mon(game, "goblin warrior", (30, 0))
    gob.base_max_hp = gob.hp = 500
    for _ in range(3):
        game.dice.force_str("d20=[2]")
        S.cast(game, m, "fire bolt", gob)
    S.cast(game, m, "magic missile", gob)
    S.cast(game, m, "magic missile", gob)
    assert m.slots_left(1) == 0
    with pytest.raises(Refusal, match="no level 1"):
        S.cast(game, m, "magic missile", gob)
    R.long_rest(game, [m])
    assert m.slots_left(1) == 2


def test_spl01_upcast(game):
    m = pc(game, "MIALEE")
    m.award_xp(900)
    gob = mon(game, "ogre", (30, 0))
    game.dice.force_str("d4=[1,1,1,1]")
    S.cast(game, m, "magic missile", gob, slot=2)
    assert gob.hp == 68 - 8 and m.slots_left(2) == 1


def test_spl01_one_slot_per_turn(game):
    j = pc(game, "JOZAN")
    m = pc(game, "MIALEE", (5, 0))
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, j, m, gob)
    set_turn(game, j)
    S.cast(game, j, "healing word", m)
    with pytest.raises(Refusal, match="one spell slot"):
        S.cast(game, j, "guiding bolt", gob)
    game.dice.force_str("d20=[5]")
    S.cast(game, j, "sacred flame", gob)             # a cantrip is fine


# ---------------- FEAT-03 ----------------
def test_feat03_magic_initiate(game):
    j = pc(game, "JOZAN")
    m = pc(game, "MIALEE", (5, 0))
    gob = mon(game, "cultist", (20, 0))
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, j, m, gob)
    set_turn(game, j)
    S.cast(game, j, "healing word", m)
    game.dice.force_str("d20=[1]")
    c = S.cast(game, j, "command", gob, free=True, option="halt")
    assert c.dc == 13 and c.slot is None
    set_turn(game, j)
    with pytest.raises(Refusal, match="Long Rest"):
        S.cast(game, j, "command", gob, free=True)
    game.dice.force_str("d20=[1]")
    c = S.cast(game, j, "command", gob, option="halt")
    assert c.slot == 1 and c.dc == 13
    C.end_combat(game)
    R.long_rest(game, [j])
    assert j.free_casts["command"]["available"]
    assert m.castable("thunderwave")[0]["ability"] == "int" and m.spell_dc("int") == 13


# ---------------- SPL-02 · Concentration ----------------
def test_spl02_concentration(game):
    j = pc(game, "JOZAN")
    j.base_max_hp = j.hp = 40
    b = pc(game, "BROM", (5, 0))
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[9]")
    j.take_damage(22, "slashing")
    assert j.concentrating is None and not b.find_effects("Bless")
    R.long_rest(game, [j])
    S.cast(game, j, "bless", [b])
    game.dice.force_str("d20=[9]")
    j.take_damage(7, "slashing")
    assert "DC 10" in game.log.last("save").text and j.concentrating == "Bless"
    j.prepared.append("shield of faith")
    S.cast(game, j, "shield of faith", b)
    assert not b.find_effects("Bless") and j.concentrating == "Shield Of Faith"
    j.add_condition("incapacitated")
    assert j.concentrating is None and b.ac() == 19
    j.remove_condition("incapacitated")
    j.base_max_hp = j.hp = 200
    j.concentrating = "x"
    game.dice.force_str("d20=[20]")
    j.take_damage(100, "slashing")
    assert "DC 30" in game.log.last("save").text


def test_spl02_bless_duration(game):
    j = pc(game, "JOZAN")
    gob = mon(game, "goblin warrior", (60, 0))
    game.dice.force_str("d20=[20, 1]")
    start(game, j, gob)
    set_turn(game, j)
    S.cast(game, j, "bless", [j])
    for _ in range(19):
        C.end_turn(game)
    assert j.find_effects("Bless")                    # still round 10
    C.end_turn(game)
    assert not j.find_effects("Bless")               # start of round 11: 10 rounds elapsed


# ---------------- SPL-03 · Rituals ----------------
def test_spl03_rituals(game):
    j, m = pc(game, "JOZAN"), pc(game, "MIALEE")
    with pytest.raises(Refusal, match="prepared"):
        S.cast(game, j, "detect magic", ritual=True)
    j.prepared.append("detect magic")
    t0 = game.clock
    S.cast(game, j, "detect magic", ritual=True)
    assert game.clock - t0 >= 600 and j.slots_left(1) == 2
    m.slots_used = {1: 2}
    S.cast(game, m, "detect magic", ritual=True)      # from the spellbook, unprepared, no slots left
    with pytest.raises(Refusal, match="higher level"):
        S.cast(game, j, "detect magic", ritual=True, slot=2)
    gob = mon(game, "goblin warrior", (60, 0))
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, j, gob, m)
    with pytest.raises(Refusal, match="Ritual"):
        S.cast(game, j, "detect magic", ritual=True)


# ---------------- SPL-04 · Components ----------------
def test_spl04_components(game):
    m, j = pc(game, "MIALEE"), pc(game, "JOZAN")
    gob = mon(game, "goblin warrior", (10, 0))
    m.notes["gagged"] = True
    with pytest.raises(Refusal, match="Verbal"):
        S.cast(game, m, "magic missile", gob)
    m.notes.pop("gagged")
    m.prepared.append("burning hands")
    m.notes["hands_full"] = True
    m.wielded = [m.inventory.find("dagger"), m.inventory.find("quarterstaff")]
    with pytest.raises(Refusal, match="free hand"):
        S.cast(game, m, "burning hands", [gob])
    m.wielded = []
    m.notes.pop("hands_full")
    m.inventory.add("component pouch")
    game.dice.force_str("d20=[20]")
    S.cast(game, m, "sleep", [gob])
    S.cast(game, j, "bless", [j])
    for it in list(j.inventory):
        if it.name == "holy symbol":
            j.inventory.remove(it, it.qty)
    game.advance(8 * 3600)
    with pytest.raises(Refusal, match="Holy Symbol"):
        S.cast(game, j, "bless", [j])
    m.inventory.add("leather armor")
    m.armor = m.inventory.find("leather armor")
    with pytest.raises(Refusal, match="training"):
        S.cast(game, m, "fire bolt", gob)
    m.armor = None
    game.scene.silence = True
    with pytest.raises(Refusal, match="Silence"):
        S.cast(game, m, "fire bolt", gob)


# ---------------- SPL-05 · Areas ----------------
def test_spl05_burning_hands(game):
    m = pc(game, "MIALEE", (0, 0))
    m.prepared.append("burning hands")
    g1 = mon(game, "goblin warrior", (5, 0), name="G1")
    g2 = mon(game, "goblin warrior", (10, 0), name="G2")
    g3 = mon(game, "goblin warrior", (15, 0), name="G3")
    game.scene.cover_all[g3.id] = "total"
    game.scene.objects["dry hay"] = {"flammable": True, "in_cone": True}
    game.dice.force_str("d6=[3,4,5]; d20=[12]; d20=[9]")
    S.cast(game, m, "burning hands", [m, g1, g2, g3])
    assert g1.hp == 10 - 6 and g2.dead and g3.hp == 10
    assert game.scene.objects["dry hay"]["burning"]
    assert len([e for e in game.log.of_kind("save")]) == 2


# ---------------- SPL-06 · Targeting ----------------
def test_spl06_targeting(game):
    j = pc(game, "JOZAN")
    j.award_xp(900)
    j.prepared.append("hold person")
    wolf = mon(game, "wolf", (20, 0))
    n = len(game.dice.history)
    S.cast(game, j, "hold person", wolf)
    assert j.slots_left(2) == 1 and not wolf.has("paralyzed")
    assert "succeeds" in game.log.last("save").text and game.log.last("invalid_target").visibility == "gm"
    b = pc(game, "BROM", (5, 0))
    j2 = pc(game, "JOZAN", (5, 5))
    S.cast(game, j, "bless", [b])
    S.cast(game, j2, "bless", [b])
    game.dice.force_str("d20=[10]; d4=[2,3]")
    r = b.save("wis", 10)
    assert sum(1 for _, s in r.mods if "Bless" in s) == 1
    game.scene.cover_all[wolf.id] = "total"
    with pytest.raises(Refusal, match="Total Cover"):
        S.cast(game, j, "guiding bolt", wolf)


# ---------------- SPELLS-01 ----------------
def test_spells01_mm_vs_shield(game):
    m = pc(game, "MIALEE", (0, 0))
    enemy = pc(game, "MIALEE", (30, 0))
    enemy.team = "enemy"
    game.answer("shield", True, who=m)
    S.cast(game, enemy, "magic missile", m)
    assert m.hp == 8 and m.find_effects(cls=S.ShieldSpell)
    game.combat = None
    m.effects = [e for e in m.effects if not isinstance(e, S.ShieldSpell)]
    boss = mon(game, "goblin boss", (5, 0))
    game.dice.force_str("d20=[20, 1]")
    start(game, boss, m)
    game.combat.reaction_used.discard(m.id)
    set_turn(game, boss)
    game.answer("shield", True, who=m)
    game.dice.force_str("d20=[8]")
    r = C.attack(game, boss, m, attack_name="scimitar")
    assert r.roll.total == 12 and not r.hit and m.ac() == 16
    set_turn(game, m)
    assert m.ac() == 11
    m2 = mon(game, "ogre", (40, 0), name="Target")
    m.slots_used = {}
    game.dice.force_str("d4=[1,2,3]")
    S.cast(game, m, "magic missile", m2)
    assert m2.hp == 68 - (2 + 3 + 4)


# ---------------- SPELLS-02 · Sleep ----------------
def test_spells02_sleep(game):
    m = pc(game, "MIALEE", (0, 0))
    a = mon(game, "goblin warrior", (30, 0), name="A")
    b = mon(game, "goblin warrior", (30, 5), name="B")
    sk = mon(game, "skeleton", (35, 0))
    from dungdra.monster import Monster
    elf = game.add(Monster("guard", name="Elf Guard"), team="enemy", position=(35, 5))
    elf.traits.add("trance")
    game.dice.force_str("d20=[20, 1, 1, 1]")
    start(game, m, a, b, sk, elf)
    set_turn(game, m)
    game.dice.force_str("d20=[10]; d20=[14]")
    S.cast(game, m, "sleep", [a, b, sk, elf])
    assert a.has("incapacitated") and not a.has("unconscious") and not b.has("incapacitated")
    assert not sk.has("incapacitated") and not elf.has("incapacitated")
    set_turn(game, a)
    game.dice.force_str("d20=[6]")
    C._expire(game, "end", a)
    for e in list(a.effects):
        e.on_turn_end(game)
    assert a.has("unconscious")
    a.take_damage(1, "slashing")
    assert not a.has("unconscious") and a.has("prone")


# ---------------- SPELLS-03 · Healing ----------------
def test_spells03_healing(game):
    j = pc(game, "JOZAN", (0, 0))
    b = pc(game, "BROM", (5, 0))
    m = pc(game, "MIALEE", (50, 0))
    b.hp = 2
    game.dice.force_str("d8=[5,4]")
    S.cast(game, j, "cure wounds", b)
    assert b.hp == 13
    m.take_damage(8, "slashing")
    m.death_saves["failure"] = 1
    game.dice.force_str("d4=[2,3]")
    S.cast(game, j, "healing word", m)
    assert m.hp == 8 and m.death_saves == {"success": 0, "failure": 0} and not m.has("unconscious")
    m.position = (70, 0)
    R.long_rest(game, [j])
    with pytest.raises(Refusal, match="range"):
        S.cast(game, j, "healing word", m)
    z = mon(game, "zombie", (5, 5))
    z.hp = 1
    game.dice.force_str("d8=[1,1]")
    S.cast(game, j, "cure wounds", z)
    assert z.hp == 6


def test_spells03_aid(game):
    j = pc(game, "JOZAN")
    j.award_xp(900)
    allies = [pc(game, n, (5, 0)) for n in ("BROM", "LIDDA", "MIALEE")]
    S.cast(game, j, "aid", allies)
    assert allies[0].max_hp == 13 + 5 and allies[0].hp == 18
    game.advance(8 * 3600)
    assert allies[0].max_hp == 13 and allies[0].hp == 13


# ---------------- SPELLS-04 ----------------
def test_spells04(game):
    j = pc(game, "JOZAN")
    j.award_xp(900)
    j.prepared.append("hold person")
    b = pc(game, "BROM", (0, 5))
    bandit = mon(game, "bandit", (5, 5))
    bandit.base_max_hp = bandit.hp = 100
    game.dice.force_str("d20=[20, 15, 1]")
    start(game, j, b, bandit)
    set_turn(game, j)
    game.dice.force_str("d20=[7]")
    S.cast(game, j, "hold person", bandit)
    assert bandit.has("paralyzed")
    set_turn(game, b)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[3,12]; d8=[1,1]")
    r = C.attack(game, b, bandit, weapon="longsword")
    assert r.roll.mode == "advantage" and r.crit
    set_turn(game, bandit)
    game.dice.force_str("d20=[15]")
    for e in list(bandit.effects):
        e.on_turn_end(game)
    assert not bandit.has("paralyzed")
    cult = mon(game, "cultist", (20, 0))
    game.dice.force_str("d20=[8]")
    set_turn(game, j)
    S.cast(game, j, "command", cult, free=True, option="grovel")
    assert "DC 13" in game.log.last("save").text and "= 10" in game.log.last("save").text
    game.combat.order.append((cult.id, 1))
    set_turn(game, cult)
    assert cult.has("prone") and not game.combat.turn.action_available()


def test_spells04_sanctuary(game):
    j = pc(game, "JOZAN", (0, 0))
    j.prepared.append("sanctuary")
    m = pc(game, "MIALEE", (5, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    S.cast(game, j, "sanctuary", m)
    game.answer("sanctuary_retarget", None)
    game.dice.force_str("d20=[11]")
    r = C.attack(game, gob, m, attack_name="scimitar")
    assert r.roll is None and m.hp == 8
    game.dice.force_str("d20=[2]")
    S.cast(game, m, "fire bolt", gob)
    assert not m.find_effects("Sanctuary")


# ---------------- SPELLS-05 ----------------
def test_spells05_cantrips(game):
    m = pc(game, "MIALEE", (0, 0))
    j = pc(game, "JOZAN", (0, 5))
    assert S.cantrip_dice(m) == 1
    m.level = 5
    assert S.cantrip_dice(m) == 2
    m.level = 1
    game.scene.objects["wooden crate"] = {"flammable": True}
    S.cast(game, m, "fire bolt", "wooden crate")
    assert game.scene.objects["wooden crate"]["burning"]
    gob = mon(game, "goblin warrior", (30, 0))
    game.scene.cover_all[gob.id] = "half"
    game.dice.force_str("d20=[10]; d8=[3]")
    S.cast(game, j, "sacred flame", gob)
    assert "Cover" not in game.log.last("save").text
    game.dice.force_str("d20=[15]; d8=[3]")
    S.cast(game, m, "ray of frost", gob)
    assert gob.speed() == 20


# ---------------- SPELLS-06 ----------------
def test_spells06(game):
    m = pc(game, "MIALEE", (0, 0))
    m.award_xp(900)
    m.prepared = ["misty step", "invisibility", "web", "scorching ray", "magic missile", "shield"]
    l = pc(game, "LIDDA", (0, 5))
    j = pc(game, "JOZAN", (5, 0))
    j.award_xp(900)
    j.prepared.append("spiritual weapon")
    gob = mon(game, "goblin warrior", (5, 5))
    gob.base_max_hp = gob.hp = 100
    game.dice.force_str("d20=[20, 15, 10, 1]")
    start(game, m, l, j, gob)
    set_turn(game, m)
    S.cast(game, m, "misty step", point=(30, 0))
    assert m.position == (30, 0) and not any("makes an Opportunity" in e.text for e in game.log.of_kind("oa"))
    m.position = (0, 0)
    set_turn(game, m)
    S.cast(game, m, "invisibility", l)
    assert l.has("invisible")
    set_turn(game, l)
    game.dice.force_str("d20=[15,5]; d6=[1,1]")
    C.attack(game, l, gob, weapon="shortsword")
    assert not l.has("invisible")
    set_turn(game, m)
    m.slots_used = {}
    game.dice.force_str("d20=[5]")
    S.cast(game, m, "web", [gob])
    assert gob.has("restrained") and m.concentrating == "Web"
    set_turn(game, gob)
    game.dice.force_str("d20=[20]")
    r = S.break_web(game, gob)
    assert r.target == 13
    gob.add_condition("restrained", "Web", web="web (MIALEE)")
    game.dice.force_str("d4=[2,3]")
    S.burn_web(game, "web (MIALEE)", [gob])
    assert not gob.has("restrained")
    set_turn(game, j)
    game.dice.force_str("d20=[15]; d8=[4]")
    hp = gob.hp
    S.cast(game, j, "spiritual weapon", gob)
    assert j.concentrating == "Spiritual Weapon" and game.combat.turn.bonus_used and hp - gob.hp == 7
    set_turn(game, m)
    m.slots_used = {}
    game.dice.force_str("d20=[15,15,2]; d6=[1,1,1,1]")
    n = len(game.log.of_kind("attack"))
    S.cast(game, m, "scorching ray", [gob, gob, gob])
    assert len(game.log.of_kind("attack")) - n == 3
    ally = pc(game, "BROM", (5, 0))
    ally.add_condition("poisoned")
    set_turn(game, j)
    j.prepared.append("lesser restoration")
    j.slots_used = {}
    S.cast(game, j, "lesser restoration", ally)
    assert not ally.has("poisoned") and game.combat.turn.bonus_used


# ---------------- CLS-CLR-01 ----------------
def test_cls_clr01(game):
    j = pc(game, "JOZAN")
    assert j.cantrip_limit() == 3 and j.prepared_limit() == 4 and j.slots_max() == {1: 2}
    j.award_xp(900)
    assert j.prepared_limit() == 6 and j.slots_max() == {1: 4, 2: 2}
    assert "martial" in j.weapon_profs and "heavy" in j.armor_training
    from dungdra.creation import CharacterBuilder
    from dungdra.fixtures import FIXTURES
    fx = dict(FIXTURES["JOZAN"], name="THAUM", divine_order="thaumaturge",
              cantrips=["sacred flame", "guidance", "spare the dying", "thaumaturgy"])
    t = CharacterBuilder(game).update(**fx).build()
    game.dice.force_str("d20=[10]")
    r = t.check("religion")
    assert ("Thaumaturge" in " ".join(s for _, s in r.mods)) and r.total == 10 + 0 + 2 + 3
    with pytest.raises(Refusal, match="Long Rest"):
        prepare_spells(j, ["bless"])
    R.long_rest(game, [j])
    prepare_spells(j, ["bless", "guiding bolt", "sanctuary", "shield of faith", "command", "healing word"])


# ---------------- CLS-CLR-02 ----------------
def test_cls_clr02(game):
    j = pc(game, "JOZAN", (0, 0))
    j.award_xp(300)
    b = pc(game, "BROM", (10, 0))
    b.hp = 3
    game.dice.force_str("d8=[5]")
    CA.divine_spark(game, j, b)
    assert b.hp == 11
    sk = mon(game, "skeleton", (20, 0))
    z = mon(game, "zombie", (25, 0))
    game.dice.force_str("d20=[6]; d20=[18]")
    CA.turn_undead(game, j, [sk, z])
    assert sk.has("frightened") and sk.has("incapacitated") and not z.has("frightened")
    game.answer("use_savage_attacker", False)
    b.position = (15, 0)
    game.dice.force_str("d20=[18]; d8=[2]")
    C.attack(game, b, sk, weapon="longsword")
    assert not sk.has("frightened")
    assert j.resource_left("channel divinity") == 0
    R.short_rest(game, [j], hit_dice={j.id: 0})
    assert j.resource_left("channel divinity") == 1
    R.long_rest(game, [j])
    assert j.resource_left("channel divinity") == 2


# ---------------- CLS-CLR-03 ----------------
def test_cls_clr03(game):
    j = pc(game, "JOZAN", (0, 0))
    j.award_xp(900)
    b = pc(game, "BROM", (5, 0))
    b.award_xp(900)
    b.hp = 10
    game.dice.force_str("d8=[5,4]")
    S.cast(game, j, "cure wounds", b)
    assert b.hp == 25
    b.hp = 1
    game.dice.force_str("d8=[1,1,1,1]")
    S.cast(game, j, "cure wounds", b, slot=2)
    assert b.hp == 1 + 4 + 3 + 4
    scroll = MI.make("spell scroll", spell="cure wounds")
    j.inventory.add(scroll)
    b.hp = 1
    game.dice.force_str("d8=[1,1]")
    S.cast(game, j, "cure wounds", b, item=scroll, scroll=True)
    assert b.hp == 1 + 2 + 3
    l = pc(game, "LIDDA", (10, 0)); l.award_xp(900)
    m = pc(game, "MIALEE", (10, 5)); m.award_xp(900)
    b.hp, l.hp, m.hp = 5, 3, 2
    res = CA.preserve_life(game, j, {"brom": 5, "lidda": 5, "mialee": 5})
    assert b.hp == 10 and l.hp == 8 and m.hp == 7
    assert set(j.always_prepared) >= {"aid", "bless", "cure wounds", "lesser restoration"}
    R.long_rest(game, [j])
    prepare_spells(j, ["guiding bolt", "healing word", "sanctuary", "shield of faith", "hold person",
                       "spiritual weapon"])
    assert len(j.prepared) == 6 and "bless" not in j.prepared and j.castable("bless")


# ---------------- CLS-WIZ-01 ----------------
def test_cls_wiz01(game):
    m = pc(game, "MIALEE")
    m.slots_used = {1: 2}
    game.answer("arcane_recovery", [1])
    R.short_rest(game, [m])
    assert m.slots_left(1) == 1
    m.slots_used = {1: 2}
    R.short_rest(game, [m])
    assert m.slots_left(1) == 0
    R.long_rest(game, [m])
    with pytest.raises(Refusal, match="4"):
        prepare_spells(m, ["magic missile", "shield", "sleep", "mage armor", "burning hands"])
    game.advance(16 * 3600)
    R.long_rest(game, [m])
    m.spellbook.remove("detect magic")
    with pytest.raises(Refusal, match="spellbook"):
        prepare_spells(m, ["magic missile", "detect magic"])
    game.advance(16 * 3600)
    m.award_xp(900)
    m.slots_used = {2: 2}
    game.answer("arcane_recovery", [2])
    R.short_rest(game, [m])
    assert m.slots_left(2) == 1
    with pytest.raises(Refusal):
        from dungdra.spellcasting import arcane_recovery
        arcane_recovery(game, m, [1, 1, 1])


# ---------------- CLS-WIZ-02 ----------------
def test_cls_wiz02(game):
    m = pc(game, "MIALEE")
    game.answer("scholar", "arcana")
    m.award_xp(900)
    assert m.skill_total("arcana") == 7
    m.prepared = [s for s in m.prepared if s != "detect magic"]
    m.always_prepared.pop("detect magic", None); m.free_casts.pop("detect magic", None)
    S.cast(game, m, "detect magic", ritual=True)
    assert m.subclass == "evoker"
    gob = mon(game, "goblin warrior", (30, 0))
    game.dice.force_str("d20=[2]; d8=[6]")
    S.cast(game, m, "ray of frost", gob)
    assert gob.hp == 7 and gob.speed() == 30


# ---------------- CLS-WIZ-03 ----------------
def test_cls_wiz03(game):
    m = pc(game, "MIALEE")
    web = MI.make("spell scroll", spell="web")
    misty = MI.make("spell scroll", spell="misty step")
    m.inventory.add(web); m.inventory.add(misty)
    with pytest.raises(Refusal, match="level"):
        MI.copy_scroll(game, m, web)
    with pytest.raises(Refusal, match="level"):
        MI.copy_scroll(game, m, misty)
    m.award_xp(900)
    m.purse.add(gp=200)
    gp0, t0 = m.purse.total_cp(), game.clock
    game.dice.force_str("d20=[10]")
    assert MI.copy_scroll(game, m, web)
    assert gp0 - m.purse.total_cp() == 10000 and game.clock - t0 == 4 * 3600 and "web" in m.spellbook
    # SRD p.244: the scroll is destroyed whether the check succeeds or fails (see docs/scenario-notes.md)
    assert m.inventory.find("spell scroll") is misty
