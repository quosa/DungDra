"""CMB: combat (p.13-16), plus FEAT-01/02, CLS-ROG-01, EQP-02/03, CMB-07."""
import pytest

from dungdra import Refusal
from dungdra import actions, combat as C, class_actions as CA, mounted
from dungdra.effects import Flag
from tests.helpers import pc, mon


def start(game, *cs, surprised=()):
    return C.roll_initiative(game, cs, surprised=surprised)


def set_turn(game, c):
    cb = game.combat
    if cb.current is not None:
        C._expire(game, "end", cb.current)
    cb.index = next(i for i, (cid, _) in enumerate(cb.order) if cid == c.id)
    C.start_turn(game)


# ---------------- CMB-01 · Surprise and Initiative ----------------
def test_cmb01_surprise(game):
    party = [pc(game, n, (i * 5, 0)) for i, n in enumerate(["BROM", "LIDDA", "MIALEE", "JOZAN"])]
    gobs = [mon(game, "goblin warrior", (40, 10 * i), name=f"Goblin {i + 1}") for i in range(4)]
    for g in gobs:
        g.add_condition("invisible", "Hide (Stealth 16)")
        g.hidden_total = 16
    surprised = [p for p in party if not any(actions.notices(game, p, g) for g in gobs)]
    assert len(surprised) == 4                     # best Passive Perception 15 < 16
    game.answer("alert_swap", None)
    game.dice.force_str("d20=[11,6, 15,4, 15,4, 15,4, 15,4]")
    cb = start(game, *gobs, *party, surprised=surprised)
    inits = dict(cb.order)
    assert all(inits[g.id] == 13 for g in gobs)
    assert inits["brom"] == 4 + 2 and inits["lidda"] == 4 + 5 and inits["mialee"] == 4 + 1 and inits["jozan"] == 4 - 1
    rolls = game.log.of_kind("initiative")
    assert any("surprised" in e.text for e in rolls) and any("Invisible" in e.text for e in rolls)
    order0 = list(cb.order)
    for _ in range(len(order0)):
        C.end_turn(game)
    assert cb.round == 2 and cb.order == order0
    assert cb.current.id == order0[0][0]          # nobody loses a turn


# ---------------- FEAT-01 · Alert ----------------
def test_feat01_alert(game):
    brom, lidda = pc(game, "BROM"), pc(game, "LIDDA", (5, 0))
    game.dice.force_str("d20=[15, 8]")
    game.answer("alert_swap", "brom")
    cb = start(game, brom, lidda)
    assert dict(cb.order) == {"brom": 13, "lidda": 17}
    lidda.add_condition("incapacitated", "test")
    with pytest.raises(Refusal):
        C.swap_initiative(game, lidda, brom)


# ---------------- CMB-02 · Turn economy ----------------
def test_cmb02_turn_economy(game):
    brom, mia = pc(game, "BROM"), pc(game, "MIALEE", (0, 50))
    gob = mon(game, "goblin warrior", (15, 0))
    game.dice.force_str("d20=[20,1,1]")
    start(game, brom, mia, gob)
    set_turn(game, brom)
    C.move(game, brom, to=(10, 0))
    game.dice.force_str("d20=[12]; d6=[3,3]")
    game.answer("use_savage_attacker", False)
    C.attack(game, brom, gob, weapon="javelin", thrown=True)
    assert any("draws the Javelin" in e.text for e in game.log.of_kind("equip"))
    C.move(game, brom, to=(10, 20))
    with pytest.raises(Refusal):
        C.move(game, brom, to=(10, 25))              # 35 ft > Speed 30
    assert C.interact(game, brom, "open the door") == "free"
    with pytest.raises(Refusal, match="action"):
        C.interact(game, brom, "pick up a Shield")  # second interaction needs Utilize; action already used
    with pytest.raises(Refusal):
        actions.dodge(game, brom)                   # a second action
    set_turn(game, mia)
    with pytest.raises(Refusal, match="no feature"):
        CA.bonus_action(game, mia, "dash")
    C.drop_prone(game, mia)
    assert game.combat.turn.movement_left == 30


