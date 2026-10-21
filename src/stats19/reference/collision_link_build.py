"""Match collisions to OS road links: geo.collision_link (PLAN-008 T3b).

Every collision of the last ``COLLISION_YEARS`` with a location is scored against the OS
links within 25 m (``collision_links``); the best link, the position along it (``frac``),
the score and the margin over the runner-up are kept. Rebuilt when the road network or
STATS19 changes. Which count point a collision's flow comes from is looked up at query time
(geo.traffic_link pieces), so a traffic reload needs no re-match.
"""

from __future__ import annotations

import logging
from itertools import groupby

import psycopg

from stats19.reference import collision_links as cl
from stats19.reference.junction_build import COLLISION_YEARS
from stats19.reference.swap import swap_tables, tables_exist

log = logging.getLogger(__name__)

_CANDIDATES = """
SELECT c.collision_index, c.first_road_class, c.first_road_number, c.road_type,
       l.id, ST_Distance(l.geom_bng, c.geom_bng), l.road_class, l.road_number, l.form_of_way,
       ST_LineLocatePoint(l.geom_bng, c.geom_bng)
FROM core.collision c
JOIN geo.road_link l ON ST_DWithin(l.geom_bng, c.geom_bng, %(radius)s)
WHERE c.collision_year = %(year)s AND c.geom_bng IS NOT NULL
ORDER BY c.collision_index
"""


def _match_year(conn: psycopg.Connection, year: int) -> tuple[list[tuple], int]:
    rows = conn.execute(_CANDIDATES, {"radius": cl.CANDIDATE_RADIUS_M, "year": year}).fetchall()
    out = []
    for collision_index, group in groupby(rows, key=lambda r: r[0]):
        group = list(group)
        road = cl.CollisionRoad(*group[0][1:4])
        candidates = [cl.Candidate(r[4], r[5], *r[6:9]) for r in group]
        match = cl.best_match(road, candidates)
        frac = next(r[9] for r in group if r[4] == match.link_id)
        out.append(
            (collision_index, match.link_id, frac, match.distance_m, match.score, match.margin)
        )
    return out, len(out)


def match_collision_links(conn: psycopg.Connection) -> None:
    if not tables_exist(conn, "geo.road_link", "core.collision"):
        log.info("collision links skipped: needs the road network and STATS19 loaded")
        return
    latest = conn.execute("SELECT max(collision_year) FROM core.collision").fetchone()[0]
    if latest is None:
        return
    years = range(latest - COLLISION_YEARS + 1, latest + 1)
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.collision_link__new")
        conn.execute(
            """CREATE TABLE geo.collision_link__new (
                   collision_index text NOT NULL, link_id text NOT NULL,
                   frac double precision NOT NULL, dist_m real, score real, margin real)"""
        )
        total = 0
        for year in years:
            rows, n = _match_year(conn, year)
            with (
                conn.cursor() as cur,
                cur.copy(
                    "COPY geo.collision_link__new "
                    "(collision_index, link_id, frac, dist_m, score, margin) FROM STDIN"
                ) as copy,
            ):
                for row in rows:
                    copy.write_row(row)
            total += n
        located = conn.execute(
            "SELECT count(*) FROM core.collision WHERE collision_year BETWEEN %s AND %s "
            "AND geom_bng IS NOT NULL",
            (years.start, years.stop - 1),
        ).fetchone()[0]
        good = conn.execute(
            "SELECT count(*) FROM geo.collision_link__new WHERE score >= %s", (cl.GOOD_SCORE,)
        ).fetchone()[0]
    swap_tables(
        conn,
        "collision_links",
        {
            "collision_link": [
                "ALTER TABLE geo.collision_link ADD PRIMARY KEY (collision_index)",
                "CREATE INDEX collision_link_link_idx ON geo.collision_link (link_id)",
            ]
        },
        "STATS19 collisions matched to OS Open Roads links",
        total,
        f"last {COLLISION_YEARS} years: {total:,} of {located:,} matched, "
        f"{good:,} scoring {cl.GOOD_SCORE}+",
    )
