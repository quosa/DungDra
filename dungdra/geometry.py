"""Positions and distances (feet). The grid uses the SRD's 5-ft squares with
diagonals counting 5 ft (Chebyshev distance), plus elevation."""

from __future__ import annotations


def distance(a, b) -> int:
    ax, ay = a.position
    bx, by = b.position
    dz = abs(getattr(a, "elevation", 0) - getattr(b, "elevation", 0))
    return max(abs(ax - bx), abs(ay - by), dz)


def dist_points(p, q) -> int:
    return max(abs(p[0] - q[0]), abs(p[1] - q[1]))


def step_toward(p, q, feet) -> tuple[int, int]:
    """Move from p toward q by up to `feet` (in 5-ft steps)."""
    x, y = p
    moved = 0
    while moved + 5 <= feet and (x, y) != tuple(q):
        x += (q[0] > x) * 5 - (q[0] < x) * 5
        y += (q[1] > y) * 5 - (q[1] < y) * 5
        moved += 5
    return (x, y)


def step_away(p, q, feet) -> tuple[int, int]:
    """Move from p directly away from q by `feet`."""
    x, y = p
    dx = (x > q[0]) - (x < q[0])
    dy = (y > q[1]) - (y < q[1])
    if dx == 0 and dy == 0:
        dx = 1
    steps = feet // 5
    return (x + dx * 5 * steps, y + dy * 5 * steps)


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
