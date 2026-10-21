"""Build geo.authority, geo.authority_year and geo.authority_peer (PLAN-009 §10, V4).

The denominators for each highway authority's rates, by year:
- population (ONS mid-year estimates, geo.population);
- vehicle-km on all roads and road length (DfT local authority traffic, geo.traffic_la);
- vehicle-km and length on major roads: AADF x link length of the authority's major count
  points, as DfT computes it. Minor = all roads - major.

Casualty counts aren't stored: they follow the user's filter, so the API counts them per
request. Peers are each authority's nearest neighbours on open measures, within its own
country, and years with a recording gap are flagged (``authorities``, FU-047).
"""

from __future__ import annotations

import logging

import psycopg

from stats19.reference import authorities as au
from stats19.reference.swap import swap_tables, tables_exist

log = logging.getLogger(__name__)

PEER_YEARS = 5  # measures for choosing peers: averages over the latest five years
KM_PER_MILE = 1.609344

# DfT's traffic tables (and count points) use the pre-2023 codes for these two.
_OLD_CODES = "('E08000016', 'E08000038'), ('E08000019', 'E08000039')"

_YEARS = f"""
CREATE TEMP TABLE ay ON COMMIT DROP AS
WITH alias(old, new) AS (VALUES {_OLD_CODES}),
la AS (
    SELECT coalesce(a.new, t.local_authority_code) AS code, t.year,
           t.vehicle_miles * {KM_PER_MILE} AS vehicle_km, t.road_length_km AS road_km
    FROM geo.traffic_la t LEFT JOIN alias a ON a.old = t.local_authority_code
), major AS (
    SELECT coalesce(a.new, p.local_authority_code) AS code, f.year,
           -- that year's link length (DfT re-measures links), else today's (FU-047 #8)
           sum(f.all_motor_vehicles * coalesce(f.link_length_km, p.link_length_km) * 365)
               AS vehicle_km,
           sum(coalesce(f.link_length_km, p.link_length_km)) AS road_km
    FROM geo.traffic_count_point p
    JOIN geo.traffic_aadf f USING (count_point_id)
    LEFT JOIN alias a ON a.old = p.local_authority_code
    WHERE p.road_type = 'Major' AND coalesce(f.link_length_km, p.link_length_km) > 0
      AND f.all_motor_vehicles > 0
    GROUP BY 1, 2
), years AS (
    SELECT DISTINCT year FROM geo.population
    UNION
    SELECT DISTINCT year FROM geo.traffic_la
    WHERE year >= (SELECT min(year) FROM geo.population)
)
SELECT b.code, y.year, p.population, la.vehicle_km, m.vehicle_km AS major_vehicle_km,
       CASE WHEN la.vehicle_km >= m.vehicle_km THEN la.vehicle_km - m.vehicle_km END
           AS minor_vehicle_km,
       la.road_km, m.road_km AS major_road_km
FROM geo.boundary b
CROSS JOIN years y
LEFT JOIN geo.population p ON p.code = b.code AND p.year = y.year
LEFT JOIN la ON la.code = b.code AND la.year = y.year
LEFT JOIN major m ON m.code = b.code AND m.year = y.year
WHERE b.boundary_type = 'highway_authority'
"""

# One row per authority: its name, region (DfT's, from its count points) and area.
_AUTHORITIES = f"""
WITH alias(old, new) AS (VALUES {_OLD_CODES}),
region AS (
    SELECT coalesce(a.new, p.local_authority_code) AS code, min(p.region_name) AS region
    FROM geo.traffic_count_point p LEFT JOIN alias a ON a.old = p.local_authority_code
    GROUP BY 1
)
SELECT b.code, b.name, r.region, ST_Area(b.geom_bng) / 1e6 AS area_km2
FROM geo.boundary b LEFT JOIN region r USING (code)
WHERE b.boundary_type = 'highway_authority'
"""

# Five-year averages for choosing peers (the latest PEER_YEARS with population).
_MEASURES = """
SELECT code, avg(population)::float8, avg(vehicle_km), avg(major_vehicle_km), avg(road_km)
FROM ay
WHERE year > (SELECT max(year) FROM ay WHERE population IS NOT NULL) - %(years)s
GROUP BY code
"""

