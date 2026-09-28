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
