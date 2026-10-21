"""Reference loaders end-to-end against PostGIS, with all sources mocked."""

import json
import urllib.parse

import httpx
import pytest

from stats19 import db
from stats19.reference.boundaries import ARCGIS_ROOT
from stats19.reference.names import SOURCE_URL as NAMES_URL
from stats19.reference.osm_nodes import SOURCE_URL as OSM_URL
from stats19.reference.population import population_url
from stats19.reference.postcodes import SOURCE_URL as POSTCODES_URL
from stats19.reference.prevention import DATA_TABLES_API
from stats19.reference.refresh import DATASETS, refresh_if_stale, refresh_reference
from stats19.reference.roads import SOURCE_URL as ROADS_URL
from stats19.reference.traffic import AADF_URL, COUNT_POINTS_URL, LA_TRAFFIC_URL, MRDB_URL
from stats19.reference.traffic_links import build_traffic_links

from .osm_fixtures import osm_pbf
from .road_fixtures import roads_zip
from .test_reference_parsers import CONTENT_XML, NAMES_ROW, _zip
from .traffic_fixtures import LA_CSV, aadf_zip, count_points_zip, mrdb_zip

pytestmark = pytest.mark.integration

RAS_URL = "https://assets.publishing.service.gov.uk/media/abc/ras4001.ods"

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-3.6, 50.7], [-3.4, 50.7], [-3.4, 50.8], [-3.6, 50.8], [-3.6, 50.7]]],
}


def _features(code_field: str, name_field: str, items: list[tuple[str, str]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": SQUARE, "properties": {code_field: c, name_field: n}}
            for c, n in items
        ],
    }


