"""Combat encounter budgets and XP awards (Gameplay Toolbox p.202-203, p.255)."""
from __future__ import annotations

from .data.monsters import MONSTERS
from .monster import Monster
from .rules import Refusal, norm

XP_BUDGET = {1: (50, 75, 100), 2: (100, 150, 200), 3: (150, 225, 400), 4: (250, 375, 500)}
DIFFICULTIES = ("low", "moderate", "high")

TERRAIN_MONSTERS = {
    "forest": ["wolf", "goblin warrior", "goblin minion", "bandit", "giant rat", "goblin boss", "ogre"],
    "road": ["bandit", "goblin warrior", "wolf", "guard"],
    "dungeon": ["skeleton", "zombie", "giant rat", "kobold warrior", "cultist", "goblin warrior"],
    "hill": ["goblin warrior", "wolf", "ogre", "kobold warrior"],
    "urban": ["bandit", "cultist", "guard", "giant rat"],
}


def budgets(levels: list[int]) -> dict[str, int]:
    """p.202: per-character budget by level, summed over the party (no multipliers)."""
    out = {d: 0 for d in DIFFICULTIES}
    for lvl in levels:
        for d, v in zip(DIFFICULTIES, XP_BUDGET[lvl]):
            out[d] += v
    return out


def encounter_xp(monsters) -> int:
    total = 0
    for m in monsters:
        total += m.xp if hasattr(m, "xp") else MONSTERS[norm(m)]["xp"]
    return total


def rate(game, levels, monsters, gm_log=True) -> dict:
    """Rate an encounter. The rating goes to the GM log only; players never see budgets (R-03)."""
    b = budgets(levels)
    xp = encounter_xp(monsters)
    if xp <= b["low"]:
        band = "low"
    elif xp <= b["moderate"]:
        band = "moderate"
    elif xp <= b["high"]:
        band = "high"
    else:
        band = "over high"
    party_level = max(levels)
    crs = [m.cr if hasattr(m, "cr") else MONSTERS[norm(m)]["cr"] for m in monsters]
    strong = [c for c in crs if c > party_level]
    res = {"xp": xp, "budgets": b, "band": band, "cr_above_level": bool(strong)}
    if gm_log:
        text = (f"Encounter rating: {xp} XP vs budgets Low {b['low']} / Moderate {b['moderate']} / High {b['high']} "
                f"→ {'Over High budget' if band == 'over high' else band.title()}")
        if strong:
            text += f"; a creature's CR ({max(strong):g}) is above the party's level {party_level} (p.203)"
        game.log.gm("encounter", text, page=202, ruling="R-03" if band == "over high" else None, **res)
    return res


def add_reinforcements(game, levels, current, new, justification: str | None = None):
    """R-03: block additions that would push an encounter over High unless justified (logged GM-only)."""
    after = list(current) + list(new)
    r = rate(game, levels, after, gm_log=False)
    if r["band"] == "over high":
        if not justification:
            raise Refusal("Those reinforcements would push the encounter over the High budget; blocked (R-03). "
                          "Provide a justification to override.", ruling="R-03")
        game.log.gm("encounter", f"Reinforcements push the encounter over High ({r['xp']} XP); justification: "
                    f"{justification}", ruling="R-03", page=202)
    return after


def build(game, levels, difficulty="moderate", terrain="forest", rng=None) -> list[str]:
    """Generate an encounter from subset monsters, spending the budget without going over."""
    difficulty = norm(difficulty)
    budget = budgets(levels)[difficulty]
    pool = [m for m in TERRAIN_MONSTERS.get(norm(terrain), TERRAIN_MONSTERS["forest"])
            if MONSTERS[m]["xp"] <= budget and not MONSTERS[m].get("mount")]
    rng = rng or game.dice.rng
    party_level = max(levels)
    pool = [m for m in pool if MONSTERS[m]["cr"] <= party_level] or pool
    chosen, left = [], budget
    lead = max(pool, key=lambda m: MONSTERS[m]["xp"])
    # pick a lead monster, then fill with its allies
    lead = rng.choice([m for m in pool if MONSTERS[m]["xp"] >= min(MONSTERS[x]["xp"] for x in pool)])
    while left >= MONSTERS[lead]["xp"] and len(chosen) < 2 * len(levels):
        chosen.append(lead)
        left -= MONSTERS[lead]["xp"]
        cheaper = [m for m in pool if MONSTERS[m]["xp"] <= left]
        if not cheaper:
            break
        lead = rng.choice(cheaper)
    features = {"forest": "a fallen log and thick undergrowth (Difficult Terrain) give cover",
                "road": "an overturned wagon offers Half Cover", "dungeon": "a pillar-lined hall with a collapsed "
                "section of floor", "hill": "a rocky rise gives the high ground", "urban": "crates and an alley"}
    game.log.gm("encounter", f"Generated {difficulty} {terrain} encounter: {', '.join(m.title() for m in chosen)} "
                f"({budget - left}/{budget} XP); terrain: {features.get(norm(terrain), 'broken ground')}", page=202)
    return chosen


def spawn(game, keys, positions=None, team="enemy"):
    mons = []
    counts = {}
    for i, k in enumerate(keys):
        counts[k] = counts.get(k, 0) + 1
        same = sum(1 for x in keys if x == k)
        name = f"{k.title()}" + (f" {counts[k]}" if same > 1 else "")
        m = Monster(k, name=name)
        pos = positions[i] if positions else (30 + 5 * i, 0)
        game.add(m, team=team, position=pos)
        mons.append(m)
    return mons


def award_xp(game, monsters, pcs, reason="defeated foes"):
    """R-02: divide the XP total evenly among participating PCs, rounding down.
    Defeated or neutralized (fled, surrendered, pacified) foes count (p.255)."""
    total = encounter_xp(monsters)
    share = total // max(1, len(pcs))
    game.log.player("xp", f"{total} XP for {reason}, divided among {len(pcs)} PCs: {share} each", page=255,
                    ruling="R-02")
    for pc in pcs:
        pc.award_xp(share, reason, ruling="R-02")
    return share