_DDL = {
    "authority": """CREATE TABLE geo.authority__new (
        code text NOT NULL, name text NOT NULL, region text, area_km2 double precision)""",
    "authority_year": """CREATE TABLE geo.authority_year__new (
        code text NOT NULL, year smallint NOT NULL, population integer,
        vehicle_km double precision, major_vehicle_km double precision,
        minor_vehicle_km double precision, road_km double precision,
        major_road_km double precision,
        recording_gap real)  -- share of GB collisions / usual share, when flagged""",
    "authority_peer": """CREATE TABLE geo.authority_peer__new (
        code text NOT NULL, rank smallint NOT NULL, peer_code text NOT NULL,
        distance double precision NOT NULL)""",
}
_SWAP_DDL = {
    "authority": ["ALTER TABLE geo.authority ADD PRIMARY KEY (code)"],
    "authority_year": ["ALTER TABLE geo.authority_year ADD PRIMARY KEY (code, year)"],
    "authority_peer": ["ALTER TABLE geo.authority_peer ADD PRIMARY KEY (code, rank)"],
}


def _peers(
    conn: psycopg.Connection, area: dict[str, float], regions: dict[str, str | None]
) -> list[tuple]:
    features = {}
    for code, population, vkm, major, road_km in conn.execute(_MEASURES, {"years": PEER_YEARS}):
        f = au.peer_features(au.AuthorityMeasures(population, area.get(code), vkm, major, road_km))
        if f is not None:
            features[code] = f
    return [
        (code, rank, peer, distance)
        for code, peers in au.peers_within_country(features, regions).items()
        for rank, (peer, distance) in enumerate(peers, start=1)
    ]


# Collisions per authority (STATS19's own field, as the rates count them) and GB, by year.
_COLLISIONS = """
SELECT local_authority_highway_current, collision_year, count(*)
FROM core.collision
WHERE collision_year >= (SELECT min(year) FROM geo.population)
GROUP BY 1, 2
"""


def _flag_gaps(conn: psycopg.Connection) -> int:
    """Mark authority-years far below the authority's usual share of GB collisions."""
    if not tables_exist(conn, "core.collision"):
        return 0
    counts: dict[str, dict[int, int]] = {}
    gb: dict[int, int] = {}
    for code, year, n in conn.execute(_COLLISIONS):
        gb[year] = gb.get(year, 0) + n
        counts.setdefault(code, {})[year] = n
    gaps = [
        (ratio, code, year)
        for code, by_year in counts.items()
        for year, ratio in au.recording_gaps(by_year, gb).items()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE geo.authority_year__new SET recording_gap = %s WHERE code = %s AND year = %s",
            gaps,
        )
    return len(gaps)


def _copy(conn: psycopg.Connection, table: str, rows: list[tuple]) -> None:
    with conn.cursor() as cur, cur.copy(f"COPY geo.{table}__new FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def build_authorities(conn: psycopg.Connection) -> None:
    needed = ("geo.boundary", "geo.population", "geo.traffic_la", "geo.traffic_count_point")
    if not tables_exist(conn, *needed):
        log.info("authorities skipped: needs boundaries, population and traffic")
        return
    with conn.transaction():
        for table, ddl in _DDL.items():
            conn.execute(f"DROP TABLE IF EXISTS geo.{table}__new")
            conn.execute(ddl)
        authorities = conn.execute(_AUTHORITIES).fetchall()
        # ON COMMIT DROP doesn't fire inside an outer transaction: clear a previous build's
        conn.execute("DROP TABLE IF EXISTS ay")
        _copy(conn, "authority", authorities)
        conn.execute(_YEARS)
        conn.execute("INSERT INTO geo.authority_year__new SELECT *, NULL FROM ay")
        gaps = _flag_gaps(conn)
        peers = _peers(
            conn,
            {code: area for code, _, _, area in authorities},
            {code: region for code, _, region, _ in authorities},
        )
        _copy(conn, "authority_peer", peers)
    with_peers = len({p[0] for p in peers})
    swap_tables(
        conn,
        "authorities",
        _SWAP_DDL,
        "ONS population + DfT traffic, per highway authority",
        len(authorities),
        f"{with_peers} with similar authorities (same country); {gaps} recording gaps",
    )
