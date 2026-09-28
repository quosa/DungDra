"""EXPL, SOC, HAZ, MON, ENC, TRAP, POIS, CLS-ROG-02."""
import pytest

from dungdra import Refusal
from dungdra import actions, combat as C, class_actions as CA, encounters as E, explore as X, hazards as H, traps as T
from dungdra.monster import Monster
from tests.helpers import pc, mon
from tests.test_combat import start, set_turn


# ---------------- EXPL-01 ----------------
def test_expl01_travel(game):
    b, m = pc(game, "BROM"), pc(game, "MIALEE")
    t0 = game.clock
    assert X.travel(game, [b, m], miles=24, pace="normal", terrain="forest") == 8
    assert game.clock - t0 == 8 * 3600
    game.dice.force_str("d20=[5,5]")
    assert b.check("stealth").mode == "disadvantage"          # Normal pace + chain mail anyway
    game.dice.force_str("d20=[5,5]")
    assert m.check("stealth").mode == "disadvantage"
    with pytest.raises(Refusal, match="Normal"):
        X.travel(game, [b, m], miles=4, pace="fast", terrain="forest")
    X.travel(game, [b, m], miles=4, pace="fast", terrain="forest", road=True)
    game.dice.force_str("d20=[5,5]")
    assert m.check("perception").mode == "disadvantage"
    game.dice.force_str("d20=[5,5]")
    assert m.check("survival").mode == "disadvantage"
    X.travel(game, [b, m], miles=2, pace="slow", terrain="forest")
    game.dice.force_str("d20=[5,5]")
    assert m.check("perception").mode == "advantage"


def test_expl01_extended(game):
    b, m = pc(game, "BROM"), pc(game, "MIALEE")
    game.dice.force_str("d20=[8,10, 14,14]")
    t0 = game.clock
    X.travel(game, [b, m], hours=10, pace="normal", terrain="forest")
    saves = [e for e in game.log.of_kind("save") if "travel" in e.text]
    assert "DC 11" in saves[0].text and "= 12" in saves[0].text and "success" in saves[0].text
    assert "DC 12" in saves[3].text and "= 16" in saves[3].text
    assert m.exhaustion == 0 and b.exhaustion == 0
    assert game.clock - t0 == 10 * 3600


# ---------------- EXPL-02 ----------------
def test_expl02_vision(game):
    j, b, l = pc(game, "JOZAN"), pc(game, "BROM", (5, 0)), pc(game, "LIDDA", (10, 0))
    game.scene.light = "dark"
    assert j.check("perception").success is False           # effectively Blinded
    game.dice.force_str("d20=[5,5]")
    assert b.check("perception").mode == "disadvantage"      # Darkness -> Dim for Darkvision
    X.light_torch(game, b)
    game.dice.force_str("d20=[5]")
    assert j.check("perception").mode == "normal"
    game.dice.force_str("d20=[5]")
    assert b.check("perception").mode == "normal"
    game.advance(3600)
    assert not any(it.props.get("lit") for it in b.inventory)


# ---------------- EXPL-03 ----------------
def test_expl03_hide(game):
    l = pc(game, "LIDDA", (0, 0))
    gob = mon(game, "goblin warrior", (20, 0))
    with pytest.raises(Refusal, match="plain view"):
        actions.hide(game, l)
    game.dice.force_str("d20=[9]")
    r = actions.hide(game, l, cover="three-quarters")
    assert r.total == 16 and r.target == 15 and l.has("invisible") and l.hidden_total == 16
    assert not actions.notices(game, gob, l)
    actions.make_sound(game, l, "whisper")
    assert l.has("invisible")
    game.dice.force_str("d20=[5,15]; d6=[1,1]")
    res = C.attack(game, l, gob, weapon="shortbow")
    assert any("can't see" in s for s in res.roll.adv)
    assert not l.has("invisible")
    game.dice.force_str("d20=[9]")
    actions.hide(game, l, cover="three-quarters")
    actions.make_sound(game, l, "shout")
    assert not l.has("invisible")