def _transport(requested: list[str]):
    postcodes = _zip(
        {
            "Data/CSV/ex.csv": '"EX1 1AE",10,291966,92583,"E92000001","","","E10000008","E07000041","E05011020"\n'
        }
    )
    names = _zip(
        {
            "Data/SX99.csv": NAMES_ROW.format(
                name="Sidwell Street", type="transportNetwork", local="Named Road"
            )
            + "\n"
            + NAMES_ROW.format(name="Exeter", type="populatedPlace", local="City").replace(
                "osgb4000000074564391", "osgb4000000000000002"
            )
            + "\n"
        }
    )
    ods = _zip(
        {"mimetype": "application/vnd.oasis.opendocument.spreadsheet", "content.xml": CONTENT_XML}
    )
    services = {
        "services": [
            {"name": "Counties_and_Unitary_Authorities_December_2024_Boundaries_UK_BGC"},
            {"name": "Local_Authority_Districts_May_2026_Boundaries_UK_BGC"},
            {"name": "Police_Force_Areas_December_2023_EW_BGC"},
        ]
    }
    layers = {
        "Counties_and_Unitary_Authorities": _features(
            "CTYUA24CD", "CTYUA24NM", [("E10000008", "Devon")]
        ),
        "Local_Authority_Districts": _features("LAD26CD", "LAD26NM", [("E07000041", "Exeter")]),
        "Police_Force_Areas": _features("PFA23CD", "PFA23NM", [("E23000035", "Devon & Cornwall")]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url == POSTCODES_URL:
            return httpx.Response(200, content=postcodes)
        if url == NAMES_URL:
            return httpx.Response(200, content=names)
        if url == DATA_TABLES_API:
            return httpx.Response(
                200, json={"details": {"body": f'<a href="{RAS_URL}">RAS4001</a>'}}
            )
        if url == RAS_URL:
            return httpx.Response(200, content=ods)
        if url == population_url():
            return httpx.Response(
                200,
                text='"DATE_NAME","GEOGRAPHY_CODE","OBS_VALUE"\n'
                '"2024","E10000008",820000\n"2025","E10000008",830000\n',
            )
        traffic = {
            AADF_URL: aadf_zip(),
            COUNT_POINTS_URL: count_points_zip(),
            LA_TRAFFIC_URL: LA_CSV.encode(),
            MRDB_URL.format(year=2024): mrdb_zip(),  # 2025 not yet published: 404 below
            ROADS_URL: roads_zip(),
            OSM_URL: osm_pbf(),
        }
        if url in traffic:
            return httpx.Response(200, content=traffic[url])
        if url.startswith(ARCGIS_ROOT):
            path = urllib.parse.urlparse(url).path
            if path.endswith("/services"):
                return httpx.Response(200, json=services)
            offset = int(
                dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["resultOffset"]
            )
            for prefix, fc in layers.items():
                if f"/{prefix}_" in path:
                    body = fc if offset == 0 else {"type": "FeatureCollection", "features": []}
                    return httpx.Response(200, content=json.dumps(body))
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def client():
    requested: list[str] = []
    with httpx.Client(transport=_transport(requested)) as c:
        c.requested = requested
        yield c


def _one(conn, q, p=None):
    return conn.execute(q, p).fetchone()


def test_refresh_loads_all_reference_tables(db_conn, client, tmp_path):
    db.migrate(db_conn)

    refresh_reference(db_conn, client, tmp_path)

    assert _one(
        db_conn, "SELECT postcode, admin_district_code, ST_X(geom_bng)::int FROM geo.postcode"
    ) == (
        "EX1 1AE",
        "E07000041",
        291966,
    )
    assert _one(db_conn, "SELECT count(*), min(category), max(category) FROM geo.place") == (
        2,
        "place",
        "road",
    )
    assert db_conn.execute(
        "SELECT boundary_type, code, name, vintage FROM geo.boundary ORDER BY 1"
    ).fetchall() == [
        ("district", "E07000041", "Exeter", "2026-05"),
        ("highway_authority", "E10000008", "Devon", "2024-12"),
        ("police_force", "E23000035", "Devon & Cornwall", "2023-12"),
    ]
    assert _one(
        db_conn, "SELECT ST_SRID(geom_bng), ST_IsValid(geom_bng) FROM geo.boundary LIMIT 1"
    ) == (27700, True)
    assert _one(
        db_conn, "SELECT per_collision FROM geo.value_of_prevention WHERE severity = 'Fatal'"
    ) == (2896024.2,)
    assert {r[0] for r in db_conn.execute("SELECT dataset FROM geo.reference_refresh")} == set(
        DATASETS
    ) | {"traffic_links", "junctions", "authorities"}


def test_refresh_is_repeatable(db_conn, client, tmp_path):
    db.migrate(db_conn)
    refresh_reference(db_conn, client, tmp_path)
    refresh_reference(db_conn, client, tmp_path)

    assert _one(db_conn, "SELECT count(*) FROM geo.postcode") == (1,)


def test_refresh_if_stale_skips_recent(db_conn, client, tmp_path):
    db.migrate(db_conn)
    refresh_reference(db_conn, client, tmp_path)
    client.requested.clear()

    refreshed = refresh_if_stale(db_conn, client, tmp_path, max_age_days=90)

    assert refreshed == []
    assert client.requested == []


def test_refresh_if_stale_reloads_old_dataset(db_conn, client, tmp_path):
    db.migrate(db_conn)
    refresh_reference(db_conn, client, tmp_path)
    db_conn.execute(
        "UPDATE geo.reference_refresh SET refreshed_at = now() - interval '200 days' WHERE dataset = 'postcode'"
    )
    db_conn.commit()

    assert refresh_if_stale(db_conn, client, tmp_path, max_age_days=90) == ["postcode"]


def test_os_downloads_get_distinct_filenames(db_conn, client, tmp_path):
    db.migrate(db_conn)
    refresh_reference(db_conn, client, tmp_path, ["postcode", "place"])

    assert sorted(p.name for p in (tmp_path / "reference").iterdir()) == [
        "codepoint_open.zip",
        "open_names.zip",
    ]


def test_traffic_load_derives_quality_links_and_la(db_conn, client, tmp_path):
    db.migrate(db_conn)

    refresh_reference(db_conn, client, tmp_path, ["traffic"])

    rows = db_conn.execute(
        """SELECT count_point_id, quality, latest_year, last_counted_year, latest_aadf,
                  link_year, ST_NumGeometries(link_bng)
           FROM geo.traffic_count_point ORDER BY 1"""
    ).fetchall()
    assert rows == [
        (1001, 0, 2025, 2025, 21000, 2024, 1),
        (1002, 1, 2025, 2022, 31500, 2024, 2),
        (1003, 3, 2012, 2012, 400, None, None),
        (1004, 2, 2025, 2015, 1300, None, None),
    ]
    assert _one(
        db_conn, "SELECT latest_hgv_pct FROM geo.traffic_count_point WHERE count_point_id = 1001"
    ) == (1.4,)
    assert _one(db_conn, "SELECT count(*) FROM geo.traffic_aadf") == (9,)
    assert _one(db_conn, "SELECT vehicle_miles FROM geo.traffic_la WHERE year = 2025") == (7.0e9,)
    assert _one(db_conn, "SELECT detail FROM geo.reference_refresh WHERE dataset = 'traffic'") == (
        "AADF 2025; MRDB 2024",
    )
    assert MRDB_URL.format(year=2025) in client.requested  # tried the newest first


def test_traffic_load_without_any_mrdb(db_conn, tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if "mrdb-" in str(request.url):
            return httpx.Response(404)
        return inner.handle_request(request)

    inner = _transport([])
    db.migrate(db_conn)
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        refresh_reference(db_conn, c, tmp_path, ["traffic"])

    assert _one(db_conn, "SELECT count(link_bng) FROM geo.traffic_count_point") == (0,)
    assert _one(db_conn, "SELECT detail FROM geo.reference_refresh WHERE dataset = 'traffic'") == (
        "AADF 2025; no MRDB",
    )


def test_road_network_load_skips_fictitious_and_keeps_attributes(db_conn, client, tmp_path):
    db.migrate(db_conn)

    refresh_reference(db_conn, client, tmp_path, ["road_network"])

    assert _one(db_conn, "SELECT count(*) FROM geo.road_link") == (23,)
    assert _one(
        db_conn,
        "SELECT road_class, road_number, name, round(length_m), ST_SRID(geom_bng) "
        "FROM geo.road_link WHERE id = 'M1'",
    ) == ("Unclassified", None, "Mill Lane", 100, 27700)
    assert _one(db_conn, "SELECT count(*) FROM geo.road_node") == (28,)
    assert _one(db_conn, "SELECT id, junction_number FROM geo.motorway_junction") == (
        "MJ1",
        "M5 J30",
    )
    assert not list((tmp_path / "reference").glob("*.gpkg"))  # the 2 GB unpack is removed
    # no traffic yet, so no links were built
    assert _one(db_conn, "SELECT to_regclass('geo.traffic_stretch') IS NULL") == (True,)


def test_traffic_links_trace_major_links_and_grow_minor_stretches(db_conn, client, tmp_path):
    db.migrate(db_conn)

    refresh_reference(db_conn, client, tmp_path, ["road_network", "traffic"])

    links = db_conn.execute(
        "SELECT link_id, count_point_id, method, round(frac_from::numeric, 2), "
        "round(frac_to::numeric, 2) FROM geo.traffic_link ORDER BY 1"
    ).fetchall()
    assert [(lid, cp, m) for lid, cp, m, *_ in links] == [
        ("A30-1", 1001, "major"),
        ("A30-2", 1001, "major"),
        ("A38-1", 1002, "major"),
        ("C1", 1004, "minor"),
        ("M1", 1003, "minor"),
        ("M2", 1003, "minor"),
    ]  # not A30-3 (beyond the DfT line), the slip road, or M3 (past the B3212 junction)
    stretches = db_conn.execute(
        "SELECT count_point_id, method, round(length_m), links, name FROM geo.traffic_stretch ORDER BY 1"
    ).fetchall()
    assert stretches == [
        (1001, "major", 2059, 2, None),
        (1002, "major", 1628, 1, None),
        (1003, "minor", 250, 2, "Mill Lane"),
        (1004, "minor", 200, 1, None),
    ]
    assert _one(
        db_conn, "SELECT detail FROM geo.reference_refresh WHERE dataset = 'traffic_links'"
    ) == ("major count points rescued 0, unmatched 0; minor count points snapped 2, unmatched 0",)


def test_unmatched_major_count_point_takes_the_os_link_it_sits_on(db_conn, client, tmp_path):
    # FU-034 #1: DfT still calls this road the A3999, OS numbers it A30 (renumbered), so
    # no OS link carries its number; it sits on A30-3, which no other count point claims.
    db.migrate(db_conn)
    refresh_reference(db_conn, client, tmp_path, ["road_network", "traffic"])
    db_conn.execute(
        """INSERT INTO geo.traffic_count_point (count_point_id, road_name, road_type, quality,
               geom_bng, link_bng)
           VALUES (1009, 'A3999', 'Major', 0, ST_SetSRID(ST_MakePoint(293150, 93200), 27700),
                   ST_Multi(ST_SetSRID(ST_MakeLine(ST_MakePoint(292850, 93030),
                                                   ST_MakePoint(293450, 93370)), 27700)))"""
    )
    db_conn.commit()

    build_traffic_links(db_conn)

    assert db_conn.execute(
        "SELECT link_id, method FROM geo.traffic_link WHERE count_point_id = 1009"
    ).fetchall() == [("A30-3", "major")]
    assert _one(
        db_conn, "SELECT detail FROM geo.reference_refresh WHERE dataset = 'traffic_links'"
    ) == ("major count points rescued 1, unmatched 0; minor count points snapped 2, unmatched 0",)


def test_authority_rates_denominators_come_from_population_and_traffic(db_conn, client, tmp_path):
    db.migrate(db_conn)

    refresh_reference(db_conn, client, tmp_path, ["boundary", "population", "traffic"])

    assert _one(db_conn, "SELECT code, name, region FROM geo.authority") == (
        "E10000008",
        "Devon",
        "South West",
    )
    row = _one(
        db_conn,
        """SELECT population, round(vehicle_km), round(major_vehicle_km),
                  round(minor_vehicle_km), road_km
           FROM geo.authority_year WHERE code = 'E10000008' AND year = 2025""",
    )
    all_km = 7.0e9 * 1.609344
    major_km = (21_000 * 2.0 + 31_500 * 1.5) * 365  # AADF x link length, the two A roads
    assert row == (830_000, round(all_km), round(major_km), round(all_km - major_km), 13010)
    assert _one(db_conn, "SELECT count(*) FROM geo.authority_peer") == (0,)  # no others
