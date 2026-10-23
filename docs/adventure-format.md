# Adventure files

An adventure is a JSON file of places joined by exits. The ones that come with the game live in
`dungdra/data/adventures/`; play one with `python -m dungdra --adventure <name>`, or pass the path
of your own file. The file is checked when it is read, and a mistake is reported with where it
is (`goblin-trail: places.road.ambush.monsters: no monster 'gobln'`).

```json
{
  "title": "The Goblin Trail",
  "about": "One line for the player: what the adventure is.",
  "start": "village",
  "places": {
    "village": {
      "name": "Millbrook",
      "text": "What the party sees when it arrives.",
      "exits": [{"to": "road", "travel": {"miles": 6, "pace": "normal", "terrain": "forest", "road": true}}]
    },
    "road": { "name": "The Forest Road", "text": "…" }
  }
}
```

## A place

| Key | What |
|---|---|
| `name`, `text` | Required. The name the player uses (`go to the forest road`) and the description. |
| `aliases` | Other names the player may use for it. |
| `exits` | Where the party can go from here (below). |
| `light` | `bright` (default), `dim` or `dark`. `sunlight: true` for daylight. |
| `ground` | Difficult Terrain: `"heavy snow"` for the whole place, or a list of patches `{"kind": "rubble", "rect": [x0, y0, x1, y1]}`. The kinds are heavy snow, ice, rubble and undergrowth (p.181). |
| `encounter` | A fight when the party first arrives: `{"monsters": ["goblin warrior"], "positions": [[30, 0]]}`. |
| `ambush` | A fight with hidden attackers: an encounter plus `hide_total` (their Stealth) and `text`. |
| `traps` | `[{"kind": "hidden pit", "location": "the hall floor"}]`. |
| `loot` | `{"items": ["potion of healing"], "gp": 30}`, picked up by the first character on their feet when the party leaves, or with `open the chest`. A `poisoned needle` trap locks it in a chest: the party must open or leave the chest to press on, and turning back leaves it locked. |
| `ending` | Said when the party says `continue` here and the place has no exit of its own: the adventure ends. |

| `shop` | `{"name": "the general store", "sells": ["rope", "iron spikes"], "buys": true}`. Without `sells` it stocks every weapon, armor and piece of gear at list price (p.89). When an adventure has any shop, buying and selling happen only at one. |
| `inn` | `{"name": "The Sleepy Ferret", "room": "modest"}`: `rent a room` is a Long Rest, each character paying a day of that lifestyle (p.101). |
| `people` | `[{"id": "reeve", "name": "Reeve Alda", "text": "…", "says": "…", "quest": "rats"}]`. `talk to <name>` hears `says`. A person with `"creature": "guard"` also stands in the place as that creature, with `attitude` (friendly, indifferent, hostile) and `side` (neutral, party, enemy). |

A place's fight and traps happen the first time the party arrives. What is left there (a trap, a
web, Difficult Terrain) is still there when it comes back.

## An exit

`{"to": "road"}` leads to the place `road` and back. `"one_way": true` makes it one way only.
`"travel"` is the overland travel it takes (`miles` or `hours`, `pace`, `terrain`, `road`), resolved
by the travel rules (p.12) each time the party goes that way.

The party moves with `continue` (the place's first exit), `go to <place>` (any place it can
reach, one place at a time), and `go back` (retracing the way it came, one place at a time). `exits` describes the place,
and `map` lists the places visited and their ways on.

## Quests

`"quests"` at the top of the file names each quest and who gives it:

```json
"quests": {
  "rats": {
    "title": "Rats in the Cellar",
    "giver": "reeve",
    "offer": "Clear the rats out of the cellar and I'll pay you 40 gold.",
    "goal": {"defeat": "cellar"},
    "reward": {"gp": 40, "xp": 25, "items": ["potion of healing"]},
    "done": "The reeve counts out the coins."
  }
}
```

The giver offers it when the party talks to them (`accept the quest` takes it on). The goal is
`defeat` (every monster of that place's encounter or ambush is dead or fled) or `bring` (someone
in the party carries the item). Talking to the giver, or `turn in the quest` where they are, then
pays the reward: the gold is shared out, each character gains the `xp`, and the items go to the
first character on their feet. Monsters defeated on the way give their own XP as usual (R-02).
`quests` lists the party's quests.

## Positions

Positions are in feet on the 5-ft grid. On arrival the party stands in marching order at
`(0, 0)`, `(0, 5)`, `(0, 10)`, …, so monsters 30 feet east stand at `[30, 0]`. A `rect` holds the
squares whose corners lie between its two corners, edges included.