# ---------------- EXPL-04 ----------------
def test_expl04_jump_climb_search(game):
    b, m = pc(game, "BROM"), pc(game, "MIALEE")
    assert X.long_jump(game, b, 16, running=True)
    assert not X.long_jump(game, b, 9, running=False)
    assert X.high_jump_distance(b) == 6
    game.dice.force_str("d20=[20]")
    start(game, m)
    set_turn(game, m)
    assert C.move(game, m, to=(0, 10), mode="climb") == 20
    set_turn(game, m)
    assert C.move(game, m, to=(0, 15), mode="climb", difficult=True) == 15
    C.end_combat(game)
    game.scene.hidden["secret door"] = {"location": "library", "dc": 10}
    game.dice.force_str("d20=[20]")
    assert actions.search_for_hidden(game, b, "kitchen") is None


# ---------------- CLS-ROG-02 ----------------
def test_rog02(game):
    l = pc(game, "LIDDA", (0, 0))
    l.award_xp(900)
    gob = mon(game, "goblin warrior", (40, 0))
    gob.base_max_hp = gob.hp = 100
    game.dice.force_str("d20=[20, 1]")
    start(game, l, gob)
    set_turn(game, l)
    CA.steady_aim(game, l)
    assert l.speed() == 0
    game.dice.force_str("d20=[5,15]; d6=[1,1,1]")
    r = C.attack(game, l, gob, weapon="shortbow")
    assert r.roll.mode == "advantage"
    set_turn(game, l)
    C.move(game, l, to=(5, 0))
    with pytest.raises(Refusal, match="moved"):
        CA.steady_aim(game, l)
    with pytest.raises(Refusal, match="Dash, Disengage or Hide"):
        CA.cunning_action(game, l, "dodge")
    game.dice.force_str("d20=[15]")
    actions.hide(game, l, cover="three-quarters", bonus=True, source="Cunning Action (Hide)")
    assert game.combat.turn.bonus_used
    set_turn(game, l)
    trap = T.place(game, "poisoned needle")
    trap.detected = True
    game.dice.force_str("d20=[15,15]")
    T.disarm(game, l, trap, bonus_action=True)
    assert trap.disabled and game.combat.turn.bonus_used and game.combat.turn.action_available()
    assert l.speed("climb") == 30
    assert X.long_jump_distance(l) == 17


# ---------------- SOC-01 / SOC-02 ----------------
def test_soc01_influence(game):
    j = pc(game, "JOZAN")
    guard = mon(game, "guard", team_attitude := None) if False else Monster("guard")
    game.add(guard, team="neutral")
    guard.attitude = "indifferent"
    game.dice.force_str("d20=[5]")
    ok = actions.influence(game, j, guard, "open the gate after dark", "hesitant")
    assert not ok
    dc_ev = game.log.last("influence_dc")
    assert dc_ev.visibility == "gm" and "15" in dc_ev.text
    with pytest.raises(Refusal, match="24"):
        actions.influence(game, j, guard, "open the gate after dark", "hesitant")
    boss = Monster("goblin boss"); game.add(boss)
    n = len(game.log.of_kind("check"))
    assert actions.influence(game, j, boss, "hand over the treasure", "unwilling") is False
    priest = Monster("priest acolyte"); game.add(priest, team="neutral"); priest.attitude = "friendly"
    assert actions.influence(game, j, priest, "a blessing", "willing") is True
    assert len(game.log.of_kind("check")) == n
    game.dice.force_str("d20=[5,15]")
    game.advance(86400)
    boss.attitude = "hostile"
    actions.influence(game, j, boss, "leave", "hesitant")
    assert game.log.last("check").data["roll"]["mode"] == "disadvantage"
    game.dice.force_str("d20=[5,15]")
    actions.influence(game, j, priest, "tell me more", "hesitant")
    assert game.log.last("check").data["roll"]["mode"] == "advantage"


