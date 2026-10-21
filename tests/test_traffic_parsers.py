"""Parsers for DfT traffic downloads: AADF, count points, LA traffic, MRDB shapefile."""

import pytest

from stats19.reference.traffic import (
    _dbf_records,
    _shp_lines,
    parse_aadf,
    parse_count_points,
    parse_la_traffic,
    parse_mrdb,
)

from .traffic_fixtures import (
    LA_CSV,
    MRDB_FIELDS,
    aadf_zip,
    count_points_zip,
    dbf_bytes,
    mrdb_zip,
    shp_bytes,
    zip_bytes,
)


@pytest.fixture
def write(tmp_path):
    def _write(name: str, content: bytes | str):
        path = tmp_path / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
        return path

    return _write


def test_parse_aadf_reads_method_and_vehicles(write):
    rows = list(parse_aadf(write("aadf.zip", aadf_zip())))

    assert len(rows) == 9
    cp, year, method, detail, *vehicles, length_km = rows[1]
    assert (cp, year, method, detail) == (1001, 2025, "Counted", "Manual count")
    assert vehicles[0] == 10  # pedal cycles first
    assert vehicles[-1] == 21000  # all motor vehicles last
    assert length_km == 2.0  # that year's link length (FU-047 #8)


def test_parse_aadf_handles_exponents_blanks_and_na(write):
    rows = {(r[0], r[1]): r for r in parse_aadf(write("aadf.zip", aadf_zip()))}
    vehicles = rows[(1004, 2025)][4:-1]

    assert vehicles[-1] == 1300  # "1.3e+03"
    assert vehicles[6] is None  # blank HGV_3_rigid
    assert vehicles[7] is None  # "NA"


def test_parse_aadf_rejects_zip_without_csv(write):
    with pytest.raises(ValueError, match="no member"):
        list(parse_aadf(write("aadf.zip", zip_bytes({"readme.txt": "x"}))))


def test_parse_count_points_skips_unlocated_and_maps_na(write):
    rows = list(parse_count_points(write("cp.zip", count_points_zip())))

    assert [r[0] for r in rows] == [1001, 1002, 1003, 1004]  # 9999 has no coordinates
    minor = rows[2]
    assert minor[4] is None and minor[5] is None  # junctions "NA"
    assert minor[9] is None  # no link length on minor roads
    assert rows[0][9] == 2.0 and rows[0][10:] == (291900.0, 92500.0)


def test_parse_la_traffic(write):
    rows = list(parse_la_traffic(write("la.csv", LA_CSV)))

    assert rows == [
        ("E10000008", "Devon", 2024, 13000.0, 5.1e9, 6.9e9),
        ("E10000008", "Devon", 2025, 13010.0, 5.2e9, 7.0e9),
    ]


def test_shp_lines_reads_parts_and_null_shapes():
    shapes = _shp_lines(shp_bytes([[[(0, 0), (1, 1)]], [], [[(0, 0), (1, 0)], [(2, 0), (3, 0)]]]))

    assert shapes == [
        [[(0.0, 0.0), (1.0, 1.0)]],
        [],
        [[(0.0, 0.0), (1.0, 0.0)], [(2.0, 0.0), (3.0, 0.0)]],
    ]


def test_dbf_records_strip_padding():
    records = _dbf_records(dbf_bytes(MRDB_FIELDS, [["1.00100000000e+03", "A30"]]))

    assert records == [{"CP_Number": "1.00100000000e+03", "RoadNumber": "A30"}]


def test_parse_mrdb_yields_ewkt_per_link_and_skips_null_shapes(write):
    links = list(parse_mrdb(write("mrdb.zip", mrdb_zip())))

    assert [(cp, road) for cp, road, _ in links] == [(1001, "A30"), (1002, "A38")]
    assert links[0][2] == "SRID=27700;MULTILINESTRING((291000.0 92000.0,292800.0 93000.0))"
    assert links[1][2].count("(") == 3  # two parts


def test_parse_mrdb_requires_shp_and_dbf(write):
    with pytest.raises(ValueError, match=r"\.shp/\.dbf"):
        list(parse_mrdb(write("mrdb.zip", zip_bytes({"x.shp": b""}))))


def test_parse_mrdb_rejects_mismatched_counts(write):
    bad = zip_bytes({"m.shp": shp_bytes([[[(0, 0), (1, 1)]]]), "m.dbf": dbf_bytes(MRDB_FIELDS, [])})
    with pytest.raises(ValueError, match="1 shapes but 0 records"):
        list(parse_mrdb(write("mrdb.zip", bad)))
