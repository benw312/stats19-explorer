"""Putting a road's count point links in order along it (PLAN-009 V2, the corridor view).

DfT count point links carry no sequence, so the corridor chains them geometrically: start
at a terminus (the loose end furthest from the road's middle), keep taking the nearest
unvisited link, and flip each so its near end comes first. A jump longer than GAP_KM is a
gap: the road left the area, or a section isn't counted. The result runs west to east, or
south to north when the road runs mostly north-south, so the same road always reads the
same way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]

GAP_KM = 0.2  # dual carriageway ends sit a few tens of metres apart; more is a real gap


@dataclass(frozen=True)
class Link:
    key: str
    a: Point
    b: Point
    length_km: float


@dataclass(frozen=True)
class Placed:
    key: str
    start: Point
    end: Point
    length_km: float
    gap_before_km: float


def _dist_km(p: Point, q: Point) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1]) / 1000


def link_ends(points: list[Point]) -> tuple[Point, Point]:
    """The two part ends furthest apart (a dual carriageway has two parts, four ends)."""
    if not points:
        raise ValueError("a link needs at least one point")
    best = (points[0], points[0])
    best_d = -1.0
    for i, p in enumerate(points):
        for q in points[i + 1 :]:
            d = _dist_km(p, q)
            if d > best_d:
                best, best_d = (p, q), d
    return best


def _start(links: list[Link]) -> tuple[int, bool]:
    """Where the route begins (link index, True = its b end).

    A loose end (no other link's end within GAP_KM) furthest from the middle of the road:
    a gap's ends are loose too, but they sit inside the route, nearer the middle.
    """
    ends = [
        (i, use_b, end) for i, x in enumerate(links) for use_b, end in ((False, x.a), (True, x.b))
    ]
    cx = sum(e[2][0] for e in ends) / len(ends)
    cy = sum(e[2][1] for e in ends) / len(ends)

    def loose(i: int, end: Point) -> bool:
        return all(
            min(_dist_km(end, o.a), _dist_km(end, o.b)) > GAP_KM
            for j, o in enumerate(links)
            if j != i
        )

    candidates = [e for e in ends if loose(e[0], e[2])] or ends
    i, use_b, _ = max(candidates, key=lambda e: _dist_km(e[2], (cx, cy)))
    return i, use_b


def chain(links: list[Link]) -> list[Placed]:
    """Links in order along the road, each oriented, with the gap before it."""
    if not links:
        return []
    first, start_at_b = _start(links)
    link = links[first]
    # the terminus end is where the route begins
    start, end = (link.b, link.a) if start_at_b else (link.a, link.b)
    out = [Placed(link.key, start, end, link.length_km, 0.0)]
    remaining = [x for i, x in enumerate(links) if i != first]
    while remaining:
        tip = out[-1].end
        i, d, flip = min(
            (
                (
                    i,
                    min(_dist_km(tip, x.a), _dist_km(tip, x.b)),
                    _dist_km(tip, x.b) < _dist_km(tip, x.a),
                )
                for i, x in enumerate(remaining)
            ),
            key=lambda t: t[1],
        )
        x = remaining.pop(i)
        s, e = (x.b, x.a) if flip else (x.a, x.b)
        out.append(Placed(x.key, s, e, x.length_km, 0.0))
    return _west_to_east(_with_gaps(_untangle(out)))


def _jump(p: Placed | None, q: Placed | None) -> float:
    return 0.0 if p is None or q is None else _dist_km(p.end, q.start)


def _flip(p: Placed) -> Placed:
    return Placed(p.key, p.end, p.start, p.length_km, 0.0)


def _untangle(order: list[Placed], max_passes: int = 8) -> list[Placed]:
    """Shorten the total jumps between links: 2-opt reversals, then single-link moves.

    Nearest-neighbour chaining skips short spurs and parallel pieces, then reaches them last
    with a long jump back, and on long roads with many gaps it can double back. Reversing a
    run of links (2-opt) and moving single links to their cheapest place (or-opt) fix both.
    """
    order = list(order)
    for _ in range(max_passes):
        order, reversed_any = _two_opt(order)
        order, moved_any = _or_opt(order)
        if not (reversed_any or moved_any):
            break
    return order


def _two_opt(order: list[Placed]) -> tuple[list[Placed], bool]:
    improved = False
    n = len(order)
    for i in range(n - 1):
        for j in range(i + 1, n):
            prev = order[i - 1] if i > 0 else None
            nxt = order[j + 1] if j + 1 < n else None
            before = _jump(prev, order[i]) + _jump(order[j], nxt)
            after = _jump(prev, _flip(order[j])) + _jump(_flip(order[i]), nxt)
            if after < before - 1e-9:
                order = order[:i] + [_flip(p) for p in reversed(order[i : j + 1])] + order[j + 1 :]
                improved = True
    return order, improved


def _or_opt(order: list[Placed]) -> tuple[list[Placed], bool]:
    """Move single links to wherever they shorten the total jumps, either way round."""
    improved = False
    for i in range(len(order)):
        x = order[i]
        prev = order[i - 1] if i > 0 else None
        nxt = order[i + 1] if i + 1 < len(order) else None
        saved = _jump(prev, x) + _jump(x, nxt) - _jump(prev, nxt)
        rest = order[:i] + order[i + 1 :]
        move = _cheapest_place(rest, x, saved)
        if move is not None:
            k, y = move
            order = rest[:k] + [y] + rest[k:]
            improved = True
    return order, improved


def _cheapest_place(rest: list[Placed], x: Placed, limit: float) -> tuple[int, Placed] | None:
    """Where x (either way round) adds the least jump, if less than limit."""
    best: tuple[int, Placed] | None = None
    for k in range(len(rest) + 1):
        a = rest[k - 1] if k > 0 else None
        b = rest[k] if k < len(rest) else None
        for y in (x, _flip(x)):
            added = _jump(a, y) + _jump(y, b) - _jump(a, b)
            if added < limit - 1e-9:
                best, limit = (k, y), added
    return best


def _with_gaps(order: list[Placed]) -> list[Placed]:
    out = []
    for i, p in enumerate(order):
        d = _jump(order[i - 1], p) if i > 0 else 0.0
        out.append(Placed(p.key, p.start, p.end, p.length_km, d if d > GAP_KM else 0.0))
    return out


def _west_to_east(placed: list[Placed]) -> list[Placed]:
    first, last = placed[0].start, placed[-1].end
    dx, dy = last[0] - first[0], last[1] - first[1]
    forwards = dx >= 0 if abs(dx) >= abs(dy) else dy >= 0
    if forwards:
        return placed
    rev = list(reversed(placed))
    # the gap before each link is now the gap after it
    gaps = [p.gap_before_km for p in placed][1:] + [0.0]
    gaps = list(reversed(gaps))
    return [Placed(p.key, p.end, p.start, p.length_km, g) for p, g in zip(rev, gaps, strict=True)]


def fraction_along(start: Point, end: Point, point: Point) -> float:
    """How far along a link a point sits, 0 at its start and 1 at its end."""
    ds, de = _dist_km(start, point), _dist_km(end, point)
    return 0.5 if ds + de == 0 else ds / (ds + de)
