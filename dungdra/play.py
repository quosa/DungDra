"""The natural-language play loop: text in, narration out."""

from __future__ import annotations

import difflib
import re
import traceback

from . import nl
from .api import Session
from .events import PLAYER

SAMPLE_PARTY = re.compile(
    r"(?:use |take |pick |play with )?(?:the |a )?(?:sample|default|ready-made|premade) "
    r"(?:party|characters|heroes|team)|quick ?start"
)
BEGIN = re.compile(r"(?:let'?s )?(?:begin|start|play)(?: (?:the |an |our )?(?:adventure|game|quest))?")
# whole commands a player types as they are: the candidates for "Did you mean ...?"
KNOWN = (
    "use the sample party",
    "begin the adventure",
    "continue",
    "go back",
    "map",
    "exits",
    "look",
    "status",
    "inventory",
    "short rest",
    "long rest",
    "end turn",
)
# commands whose answer is text for the player (the rest report through the event log)
SHOWN = (
    "status",
    "sheet",
    "look",
    "map",
    "inventory",
    "talk",
    "accept_quest",
    "quests",
    "turn_in",
    "wares",
    "rent_room",
)
YES = ("yes", "y", "yes please", "sure", "ok", "okay", "do that")


class Play:
    def __init__(
        self, seed: int | None = 1, decider=None, adventure: bool | str = True, llm=None, auto_end_turn=False
    ):
        """`adventure`: True for the default adventure, an adventure's name or file path, or False."""
        self.auto_end_turn = auto_end_turn
        self.errors: list[str] = []  # tracebacks of commands that hit a bug; the game goes on
        # what a 'yes' does next: a line offered by "Did you mean ...?", or commands waiting for
        # "Are you sure?"
        self.pending: str | list[dict] | None = None
        self.session = Session(seed=seed)
        self.game = self.session.game
        self.game.decider = decider
        self.llm = llm
        if adventure:
            from . import scenario
            from .adventure import Adventure

            data = scenario.load(adventure if isinstance(adventure, str) else scenario.DEFAULT)
            self.session.adventure = Adventure(self.session, data)

    def begin(self) -> str:
        adv = self.session.adventure
        about = f"This adventure: {adv.title}. {adv.data.get('about', '')}\n" if adv is not None else ""
        return (
            "Welcome to DungDra, a fifth-edition-compatible adventure.\n"
            + about
            + "Create your party: describe a character (e.g. 'A dwarf fighter, ex-soldier, standard "
            "array ...'), "
            "or type 'use the sample party'. Type 'begin the adventure' when everyone is ready."
        )

    def say(self, text: str) -> str:
        """One line of player input in, narration out. A bug in the engine never ends the game:
        the command stops, the traceback goes to `errors`, and the player is told."""
        start = len(self.game.log)
        try:
            return self._say(text)
        except Exception:
            self.errors.append(f"> {text}\n{traceback.format_exc()}")
            done = self._events(start)
            return (done + "\n" if done else "") + (
                "(That command ran into a bug in the game and was stopped. The game goes on; "
                "what happened above still counts.)"
            )

    def _say(self, text: str) -> str:
        t = text.strip()
        low = re.sub(r"\s+", " ", t.lower()).strip(" .!?")
        offered, self.pending = self.pending, None
        if offered and low in YES:
            if isinstance(offered, list):
                return self._run(offered)
            t = low = offered
        elif offered and low in ("no", "n", "nope", "no thanks"):
            return "OK."
        if SAMPLE_PARTY.fullmatch(low):
            for n in ("BROM", "LIDDA", "MIALEE", "JOZAN"):
                self.session.execute({"cmd": "fixture", "name": n})
            return "The sample party joins you: " + ", ".join(p.name for p in self.game.pcs()) + "."
        if BEGIN.fullmatch(low):
            if not self.game.pcs():
                return "Create at least one character first."
            start = len(self.game.log)
            self.session.adventure.start()
            return self._events(start)
        cmds = self.llm.translate(self, t) if self.llm is not None else nl.parse(self.session, t)
        if isinstance(cmds, dict) and "create" in cmds:
            return self._create(cmds["create"])
        if isinstance(cmds, dict):
            said = cmds.get("say", "")
            guess = self._guess(low) if said.startswith("I didn't catch that") else None
            if guess:
                self.pending = guess
                return f"I didn't catch that. Did you mean '{guess}'? Say 'yes' to do that."
            return said
        caught = [c for cmd in cmds for c in self.session.would_harm(cmd)]
        if caught:
            self.pending = cmds
            names = list(dict.fromkeys(c.name for c in caught))
            who = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
            not_foes = "who isn't your enemy" if len(names) == 1 else "who aren't your enemies"
            return f"That would harm {who}, {not_foes}. Do it anyway? Say 'yes' or 'no'."
        return self._run(cmds)

    def _run(self, cmds: list[dict]) -> str:
        """Carry out the commands in order, stopping at the first one the rules refuse."""
        out = []
        for cmd in cmds:
            res = self.session.execute(cmd)
            out += res["events"]
            if not res["ok"]:
                out.append(f"(Refused) {res['error']}")
                break
            r = res.get("result")
            if isinstance(r, str) and cmd["cmd"] in SHOWN:
                out.append(r)
        out += self._turn_flow(cmds)
        return "\n".join(x for x in out if x)

    def _guess(self, low: str) -> str | None:
        """The known command the line most likely misspells, if one is close enough."""
        adv = self.session.adventure
        places = [f"go to {p['name'].lower()}" for p in adv.places.values()] if adv is not None else []
        close = difflib.get_close_matches(low, [*KNOWN, *places], n=1, cutoff=0.8)
        return close[0] if close else None

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
