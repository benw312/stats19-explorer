"""Map endpoints: vector tiles and collision detail."""

import json
import math

import pytest

pytestmark = pytest.mark.integration

MVT = "application/vnd.mapbox-vector-tile"


def tile_for(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


# Fixture collision 1980A sits at lon -1.2642, lat 54.5665 (Teesside).
X14, Y14 = tile_for(-1.2642, 54.5665, 14)
X6, Y6 = tile_for(-1.2642, 54.5665, 6)


def _tile(api, z, x, y, f=None):
    params = {"f": json.dumps(f)} if f is not None else {}
    return api.get(f"/api/tiles/collisions/{z}/{x}/{y}.mvt", params=params)


def test_point_tile_contains_collision(api):
    r = _tile(api, 14, X14, Y14)

    assert r.status_code == 200
    assert r.headers["content-type"] == MVT
    assert b"collisions" in r.content  # layer name
    assert len(r.content) > 20


def test_empty_tile_elsewhere(api):
    r = _tile(api, 14, X14 + 50, Y14)

    assert r.status_code == 200
    assert r.content == b""


def test_filter_applies_to_tiles(api):
    # fixture collisions have severity 1 (default code); asking for slight only empties the tile
    assert _tile(api, 14, X14, Y14, {"severity": [3]}).content == b""
    assert _tile(api, 14, X14, Y14, {"severity": [1]}).content != b""


def test_low_zoom_tile_is_aggregated(api):
    r = _tile(api, 6, X6, Y6)

    assert r.status_code == 200
    assert b"collision_bins" in r.content


def test_invalid_filter_rejected(api):
    r = api.get(f"/api/tiles/collisions/14/{X14}/{Y14}.mvt", params={"f": '{"severity":[9]}'})

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_malformed_filter_json_rejected(api):
    r = api.get(f"/api/tiles/collisions/14/{X14}/{Y14}.mvt", params={"f": "{not json"})

    assert r.status_code == 422


@pytest.mark.parametrize(
    "path", ["/api/tiles/collisions/25/0/0.mvt", "/api/tiles/collisions/3/9/0.mvt"]
)
def test_tile_coordinates_validated(api, path):
    assert api.get(path).status_code == 422


def test_collision_detail(api):
    d = api.get("/api/collisions/1980A").json()["data"]

    assert d["collision"]["collision_index"] == "1980A"
    assert d["collision"]["light_conditions_label"] == "One"
    assert "geom_bng" not in d["collision"]
    assert round(d["collision"]["lon"], 4) == -1.2642
    assert [v["vehicle_reference"] for v in d["vehicles"]] == [1, 2]
    assert [k["casualty_reference"] for k in d["casualties"]] == [1, 2]
    assert d["vehicles"][0]["road_user_group"] == "pedal_cycle"
    assert set(d["collision"]) >= {"highway_authority_name", "district_name"}


def test_collision_not_found(api):
    r = api.get("/api/collisions/2099ZZZZZZ")

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_collision_index_validated(api):
    assert api.get("/api/collisions/abc;drop").status_code == 422


def test_simple_filter_low_zoom_uses_pre_aggregated_grid(api, db_conn):
    from stats19.api.filters import Filter
    from stats19.api.tiles import uses_grid

    assert uses_grid(Filter(year_from=2020, severity=[1]), 6)
    assert not uses_grid(Filter(year_from=2020), 12)
    assert not uses_grid(Filter(involves=["motorcycle"]), 6)
    assert not uses_grid(
        Filter(fields=[{"table": "collision", "field": "light_conditions", "values": [4]}]), 6
    )

    # grid tile has the same total as the live aggregation
    grid = db_conn.execute("SELECT sum(n) FROM mart.collision_grid WHERE lvl = 8").fetchone()[0]
    assert (
        grid
        == db_conn.execute(
            "SELECT count(*) FROM core.collision WHERE geom_3857 IS NOT NULL"
        ).fetchone()[0]
    )
    r = _tile(api, 6, X6, Y6, {"severity": [1]})
    assert r.status_code == 200 and b"collision_bins" in r.content


def test_dense_point_tile_falls_back_to_fine_bins(api, monkeypatch):
    import stats19.api.tiles as tiles

    monkeypatch.setattr(tiles, "MAX_POINTS_PER_TILE", 0)

    r = _tile(api, 14, X14, Y14)

    assert b"collision_bins" in r.content
    assert b"collisions" not in r.content.replace(b"collision_bins", b"")


def test_tiles_are_cached_per_filter_and_data_load(api, monkeypatch):
    import json

    import stats19.api.tiles as tiles

    calls: list[int] = []
    real = tiles._query_for
    monkeypatch.setattr(tiles, "_query_for", lambda *a: calls.append(1) or real(*a))
    tiles.TILE_CACHE.clear()
    f = json.dumps({"severity": [3]})

    first = api.get("/api/tiles/collisions/6/31/20.mvt", params={"f": f})
    again = api.get("/api/tiles/collisions/6/31/20.mvt", params={"f": f})
    other = api.get("/api/tiles/collisions/6/31/20.mvt")

    assert first.content == again.content
    assert len(calls) == 2  # the repeat came from the cache; another filter did not
    assert other.status_code == 200
    tiles.TILE_CACHE.clear()
