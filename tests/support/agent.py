"""A scripted 'player agent' that plays through the natural-language interface."""


def pc_turn(p, cur):
    g = p.game
    out = []
    foes = [e for e in g.enemies_of(cur) if e.conscious and not e.notes.get("fled")]
    if not foes:
        return p.say("end turn")
    visible = [f for f in foes if g.can_see(cur, f)]
    tgt = min(visible or foes, key=lambda f: (cur.distance_to(f), f.hp))
    if cur.has("prone") and cur.speed() > 0:
        out.append(p.say(f"{cur.name} stands up"))
    down = [a for a in g.pcs() if a.hp == 0 and not a.dead and not a.stable]
    if cur.name == "JOZAN" and down and (cur.slots_left(1) or cur.slots_left(2)):
        out.append(p.say(f"JOZAN casts healing word on {down[0].name}"))
    if not visible:
        out.append(p.say(f"{cur.name} searches for hidden enemies"))
        out.append(p.say("end turn"))
        return "\n".join(out)
    if cur.name == "MIALEE":
        spell = "magic missile" if cur.slots_left(1) and tgt.hp > 5 else "fire bolt"
        out.append(p.say(f"MIALEE casts {spell} at {tgt.name}"))
    elif cur.name == "JOZAN":
        if not g.combat.turn.action_available():
            pass
        else:
            out.append(p.say(f"JOZAN casts sacred flame at {tgt.name}"))
    elif cur.name == "LIDDA":
        out.append(p.say(f"LIDDA shoots {tgt.name} with her shortbow"))
    else:
        if cur.distance_to(tgt) > 5:
            out.append(p.say(f"{cur.name} moves 30 feet toward {tgt.name}"))
        if cur.distance_to(tgt) <= 5:
            out.append(p.say(f"{cur.name} attacks {tgt.name} with his longsword"))
        elif cur.inventory.find("javelin"):
            out.append(p.say(f"{cur.name} throws a javelin at {tgt.name}"))
    out.append(p.say("end turn"))
    return "\n".join(out)


def fight(p, limit=80):
    log = []
    for _ in range(limit):
        if p.game.combat is None:
            break
        log.append(pc_turn(p, p.game.combat.current))
    return "\n".join(log)
