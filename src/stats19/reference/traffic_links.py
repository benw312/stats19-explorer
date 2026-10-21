"""Give each DfT count point the OS Open Roads links its flow applies to (PLAN-008 T2).

- **Major roads:** DfT's MRDB gives each link's extent as a straight line, junction to junction.
  An OS link on the same road number belongs to that count point when its midpoint projects
  between the line's ends and lies within a corridor around it. Slip roads and roundabouts
  belong to junctions, not links, so they are left out.
- **Rescue (FU-034 #1):** a count point that loses every piece to its neighbours' lines (or
  whose DfT road number isn't on OS, e.g. a renumbered road) takes the OS piece it sits on.
- **Minor roads:** snap the count point to the best nearby OS link (class and number must
  agree), then grow a stretch along the network (``stretch.grow_stretch``).

Major OS links are cut at DfT's link ends, so a long OS link can be shared between count
points (``frac_from``/``frac_to`` along it). Each minor link goes to one count point: the
nearest, with current counts beating historic ones.
Results: geo.traffic_link (link -> count point) and geo.traffic_stretch (one row per count
point with its merged geometry). Rebuilt whenever traffic or the road network reloads.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace

import psycopg

from stats19.reference.stretch import MAX_STRETCH_EACH_WAY_M, Link, grow_stretch, node_links
from stats19.reference.swap import swap_tables

log = logging.getLogger(__name__)

SNAP_RADIUS_M = 30.0
CORRIDOR_MIN_M = 150.0
CORRIDOR_SHARE = 0.25  # of the straight-line link length
_FETCH_PAD_M = 200.0
_MINOR_CLASSES = {
    "MB": ("B Road",),
    "C": ("Classified Unnumbered", "Unclassified", "Not Classified"),
    "U": ("Unclassified", "Not Classified", "Unknown", "Classified Unnumbered"),
}
# Snapping penalty (m) when the OS class is a fallback rather than the expected one.
_CLASS_PENALTY_M = 15.0


def tables_present(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        """SELECT to_regclass('geo.road_link') IS NOT NULL
                  AND to_regclass('geo.traffic_count_point') IS NOT NULL"""
    ).fetchone()
    return bool(row[0])


# ------------------------------------------------------------------ major roads

# DfT names that differ from OS road numbers.
ROAD_NUMBER_ALIASES = {"M6(T)": "M6 TOLL"}
MIN_PIECE_M = 5.0
RESCUE_OWN_M = 50.0  # an unmatched count point this near one of its own road's pieces takes it
RESCUE_ANY_M = 10.0  # ...else an A road or motorway it sits on, whatever OS numbers it
RESCUE_ANGLE_DEG = 20.0  # ...running the same way as DfT's line (not a crossing road)

# Each candidate OS link keeps the part between its points nearest DfT's two junctions.
# A link wholly inside the DfT line keeps 0-1 (its ends are those nearest points); one that
# crosses a junction is cut there; one wholly beyond a junction collapses to nothing.
# Neighbouring count points therefore split a shared OS link at their common junction.
_MAJOR = """
INSERT INTO major_piece (link_id, count_point_id, frac_from, frac_to, dist_m, point_m)
SELECT link_id, count_point_id, least(fa, fb), greatest(fa, fb), d, pt
FROM (
    SELECT cp.count_point_id, l.id AS link_id, l.length_m, x.fa, x.fb, x.d, x.pt
    FROM (
        SELECT count_point_id, geom_bng AS point,
               coalesce((%(aliases)s::jsonb) ->> road_name, road_name) AS road_number,
               ST_MakeLine(ST_StartPoint(ST_GeometryN(link_bng, 1)),
                           ST_EndPoint(ST_GeometryN(link_bng, ST_NumGeometries(link_bng)))) AS seg
        FROM geo.traffic_count_point
        WHERE road_type = 'Major' AND quality < 3 AND link_bng IS NOT NULL
    ) cp
    JOIN geo.road_link l
      ON l.road_number = cp.road_number
     AND ST_DWithin(l.geom_bng, cp.seg, GREATEST(%(min)s, %(share)s * ST_Length(cp.seg)))
    CROSS JOIN LATERAL (
        SELECT ST_LineLocatePoint(l.geom_bng, ST_StartPoint(cp.seg)) AS fa,
               ST_LineLocatePoint(l.geom_bng, ST_EndPoint(cp.seg)) AS fb
    ) f
    CROSS JOIN LATERAL (  -- how far the DfT line is from this piece (at its midpoint)
        SELECT f.fa, f.fb,
               ST_Distance(cp.seg, ST_LineInterpolatePoint(l.geom_bng, (f.fa + f.fb) / 2)) AS d,
               ST_Distance(cp.point, ST_LineInterpolatePoint(l.geom_bng, (f.fa + f.fb) / 2)) AS pt
    ) x
    WHERE l.form_of_way NOT IN ('Slip Road', 'Roundabout')
) c
WHERE abs(fb - fa) * length_m >= %(min_piece)s
"""


@dataclass(frozen=True)
class Piece:
    link_id: str
    count_point_id: int
    frac_from: float
    frac_to: float
    dist_m: float  # from the DfT line to the piece's midpoint
    point_m: float = 0.0  # from the count point itself: breaks ties between coincident lines
    rescued: bool = False  # the piece an otherwise unmatched count point sits on: it wins


def trim_overlaps(pieces: list[Piece], min_frac: float = 0.0) -> list[Piece]:
    """Make the pieces on each OS link disjoint.

    Consecutive DfT links don't always end at exactly the same point for their shared
    junction, and roads can curve back near themselves, so pieces can overlap. Cut each link
    at every piece boundary and give each sub-interval to the covering count point whose DfT
    line is nearest; adjacent sub-intervals of the same count point are merged again.
    DfT lines can coincide (a one-way pair, or a main road and its slip road), so ties go to
    the count point physically nearest the piece.
    """
    by_link: dict[str, list[Piece]] = {}
    for piece in pieces:
        by_link.setdefault(piece.link_id, []).append(piece)
    out: list[Piece] = []
    for group in by_link.values():
        cuts = sorted({f for p in group for f in (p.frac_from, p.frac_to)})
        merged: list[Piece] = []
        for a, b in zip(cuts, cuts[1:], strict=False):
            covering = [p for p in group if p.frac_from <= a and p.frac_to >= b]
            if not covering:
                continue
            owner = min(
                covering,
                key=lambda p: (not p.rescued, round(p.dist_m), p.point_m, p.count_point_id),
            )
            last = merged[-1] if merged else None
            if last and last.count_point_id == owner.count_point_id and last.frac_to == a:
                merged[-1] = replace(last, frac_to=b)
            else:
                merged.append(replace(owner, frac_from=a, frac_to=b))
        out += [p for p in merged if p.frac_to - p.frac_from > min_frac]
    return out


def with_rescues(pieces: list[Piece], rescues: list[Piece]) -> list[Piece]:
    """Trim with each rescued piece winning its stretch, unless that would leave another count
    point with no link at all: then that rescue is dropped."""
    before = {p.count_point_id for p in trim_overlaps(pieces)}
    rescues = list(rescues)
    while True:
        got = trim_overlaps(pieces + rescues)
        orphaned = before - {p.count_point_id for p in got}
        if not orphaned:
            return got
        lost = [p for p in pieces if p.count_point_id in orphaned]
        rescues = [r for r in rescues if not any(_overlaps(r, p) for p in lost)]


def _overlaps(a: Piece, b: Piece) -> bool:
    return a.link_id == b.link_id and a.frac_from < b.frac_to and b.frac_from < a.frac_to


# For each count point with no piece after trimming: its own road's piece nearest the count
# point, else the A road or motorway link it sits on, cut where DfT's line ends project.
_RESCUE = """
WITH cp AS (
    SELECT count_point_id, geom_bng AS point,
           ST_MakeLine(ST_StartPoint(ST_GeometryN(link_bng, 1)),
                       ST_EndPoint(ST_GeometryN(link_bng, ST_NumGeometries(link_bng)))) AS seg
    FROM geo.traffic_count_point WHERE count_point_id = ANY(%(ids)s)
), own AS (
    SELECT DISTINCT ON (m.count_point_id) m.link_id, m.count_point_id, m.frac_from, m.frac_to,
           m.dist_m, d.d AS point_m
    FROM major_piece m
    JOIN cp USING (count_point_id)
    JOIN geo.road_link l ON l.id = m.link_id
    CROSS JOIN LATERAL (
        SELECT ST_Distance(cp.point, ST_LineSubstring(l.geom_bng, m.frac_from, m.frac_to)) AS d
    ) d
    WHERE d.d <= %(own_m)s
    ORDER BY m.count_point_id, d.d
), any_road AS (
    SELECT l.id AS link_id, cp.count_point_id, least(f.fa, f.fb) AS frac_from,
           greatest(f.fa, f.fb) AS frac_to, ST_Distance(cp.seg, l.geom_bng) AS dist_m,
           ST_Distance(cp.point, l.geom_bng) AS point_m
    FROM cp
    CROSS JOIN LATERAL (
        SELECT * FROM geo.road_link l
        WHERE l.road_class IN ('A Road', 'Motorway')
          AND l.form_of_way NOT IN ('Slip Road', 'Roundabout')
          AND ST_DWithin(l.geom_bng, cp.point, %(any_m)s)
        ORDER BY l.geom_bng <-> cp.point LIMIT 1
    ) l
    CROSS JOIN LATERAL (
        SELECT ST_LineLocatePoint(l.geom_bng, ST_StartPoint(cp.seg)) AS fa,
               ST_LineLocatePoint(l.geom_bng, ST_EndPoint(cp.seg)) AS fb,
               ST_LineLocatePoint(l.geom_bng, cp.point) AS t
    ) f
    CROSS JOIN LATERAL (  -- the link's direction at the count point vs DfT's line, 0-90
        SELECT abs(mod((degrees(ST_Azimuth(ST_StartPoint(cp.seg), ST_EndPoint(cp.seg)))
                   - degrees(ST_Azimuth(
                         ST_LineInterpolatePoint(l.geom_bng, greatest(0.0, f.t - 0.02)),
                         ST_LineInterpolatePoint(l.geom_bng, least(1.0, f.t + 0.02))))
                   + 360)::numeric, 180)) AS a
    ) a
    WHERE cp.count_point_id NOT IN (SELECT count_point_id FROM own)
      AND least(a.a, 180 - a.a) <= %(angle)s
      AND abs(f.fb - f.fa) * l.length_m >= %(min_piece)s
)
SELECT * FROM own UNION ALL SELECT * FROM any_road
"""


def _rescues(conn: psycopg.Connection, pieces: list[Piece]) -> list[Piece]:
    matched = {p.count_point_id for p in trim_overlaps(pieces)}
    ids = [
        r[0]
        for r in conn.execute(
            """SELECT count_point_id FROM geo.traffic_count_point
               WHERE road_type = 'Major' AND quality < 3 AND link_bng IS NOT NULL"""
        )
        if r[0] not in matched
    ]
    rows = conn.execute(
        _RESCUE,
        {
            "ids": ids,
            "own_m": RESCUE_OWN_M,
            "any_m": RESCUE_ANY_M,
            "angle": RESCUE_ANGLE_DEG,
            "min_piece": MIN_PIECE_M,
        },
    ).fetchall()
    return [Piece(*r, rescued=True) for r in rows]


def _trim_major(conn: psycopg.Connection) -> tuple[int, int]:
    rows = conn.execute(
        "SELECT link_id, count_point_id, frac_from, frac_to, dist_m, point_m FROM major_piece"
    ).fetchall()
    found = [Piece(*r) for r in rows]
    rescues = _rescues(conn, found)
    pieces = with_rescues(found, rescues)
    with (
        conn.cursor() as cur,
        cur.copy(
            "COPY geo.traffic_link__new "
            "(link_id, count_point_id, method, frac_from, frac_to, dist_m) FROM STDIN"
        ) as copy,
    ):
        for p in pieces:
            copy.write_row((p.link_id, p.count_point_id, "major", p.frac_from, p.frac_to, p.dist_m))
    rescued = {p.count_point_id for p in pieces if p.rescued}
    unmatched = conn.execute(
        """SELECT count(*) FROM geo.traffic_count_point
           WHERE road_type = 'Major' AND quality < 3 AND link_bng IS NOT NULL
             AND NOT count_point_id = ANY(%s)""",
        (list({p.count_point_id for p in pieces}),),
    ).fetchone()[0]
    return len(rescued), unmatched


# ------------------------------------------------------------------ minor roads


@dataclass(frozen=True)
class MinorPoint:
    count_point_id: int
    road: str | None
    category: str | None
    historic: bool
    x: float
    y: float


def _expected_classes(p: MinorPoint) -> tuple[str, ...]:
    if p.category == "MB":
        return _MINOR_CLASSES["MB"]
    return _MINOR_CLASSES["C" if p.road == "C" else "U"]


# Each link's direction leaving either end, measured to this far along it (forks, FU-034 #2).
_BEARING_M = 20.0
_BEARINGS = f"""
       coalesce(degrees(ST_Azimuth(ST_StartPoint(geom_bng), ST_LineInterpolatePoint(geom_bng,
           least(1.0, {_BEARING_M} / greatest(length_m, 1.0))))), 0) AS start_bearing,
       coalesce(degrees(ST_Azimuth(ST_EndPoint(geom_bng), ST_LineInterpolatePoint(geom_bng,
           greatest(0.0, 1.0 - {_BEARING_M} / greatest(length_m, 1.0))))), 0) AS end_bearing"""

_SNAP = f"""
SELECT id, road_class, road_number, name, start_node, end_node, length_m,
       ST_LineLocatePoint(geom_bng, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 27700)) AS t,
       ST_Distance(geom_bng, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 27700)) AS d,{_BEARINGS}