def test_cmb02_one_reaction_per_round(game):
    brom = pc(game, "BROM")
    gob = mon(game, "goblin warrior", (5, 0))
    start(game, brom, gob)
    game.combat.spend(brom, "reaction")
    with pytest.raises(Refusal):
        game.combat.spend(brom, "reaction")
    set_turn(game, brom)
    game.combat.spend(brom, "reaction")             # reset at the start of his turn


# ---------------- CMB-03 extra: crits double extra dice ----------------
def test_cmb03(game):
    brom = pc(game, "BROM")
    gob = mon(game, "goblin warrior")
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10]; d8=[4]")
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.hit and r.roll.total == 15 and gob.hp == 3
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[20]; d8=[3,5]")
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.crit and r.damage == 11 and gob.dead
    gob2 = mon(game, "goblin warrior", name="G2")
    gob2.gear_ac = 1
    game.dice.force_str("d20=[1]")
    assert not C.attack(game, brom, gob2, weapon="longsword").hit


# ---------------- CMB-04 · Opportunity Attacks ----------------
def _oa_count(game):
    return len([e for e in game.log.of_kind("oa") if "makes an Opportunity Attack" in e.text])


def test_cmb04_oa(game):
    lidda = pc(game, "LIDDA", (0, 0))
    ogre = mon(game, "ogre", (5, 0))
    game.dice.force_str("d20=[20, 1]")
    start(game, lidda, ogre)
    set_turn(game, lidda)
    game.dice.force_str("d20=[2]")
    C.move(game, lidda, to=(-15, 0))                  # (a) leaves reach -> OA
    assert _oa_count(game) == 1
    lidda.position = (0, 0)
    set_turn(game, ogre)
    set_turn(game, lidda)                           # new turn: ogre's reaction reset at ogre's turn
    actions.disengage(game, lidda)
    C.move(game, lidda, to=(-15, 0))                  # (b) no OA
    assert _oa_count(game) == 1


