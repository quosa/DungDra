# T-79: a proposed ruling for where a Cube placed at a point sits (GLOSS.cube, Web)

The SRD says a Cube's point of origin is "anywhere on a face" (GLOSS.cube#1), and Web's webs
"fill a 20-foot Cube there", at the chosen point. It doesn't say which face holds the point, or
where on that face the point lies. The register doesn't cover this either: R-30 aligns a Cube to
the grid and counts a creature by the centre of its space, and R-31 leaves out the creature at the
origin.

**What the engine does now (T-79), up for a person's decision:** the Cube rests on the floor of
the chosen space. Its origin is the centre of the bottom face, it rises `side` ft and it reaches
`side/2` to each side, as `in_cube_direction` already does across its axis (see
`dungdra/geometry.py::in_cube_resting`). The engine counts a creature by the centre of its space,
2.5 ft above the elevation it stands at (R-30). So a creature standing on the chosen point is in
the Cube, and only the floor point itself is "the origin" (GLOSS.cube#3, R-31). This keeps
SPELLS-06 (Web cast on a goblin with no point catches that goblin) and Web's "layered across a
floor" wording.

**Open points for the ruling:**

1. Should the floor-resting placement be the default, or should the caster choose a face and
   direction, the way Thunderwave's direction is chosen?
2. With an even side (20 ft) and the origin at the centre of a square, `side/2` inclusive takes
   in 5 squares across, not 4. Thunderwave's `in_cube_direction` already has the same
   inclusive-width convention. R-30 says a Cube holds whole squares, so a 20-ft Cube should take
   in 4×4. Which 4 (that is, where on the face the origin lies) is a choice the SRD leaves to the
   caster.
3. Does a caster who places Web on a named creature's own space "decide otherwise" under
   GLOSS.cube#3? This reading avoids that question, because the origin is on the floor and not at
   anyone's centre.
