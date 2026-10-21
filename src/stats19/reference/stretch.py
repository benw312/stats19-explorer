"""Grow a minor-road "stretch" from a count point along the OS Open Roads network.

DfT counts minor roads at single sites and publishes no link. We extend the site's road
both ways through the network (PLAN-008 §1 Q1) until one of:

- a junction with a road of equal or higher class (side roads of lower class don't stop it),
- the road's identity changes (number, or name, or for unnamed roads any junction),
- a road end, or
- ``max_m`` along the network from the count point.

Where the road forks and both branches keep its identity, only one is followed (FU-034 #2):
the branch of the count point's own class, then the one most in line with the road. Branches
of that class both within ``SPLIT_DEG`` of straight on are carriageways splitting, and both
are followed.

Pure functions over small dicts, so the rules are unit-tested without a database.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from stats19.reference.roads import CLASS_RANK

MAX_STRETCH_EACH_WAY_M = 1000.0
SPLIT_DEG = 30.0
_LOWEST_RANK = max(CLASS_RANK.values())


@dataclass(frozen=True)
class Link:
    id: str
    road_class: str | None
    road_number: str | None
    name: str | None
    start_node: str
    end_node: str
    length_m: float
    start_bearing: float | None = None  # degrees from north, leaving the start node
    end_bearing: float | None = None  # ...and leaving the end node

    @property
    def rank(self) -> int:
        return CLASS_RANK.get(self.road_class or "", _LOWEST_RANK)

    def other_end(self, node: str) -> str:
        return self.end_node if node == self.start_node else self.start_node

    def leaving(self, node: str) -> float | None:
        return self.start_bearing if node == self.start_node else self.end_bearing


def _turn(via: Link, onto: Link, node: str) -> float:
    """Degrees turned at ``node`` from ``via`` onto ``onto`` (0 = straight on)."""
    arrive, leave = via.leaving(node), onto.leaving(node)
    if arrive is None or leave is None:
        return 0.0
    return abs((leave - arrive) % 360 - 180)


def _branches(start: Link, via: Link, node: str, forks: list[Link]) -> list[Link]:
    """At a fork of the same road, the branches to follow."""
    ahead = [
        lk
        for lk in forks
        if lk.road_class == start.road_class and _turn(via, lk, node) <= SPLIT_DEG
    ]
    if len(ahead) > 1:
        return ahead
    return [
        min(forks, key=lambda lk: (lk.road_class != start.road_class, _turn(via, lk, node), lk.id))
    ]


def same_road(road: Link, other: Link, node_degree: int) -> bool:
    """Is ``other`` a continuation of ``road`` at a node with ``node_degree`` links?"""
    if road.road_number:
        return other.road_number == road.road_number
    if road.name:
        return other.name == road.name and not other.road_number
    # Unnamed, unnumbered: only through simple joins (pseudo nodes) of the same class.
    return (
        node_degree == 2
        and not other.name
        and not other.road_number
        and other.road_class == road.road_class
    )


def node_links(links: dict[str, Link]) -> dict[str, list[str]]:
    """Node id -> ids of the links meeting there."""
    out: dict[str, list[str]] = {}
    for link in links.values():
        out.setdefault(link.start_node, []).append(link.id)
        out.setdefault(link.end_node, []).append(link.id)
    return out


def grow_stretch(
    start: Link,
    fraction: float,
    links: dict[str, Link],
    nodes: dict[str, list[str]] | None = None,
    max_m: float = MAX_STRETCH_EACH_WAY_M,
) -> dict[str, float]:
    """Link id -> network distance (m) from the count point to the nearest end of that link.

    ``fraction`` is where the count point sits along ``start`` (0 = start node).
    """
    nodes = nodes if nodes is not None else node_links(links)
    claimed = {start.id: 0.0}
    queue = [
        (fraction * start.length_m, start.start_node, start.id),
        ((1 - fraction) * start.length_m, start.end_node, start.id),
    ]
    best: dict[str, float] = {}
    while queue:
        dist, node, via = heapq.heappop(queue)
        if dist >= max_m or best.get(node, float("inf")) <= dist:
            continue
        best[node] = dist
        incident = [links[i] for i in nodes.get(node, []) if i in links]
        degree = len(incident)
        continuing = [
            lk for lk in incident if lk.id not in claimed and same_road(start, lk, degree)
        ]
        crossing = [lk for lk in incident if lk.id not in claimed and lk not in continuing]
        if not continuing or any(lk.rank <= start.rank for lk in crossing):
            continue  # road end, identity change, or a junction with an equal/higher road
        if len(continuing) > 1:
            continuing = _branches(start, links[via], node, continuing)
        for lk in continuing:
            claimed[lk.id] = dist
            heapq.heappush(queue, (dist + lk.length_m, lk.other_end(node), lk.id))
    return claimed