def test_cmb04_nimble_forced_teleport_reaction(game):
    brom = pc(game, "BROM", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    ogre = mon(game, "ogre", (-5, 0))
    game.dice.force_str("d20=[20, 1, 1]")
    start(game, brom, gob, ogre)
    set_turn(game, gob)
    CA.nimble_escape(game, gob, "disengage")         # (c)
    C.move(game, gob, to=(30, 0))
    assert _oa_count(game) == 0 and game.combat.turn.action_available()
    gob.position = (5, 0)
    C.move(game, brom, to=(10, 0), forced=True)      # (d) shoved out of the ogre's reach
    assert _oa_count(game) == 0
    brom.position = (0, 0)
    C.move(game, brom, to=(30, 0), teleport=True)    # (e) Misty Step
    assert _oa_count(game) == 0
    brom.position = (0, 0)
    game.combat.reaction_used.add(brom.id)           # (f) PC already used its Reaction
    set_turn(game, gob)
    gob.effects = [e for e in gob.effects if e.name != "disengage"]
    C.move(game, gob, to=(30, 0))
    assert _oa_count(game) == 0


def test_cmb04_controlled_mount_provokes(game):
    jozan = pc(game, "JOZAN", (0, 0))
    horse = game.add(__import__("dungdra.monster", fromlist=["Monster"]).Monster("riding horse"), team="party",
                     position=(5, 0))
    gob = mon(game, "goblin warrior", (10, 0))
    game.dice.force_str("d20=[20, 5, 1]")
    start(game, jozan, horse, gob)
    set_turn(game, jozan)
    mounted.mount(game, jozan, horse)
    assert game.combat.turn.movement_left == 15      # CMB-08: mounting costs half Speed
    assert game.combat.initiative_of(horse) == game.combat.initiative_of(jozan)
    with pytest.raises(Refusal):
        mounted.mount_action(game, horse, "attack")
    game.dice.force_str("d20=[2]")
    C.move(game, horse, to=(-30, 0))                # (g) the mount leaves using its own speed
    assert _oa_count(game) == 1


# ---------------- CMB-05 · Ranged attacks and cover ----------------
def test_cmb05_ranged_cover(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (100, 0))
    gob.base_max_hp = gob.hp = 500
    game.dice.force_str("d20=[10,10]; d6=[1]")
    r = C.attack(game, lidda, gob, weapon="shortbow")
    assert r.roll.mode == "disadvantage"
    gob.position = (50, 0)
    game.scene.cover[(lidda.id, gob.id)] = "half"
    game.dice.force_str("d20=[10]")
    assert C.attack(game, lidda, gob, weapon="shortbow").roll.target == 17
    game.scene.cover[(lidda.id, gob.id)] = "three-quarters"
    game.scene.cover_all[gob.id] = "half"
    game.dice.force_str("d20=[10]")
    assert C.attack(game, lidda, gob, weapon="shortbow").roll.target == 20   # only best degree
    game.scene.cover[(lidda.id, gob.id)] = "total"
    with pytest.raises(Refusal, match="Total Cover"):
        C.attack(game, lidda, gob, weapon="shortbow")
    game.scene.cover.clear(); game.scene.cover_all.clear()
    gob.position = (400, 0)
    with pytest.raises(Refusal):
        C.attack(game, lidda, gob, weapon="shortbow")
    gob.position = (50, 0)
    adj = mon(game, "goblin warrior", (5, 0), name="Adjacent")
    game.dice.force_str("d20=[10,10]")
    assert C.attack(game, lidda, gob, weapon="shortbow").roll.mode == "disadvantage"
    adj.add_condition("incapacitated", "test")
    game.dice.force_str("d20=[10]")
    assert C.attack(game, lidda, gob, weapon="shortbow").roll.mode == "normal"


# ---------------- CMB-06 · Grapple and Shove ----------------
def test_cmb06_grapple_shove(game):
    brom = pc(game, "BROM", (0, 0))
    brom.shield = None                               # Shield hand free
    gob = mon(game, "goblin warrior", (5, 0))
    game.dice.force_str("d20=[9]")
    assert C.grapple(game, brom, gob)
    assert gob.has("grappled") and gob.speed() == 0
    save = game.log.last("save")
    assert "DC 13" in save.text and "Dexterity" in save.text
    lidda = pc(game, "LIDDA", (10, 5))
    game.dice.force_str("d20=[10,10]")
    r = C.attack(game, gob, lidda, attack_name="shortbow")
    assert any("Grappled" in s for s in r.roll.dis)
    game.dice.force_str("d20=[20]")
    start(game, brom, gob, lidda)
    set_turn(game, brom)
    cost = C.move(game, brom, to=(-10, 0), drag=gob)
    assert cost == 20
    ogre = mon(game, "ogre", (15, 5))
    lidda.position = (10, 5)
    with pytest.raises(Refusal, match="size"):
        C.grapple(game, lidda, ogre)
    bandit = mon(game, "bandit", (-10, 5))
    game.dice.force_str("d20=[2]")
    game.combat.turn.actions += 1
    assert C.shove(game, brom, bandit, "prone") and bandit.has("prone")
    set_turn(game, gob)
    game.dice.force_str("d20=[14]")
    r = C.escape_grapple(game, gob)
    assert r.total == 16 and not gob.has("grappled")
    game.dice.force_str("d20=[1]")
    set_turn(game, brom)
    game.combat.turn.actions += 1
    brom.position = (0, 0); gob.position = (5, 0)
    game.dice.force_str("d20=[1]")
    C.grapple(game, brom, gob)
    brom.add_condition("incapacitated", "test")
    assert not gob.has("grappled")


# ---------------- CMB-07 · Light-weapon extra attack ----------------
def test_cmb07_light_extra(game):
    lidda = pc(game, "LIDDA", (0, 0))
    lidda.weapon_masteries = []                      # no Nick/Vex for this test
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 100
    game.dice.force_str("d20=[20, 1]")
    start(game, lidda, gob)
    set_turn(game, lidda)
    game.dice.force_str("d20=[15]; d6=[4]")
    C.attack(game, lidda, gob, weapon="shortsword")
    game.dice.force_str("d20=[15]; d4=[3]")
    r = C.attack(game, lidda, gob, weapon="dagger", light_extra=True)
    assert r.damage == 3 and game.combat.turn.bonus_used
    lidda.inventory.add("rapier")
    set_turn(game, lidda)
    game.dice.force_str("d20=[15]; d6=[4]")
    C.attack(game, lidda, gob, weapon="shortsword")
    with pytest.raises(Refusal):
        C.attack(game, lidda, gob, weapon="rapier", light_extra=True)
    lidda.fighting_style = "two-weapon fighting"
    game.dice.force_str("d20=[15]; d4=[3]")
    assert C.attack(game, lidda, gob, weapon="dagger", light_extra=True).damage == 6


# ---------------- CMB-08 · Underwater ----------------
def test_cmb08_underwater(game):
    brom = pc(game, "BROM", (0, 0))
    lidda = pc(game, "LIDDA", (0, 5))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 500
    game.scene.underwater = True
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[10,10]")
    assert C.attack(game, brom, gob, weapon="longsword").roll.mode == "disadvantage"
    game.dice.force_str("d20=[10]")
    assert C.attack(game, brom, gob, weapon="spear").roll.mode == "normal"
    far = mon(game, "goblin warrior", (0, 65), name="Far")
    game.dice.force_str("d20=[10,10]")
    assert C.attack(game, lidda, far, weapon="shortbow").roll.mode == "disadvantage"
    far.position = (0, 105)
    game.dice.force_str("d20=[19]")
    assert not C.attack(game, lidda, far, weapon="shortbow").hit
    hp = far.hp
    far.take_damage(4, "fire")
    assert hp - far.hp == 2                               # Resistance to Fire underwater


def test_cmb08_fall_off_mount(game):
    from dungdra.monster import Monster
    jozan = pc(game, "JOZAN", (0, 0))
    horse = game.add(Monster("riding horse"), team="party", position=(5, 0))
    mounted.mount(game, jozan, horse)
    game.dice.force_str("d20=[4]")
    horse.add_condition("prone", "knocked down")
    assert jozan.has("prone") and "mount" not in jozan.notes


# ---------------- FEAT-02 · Savage Attacker ----------------
def test_feat02_savage_attacker(game):
    brom = pc(game, "BROM")
    brom.award_xp(300)
    gob = mon(game, "ogre", (5, 0))
    game.dice.force_str("d20=[20, 1]")
    start(game, brom, gob)
    set_turn(game, brom)
    game.dice.force_str("d20=[15]; d8=[2,7]")
    game.answer("use_savage_attacker", True)
    game.answer("savage_attacker", [7])
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.damage == 10
    CA.action_surge(game, brom)
    game.dice.force_str("d20=[15]; d8=[3]")
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.damage == 6
    assert len([e for e in game.log.of_kind("feat") if "Savage" in e.text]) == 1


# ---------------- CLS-ROG-01 · Sneak Attack ----------------
@pytest.fixture
def rog(game):
    lidda = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 100
    game.dice.force_str("d20=[20, 1]")
    start(game, lidda, gob)
    set_turn(game, lidda)
    return lidda, gob


def test_rog01a_ally_adjacent(game, rog):
    lidda, gob = rog
    pc(game, "BROM", (10, 0))
    game.dice.force_str("d20=[15]; d6=[4,5]")
    assert C.attack(game, lidda, gob, weapon="shortsword").damage == 12


def test_rog01b_no_ally(game, rog):
    lidda, gob = rog
    game.dice.force_str("d20=[15]; d6=[4,5]")
    assert C.attack(game, lidda, gob, weapon="shortsword").damage == 7


def test_rog01c_greatclub(game, rog):
    lidda, gob = rog
    lidda.inventory.add("greatclub")
    lidda.shield = None
    game.dice.force_str("d20=[15,15]; d8=[4]")
    r = C.attack(game, lidda, gob, weapon="greatclub", adv=["test"])
    assert not any("Sneak Attack" in e.text for e in game.log.of_kind("sneak") if "d6" in e.text)


def test_rog01d_disadvantage(game, rog):
    lidda, gob = rog
    pc(game, "BROM", (10, 0))
    game.dice.force_str("d20=[15,15]; d6=[4]")
    r = C.attack(game, lidda, gob, weapon="shortsword", dis=["test"])
    assert r.damage == 7


def test_rog01e_incapacitated_ally(game, rog):
    lidda, gob = rog
    b = pc(game, "BROM", (10, 0))
    b.add_condition("incapacitated", "test")
    game.dice.force_str("d20=[15]; d6=[4]")
    assert C.attack(game, lidda, gob, weapon="shortsword").damage == 7


def test_rog01f_once_per_turn_and_crit(game, rog):
    lidda, gob = rog
    pc(game, "BROM", (10, 0))
    game.dice.force_str("d20=[15]; d6=[4,5]")
    assert C.attack(game, lidda, gob, weapon="shortsword").damage == 12
    game.dice.force_str("d20=[15]; d4=[2]")
    assert C.attack(game, lidda, gob, weapon="dagger", light_extra=True).damage == 2   # Nick, no SA
    set_turn(game, lidda)
    game.dice.force_str("d20=[20]; d6=[1,2,3,4]")
    r = C.attack(game, lidda, gob, weapon="shortsword")
    assert r.crit and r.damage == 1 + 2 + 3 + 4 + 3


def test_rog01_level3_2d6(game):
    lidda = pc(game, "LIDDA")
    lidda.award_xp(900)
    from dungdra.features import sneak_attack_dice
    assert sneak_attack_dice(lidda) == 2


# ---------------- EQP-02 · Weapon properties ----------------
def test_eqp02_properties(game):
    lidda = pc(game, "LIDDA", (0, 0))
    brom = pc(game, "BROM", (0, 10))
    gob = mon(game, "goblin warrior", (5, 0))
    gob.base_max_hp = gob.hp = 200
    game.dice.force_str("d20=[15]; d4=[2]")
    r = C.attack(game, lidda, gob, weapon="dagger")
    assert ("Dex" in [s for _, s in r.roll.mods] and r.damage == 5)
    brom.shield = None
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[15]; d10=[7]")
    brom.position = (5, 5)
    assert C.attack(game, brom, gob, weapon="longsword", two_handed=True).damage == 10
    gob.position = (40, 0)
    game.dice.force_str("d20=[15,15]; d4=[1]")
    assert C.attack(game, lidda, gob, weapon="dagger", thrown=True).roll.mode == "disadvantage"
    gob.position = (70, 0)
    with pytest.raises(Refusal):
        C.attack(game, lidda, gob, weapon="dagger", thrown=True)
    gob.position = (5, 0)
    lidda.inventory.add("greatsword")
    lidda.shield = None
    game.dice.force_str("d20=[15,15]; d6=[1,1]")
    r = C.attack(game, lidda, gob, weapon="greatsword")
    assert any("Strength 12 < 13" in s for s in r.roll.dis)
    # Loading: one shot per action
    x = pc(game, "BROM", (0, 30))
    x.inventory.add("light crossbow"); x.inventory.add("bolts", 20)
    x.shield = None
    game.dice.force_str("d20=[20, 1, 1, 1]")
    start(game, x, gob, lidda, brom)
    set_turn(game, x)
    game.dice.force_str("d20=[15]; d8=[2]")
    C.attack(game, x, gob, weapon="light crossbow")
    with pytest.raises(Refusal):
        C.attack(game, x, gob, weapon="light crossbow")


def test_eqp02_recover_arrows(game):
    lidda = pc(game, "LIDDA")
    gob = mon(game, "goblin warrior", (30, 0))
    gob.base_max_hp = gob.hp = 500
    for _ in range(10):
        game.dice.force_str("d20=[2]")
        C.attack(game, lidda, gob, weapon="shortbow")
    assert lidda.inventory.count("arrows") == 10
    assert C.recover_ammunition(game, lidda, "arrows") == 5
    assert lidda.inventory.count("arrows") == 15


# ---------------- EQP-03 · Mastery properties ----------------
def test_eqp03_masteries(game):
    brom = pc(game, "BROM", (0, 0))
    lidda = pc(game, "LIDDA", (0, 10))
    jozan = pc(game, "JOZAN", (10, 10))
    gob = mon(game, "goblin warrior", (5, 5))
    gob.base_max_hp = gob.hp = 200
    game.dice.force_str("d20=[20, 15, 10, 1]")
    start(game, brom, lidda, jozan, gob)
    set_turn(game, brom)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[15]; d8=[3]")
    C.attack(game, brom, gob, weapon="longsword")
    set_turn(game, gob)
    game.dice.force_str("d20=[10,10]")
    r = C.attack(game, gob, brom, attack_name="scimitar")
    assert any("Sap" in s for s in r.roll.dis)
    set_turn(game, lidda)
    game.dice.force_str("d20=[15]; d6=[2, 3]")
    C.attack(game, lidda, gob, weapon="shortsword")
    game.dice.force_str("d20=[5,15]; d4=[3]")
    r = C.attack(game, lidda, gob, weapon="dagger", light_extra=True)
    assert any("Vex" in s for s in r.roll.adv)      # Vex: Advantage on the next attack vs that target
    assert r.damage == 3                             # Nick extra attack: no ability modifier
    t = game.combat.turn
    assert t.nick_used and not t.bonus_used
    set_turn(game, brom)
    brom.shield = None
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[2]")
    hp = gob.hp
    C.attack(game, brom, gob, weapon="glaive")
    assert hp - gob.hp == 3                          # Graze
    set_turn(game, brom)
    gob.position = (20, 0)
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[15]; d6=[2]")
    C.attack(game, brom, gob, weapon="javelin", thrown=True)
    assert gob.speed() == 20
    brom.inventory.add("javelin")
    game.combat.turn.actions += 1
    game.dice.force_str("d20=[15]; d6=[2]")
    C.attack(game, brom, gob, weapon="javelin", thrown=True)
    assert gob.speed() == 20                         # doesn't stack past 10
    set_turn(game, jozan)
    gob.position = (15, 10)
    game.dice.force_str("d20=[15]; d6=[2]")
    C.attack(game, jozan, gob, weapon="mace")
    assert not any("Sap (JOZAN" in e.source for e in gob.effects)


def test_cls_ftr02_mace_no_mastery_and_champion(game):
    brom = pc(game, "BROM")
    brom.award_xp(900)
    gob = mon(game, "ogre", (5, 0))
    game.answer("use_savage_attacker", False)
    game.dice.force_str("d20=[19]; d8=[4,6]")
    r = C.attack(game, brom, gob, weapon="longsword")
    assert r.crit and r.damage == 13
    assert brom.find_effects("remarkable athlete move")
    brom.inventory.add("mace")
    game.dice.force_str("d20=[19]; d6=[1,1]")
    C.attack(game, brom, gob, weapon="mace")
    assert not any("Sap" in e.source and "BROM" in e.source and "Mace" in e.source for e in gob.effects)
    assert not brom.has_mastery(brom.inventory.find("mace"))
    game.dice.force_str("d20=[5,14]")
    r = C.initiative_roll(game, brom)
    assert r.mode == "advantage" and r.chosen == 14
