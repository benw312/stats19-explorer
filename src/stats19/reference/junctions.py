"""Junctions built from the OS Open Roads network (PLAN-008 T3).

OS Open Roads has nodes, not junctions: a dual carriageway or staggered junction is
several nodes, a roundabout is a ring of links, and some junction-form nodes are only a
carriageway splitting. We assemble junctions the way COBALT and the Highway Safety Manual
see them:

- **Cluster** junction nodes joined by a short link (dual carriageway crossings, staggers),
  and every node of a roundabout ring, into one junction; clusters can't span more than
  ``MAX_SPAN_M`` (or a ring plus a short link), so a street of close junctions doesn't chain.
- **Arms** are the links leaving the cluster, grouped by road identity and direction: the
  two carriageways of a dual road are one arm, the two sides of a through road are two.
- **Type** from the arm count, with merges and diverges (a slip road leaving a motorway or
  dual carriageway) left with the link, as COBALT does.

Pure functions over small inputs, so the rules are unit-tested without a database.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from stats19.reference.roads import CLASS_RANK

JOIN_M = 30.0  # junction nodes joined by a link this short are one junction
MAX_SPAN_M = 60.0  # ...unless the merged junction would span more than this
ARM_ANGLE_DEG = 60.0  # links of the same road within this angle are one arm
NAME_ROADS = 4
_LOWEST_RANK = max(CLASS_RANK.values())
_MAINLINE_FORMS = {"Dual Carriageway", "Collapsed Dual Carriageway"}


# ------------------------------------------------------------------ clustering


class _Clusters:
    """Union-find over nodes, keeping each cluster's bounding box and ring size."""

    def __init__(self, nodes: dict[str, tuple[float, float]]):
        self.parent: dict[str, str] = {}
        self.box: dict[str, tuple[float, float, float, float]] = {}
        self.core: dict[str, float] = {}
        self.nodes = nodes

    def find(self, n: str) -> str:
        if n not in self.parent:
            x, y = self.nodes[n]
            self.parent[n], self.box[n], self.core[n] = n, (x, y, x, y), 0.0
        root = n
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[n] != root:
            self.parent[n], n = root, self.parent[n]
        return root

    def span(self, a: str, b: str) -> float:
        (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = self.box[a], self.box[b]
        w, h = max(ax1, bx1) - min(ax0, bx0), max(ay1, by1) - min(ay0, by0)
        return (w * w + h * h) ** 0.5

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        keep, drop = sorted((ra, rb))
        (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = self.box[keep], self.box[drop]
        self.box[keep] = (min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1))
        self.core[keep] = max(self.core[keep], self.core[drop])
        self.parent[drop] = keep


def cluster_nodes(
    nodes: dict[str, tuple[float, float]],
    ring_edges: list[tuple[str, str]],
    short_edges: list[tuple[str, str, float]],
) -> dict[str, str]:
    """Node -> junction id (its smallest node id), for nodes in multi-node junctions only.

    ``ring_edges`` (roundabout links) always join; ``short_edges`` (a, b, length) join,
    shortest first, while the junction stays within ``MAX_SPAN_M``, or within a ring's own
    size plus a short link each side.
    """
    uf = _Clusters(nodes)
    for a, b in ring_edges:
        uf.union(a, b)
    for root in {uf.find(n) for edge in ring_edges for n in edge}:
        uf.core[root] = uf.span(root, root)
    for a, b, _ in sorted(short_edges, key=lambda e: e[2]):
        ra, rb = uf.find(a), uf.find(b)
        if ra == rb:
            continue
        limit = max(MAX_SPAN_M, uf.core[ra] + 2 * JOIN_M, uf.core[rb] + 2 * JOIN_M)
        if uf.span(ra, rb) <= limit:
            uf.union(ra, rb)
    out = {n: uf.find(n) for n in uf.parent}
    sizes = Counter(out.values())
    return {n: c for n, c in out.items() if sizes[c] > 1}


# ------------------------------------------------------------------ arms


@dataclass(frozen=True)
class ArmLink:
    link_id: str
    road_class: str | None
    road_number: str | None
    name: str | None
    form_of_way: str | None
    bearing: float  # degrees from north, leaving the junction
    count_point_id: int | None = None

    @property
    def rank(self) -> int:
        return CLASS_RANK.get(self.road_class or "", _LOWEST_RANK)

    @property
    def is_slip(self) -> bool:
        return self.form_of_way == "Slip Road"

    @property
    def identity(self) -> tuple[str, str] | None:
        """Links with the same identity are the same road; None is never matched."""
        if self.road_number:
            return ("number", self.road_number)
        if self.name:
            return ("name", self.name)
        return ("slip", "") if self.is_slip else None


@dataclass(frozen=True)
class Arm:
    links: tuple[ArmLink, ...]

    @property
    def lead(self) -> ArmLink:
        return min(self.links, key=lambda lk: lk.rank)

    @property
    def rank(self) -> int:
        return self.lead.rank

    @property
    def identity(self) -> tuple[str, str] | None:
        return self.links[0].identity

    @property
    def label(self) -> str | None:
        return self.lead.road_number or self.lead.name

    @property
    def is_slip(self) -> bool:
        return all(lk.is_slip for lk in self.links)

    @property
    def bearing(self) -> float:
        return self.links[0].bearing

    @property
    def count_point_id(self) -> int | None:
        counted = Counter(lk.count_point_id for lk in self.links if lk.count_point_id is not None)
        return counted.most_common(1)[0][0] if counted else None


def angle_between(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def group_arms(links: list[ArmLink]) -> list[Arm]:
    """Group a junction's outgoing links into arms: same road, similar direction."""
    groups: list[list[ArmLink]] = []
    for link in links:
        key = link.identity
        home = next(
            (
                g
                for g in groups
                if key is not None
                and g[0].identity == key
                and angle_between(g[0].bearing, link.bearing) <= ARM_ANGLE_DEG
            ),
            None,
        )
        if home is None:
            groups.append([link])
        else:
            home.append(link)
    return [Arm(tuple(g)) for g in groups]


def _merge_or_diverge(arms: list[Arm]) -> bool:
    """A slip road joining or leaving a motorway or dual carriageway mid-link, or slip roads
    splitting or joining each other."""
    slips = [a for a in arms if a.is_slip]
    main = [a for a in arms if not a.is_slip]
    if slips and not main:
        return True  # slip roads splitting or joining inside an interchange
    if not slips or len({a.identity for a in main}) != 1 or main[0].identity is None:
        return False
    return all(
        lk.road_class == "Motorway" or lk.form_of_way in _MAINLINE_FORMS
        for a in main
        for lk in a.links
    )


def classify(arms: list[Arm], ring: bool, mini: bool) -> str | None:
    """Junction type, or None when the cluster isn't a junction to assign collisions to."""
    if len(arms) < 3:
        return None  # a carriageway split, a turning circle
    if ring:
        return "roundabout"
    if mini:
        return "mini_roundabout"
    if _merge_or_diverge(arms):
        return None
    return {3: "t_junction", 4: "crossroads"}.get(len(arms), "multi_arm")


def junction_name(arms: list[Arm]) -> str | None:
    """The roads that meet, biggest first: 'A38 / B3212 / Mill Lane'."""
    labels: list[str] = []
    for a in sorted(arms, key=lambda a: (a.rank, a.label or "")):
        if a.label and a.label not in labels:
            labels.append(a.label)
    return " / ".join(labels[:NAME_ROADS]) or None


def arm_roles(arms: list[Arm]) -> list[str]:
    """'major' for the arms of the top road (both sides of it), 'minor' for the rest."""
    top = min(arms, key=lambda a: a.rank)
    key = top.identity
    return [
        "major" if a is top or (key is not None and a.identity == key) else "minor" for a in arms
    ]