def test_soc02(game):
    j, m = pc(game, "JOZAN"), pc(game, "MIALEE")
    game.dice.force_str("d20=[10]")
    r = actions.search(game, j, "insight", what="the merchant's body language")
    assert "Insight" in r.label and "Search" in r.label
    with pytest.raises(Refusal, match="Arcana"):
        actions.study(game, m, skill="history", creature_type="fey")
    game.dice.force_str("d20=[10]")
    r = actions.study(game, m, creature_type="fey", topic="goblins")
    assert "Arcana" in r.label
    with pytest.raises(Refusal):
        actions.single_action(game, j, ["influence", "search"])


# ---------------- HAZ-01 ----------------
def test_haz01_exhaustion(game):
    m = pc(game, "MIALEE")
    for lvl in range(1, 6):
        m.gain_exhaustion(1)
        game.dice.force_str("d20=[10]")
        r = m.check("arcana")
        assert r.total == 10 + 5 - 2 * lvl
        assert m.speed() == 30 - 5 * lvl
    m.gain_exhaustion(1)
    assert m.dead
    b = pc(game, "BROM")
    b.gain_exhaustion(3)
    from dungdra import rest as R
    R.long_rest(game, [b])
    assert b.exhaustion == 2


# ---------------- HAZ-02 ----------------
def test_haz02_falling(game):
    m = pc(game, "MIALEE")
    m.base_max_hp = m.hp = 30
    game.dice.force_str("d6=[2,3,4]")
    H.fall(game, m, 30)
    assert m.hp == 21 and m.has("prone")
    m.remove_condition("prone")
    game.dice.force_str("d20=[12]; d6=[2,3,4]")
    H.fall(game, m, 30, into_water=True)
    chk = game.log.last("check").text
    assert "Acrobatics" in chk and "= 13" in chk and m.hp == 12


def test_haz02_suffocation(game):
    m = pc(game, "MIALEE")
    assert H.breath_seconds(m) == 180
    H.start_holding_breath(game, m)
    game.dice.force_str("d20=[20]")
    start(game, m)
    for _ in range(31):
        C.end_turn(game)
    assert m.exhaustion >= 1
    H.breathe_again(game, m)
    assert m.exhaustion == 0


def test_haz02_food_water(game):
    b, j, l = pc(game, "BROM"), pc(game, "JOZAN"), pc(game, "LIDDA")
    for day in range(1, 7):
        H.end_of_day_food(game, b, 0)
        assert b.exhaustion == max(0, day - 4)
    game.dice.force_str("d20=[7]")
    H.end_of_day_food(game, j, 0.25)
    assert j.exhaustion == 1
    H.end_of_day_water(game, l, 0.25)
    assert l.exhaustion == 1
    from dungdra import rest as R
    R.long_rest(game, [l])
    assert l.exhaustion == 1                       # can't be removed until full water
    H.end_of_day_water(game, l, 1)
    game.advance(16 * 3600)
    R.long_rest(game, [l])
    assert l.exhaustion == 0


def test_haz02_burning(game):
    b = pc(game, "BROM")
    gob = mon(game, "goblin warrior", (30, 0))
    H.set_burning(game, b)
    game.dice.force_str("d20=[20, 1]; d4=[3]")
    start(game, b, gob)
    assert b.hp == 10
    H.extinguish_by_rolling(game, b)
    assert b.has("prone") and not b.find_effects(cls=H.Burning)