FROM geo.road_link
WHERE ST_DWithin(geom_bng, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 27700), %(r)s)
  AND road_class = ANY(%(classes)s)
"""

_LOCAL = f"""
SELECT id, road_class, road_number, name, start_node, end_node, length_m,{_BEARINGS}
FROM geo.road_link
WHERE ST_DWithin(geom_bng, ST_SetSRID(ST_MakePoint(%(x)s, %(y)s), 27700), %(r)s)
"""


def _link(row: tuple, bearings: tuple = (None, None)) -> Link:
    return Link(*row[:6], float(row[6] or 0.0), *bearings)


def snap(rows: list[tuple], p: MinorPoint) -> tuple[Link, float, float] | None:
    """Best (link, fraction along it, distance) for a minor count point, or None."""
    expected = _expected_classes(p)

    def cost(r: tuple) -> float:
        penalty = 0.0 if r[1] == expected[0] else _CLASS_PENALTY_M
        if p.category == "MB" and r[2] != p.road:
            penalty += 4 * _CLASS_PENALTY_M  # B count points carry their number
        return r[8] + penalty

    if not rows:
        return None
    best = min(rows, key=cost)
    return _link(best, tuple(best[9:11])), float(best[7]), float(best[8])


def _minor_points(conn: psycopg.Connection) -> list[MinorPoint]:
    rows = conn.execute(
        """SELECT count_point_id, road_name, road_category, quality = 3,
                  ST_X(geom_bng), ST_Y(geom_bng)
           FROM geo.traffic_count_point WHERE road_type = 'Minor'"""
    ).fetchall()
    return [MinorPoint(*r) for r in rows]


def _minor_claims(conn: psycopg.Connection, p: MinorPoint) -> tuple[dict[str, float], float] | None:
    params = {"x": p.x, "y": p.y}
    rows = conn.execute(
        _SNAP, params | {"r": SNAP_RADIUS_M, "classes": list(_expected_classes(p))}
    ).fetchall()
    snapped = snap(rows, p)
    if snapped is None:
        return None
    start, fraction, distance = snapped
    local = conn.execute(_LOCAL, params | {"r": MAX_STRETCH_EACH_WAY_M + _FETCH_PAD_M}).fetchall()
    links = {r[0]: _link(r, tuple(r[7:9])) for r in local} | {start.id: start}
    return grow_stretch(start, fraction, links, node_links(links)), distance


def resolve_claims(
    claims: list[tuple[int, bool, dict[str, float]]],
) -> dict[str, tuple[int, float]]:
    """Link -> (count point, distance): current counts first, then the nearest count point."""
    best: dict[str, tuple[bool, float, int]] = {}
    for cp, historic, links in claims:
        for link_id, dist in links.items():
            key = (historic, dist, cp)
            if link_id not in best or key < best[link_id]:
                best[link_id] = key
    return {link_id: (cp, dist) for link_id, (_, dist, cp) in best.items()}


def _build_minor(conn: psycopg.Connection) -> tuple[int, int]:
    points = _minor_points(conn)
    claims, snaps, unmatched = [], {}, 0
    for i, p in enumerate(points, start=1):
        got = _minor_claims(conn, p)
        if got is None:
            unmatched += 1
        else:
            links, snaps[p.count_point_id] = got
            claims.append((p.count_point_id, p.historic, links))
        if i % 5000 == 0:
            log.info("minor stretches: %s/%s count points", f"{i:,}", f"{len(points):,}")
    owned = resolve_claims(claims)
    with (
        conn.cursor() as cur,
        cur.copy(
            "COPY geo.traffic_link__new "
            "(link_id, count_point_id, method, frac_from, frac_to, dist_m) FROM STDIN"
        ) as copy,
    ):
        for link_id, (cp, dist) in owned.items():
            copy.write_row((link_id, cp, "minor", 0.0, 1.0, dist))
    with (
        conn.cursor() as cur,
        cur.copy("COPY minor_snap (count_point_id, snap_m) FROM STDIN") as copy,
    ):
        for cp, d in snaps.items():
            copy.write_row((cp, d))
    return len(points) - unmatched, unmatched


# ------------------------------------------------------------------ build

BOTH_CARRIAGEWAYS = 1.5  # traced dual length / the road it covers: both carriageways traced


def road_length_m(single_m: float, dual_m: float, dft_m: float | None) -> float:
    """The length of road a count covers, from its traced OS pieces (FU-047 #4).

    OS draws each carriageway of a dual road as its own "Dual Carriageway" link, so with both
    traced the dual length counts twice and is halved. Often only one carriageway is traced
    (a one-way pair counted separately, or a split DfT link); halving it then made the road
    about 30% short, and its rate per vehicle-km that much too high. So halve only when the
    dual pieces come to at least 1.5x the stretch DfT's link leaves for them."""
    if dual_m <= 0:
        return single_m
    if dft_m is None or dft_m <= 0:
        return single_m + dual_m / 2
    dual_road = max(dft_m - single_m, 0.0)
    both = dual_road == 0 or dual_m >= BOTH_CARRIAGEWAYS * dual_road
    return single_m + (dual_m / 2 if both else dual_m)


_LENGTHS = """
SELECT t.count_point_id,
       coalesce(sum(l.length_m * (t.frac_to - t.frac_from))
                FILTER (WHERE l.form_of_way <> 'Dual Carriageway'), 0),
       coalesce(sum(l.length_m * (t.frac_to - t.frac_from))
                FILTER (WHERE l.form_of_way = 'Dual Carriageway'), 0),
       p.link_length_km * 1000
FROM geo.traffic_link__new t
JOIN geo.road_link l ON l.id = t.link_id
JOIN geo.traffic_count_point p USING (count_point_id)
GROUP BY t.count_point_id, p.link_length_km
"""


def _set_lengths(conn: psycopg.Connection) -> None:
    rows = [
        (round(road_length_m(single, dual, dft)), cp)
        for cp, single, dual, dft in conn.execute(_LENGTHS)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE geo.traffic_stretch__new SET length_m = %s WHERE count_point_id = %s", rows
        )


_STRETCH = """
INSERT INTO geo.traffic_stretch__new
SELECT t.count_point_id, min(t.method),
       NULL,  -- set by _set_lengths
       count(*),
       mode() WITHIN GROUP (ORDER BY l.name),
       s.snap_m,
       ST_Multi(ST_LineMerge(ST_Collect(ST_LineSubstring(l.geom_bng, t.frac_from, t.frac_to))))
           ::geometry(MultiLineString, 27700),
       NULL
FROM geo.traffic_link__new t
JOIN geo.road_link l ON l.id = t.link_id
LEFT JOIN minor_snap s USING (count_point_id)
GROUP BY t.count_point_id, s.snap_m
"""


def build_traffic_links(conn: psycopg.Connection) -> None:
    if not tables_present(conn):
        log.info("traffic links skipped: needs both the road network and traffic datasets")
        return
    with conn.transaction():
        for table in ("traffic_link", "traffic_stretch"):
            conn.execute(f"DROP TABLE IF EXISTS geo.{table}__new")
        conn.execute(
            """CREATE TABLE geo.traffic_link__new (
                   link_id text NOT NULL, count_point_id integer NOT NULL,
                   method text NOT NULL, frac_from double precision NOT NULL,
                   frac_to double precision NOT NULL, dist_m double precision)"""
        )
        conn.execute(
            """CREATE TABLE geo.traffic_stretch__new (
                   count_point_id integer NOT NULL, method text NOT NULL,
                   length_m double precision, links integer, name text,
                   snap_m double precision, geom_bng geometry(MultiLineString, 27700),
                   geom_3857 geometry(MultiLineString, 3857))"""
        )
        conn.execute(
            "CREATE TEMP TABLE minor_snap (count_point_id integer, snap_m real) ON COMMIT DROP"
        )
        conn.execute(
            """CREATE TEMP TABLE major_piece (link_id text, count_point_id integer,
                   frac_from double precision, frac_to double precision,
                   dist_m double precision, point_m double precision) ON COMMIT DROP"""
        )
        conn.execute(
            _MAJOR,
            {
                "min": CORRIDOR_MIN_M,
                "share": CORRIDOR_SHARE,
                "min_piece": MIN_PIECE_M,
                "aliases": json.dumps(ROAD_NUMBER_ALIASES),
            },
        )
        rescued, major_unmatched = _trim_major(conn)
        matched, unmatched = _build_minor(conn)
        conn.execute(_STRETCH)
        _set_lengths(conn)
        conn.execute("UPDATE geo.traffic_stretch__new SET geom_3857 = ST_Transform(geom_bng, 3857)")
        n = conn.execute("SELECT count(*) FROM geo.traffic_stretch__new").fetchone()[0]
    swap_tables(
        conn,
        "traffic_links",
        {
            "traffic_link": [
                "ALTER TABLE geo.traffic_link ADD PRIMARY KEY (link_id, count_point_id, frac_from)",
                "CREATE INDEX traffic_link_cp_idx ON geo.traffic_link (count_point_id)",
            ],
            "traffic_stretch": [
                "ALTER TABLE geo.traffic_stretch ADD PRIMARY KEY (count_point_id)",
                "CREATE INDEX traffic_stretch_geom_idx ON geo.traffic_stretch "
                "USING gist (geom_3857)",
                "CREATE INDEX traffic_stretch_geom_bng_idx ON geo.traffic_stretch "
                "USING gist (geom_bng)",
            ],
        },
        "OS Open Roads + DfT count points",
        n,
        f"major count points rescued {rescued:,}, unmatched {major_unmatched:,}; "
        f"minor count points snapped {matched:,}, unmatched {unmatched:,}",
    )
