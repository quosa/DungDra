"""Positions and distances (feet). The grid uses the SRD's 5-ft squares with
diagonals counting 5 ft (Chebyshev distance), plus elevation."""

from __future__ import annotations


def distance(a, b) -> int:
    ax, ay = a.position
    bx, by = b.position
    dz = abs(getattr(a, "elevation", 0) - getattr(b, "elevation", 0))
    return max(abs(ax - bx), abs(ay - by), dz)


def dist_points(p, q) -> int:
    """Distance between two points (x, y) or (x, y, elevation); a point without an elevation is
    on the ground."""
    return max(abs(a - b) for a, b in zip(_xyz(p), _xyz(q), strict=True))


def _xyz(p) -> tuple:
    return (p[0], p[1], p[2] if len(p) > 2 else 0)


def step_toward(p, q, feet) -> tuple[int, int]:
    """Move from p toward q by up to `feet` (in 5-ft steps)."""
    x, y = p
    moved = 0
    while moved + 5 <= feet and (x, y) != tuple(q):
        x += (q[0] > x) * 5 - (q[0] < x) * 5
        y += (q[1] > y) * 5 - (q[1] < y) * 5
        moved += 5
    return (x, y)


def steps_between(p, q) -> list[tuple[int, int]]:
    """The squares (by corner) a mover enters walking from p toward q in 5-ft steps, in order;
    p's own square isn't one of them."""
    out = []
    here = tuple(p[:2])
    for _ in range(dist_points(p[:2], q[:2]) // 5):
        here = step_toward(here, q[:2], 5)
        out.append(here)
    return out


def squares_overlap(a, a_side, b, b_side) -> bool:
    """Do the squares at corners a and b (lowest x, y) with edges a_side and b_side share any
    interior? Touching an edge or a corner doesn't count."""
    return all(a[i] < b[i] + b_side and b[i] < a[i] + a_side for i in (0, 1))


def step_away(p, q, feet) -> tuple[int, int]:
    """Move from p directly away from q by `feet`."""
    x, y = p
    dx = (x > q[0]) - (x < q[0])
    dy = (y > q[1]) - (y < q[1])
    if dx == 0 and dy == 0:
        dx = 1
    steps = feet // 5
    return (x + dx * 5 * steps, y + dy * 5 * steps)


def _along_across(origin, toward, p):
    """p's distance along the axis from `origin` through `toward`, and its distance from that axis
    (None for an axis of no length). Points are (x, y) or (x, y, elevation)."""
    o, t, q = _xyz(origin), _xyz(toward), _xyz(p)
    u = [b - a for a, b in zip(o, t, strict=True)]
    norm = sum(x * x for x in u) ** 0.5
    if norm == 0:
        return None
    v = [b - a for a, b in zip(o, q, strict=True)]
    along = sum(a * b for a, b in zip(v, u, strict=True)) / norm
    cross = (v[1] * u[2] - v[2] * u[1], v[2] * u[0] - v[0] * u[2], v[0] * u[1] - v[1] * u[0])
    return along, sum(x * x for x in cross) ** 0.5 / norm


def in_cone_direction(origin, toward, p) -> bool:
    """Is p inside the (unbounded) Cone from `origin` aimed at `toward`? A Cone's width at any point
    equals that point's distance from the origin, so p may stray at most half its distance along
    the axis from it, up and down as well as sideways. The origin itself isn't included. Length is
    checked by the caller."""
    aa = _along_across(origin, toward, p)
    if aa is None:
        return False
    along, across = aa
    return along > 0 and across <= along / 2


def in_cube_direction(origin, toward, p, side) -> bool:
    """Is p inside the level Cube whose `origin` is the centre of one face, extending `side` feet
    toward `toward` and half of `side` to either side of the axis and above and below the origin?
    The origin itself isn't included."""
    o, t, q = _xyz(origin), _xyz(toward), _xyz(p)
    aa = _along_across(o[:2], t[:2], q[:2])
    if aa is None:
        return False
    along, across = aa
    return 0 < along <= side and across <= side / 2 and abs(q[2] - o[2]) <= side / 2


def in_cube_at_point(square, p, side) -> bool:
    """Is p inside the Cube placed at the point `square`, resting on the ground there and extending
    `side` feet upward (R-35)? An odd number of squares centres on `square`; an even number can't,
    so it centres on that square's top-right corner (+x/+y)."""
    # SRD[GLOSS.cube#1] the point of origin is the centre of the Cube's bottom face (R-35)
    o, q = _xyz(square), _xyz(p)
    shift = 2.5 if (side // 5) % 2 == 0 else 0
    cx, cy = o[0] + shift, o[1] + shift
    # SRD[GLOSS.cube#2] each side is the Cube's size; a creature is in it when its centre is (R-27)
    return abs(q[0] - cx) <= side / 2 and abs(q[1] - cy) <= side / 2 and 0 <= q[2] - o[2] <= side


# SRD[SPELL.casting-spells.effects.targets#5] the area shapes the engine has geometry for
def in_area(shape, size, origin, p, toward=None) -> bool:
    """Is p inside an area of `shape` ("cone", "cube" or "sphere") and `size` (a Cone's length, a
    Cube's side, a Sphere's radius) from `origin`? A Cone or Cube points at `toward`; a Cube
    without a direction is placed at the point `origin` (R-35); a Sphere is centred on `origin`.
    Points are (x, y) or (x, y, elevation). A "rect" isn't a spell's area but a footprint on a
    map (a patch of rubble, a road): `origin` holds two opposite corners (x0, y0, x1, y1), and the
    squares whose corners lie between them, edges included, are inside at any height."""
    shape = shape.lower()
    if shape == "rect":
        x0, y0, x1, y1 = origin
        q = _xyz(p)
        return min(x0, x1) <= q[0] <= max(x0, x1) and min(y0, y1) <= q[1] <= max(y0, y1)
    if shape == "sphere":
        return dist_points(origin, p) <= size
    if shape == "cube" and toward is None:
        return in_cube_at_point(origin, p, size)
    if toward is None:
        raise ValueError(f"a {shape} needs a direction")
    if shape == "cone":
        return dist_points(origin, p) <= size and in_cone_direction(origin, toward, p)
    if shape == "cube":
        return in_cube_direction(origin, toward, p, size)
    raise ValueError(f"no geometry for a {shape}")


def segment_crosses_square(p, q, corner, side) -> bool:
    """Does the open segment p→q pass through the interior of the square at `corner`
    (lowest x, y) with edge `side`? Touching an edge or a corner doesn't count."""
    t0, t1 = 0.0, 1.0
    for a, b, lo in ((p[0], q[0], corner[0]), (p[1], q[1], corner[1])):
        d = b - a
        hi = lo + side
        if d == 0:
            if not lo < a < hi:
                return False
            continue
        ta, tb = sorted(((lo - a) / d, (hi - a) / d))
        t0, t1 = max(t0, ta), min(t1, tb)
    return t0 < t1