# ---------------- MON-01 / MON-02 ----------------
def test_mon01_statblocks(game):
    from dungdra.data.monsters import MONSTERS
    assert len(MONSTERS) == 14
    expected = {"goblin warrior": (15, 10, 50), "goblin boss": (17, 21, 200), "goblin minion": (12, 7, 25),
                "wolf": (12, 11, 50), "zombie": (8, 15, 50), "skeleton": (14, 13, 50), "kobold warrior": (14, 7, 25),
                "giant rat": (13, 7, 25), "bandit": (12, 11, 25), "cultist": (12, 9, 25), "guard": (16, 11, 25),
                "priest acolyte": (13, 11, 50), "ogre": (11, 68, 450), "riding horse": (11, 13, 50)}
    for k, (ac, hp, xp) in expected.items():
        m = Monster(k)
        assert (m.ac(), m.hp, m.xp, m.pb) == (ac, hp, xp, 2), k
    assert Monster("goblin warrior").ctype == "fey" and Monster("ogre").ctype == "giant"
    assert Monster("wolf").passive() == 15
    ogre = mon(game, "ogre")
    b = pc(game, "LIDDA", (0, 0))
    game.dice.force_str("d20=[10]; d8=[3,4]")
    r = C.attack(game, ogre, b, attack_name="greatclub")
    assert r.roll.total == 16 and r.damage == 11
    with pytest.raises(Refusal, match="invent"):
        ogre.attack_named("fire breath")


def test_mon02_traits(game):
    b = pc(game, "BROM", (0, 0))
    l = pc(game, "LIDDA", (0, 20))
    w1 = mon(game, "wolf", (5, 0), name="Wolf 1")
    w2 = mon(game, "wolf", (-5, 0), name="Wolf 2")
    game.dice.force_str("d20=[3,15]; d6=[1]")
    r = C.attack(game, w1, b, attack_name="bite")
    assert any("Pack Tactics" in s for s in r.roll.adv)
    w1.position = (0, 25)
    game.dice.force_str("d20=[18]; d6=[1]")
    C.attack(game, w1, l, attack_name="bite")
    assert l.has("prone")
    gob = mon(game, "goblin warrior", (5, 5), name="Gob")
    game.dice.force_str("d20=[3,15]; d6=[1]; d4=[2]")
    r = C.attack(game, gob, b, attack_name="scimitar", adv=["test"])
    assert r.damage == 1 + 2 + 2
    z = mon(game, "zombie", (5, -5))
    z.hp = 5
    game.dice.force_str("d20=[12]")
    z.take_damage(9, "slashing")
    assert z.hp == 1 and not z.dead
    z.hp = 5
    z.take_damage(9, "slashing", crit=True)
    assert z.dead
    z2 = mon(game, "zombie", (5, -5), name="Z2")
    z2.hp = 5
    z2.take_damage(9, "radiant")
    assert z2.dead
    boss = mon(game, "goblin boss", (10, 10), name="Boss")
    minion = mon(game, "goblin warrior", (15, 10), name="Minion")
    b.position = (5, 10)
    game.dice.force_str("d20=[20, 1, 1, 1, 1, 1, 1]")
    start(game, b, boss, minion)
    set_turn(game, b)
    game.answer("use_savage_attacker", False)
    game.answer("redirect_attack", "minion")
    game.dice.force_str("d20=[18,18]; d8=[3]")
    r = C.attack(game, b, boss, weapon="longsword")
    assert r.target is minion and boss.position == (15, 10)
    k = mon(game, "kobold warrior", (0, 30), name="Kobold")
    game.scene.sunlight = True
    game.dice.force_str("d20=[5,5]")
    assert k.check("stealth").mode == "disadvantage"


# ---------------- ENC-01 / ENC-02 ----------------
def test_enc01(game):
    lv1 = [1, 1, 1, 1]
    assert E.budgets(lv1) == {"low": 200, "moderate": 300, "high": 400}
    assert E.rate(game, lv1, ["goblin warrior"] * 4)["band"] == "low"
    assert E.rate(game, lv1, ["goblin boss", "goblin warrior", "goblin warrior"])["band"] == "moderate"
    n_player = len(game.log.visible())
    r = E.rate(game, lv1, ["ogre"])
    assert r["band"] == "over high" and r["cr_above_level"]
    ev = game.log.last("encounter")
    assert ev.visibility == "gm" and ev.ruling == "R-03" and "Over High budget" in ev.text
    assert len(game.log.visible()) == n_player
    assert all("budget" not in e.text.lower() for e in game.log.visible())
    with pytest.raises(Refusal, match="R-03"):
        E.add_reinforcements(game, lv1, ["goblin boss", "goblin warrior", "goblin warrior"], ["wolf", "wolf", "wolf"])
    E.add_reinforcements(game, lv1, ["goblin boss"], ["ogre"], justification="the ogre was always in the cave")
    assert E.budgets([3] * 4) == {"low": 600, "moderate": 900, "high": 1600}
    assert E.rate(game, [3] * 4, ["ogre", "goblin boss", "wolf", "wolf"])["band"] == "moderate"
    for _ in range(20):
        built = E.build(game, lv1, "moderate", "forest")
        assert 0 < E.encounter_xp(built) <= 300


