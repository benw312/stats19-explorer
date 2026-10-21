"""Download and (re)load reference datasets into schema geo.

Each dataset loads into geo.<table>__new, then swaps in with indexes and a row in
geo.reference_refresh, all in one transaction, so readers never see a partial table.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path

import httpx
import psycopg

from stats19.download import download_file
from stats19.reference import boundaries, names, population, postcodes, prevention, traffic
from stats19.reference.derived import deferred, rebuild, run_pending
from stats19.reference.osm_load import load_osm_nodes
from stats19.reference.road_network import load_road_network
from stats19.reference.swap import swap_tables as _swap_tables

log = logging.getLogger(__name__)

PAGE_SIZE = 100

# local_type -> search category (drives ranking and icons in the UI)
_PLACE_CATEGORY = {
    **dict.fromkeys(
        ["City", "Town", "Village", "Hamlet", "Suburban Area", "Other Settlement"], "place"
    ),
    **dict.fromkeys(["Named Road", "Numbered Road", "Section Of Numbered Road"], "road"),
    **dict.fromkeys(
        [
            "Primary Education",
            "Secondary Education",
            "Special Needs Education",
            "Further Education",
            "Higher or University Education",
            "Non State Primary Education",
            "Non State Secondary Education",
        ],
        "school",
    ),
    "Hospital": "hospital",
    "Railway Station": "transport",
    "Bus Station": "transport",
}


def _swap(
    conn: psycopg.Connection,
    table: str,
    ddl_after: list[str],
    source: str,
    rows: int,
    detail: str | None = None,
) -> None:
    _swap_tables(conn, table, {table: ddl_after}, source, rows, detail)


# ------------------------------------------------------------------ postcodes


def load_postcodes(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    f = download_file(client, postcodes.SOURCE_URL, data_dir, "codepoint_open.zip")
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.postcode__new")
        conn.execute(
            """CREATE TABLE geo.postcode__new (
                   postcode text NOT NULL, postcode_key text NOT NULL,
                   positional_quality smallint, admin_district_code text,
                   geom_bng geometry(Point, 27700) NOT NULL)"""
        )
        n = 0
        with conn.cursor() as cur, cur.copy("COPY geo.postcode__new FROM STDIN") as copy:
            for pc, key, pq, district, e, nn in postcodes.parse_postcodes(f.path):
                copy.write_row((pc, key, pq, district, f"SRID=27700;POINT({e} {nn})"))
                n += 1
    _swap(
        conn,
        "postcode",
        [
            "ALTER TABLE geo.postcode ADD PRIMARY KEY (postcode_key)",
            "CREATE INDEX postcode_geom_idx ON geo.postcode USING gist (geom_bng)",
        ],
        "OS Code-Point Open",
        n,
    )


# ------------------------------------------------------------------ places / roads


def load_places(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    f = download_file(client, names.SOURCE_URL, data_dir, "open_names.zip")
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.place__new")
        conn.execute(
            """CREATE TABLE geo.place__new (
                   id text NOT NULL, name text NOT NULL, local_type text NOT NULL,
                   category text NOT NULL, populated_place text, district text, county text,
                   geom_bng geometry(Point, 27700) NOT NULL,
                   bbox_bng geometry(Polygon, 27700) NOT NULL)"""
        )
        n = 0
        with conn.cursor() as cur, cur.copy("COPY geo.place__new FROM STDIN") as copy:
            for (
                pid,
                name,
                local,
                place,
                district,
                county,
                x,
                y,
                x0,
                y0,
                x1,
                y1,
            ) in names.parse_names(f.path):
                # Pad degenerate bboxes (points) so the map can still fit to them.
                x0, y0, x1, y1 = min(x0, x - 50), min(y0, y - 50), max(x1, x + 50), max(y1, y + 50)
                copy.write_row(
                    (
                        pid,
                        name,
                        local,
                        _PLACE_CATEGORY[local],
                        place,
                        district,
                        county,
                        f"SRID=27700;POINT({x} {y})",
                        f"SRID=27700;POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))",
                    )
                )
                n += 1
    _swap(
        conn,
        "place",
        [
            "ALTER TABLE geo.place ADD PRIMARY KEY (id)",
            "CREATE INDEX place_name_trgm_idx ON geo.place USING gin (lower(name) gin_trgm_ops)",
            "CREATE INDEX place_bbox_idx ON geo.place USING gist (bbox_bng)",
        ],
        "OS Open Names",
        n,
    )


# ------------------------------------------------------------------ boundaries


def _code_and_name_fields(props: dict) -> tuple[str, str]:
    code = next(k for k in props if re.fullmatch(r"[A-Z]+\d{2}CD", k))
    return code, code[:-2] + "NM"


def _fetch_layer(client: httpx.Client, service: str) -> list[dict]:
    features, offset = [], 0
    while True:
        r = client.get(
            f"{boundaries.ARCGIS_ROOT}/{service}/FeatureServer/0/query",
            params={
                "where": "1=1",
                "outFields": "*",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": str(offset),
                "resultRecordCount": str(PAGE_SIZE),
            },
        )
        r.raise_for_status()
        page = r.json().get("features", [])
        features += page
        if len(page) < PAGE_SIZE:
            return features
        offset += PAGE_SIZE


def load_boundaries(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    r = client.get(boundaries.ARCGIS_ROOT, params={"f": "json"})
    r.raise_for_status()
    available = [s["name"] for s in r.json().get("services", [])]
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.boundary__new")
        conn.execute(
            """CREATE TABLE geo.boundary__new (
                   boundary_type text NOT NULL, code text NOT NULL, name text NOT NULL,
                   vintage text NOT NULL, source_service text NOT NULL,
                   geom_bng geometry(MultiPolygon, 27700) NOT NULL)"""
        )
        n, used = 0, []
        for bset in boundaries.BOUNDARY_SETS:
            service = boundaries.latest_service(available, bset.prefix, bset.suffix)
            if service is None:
                raise RuntimeError(f"no ONS service found for {bset.prefix}*{bset.suffix}")
            year, month = boundaries.parse_vintage(service)
            used.append(service)
            for feat in _fetch_layer(client, service):
                code_f, name_f = _code_and_name_fields(feat["properties"])
                if feat["properties"][code_f].startswith("N"):
                    continue  # Northern Ireland: STATS19 covers Great Britain only
                conn.execute(
                    """INSERT INTO geo.boundary__new VALUES (%s, %s, %s, %s, %s,
                           ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(
                               ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 27700)), 3)))""",
                    (
                        bset.boundary_type,
                        feat["properties"][code_f],
                        feat["properties"][name_f],
                        f"{year}-{month:02d}",
                        service,
                        json.dumps(feat["geometry"]),
                    ),
                )
                n += 1
    _swap(
        conn,
        "boundary",
        [
            "ALTER TABLE geo.boundary ADD PRIMARY KEY (boundary_type, code)",
            "CREATE INDEX boundary_geom_idx ON geo.boundary USING gist (geom_bng)",
        ],
        "ONS Open Geography",
        n,
        ", ".join(used),
    )
    rebuild(conn, "authorities")  # population density uses the authority's area


# ------------------------------------------------------------------ value of prevention


def load_prevention(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    r = client.get(prevention.DATA_TABLES_API)
    r.raise_for_status()
    m = re.search(r"https://[^\"'\s<>]*ras4001\.ods", json.dumps(r.json()))
    if not m:
        raise RuntimeError("RAS4001 link not found on the road safety data tables page")
    f = download_file(client, m.group(0), data_dir)
    rows = prevention.parse_prevention(f.path)
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.value_of_prevention__new")
        conn.execute(
            """CREATE TABLE geo.value_of_prevention__new (
                   data_year smallint NOT NULL, price_year smallint NOT NULL,
                   severity text NOT NULL, per_casualty double precision,
                   per_collision double precision)"""
        )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO geo.value_of_prevention__new VALUES (%s,%s,%s,%s,%s)", rows
            )
    _swap(
        conn,
        "value_of_prevention",
        ["ALTER TABLE geo.value_of_prevention ADD PRIMARY KEY (data_year, severity)"],
        "DfT RAS4001",
        len(rows),
        m.group(0),
    )


# ------------------------------------------------------------------ population (ONS)


def load_population(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    r = client.get(population.population_url(), timeout=120)
    r.raise_for_status()
    rows = population.parse_population(r.text)
    if not rows:
        raise RuntimeError("Nomis returned no population estimates")
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.population__new")
        conn.execute(
            """CREATE TABLE geo.population__new (
                   code text NOT NULL, year smallint NOT NULL, population integer NOT NULL)"""
        )
        with conn.cursor() as cur, cur.copy("COPY geo.population__new FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
    years = sorted({y for _, y, _ in rows})
    _swap(
        conn,
        "population",
        ["ALTER TABLE geo.population ADD PRIMARY KEY (code, year)"],
        "ONS mid-year population estimates (Nomis NM_2002_1)",
        len(rows),
        f"{years[0]}-{years[-1]}",
    )
    rebuild(conn, "authorities")


# ------------------------------------------------------------------ traffic flows (DfT)

# A count is "recent" if made within this many years of the latest data year (PLAN-008).
TRAFFIC_STALE_YEARS = 5
_MRDB_LOOKBACK_YEARS = 3

_AADF_VEHICLES = ", ".join(f"{c.lower()} integer" for c in traffic.VEHICLE_COLUMNS)

# quality: 0 counted in the latest data year; 1 estimated from a recent count;
# 2 estimated from an old (or no) count; 3 no longer in the published data.
_TRAFFIC_DERIVED = """
WITH s AS (
    SELECT count_point_id, min(year) AS first_year, max(year) AS latest_year,
           max(year) FILTER (WHERE estimation_method = 'Counted') AS last_counted_year
    FROM geo.traffic_aadf__new GROUP BY count_point_id
)
UPDATE geo.traffic_count_point__new p
SET first_year = s.first_year, latest_year = s.latest_year,
    last_counted_year = s.last_counted_year,
    latest_aadf = a.all_motor_vehicles,
    latest_hgv_pct = round(100.0 * a.all_hgvs / NULLIF(a.all_motor_vehicles, 0), 1),
    latest_cycles = a.pedal_cycles,
    quality = CASE
        WHEN s.latest_year < %(data_year)s THEN 3
        WHEN s.last_counted_year = s.latest_year THEN 0
        WHEN s.last_counted_year >= %(data_year)s - %(stale)s THEN 1
        ELSE 2 END
