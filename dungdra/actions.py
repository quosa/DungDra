"""Non-attack actions from the Rules Glossary: Help, Hide, Influence, Search,
Study, Utilize (tools), Dash, Disengage, Dodge, Ready (p.176-191)."""
from __future__ import annotations

from .data.equipment import TOOLS, canonical
from .effects import AdvNext, Dodge, Flag, HelpAttack
from .rules import DAY, SKILLS, Refusal, norm


def spend(game, actor, what="action", label=""):
    """Spend an action/bonus action/reaction when in combat (no-op outside combat)."""
    if game.combat is not None:
        game.combat.spend(actor, what, label)


# -- Help (p.182-183) ---------------------------------------------------------
def help_check(game, helper, ally, skill=None, tool=None):
    if not helper.can_act():
        raise Refusal(f"{helper.name} can't take actions right now")
    if tool:
        tool = canonical(tool)
        if not helper.has_tool_prof(tool):
            raise Refusal(f"{helper.name} can only Help with a skill or tool they are proficient in "
                          f"(not proficient with {tool.title()})", page=182)
    elif skill:
        skill = norm(skill)
        if skill not in helper.skills:
            raise Refusal(f"{helper.name} can only Help with a skill or tool they are proficient in "
                          f"(not proficient in {skill.title()})", page=182)
    else:
        raise Refusal("Choose one of your skill or tool proficiencies to Help with")
    spend(game, helper, "action", "Help")
    what = (skill or tool).title()
    eff = AdvNext(f"Help from {helper.name} ({what})", kinds=("check",), skill=skill, tool=tool,
                  caster=helper, ends=[("start", helper.id)])
    ally.add_effect(eff)
    game.log.player("help", f"{helper.name} Helps {ally.name}: Advantage on the next {what} check "
                    f"before the start of {helper.name}'s next turn", page=183)
    return eff


def help_attack(game, helper, enemy):
    if not helper.can_act():
        raise Refusal(f"{helper.name} can't take actions right now")
    d = helper.distance_to(enemy)
    if d > 5:
        raise Refusal(f"{enemy.name} is {d} ft away; Help can only distract an enemy within 5 feet", page=183)
    spend(game, helper, "action", "Help")
    eff = HelpAttack(f"Help from {helper.name}", caster=helper, ends=[("start", helper.id)])
    enemy.add_effect(eff)
    game.log.player("help", f"{helper.name} distracts {enemy.name}: the next attack roll by an ally against it "
                    f"has Advantage (expires at the start of {helper.name}'s next turn)", page=183)
    return eff


# -- Utilize with tools (p.93-94) --------------------------------------------------
TOOL_TASKS = {
    "pick a lock": ("thieves' tools", "sleight of hand", 15),
    "disarm a trap": ("thieves' tools", "sleight of hand", 15),
}


def use_tool(game, actor, task: str, dc: int | None = None, tool: str | None = None, skill: str | None = None,
             bonus_action=False, **kw):
    task = norm(task)
    if task in TOOL_TASKS:
        t, s, d = TOOL_TASKS[task]
        tool, skill, dc = tool or t, skill or s, dc or d
    if not tool:
        raise Refusal("Which tool?")
    tool = canonical(tool)
    if tool not in TOOLS:
        raise Refusal(f"{tool!r} isn't a tool")
    if not getattr(actor, "inventory", None) or actor.inventory.find(tool) is None:
        raise Refusal(f"{actor.name} doesn't have {tool.title()}; the attempt needs them", page=94)
    if bonus_action:
        if not actor.has_feature("fast hands"):
            raise Refusal(f"{actor.name} has no feature that allows this as a Bonus Action")
        spend(game, actor, "bonus", f"Fast Hands ({task})")
    else:
        spend(game, actor, "action", f"Utilize ({task})")
    ability = TOOLS[tool]["ability"]
    return actor.check(skill=skill, ability=ability, dc=dc, tool=tool,
                       label=f"{task.capitalize()} ({ability.title()} check with {tool.title()})", **kw)


# -- Dash / Disengage / Dodge (p.180-181) -----------------------------------------
def dash(game, actor, bonus=False, source="Dash"):
    spend(game, actor, "bonus" if bonus else "action", source)
    if game.combat:
        game.combat.turn.movement_left += actor.speed()
        game.combat.turn.dashes += 1
    game.log.player("action", f"{actor.name} takes the Dash action" + (" as a Bonus Action" if bonus else ""),
                    page=180)


def disengage(game, actor, bonus=False, source="Disengage"):
    spend(game, actor, "bonus" if bonus else "action", source)
    actor.add_effect(Flag("disengage", f"{source}", ends=[("end", actor.id)]))
    game.log.player("action", f"{actor.name} takes the Disengage action" + (" as a Bonus Action" if bonus else "")
                    + ": no Opportunity Attacks this turn", page=181)


