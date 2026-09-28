"""The natural-language play loop: text in, narration out."""
from __future__ import annotations

from . import nl
from .api import Session
from .events import PLAYER


class Play:
    def __init__(self, seed: int | None = 1, decider=None, adventure=True, llm=None, auto_end_turn=False):
        self.auto_end_turn = auto_end_turn
        self.session = Session(seed=seed)
        self.game = self.session.game
        self.game.decider = decider
        self.llm = llm
        if adventure:
            from .adventure import Adventure
            self.session.adventure = Adventure(self.session)

    def begin(self) -> str:
        return ("Welcome to DungDra, a fifth-edition-compatible adventure.\n"
                "Create your party: describe a character (e.g. 'A dwarf fighter, ex-soldier, standard array ...'), "
                "or type 'use the sample party'. Type 'begin the adventure' when everyone is ready.")

    def say(self, text: str) -> str:
        t = text.strip()
        low = t.lower()
        if low in ("use the sample party", "sample party", "quick start"):
            for n in ("BROM", "LIDDA", "MIALEE", "JOZAN"):
                self.session.execute({"cmd": "fixture", "name": n})
            return "The sample party joins you: " + ", ".join(p.name for p in self.game.pcs()) + "."
        if low in ("begin the adventure", "start the adventure", "begin", "start"):
            if not self.game.pcs():
                return "Create at least one character first."
            start = len(self.game.log)
            self.session.adventure.start()
            return self._events(start)
        if self.llm is not None:
            cmds = self.llm.translate(self, t)
        else:
            cmds = nl.parse(self.session, t)
        if isinstance(cmds, dict) and "create" in cmds:
            return self._create(cmds["create"])
        if isinstance(cmds, dict):
            return cmds.get("say", "")
        out = []
        for cmd in cmds:
            res = self.session.execute(cmd)
            out += res["events"]
            if not res["ok"]:
                out.append(f"(Refused) {res['error']}")
                break
            r = res.get("result")
            if isinstance(r, str) and cmd["cmd"] in ("status", "sheet", "look", "inventory"):
                out.append(r)
        out += self._turn_flow(cmds)
        return "\n".join(x for x in out if x)

    def _turn_flow(self, cmds):
        """After a command in combat: say what the active PC can still do, and end the turn
        automatically once the character has nothing useful left (movement alone doesn't count)."""
        from .turnhelp import turn_summary
        out = []
        info_only = all(c.get("cmd") in ("status", "sheet", "look", "inventory", "end_turn") for c in cmds)
        for _ in range(8):
            g = self.game
            cb = g.combat
            if cb is None or cb.current is None or cb.current.team != "party" or not cb.current.is_pc():
                break
            cur = cb.current
            hint, left = turn_summary(g, cur)
            acted = bool(cb.turn.log) or cb.turn.moved > 0 or cb.turn.bonus_used
            if self.auto_end_turn and not left and acted and not info_only:
                out.append(f"({cur.name} has nothing more to do this turn, so the turn ends.)")
                res = self.session.execute({"cmd": "end_turn"})
                out += res["events"]
                info_only = True
                continue
            out.append(f"→ It's {cur.name}'s turn ({hint}).")
            break
        return out

    def _events(self, start):
        return "\n".join(str(e) for e in self.game.log.since(start) if e.visibility == PLAYER)

    def _create(self, text):
        s = self.session
        res = nl.apply_creation(s, text)
        lines = list(res["notes"])
        lines += [f"(Refused) {e}" for e in res["errors"]]
        if res["missing"]:
            key, q = res["missing"][0]
            lines.append(q)
        else:
            lines.append("Everything is chosen. Say 'done' to finalize the character sheet.")
        return "\n".join(lines)