FROM s JOIN geo.traffic_aadf__new a
     ON a.count_point_id = s.count_point_id AND a.year = s.latest_year
WHERE p.count_point_id = s.count_point_id
"""


def _download_mrdb(client: httpx.Client, data_dir: Path, data_year: int) -> tuple[int, Path] | None:
    """The newest MRDB (major-road link extents) published for data_year or shortly before."""
    for year in range(data_year, data_year - _MRDB_LOOKBACK_YEARS - 1, -1):
        try:
            return year, download_file(client, traffic.MRDB_URL.format(year=year), data_dir).path
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
    log.warning("no MRDB found for %s or earlier; links omitted", data_year)
    return None


def _copy_aadf(conn: psycopg.Connection, path: Path) -> int:
    """COPY AADF rows into geo.traffic_aadf__new; returns the latest year seen."""
    data_year = 0
    with conn.cursor() as cur, cur.copy("COPY geo.traffic_aadf__new FROM STDIN") as copy:
        for row in traffic.parse_aadf(path):
            copy.write_row(row)
            data_year = max(data_year, row[1])
    if not data_year:
        raise RuntimeError(f"{path.name}: no AADF rows")
    return data_year


_TRAFFIC_TABLES_DDL = {
    "traffic_aadf": f"""CREATE TABLE geo.traffic_aadf__new (
        count_point_id integer NOT NULL, year smallint NOT NULL,
        estimation_method text, estimation_method_detailed text, {_AADF_VEHICLES},
        link_length_km double precision)""",
    "traffic_count_point": """CREATE TABLE geo.traffic_count_point__new (
        count_point_id integer NOT NULL, road_name text, road_category text,
        road_type text, start_junction text, end_junction text,
        local_authority_code text, local_authority_name text, region_name text,
        link_length_km double precision,
        geom_bng geometry(Point, 27700) NOT NULL,
        link_bng geometry(MultiLineString, 27700), link_year smallint,
        first_year smallint, latest_year smallint, last_counted_year smallint,
        latest_aadf integer, latest_hgv_pct double precision, latest_cycles integer,
        quality smallint, geom_3857 geometry(Point, 3857),
        link_3857 geometry(MultiLineString, 3857))""",
    "traffic_la": """CREATE TABLE geo.traffic_la__new (
        local_authority_code text NOT NULL, local_authority_name text NOT NULL,
        year smallint NOT NULL, road_length_km double precision,
        car_vehicle_miles double precision, vehicle_miles double precision)""",
}

_TRAFFIC_SWAP_DDL = {
    "traffic_aadf": ["ALTER TABLE geo.traffic_aadf ADD PRIMARY KEY (count_point_id, year)"],
    "traffic_count_point": [
        "ALTER TABLE geo.traffic_count_point ADD PRIMARY KEY (count_point_id)",
        *(
            f"CREATE INDEX traffic_cp_{col}_idx ON geo.traffic_count_point USING gist ({col})"
            for col in ("geom_bng", "geom_3857", "link_3857")
        ),
    ],
    "traffic_la": ["ALTER TABLE geo.traffic_la ADD PRIMARY KEY (local_authority_code, year)"],
}


def _copy_count_points(conn: psycopg.Connection, path: Path) -> int:
    n = 0
    with (
        conn.cursor() as cur,
        cur.copy(
            """COPY geo.traffic_count_point__new (count_point_id, road_name, road_category,
               road_type, start_junction, end_junction, local_authority_code,
               local_authority_name, region_name, link_length_km, geom_bng) FROM STDIN"""
        ) as copy,
    ):
        for *attrs, e, north in traffic.parse_count_points(path):
            copy.write_row((*attrs, f"SRID=27700;POINT({e} {north})"))
            n += 1
    return n


def _attach_links(conn: psycopg.Connection, year: int, path: Path) -> None:
    conn.execute(
        "CREATE TEMP TABLE mrdb_link (count_point_id integer, link geometry) ON COMMIT DROP"
    )
    with conn.cursor() as cur, cur.copy("COPY mrdb_link FROM STDIN") as copy:
        for cp, _road, wkt in traffic.parse_mrdb(path):
            copy.write_row((cp, wkt))
    conn.execute(
        """UPDATE geo.traffic_count_point__new p SET link_bng = m.link, link_year = %s
           FROM mrdb_link m WHERE m.count_point_id = p.count_point_id""",
        (year,),
    )


def _copy_la_traffic(conn: psycopg.Connection, path: Path) -> None:
    with conn.cursor() as cur, cur.copy("COPY geo.traffic_la__new FROM STDIN") as copy:
        for row in traffic.parse_la_traffic(path):
            copy.write_row(row)


def load_traffic(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    aadf = download_file(client, traffic.AADF_URL, data_dir, "dft_traffic_counts_aadf.zip")
    points = download_file(client, traffic.COUNT_POINTS_URL, data_dir, "dft_count_points.zip")
    la = download_file(client, traffic.LA_TRAFFIC_URL, data_dir, "dft_local_authority_traffic.csv")
    with conn.transaction():
        for table, ddl in _TRAFFIC_TABLES_DDL.items():
            conn.execute(f"DROP TABLE IF EXISTS geo.{table}__new")
            conn.execute(ddl)
        data_year = _copy_aadf(conn, aadf.path)
        n_points = _copy_count_points(conn, points.path)
        conn.execute(_TRAFFIC_DERIVED, {"data_year": data_year, "stale": TRAFFIC_STALE_YEARS})
        mrdb = _download_mrdb(client, data_dir, data_year)
        if mrdb is not None:
            _attach_links(conn, *mrdb)
        # Web Mercator copies for map tiles, so tiles never re-project per request.
        conn.execute(
            """UPDATE geo.traffic_count_point__new
               SET geom_3857 = ST_Transform(geom_bng, 3857),
                   link_3857 = ST_Transform(link_bng, 3857)"""
        )
        _copy_la_traffic(conn, la.path)
    detail = f"AADF {data_year}; " + (f"MRDB {mrdb[0]}" if mrdb else "no MRDB")
    _swap_tables(
        conn, "traffic", _TRAFFIC_SWAP_DDL, "DfT road traffic statistics", n_points, detail
    )
    # count points -> OS road links; junction arms take their counts from the links; flows
    # changed, so refit the safety models and the authorities' traffic
    rebuild(conn, "traffic_links", "junctions", "safety", "authorities")


# ------------------------------------------------------------------ orchestration

Loader = Callable[[psycopg.Connection, httpx.Client, Path], None]
DATASETS: dict[str, Loader] = {
    "postcode": load_postcodes,
    "place": load_places,
    "boundary": load_boundaries,
    "population": load_population,  # with traffic and boundaries: authority rates (V4)
    "value_of_prevention": load_prevention,
    "road_network": load_road_network,  # before traffic: count points are matched to it
    "traffic": load_traffic,
    "osm_nodes": load_osm_nodes,  # OSM: signal-controlled junctions and mini-roundabouts
}


def refresh_reference(
    conn: psycopg.Connection,
    client: httpx.Client,
    data_dir: Path,
    datasets: list[str] | None = None,
) -> list[str]:
    target = data_dir / "reference"
    chosen = datasets or list(DATASETS)
    # derived tables (links, junctions, matches, safety) rebuild once, after every dataset
    with deferred(conn):
        for name in chosen:
            log.info("refreshing reference dataset %s", name)
            DATASETS[name](conn, client, target)
    return chosen


def refresh_if_stale(
    conn: psycopg.Connection, client: httpx.Client, data_dir: Path, max_age_days: int = 90
) -> list[str]:
    fresh = {
        r[0]
        for r in conn.execute(
            """SELECT dataset FROM geo.reference_refresh
               WHERE refreshed_at > now() - %s * interval '1 day'""",
            (max_age_days,),
        )
    }
    conn.commit()
    stale = [d for d in DATASETS if d not in fresh]
    if stale:
        return refresh_reference(conn, client, data_dir, stale)  # also runs any pending builds
    run_pending(conn)  # a derived build that failed earlier (FU-051)
    return []