def dodge(game, actor):
    spend(game, actor, "action", "Dodge")
    actor.add_effect(Dodge(f"Dodge", ends=[("start", actor.id)]))
    game.log.player("action", f"{actor.name} takes the Dodge action", page=181)


# -- Influence (p.184) -------------------------------------------------------------
INFLUENCE_SKILLS = {"deceive": "deception", "intimidate": "intimidation", "amuse": "performance",
                    "persuade": "persuasion", "coax": "animal handling"}


def influence(game, actor, npc, request: str, disposition: str, approach: str = "persuade",
              skill: str | None = None, dc: int | None = None):
    """disposition: the GM's call of how the monster feels: willing | unwilling | hesitant."""
    disposition = norm(disposition)
    key = (actor.id, npc.id, norm(request))
    until = game.influence_cooldowns.get(key)
    if until is not None and game.clock < until:
        hrs = (until - game.clock + 3599) // 3600
        raise Refusal(f"{npc.name} already refused that; wait {hrs} more hours before urging it the same way again",
                      page=184)
    spend(game, actor, "action", "Influence")
    if disposition == "willing":
        game.log.player("influence", f"{npc.name} is willing: it does as urged, no check needed ({request})",
                        page=184)
        return True
    if disposition == "unwilling":
        game.log.player("influence", f"{npc.name} is unwilling: it refuses, no check possible ({request})",
                        page=184)
        return False
    skill = skill or INFLUENCE_SKILLS.get(norm(approach), "persuasion")
    dc = dc or max(15, npc.score("int"))
    attitude = getattr(npc, "attitude", "indifferent")
    adv, dis = [], []
    if attitude == "friendly":
        adv.append(f"{npc.name} is Friendly")
    elif attitude == "hostile":
        dis.append(f"{npc.name} is Hostile")
    game.log.gm("influence_dc", f"Influence DC for {npc.name}: {dc} (15 or Int {npc.score('int')}, whichever is higher)",
                page=184)
    r = actor.check(skill=skill, dc=dc, adv=adv, dis=dis, target=npc, tags={"social"},
                    label=f"{skill.title()} check to influence {npc.name}")
    if r.success:
        game.log.player("influence", f"{npc.name} agrees: {request}", page=184)
    else:
        game.influence_cooldowns[key] = game.clock + DAY
        game.log.player("influence", f"{npc.name} won't do it; {actor.name} must wait 24 hours before urging it "
                        f"that way again", page=184)
    return r.success


# -- Search / Study (p.187, 189) -----------------------------------------------------
SEARCH_SKILLS = {"insight", "medicine", "perception", "survival"}
STUDY_SKILLS = {"arcana", "history", "investigation", "nature", "religion"}
CREATURE_TYPE_SKILL = {"aberration": "arcana", "construct": "arcana", "elemental": "arcana", "fey": "arcana",
                       "monstrosity": "arcana", "giant": "history", "humanoid": "history", "beast": "nature",
                       "dragon": "nature", "ooze": "nature", "plant": "nature", "celestial": "religion",
                       "fiend": "religion", "undead": "religion"}


def search(game, actor, skill="perception", dc=None, target=None, what="", **kw):
    skill = norm(skill)
    if skill not in SEARCH_SKILLS:
        raise Refusal(f"The Search action uses Wisdom (Insight, Medicine, Perception or Survival), not {skill.title()}",
                      page=187)
    spend(game, actor, "action", "Search")
    return actor.check(skill=skill, ability="wis", dc=dc, target=target,
                       label=f"Search: Wisdom ({skill.title()})" + (f" — {what}" if what else ""), **kw)


def study(game, actor, skill=None, dc=None, topic="", creature_type=None, **kw):
    if creature_type:
        want = CREATURE_TYPE_SKILL[norm(creature_type)]
        if skill and norm(skill) != want:
            raise Refusal(f"Lore about {creature_type.title()} creatures is {want.title()}, not {skill.title()}",
                          page=189)
        skill = want
    skill = norm(skill or "investigation")
    if skill not in STUDY_SKILLS:
        raise Refusal(f"The Study action uses Intelligence (Arcana, History, Investigation, Nature or Religion)",
                      page=189)
    spend(game, actor, "action", "Study")
    return actor.check(skill=skill, ability="int", dc=dc,
                       label=f"Study: Intelligence ({skill.title()})" + (f" — {topic}" if topic else ""), **kw)


def single_action(game, actor, actions: list[str]):
    """A creature takes one action at a time (e.g. can't Influence and Search at once)."""
    if len(actions) > 1:
        raise Refusal(f"{actor.name} can take only one action at a time: choose one of "
                      f"{', '.join(a.title() for a in actions)}", page=9)
