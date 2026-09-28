"""Structured command API (harness contract §2.1.4): `Session.execute({...})`.

Every command returns {"ok": bool, "events": [player-visible lines], "error"?: str}.
The natural-language interface (nl.py) produces exactly these commands.
"""
from __future__ import annotations

from . import (actions, class_actions as CA, combat as C, damage as D, encounters as E, explore as X, gear, gm,
               hazards as H, magic_items as MI, rest as R, spells as S, traps as T)
from .creation import CharacterBuilder, prepare_spells
from .events import PLAYER
from .fixtures import FIXTURES, make as make_fixture
from .game import Game
from .rules import OutOfScope, Refusal, norm


class Session:
    def __init__(self, game: Game | None = None, seed: int | None = 1):
        self.game = game or Game(seed)
        self.builder: CharacterBuilder | None = None
        self.adventure = None
        self.active: str | None = None       # default acting PC
        self.auto_gm = True                   # False: monster turns are driven through the API (tests/GM tools)

    # ------------------------------------------------------------------
    def execute(self, cmd: dict) -> dict:
        g = self.game
        start = len(g.log)
        name = cmd.get("cmd")
        fn = getattr(self, f"cmd_{name}", None)
        if fn is None:
            return {"ok": False, "error": f"Unknown command {name!r}", "events": []}
        args = {k: v for k, v in cmd.items() if k != "cmd"}
        try:
            out = fn(**args)
            ok = True
            err = None
        except OutOfScope as e:
            out, ok, err = None, False, f"Out of scope: {e.reason}"
        except Refusal as e:
            out, ok, err = None, False, e.reason
        # after a PC acts in combat, let the GM run monster turns when the PC ends its turn
        events = [str(e) for e in g.log.since(start) if e.visibility == PLAYER]
        res = {"ok": ok, "events": events}
        if err:
            res["error"] = err
            g.log.player("refused", f"Refused: {err}")
        if out is not None and not isinstance(out, (Refusal,)):
            res["result"] = _plain(out)
        return res

    # -- helpers ---------------------------------------------------------------
    def _c(self, ref=None):
        g = self.game
        if ref is None:
            if g.combat is not None and g.combat.current is not None and g.combat.current.team == "party":
                return g.combat.current
            if self.active:
                return g.get(self.active)
            pcs = g.pcs()
            if len(pcs) == 1:
                return pcs[0]
            raise Refusal("Who is acting? Name the character.")
        return g.get(ref)

    def _after_pc_action(self):
        g = self.game
        if g.combat is not None and gm.combat_over(g):
            gm.finish_combat(g)

    # -- character creation ------------------------------------------------------
    def cmd_create(self, **fields):
        if self.builder is None:
            self.builder = CharacterBuilder(self.game)
        if fields.get("reset"):
            self.builder = CharacterBuilder(self.game)
            fields.pop("reset")
        for k, v in fields.items():
            self.builder.set(k, v)
        missing = self.builder.missing()
        return {"missing": [{"key": k, "question": q} for k, q in missing]}

    def cmd_finish_character(self):
        if self.builder is None:
            raise Refusal("No character in progress")
        pc = self.builder.build()
        self.builder = None
        self.active = pc.id
        return {"created": pc.id, "sheet": pc.sheet()}

    def cmd_fixture(self, name, position=None):
        pc = make_fixture(self.game, name, position)
        return {"created": pc.id}

    def cmd_prepare(self, actor=None, spells=()):
        prepare_spells(self._c(actor), list(spells))

    # -- information --------------------------------------------------------------
    def cmd_status(self):
        g = self.game
        lines = [c.summary() for c in g.pcs()]
        if g.combat:
            cb = g.combat
            lines.append(f"Round {cb.round}; turn: {cb.current.name if cb.current else '-'}")
            lines += [f"  {g.creatures[i].name}: {v}" for i, v in cb.order]
            lines += ["Enemies: " + ", ".join(f"{e.name} ({'dead' if e.dead else 'down' if not e.conscious else 'fled' if e.notes.get('fled') else 'wounded' if e.hp < e.max_hp else 'unhurt'})"
                                           for e in (g.creatures[i] for i in cb.participants if g.creatures[i].team == 'enemy'))]
        return "\n".join(lines)

    def cmd_sheet(self, actor=None):
        return self._c(actor).sheet()

    def cmd_snapshot(self):
        return self.game.snapshot()

    def cmd_answer(self, key, value, actor=None):
        self.game.answer(key, value, who=actor)

    # -- combat --------------------------------------------------------------------
    def cmd_start_combat(self, enemies=None, surprised=()):
        g = self.game
        foes = [g.get(e) for e in (enemies or [c.id for c in g.creatures.values() if c.team == "enemy" and not c.dead])]
        parts = [p for p in g.pcs() if not p.dead] + foes
        C.roll_initiative(g, parts, surprised=[g.get(s) for s in surprised])
        if self.auto_gm:
            gm.run_until_pc(g)

    def cmd_end_turn(self, actor=None):
        g = self.game
        if g.combat is None:
            raise Refusal("There's no combat going on")
        C.end_turn(g)
        if self.auto_gm:
            gm.run_until_pc(g)
        elif gm.combat_over(g):
            gm.finish_combat(g)

    def cmd_attack(self, target, actor=None, weapon=None, thrown=False, two_handed=False, light_extra=False,
                   unarmed=False):
        a = self._c(actor)
        kw = {"weapon": weapon} if a.is_pc() else {"attack_name": weapon}
        r = C.attack(self.game, a, self.game.get(target), thrown=thrown, two_handed=two_handed,
                     light_extra=light_extra, unarmed=unarmed, **kw)
        self._after_pc_action()
        return {"hit": r.hit, "crit": r.crit, "damage": r.damage}

    def cmd_cast(self, spell, actor=None, targets=None, slot=None, ritual=False, free=False, item=None,
                 option=None, point=None, charges=None):
        a = self._c(actor)
        it = a.inventory.find(item) if item else None
        if item and it is None:
            raise Refusal(f"{a.name} has no {item}")
        scroll = it is not None and it.name == "spell scroll"
        if targets is not None and not isinstance(targets, list):
            targets = [targets]
        S.cast(self.game, a, spell, targets, slot=slot, ritual=ritual, free=free, item=it, scroll=scroll,
               option=option, point=tuple(point) if point else None, charges=charges)
        self._after_pc_action()

    def cmd_move(self, actor=None, to=None, toward=None, feet=None, away_from=None, mode="walk"):
        g = self.game
        a = self._c(actor)
        C.move(g, a, to=tuple(to) if to else None, toward=g.get(toward) if toward else None, feet=feet,
               away_from=g.get(away_from) if away_from else None, mode=mode)

    def cmd_dash(self, actor=None, bonus=False):
        actions.dash(self.game, self._c(actor), bonus=bonus)

    def cmd_disengage(self, actor=None, bonus=False):
        actions.disengage(self.game, self._c(actor), bonus=bonus)

    def cmd_dodge(self, actor=None):
        actions.dodge(self.game, self._c(actor))

    def cmd_cunning_action(self, what, actor=None, cover=None):
        a = self._c(actor)
        if norm(what) == "hide":
            actions.hide(self.game, a, cover=cover or "three-quarters", bonus=True, source="Cunning Action (Hide)")
        else:
            CA.cunning_action(self.game, a, what)

    def cmd_hide(self, actor=None, cover=None, obscured=None):
        actions.hide(self.game, self._c(actor), cover=cover, obscured=obscured)

    def cmd_help(self, actor=None, ally=None, enemy=None, skill=None, tool=None):
        g = self.game
        a = self._c(actor)
        if enemy:
            actions.help_attack(g, a, g.get(enemy))
        else:
            actions.help_check(g, a, g.get(ally), skill=skill, tool=tool)

    def cmd_search(self, actor=None, skill="perception", dc=None, target=None, what=""):
        r = actions.search(self.game, self._c(actor), skill, dc=dc, target=self.game.get(target) if target else None,
                           what=what)
        return {"total": r.total, "success": r.success}

    def cmd_study(self, actor=None, skill=None, dc=None, topic="", creature_type=None):
        r = actions.study(self.game, self._c(actor), skill=skill, dc=dc, topic=topic, creature_type=creature_type)
        return {"total": r.total, "success": r.success}

    def cmd_check(self, skill=None, ability=None, dc=None, actor=None):
        r = self._c(actor).check(skill=skill, ability=ability, dc=dc)
        return {"total": r.total, "success": r.success}

    def cmd_influence(self, npc, request, disposition="hesitant", approach="persuade", actor=None):
        return actions.influence(self.game, self._c(actor), self.game.get(npc), request, disposition, approach)

    def cmd_use_tool(self, task, actor=None, dc=None, tool=None):
        r = actions.use_tool(self.game, self._c(actor), task, dc=dc, tool=tool)
        return {"total": r.total, "success": r.success}

    def cmd_second_wind(self, actor=None):
        CA.second_wind(self.game, self._c(actor))

    def cmd_action_surge(self, actor=None):
        CA.action_surge(self.game, self._c(actor))

    def cmd_steady_aim(self, actor=None):
        CA.steady_aim(self.game, self._c(actor))

    def cmd_grapple(self, target, actor=None):
        return C.grapple(self.game, self._c(actor), self.game.get(target))

    def cmd_shove(self, target, actor=None, effect="prone"):
        return C.shove(self.game, self._c(actor), self.game.get(target), effect)

    def cmd_escape(self, actor=None):
        C.escape_grapple(self.game, self._c(actor))

    def cmd_stand(self, actor=None):
        C.stand_up(self.game, self._c(actor))

    def cmd_drop_prone(self, actor=None):
        C.drop_prone(self.game, self._c(actor))

    def cmd_drink(self, actor=None, target=None):
        a = self._c(actor)
        MI.drink_potion(self.game, a, self.game.get(target) if target else None)

    def cmd_stabilize(self, target, actor=None, kit=False):
        a = self._c(actor)
        t = self.game.get(target)
        if kit:
            D.healers_kit(self.game, a, t)
        else:
            D.first_aid(self.game, a, t)

    def cmd_divine_spark(self, target, actor=None, mode="heal"):
        CA.divine_spark(self.game, self._c(actor), self.game.get(target), mode)

    def cmd_turn_undead(self, actor=None):
        a = self._c(actor)
        CA.turn_undead(self.game, a, [c for c in self.game.enemies_of(a)])

    def cmd_preserve_life(self, allocation, actor=None):
        CA.preserve_life(self.game, self._c(actor), allocation)

    def cmd_interact(self, what, actor=None):
        C.interact(self.game, self._c(actor), what)

    def cmd_light_torch(self, actor=None):
        X.light_torch(self.game, self._c(actor))

    # -- exploration & downtime ----------------------------------------------------------
    def cmd_travel(self, miles=None, hours=None, pace="normal", terrain="forest", road=False):
        g = self.game
        X.travel(g, [p for p in g.pcs() if not p.dead], miles=miles, hours=hours, pace=pace, terrain=terrain,
                 road=road)

    def _resters(self):
        g = self.game
        g.resolve_dying()
        pcs = [p for p in g.pcs() if not p.dead and p.hp >= 1]
        for p in g.pcs():
            if not p.dead and p.hp < 1:
                g.log.player("rest", f"{p.name} has 0 Hit Points and can't start a rest (needs healing first)",
                             page=187)
        if not pcs:
            raise Refusal("Nobody is able to rest")
        return pcs

    def cmd_short_rest(self, hit_dice=None, focus=None):
        g = self.game
        pcs = self._resters()
        fx = None
        if focus:
            fx = {g.get(k).id: (v[0], g.get(k).inventory.find(v[1])) for k, v in focus.items()}
        return R.short_rest(g, pcs, hit_dice=hit_dice, focus=fx)

    def cmd_long_rest(self, interrupt_after_hours=None):
        g = self.game
        pcs = self._resters()
        sched = getattr(self, "scheduled_interrupt", None)
        if sched is None:
            return R.long_rest(g, pcs, interrupt_after_hours=interrupt_after_hours)
        # a GM-scheduled interruption: rest N hours, then the encounter strikes
        self.scheduled_interrupt = None
        hours, keys = sched
        R.begin_rest(g, "long", pcs)
        g.log.player("rest", "Watches are set: each companion takes a turn standing guard (light activity)",
                     page=185)
        need = max(4 if "trance" in p.traits else 8 for p in pcs)
        g.advance(int(hours * 3600), "Long Rest")
        g.rest["interrupted"] = "an attack in the night"
        g.log.player("rest", f"The Long Rest is interrupted after {hours:g} hours!", page=185)
        if hours >= 1:
            g.log.player("rest", "At least 1 hour had passed: the rest grants Short Rest benefits", page=185)
            for p in pcs:
                R.short_rest_benefits(g, p)
        g.rest = None
        self.paused_rest = {"need": need, "rested": hours, "interruptions": 1, "members": [p.id for p in pcs]}
        mons = E.spawn(g, keys, [(25 + 5 * i, 10) for i in range(len(keys))])
        E.rate(g, [p.level for p in pcs], mons)
        C.roll_initiative(g, [p for p in g.pcs() if not p.dead] + mons, surprised=[])
        gm.run_until_pc(g)
        return False

    def cmd_resume_rest(self):
        g = self.game
        pr = getattr(self, "paused_rest", None)
        if pr is None:
            raise Refusal("There's no interrupted Long Rest to resume")
        pcs = [g.get(i) for i in pr["members"] if not g.get(i).dead and g.get(i).hp >= 1]
        R.begin_rest(g, "long", pcs)
        remaining = pr["need"] - pr["rested"] + pr["interruptions"]
        g.log.player("rest", f"The Long Rest resumes: it needs {pr['interruptions']} extra hour(s) per interruption "
                     f"({remaining:g} hours to go)", page=185)
        self.paused_rest = None
        g.advance(int(remaining * 3600), "Long Rest (resumed)")
        return R.finish_long_rest(g, pcs)

    # -- GM tools (setup; the natural-language player never issues these) ----------
    def cmd_spawn(self, monsters, positions=None, team="enemy", names=None):
        mons = E.spawn(self.game, monsters, positions, team)
        if names:
            for m, n in zip(mons, names):
                m.name = n
        return [m.id for m in mons]

    def cmd_give(self, actor, item=None, gp=0, qty=1, **props):
        a = self.game.get(actor)
        if item:
            try:
                it = MI.make(item, **props)
                a.inventory.add(it)
            except (OutOfScope, Refusal):
                a.inventory.add(item, qty)
        if gp:
            a.purse.add(gp=gp)

    def cmd_schedule_interrupt(self, hours, monsters):
        self.scheduled_interrupt = (hours, list(monsters))

    def cmd_place(self, actor, position):
        self.game.get(actor).position = tuple(position)

    def cmd_buy(self, item, qty=1, actor=None):
        gear.buy(self.game, self._c(actor), item, qty)

    def cmd_sell(self, item, qty=1, actor=None):
        return gear.sell(self.game, self._c(actor), item, qty)

    def cmd_lifestyle(self, level, days):
        gear.live(self.game, [p for p in self.game.pcs() if not p.dead], level, days)

    def cmd_craft(self, item, actor=None, helpers=()):
        return gear.craft(self.game, self._c(actor), item, [self.game.get(h) for h in helpers])

    def cmd_don(self, item, actor=None):
        gear.don_armor(self.game, self._c(actor), item)

    def cmd_doff(self, actor=None):
        gear.doff_armor(self.game, self._c(actor))

    def cmd_trap(self, action, trap, actor=None):
        g = self.game
        t = T.get(g, trap)
        a = self._c(actor)
        if action == "detect":
            return T.detect(g, a, t).success
        if action == "disarm":
            return T.disarm(g, a, t).success
        if action == "spike":
            return T.wedge_spike(g, a, t)
        if action == "trigger":
            return T.trigger(g, a, t)
        raise Refusal("Trap actions: detect, disarm, spike, trigger")

    def cmd_copy_scroll(self, item="spell scroll", actor=None):
        a = self._c(actor)
        return MI.copy_scroll(self.game, a, a.inventory.find(item))

    def cmd_attune(self, item, actor=None):
        a = self._c(actor)
        return R.short_rest(self.game, [a], focus={a.id: ("attune", a.inventory.find(item))})

    def cmd_identify(self, item, actor=None):
        a = self._c(actor)
        return R.short_rest(self.game, [a], focus={a.id: ("identify", a.inventory.find(item))})

    def cmd_award_xp(self, amount, reason="GM award"):
        for p in self.game.pcs():
            p.award_xp(amount, reason)

    # -- adventure -------------------------------------------------------------------------
    def cmd_look(self):
        if self.adventure is None:
            return self.game.scene.name
        return self.adventure.describe()

    def cmd_loot(self):
        if self.adventure is None:
            raise Refusal("There's nothing to loot here")
        g = self.game
        needle = next((o["trap"] for o in g.scene.objects.values() if "trap" in o
                       and o["trap"].kind == "poisoned needle" and not o["trap"].disabled and not o["trap"].triggered),
                      None)
        if needle is not None:
            raise Refusal("The chest is locked. Pick the lock or disarm whatever guards it first")
        self.adventure.take_loot()

    def cmd_wait(self, hours=1):
        self.game.advance(int(hours * 3600), "waiting")

    def cmd_end_day(self, food=None, water=None):
        """End of a day: each PC eats a ration if carried and drinks (p.181, 185)."""
        g = self.game
        for p in g.pcs():
            if p.dead:
                continue
            f = (food or {}).get(p.id)
            if f is None:
                if p.inventory.find("rations"):
                    p.inventory.remove("rations", 1)
                    f = 1
                else:
                    f = 0
            H.end_of_day_food(g, p, f)
            H.end_of_day_water(g, p, (water or {}).get(p.id, 1))
            g.log.player("food", f"{p.name} {'eats a day of Rations' if f >= 1 else 'goes hungry' if f == 0 else 'eats a partial ration'}"
                         f" ({p.inventory.count('rations')} left)", page=185)

    def cmd_lose_item(self, item, actor=None, qty=1):
        a = self._c(actor)
        a.inventory.remove(item, qty)
        self.game.log.player("inventory", f"{a.name} loses {qty} \u00d7 {item}")

    def cmd_go(self, where=None):
        if self.adventure is None:
            raise Refusal("There's no adventure loaded")
        return self.adventure.go(where)


def _plain(x):
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return str(x)
