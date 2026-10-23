"""Towns in an adventure: shops, inns, the people in a place and the quests they give.

Mixed into `Adventure`, which supplies the game, the places, the current place and the fights
already fought. Prices and lodging come from the equipment rules (p.89, p.101); quest rewards are
the adventure's own, given out by the person who set the quest.
"""

from __future__ import annotations

from string import capwords

from . import encounters as E
from . import gear
from . import magic_items as MI
from .data.equipment import LIFESTYLE, canonical, item_cost
from .items import fmt_cp
from .rules import XP_BY_LEVEL, Refusal, norm


def _give(pc, name: str):
    """Put an item in a character's pack: equipment by its name, anything else as a magic item."""
    if item_cost(canonical(name)) is not None:
        pc.inventory.add(canonical(name), 1)
    else:
        pc.inventory.add(MI.make(name, identified=True))


class TownMixin:
    def _town_init(self):
        self.quest_state: dict[str, str] = {}  # quest id -> "offered", "active" or "done"
        self.offered: str | None = None  # the quest most recently offered, for 'accept the quest'
        self.spawned: dict[str, list[str]] = {}  # place id -> ids of the monsters fought there
        self.standing: dict[str, str] = {}  # person id -> id of the creature standing for them

    @property
    def quests(self) -> dict:
        return self.data.get("quests", {})

    def _here(self) -> dict:
        return self.places[self.current]

    # -- what a place offers --------------------------------------------------------------
    def town_text(self) -> str:
        """Who and what is here, with what to say to use it."""
        p, lines = self._here(), []
        people = [x for x in p.get("people", []) if not self._is_dead(x)]
        if people:
            lines.append("Here: " + ", ".join(x["name"] for x in people) + " (say 'talk to <name>').")
        if "shop" in p:
            lines.append(f"{_shop_name(p['shop'])} is open (say 'shop' to see the wares).")
        if "inn" in p:
            lines.append(f"{p['inn'].get('name', 'The inn')} has rooms (say 'rent a room').")
        return "\n".join(lines)

    def place_people(self, p: dict):
        """People who stand in the place as creatures appear there the first time the party comes."""
        for i, person in enumerate(p.get("people", [])):
            if "creature" not in person:
                continue
            pos = tuple(person.get("position", (20, 5 * i)))
            (c,) = E.spawn(self.game, [person["creature"]], [pos], team=person.get("side", "neutral"))
            c.name = person["name"]
            c.attitude = person.get("attitude", "indifferent")
            self.standing[person["id"]] = c.id

    def _is_dead(self, person: dict) -> bool:
        c = self.game.creatures.get(self.standing.get(person["id"], ""))
        return c is not None and c.dead

    def _person(self, who: str) -> dict:
        w = norm(who).removeprefix("the ")
        for person in self._here().get("people", []):
            names = {norm(person["name"]), norm(person["id"])} | set(norm(person["name"]).split())
            if w in names or norm(person["name"]) in w:
                if self._is_dead(person):
                    raise Refusal(f"{person['name']} is dead.")
                return person
        here = [x["name"] for x in self._here().get("people", [])]
        raise Refusal(f"There's nobody called '{who}' here." + (f" Here: {', '.join(here)}." if here else ""))

    # -- talking and quests -----------------------------------------------------------------
    def talk(self, who: str) -> str:
        person = self._person(who)
        out = [f"{person['name']}: {person.get('says', person['text'])}"]
        qid = person.get("quest")
        if qid is None:
            return "\n".join(out)
        q, state = self.quests[qid], self.quest_state.get(qid)
        if state in (None, "offered"):
            self.quest_state[qid], self.offered = "offered", qid
            out += [q["offer"], "(Say 'accept the quest' to take it on.)"]
        elif state == "active":
            out.append(
                self._complete(qid)
                if self.goal_met(qid)
                else f"“{q['title']}” isn't done yet: {self.goal_text(q)}."
            )
        else:
            out.append(f"(You've done “{q['title']}” for {person['name']}.)")
        return "\n".join(out)

    def accept(self) -> str:
        qid = self.offered
        if qid is None or self.quest_state.get(qid) != "offered":
            raise Refusal("Nobody has offered you a quest just now. Talk to the people here first.")
        q = self.quests[qid]
        self.quest_state[qid], self.offered = "active", None
        self.game.log.player("quest", f"Quest accepted: “{q['title']}”: {self.goal_text(q)}.")
        return "(Say 'quests' to see your quests.)"

    def journal(self) -> str:
        if not self.quest_state:
            return "You have no quests yet. Talk to the people you meet."
        lines = ["Quests:"]
        for qid, state in self.quest_state.items():
            q = self.quests[qid]
            if state == "active":
                lines.append(
                    f"  “{q['title']}”: {self.goal_text(q)}"
                    + (" (done: go back to report)" if self.goal_met(qid) else "")
                )
            elif state == "done":
                lines.append(f"  “{q['title']}”: complete")
            else:
                lines.append(
                    f"  “{q['title']}”: offered by {self._giver(q)['name']} (say 'accept the quest')"
                )
        return "\n".join(lines)

    def turn_in(self) -> str:
        here = {x["id"] for x in self._here().get("people", [])}
        active = [
            qid
            for qid, st in self.quest_state.items()
            if st == "active" and self.quests[qid]["giver"] in here
        ]
        if not active:
            raise Refusal("There's nobody here waiting for a quest of yours.")
        done = [qid for qid in active if self.goal_met(qid)]
        if not done:
            q = self.quests[active[0]]
            raise Refusal(f"“{q['title']}” isn't done yet: {self.goal_text(q)}.")
        return "\n".join(self._complete(qid) for qid in done)

    def _giver(self, q: dict) -> dict:
        return next(x for p in self.places.values() for x in p.get("people", []) if x["id"] == q["giver"])

    def goal_text(self, q: dict) -> str:
        goal = q["goal"]
        if "defeat" in goal:
            return f"defeat what lurks in {self.places[goal['defeat']]['name']}"
        return f"bring {capwords(goal['bring'])} to {self._giver(q)['name']}"

    def goal_met(self, qid: str) -> bool:
        goal, g = self.quests[qid]["goal"], self.game
        if "defeat" in goal:
            pid = goal["defeat"]
            foes = [g.creatures[i] for i in self.spawned.get(pid, []) if i in g.creatures]
            return pid in self.fought and all(c.dead or c.notes.get("fled") for c in foes)
        return any(not p.dead and p.inventory.find(goal["bring"]) for p in g.pcs())

    def _complete(self, qid: str) -> str:
        g, q = self.game, self.quests[qid]
        self.quest_state[qid] = "done"
        living = [p for p in g.pcs() if not p.dead]
        if "bring" in q["goal"]:
            holder = next(p for p in living if p.inventory.find(q["goal"]["bring"]))
            holder.inventory.remove(q["goal"]["bring"], 1)
        reward, paid = q["reward"], []
        if reward.get("gp"):
            share, extra = divmod(reward["gp"], len(living))
            for i, p in enumerate(living):
                p.purse.add(gp=share + (1 if i < extra else 0))
            paid.append(f"{reward['gp']} GP, shared out")
        for it in reward.get("items", []):
            _give(living[0], it)
            paid.append(f"{capwords(it)} for {living[0].name}")
        g.log.player(
            "quest", f"Quest complete: “{q['title']}”." + (f" Reward: {'; '.join(paid)}." if paid else "")
        )
        for p in living if reward.get("xp") else []:
            p.award_xp(reward["xp"], f"quest: {q['title']}")
        lines = [q.get("done", f"“{q['title']}” is done."), f"Quest complete: “{q['title']}”."]
        if all(self.quest_state.get(k) == "done" for k in self.quests):
            lines.append("(Every quest here is done. Explore on, or type 'quit' to end the game.)")
        return "\n".join(lines)

    # -- shops and inns ------------------------------------------------------------------------
    def wares(self) -> str:
        shop = self._here().get("shop")
        if shop is None:
            raise Refusal(f"There's no shop in {self._here()['name']}.")
        sells, name = shop.get("sells"), _shop_name(shop)
        if not sells:
            return (
                f"{name} stocks the usual gear: weapons, armor and adventuring gear at list price "
                "(say who buys what, e.g. 'BROM buys a rope')."
            )
        lines = [f"{name} sells:"]
        lines += [f"  {capwords(it)}: {fmt_cp(int(item_cost(canonical(it)) or 0))}" for it in sells]
        lines.append("(Say who buys what, e.g. 'BROM buys " + sells[0] + "'.)")
        return "\n".join(lines)

    def check_trade(self, item: str, selling: bool = False):
        """Buying and selling happen at a shop, when the adventure has shops; the shop decides what
        it sells and whether it buys."""
        if self.current is None or not any("shop" in p for p in self.places.values()):
            return
        shop = self._here().get("shop")
        if shop is None:
            raise Refusal(f"There's no shop in {self._here()['name']}.")
        if selling and not shop.get("buys", True):
            raise Refusal(f"{_shop_name(shop)} doesn't buy anything.")
        sells = [canonical(x) for x in shop.get("sells", [])]
        if not selling and sells and canonical(item) not in sells:
            raise Refusal(f"{_shop_name(shop)} doesn't sell {item}. Say 'shop' to see the wares.")

    def rent_room(self) -> str:
        inn, g = self._here().get("inn"), self.game
        if inn is None:
            raise Refusal(f"There's no inn in {self._here()['name']}.")
        if g.combat is not None:
            raise Refusal("Not in the middle of a fight")
        room, name = inn.get("room", "modest"), inn.get("name", "the inn")
        guests = [p for p in g.pcs() if not p.dead]
        for p in guests:
            if p.purse.total_cp() < LIFESTYLE[room]:
                raise Refusal(f"{p.name} can't afford a night at {name} ({fmt_cp(LIFESTYLE[room])})")
        res = self.session.execute({"cmd": "long_rest"})
        if not res["ok"]:
            raise Refusal(res["error"])
        gear.live(g, guests, room, 1, advance=False)
        return f"The party spends the night at {name}."


def _shop_name(shop: dict) -> str:
    name = shop.get("name", "the shop")
    return name[0].upper() + name[1:]


def xp_text(pc) -> str:
    """Level, XP toward the next level, and coins: the progress line in 'status'."""
    nxt = XP_BY_LEVEL.get(pc.level + 1)
    return f"Level {pc.level}, XP {pc.xp}" + (f"/{nxt}" if nxt else "") + f", {pc.purse}"