def test_enc02_xp(game):
    party = [pc(game, n) for n in ("BROM", "LIDDA", "MIALEE", "JOZAN")]
    share = E.award_xp(game, ["goblin boss", "goblin warrior", "goblin warrior"], party)
    assert share == 75 and all(p.xp == 75 for p in party)
    assert "R-02" in game.log.rulings()


# ---------------- TRAP-01 / TRAP-02 ----------------
def test_trap01_hidden_pit(game):
    party = [pc(game, n) for n in ("BROM", "LIDDA", "MIALEE", "JOZAN")]
    b, l, m, j = party
    pit = T.place(game, "hidden pit")
    assert T.passive_detection(game, party, pit) is None
    game.dice.force_str("d6=[3]")
    T.trigger(game, b, pit)
    assert b.hp == 10 and b.has("prone")
    pit2 = T.place(game, "hidden pit", name="pit 2")
    game.dice.force_str("d20=[10]")
    r = T.detect(game, m, pit2)
    assert r.total == 15 and pit2.detected
    b.inventory.add("iron spikes", 10)
    T.wedge_spike(game, b, pit2)
    assert T.trigger(game, j, pit2) is None
    l.award_xp(900)
    l.notes["in_pit"] = "hidden pit"
    assert T.climb_out(game, l)
    b.notes["in_pit"] = "hidden pit"
    with pytest.raises(Refusal, match="Climb Speed"):
        T.climb_out(game, b)


def test_trap02_needle(game):
    l = pc(game, "LIDDA")
    t = T.place(game, "poisoned needle")
    game.dice.force_str("d20=[15]")
    T.detect(game, l, t)
    game.dice.force_str("d20=[4,9]")
    r = T.disarm(game, l, t)
    assert r.total == 16 and t.disabled
    t2 = T.place(game, "poisoned needle", name="needle 2")
    t2.detected = True
    game.dice.force_str("d20=[3,5]; d20=[6]; d10=[8]")
    r = T.disarm(game, l, t2)
    assert r.total == 12 and l.hp == 2 and l.has("poisoned")
    t3 = T.place(game, "poisoned needle", name="needle 3")
    t3.detected = True
    l.inventory.remove("thieves' tools", l.inventory.count("thieves' tools"))
    game.dice.force_str("d20=[20]")
    T.disarm(game, l, t3)
    assert "R-04" in game.log.rulings()


# ---------------- POIS-01 ----------------
def test_pois01(game):
    l = pc(game, "LIDDA", (0, 0))
    bandit = mon(game, "bandit", (5, 0))
    bandit.base_max_hp = bandit.hp = 50
    l.inventory.add("serpent venom", 2)
    game.dice.force_str("d20=[20, 1]")
    start(game, l, bandit)
    set_turn(game, l)
    H.apply_poison_to_weapon(game, l, "shortsword")
    assert game.combat.turn.bonus_used
    game.dice.force_str("d20=[15]; d6=[3]; d20=[6]; d6=[2,5,6]")
    C.attack(game, l, bandit, weapon="shortsword")
    assert bandit.hp == 50 - 6 - 13
    assert "coating" not in l.inventory.find("shortsword").props
    l.inventory.add("mace")
    set_turn(game, l)
    H.apply_poison_to_weapon(game, l, "mace")
    assert "never be delivered" in game.log.last("poison").text
