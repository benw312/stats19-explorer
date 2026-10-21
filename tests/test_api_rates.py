"""/api/rates: authority casualty rates against similar authorities (PLAN-009 §10)."""

import json

import pytest

pytestmark = pytest.mark.integration

DEVON = {"type": "authority", "boundary_type": "highway_authority", "code": "E10000008"}
MILE = 1.609344
POPULATION = 820_000 + 830_000  # 2024 + 2025, from the Nomis fixture
ALL_VKM = (6.9e9 + 7.0e9) * MILE  # DfT LA traffic fixture
MAJOR_VKM = ((20_000 * 2.0 + 31_000 * 1.5) + (21_000 * 2.0 + 31_500 * 1.5)) * 365  # 2024, 2025

# collision, year, police first road class, collision severity, casualties (type, class, sev)
COLLISIONS = [
    ("R1", 2025, 3, 2, [(0, 3, 2), (9, 1, 3)]),  # A road: a pedestrian and a driver
    ("R2", 2025, 6, 3, [(9, 1, 3)]),  # unclassified road
    ("R3", 2024, 4, 1, [(1, 1, 1)]),  # B road: a cyclist killed
]


@pytest.fixture
def rates_api(api, db_conn):
    for index, year, road_class, severity, casualties in COLLISIONS:
        db_conn.execute(
            """INSERT INTO core.collision (collision_index, collision_year, first_road_class,
                   collision_severity, local_authority_highway_current, geom_bng)
               VALUES (%s, %s, %s, %s, 'E10000008', ST_SetSRID(ST_MakePoint(292000, 92500), 27700))""",
            (index, year, road_class, severity),
        )
        for seq, (ctype, cclass, csev) in enumerate(casualties, start=1):
            db_conn.execute(
                """INSERT INTO core.casualty (collision_index, casualty_reference, casualty_seq,
                       casualty_type, casualty_class, casualty_severity)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (index, seq, seq, ctype, cclass, csev),
            )
    db_conn.commit()
    return api


def get(client, **flt):
    r = client.get(
        "/api/rates", params={"f": json.dumps({"year_from": 2024, "year_to": 2025} | flt)}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_authority_rates_use_population_traffic_and_road_class(rates_api):
    d = get(rates_api, area=DEVON)

    assert d["scope"] == "authority"
    assert d["authority"] == {"code": "E10000008", "name": "Devon", "region": "South West"}
    own = d["rates"]["self"]
    assert own["per_100k_pop"]["count"] == 4
    assert own["per_100k_pop"]["value"] == pytest.approx(4 / POPULATION * 1e5)
    assert own["ksi_per_100k_pop"]["count"] == 2  # the pedestrian (serious), the cyclist
    assert own["per_100m_vkm"]["value"] == pytest.approx(4 / ALL_VKM * 1e8)
    assert own["major_per_100m_vkm"]["count"] == 2
    assert own["major_per_100m_vkm"]["value"] == pytest.approx(2 / MAJOR_VKM * 1e8)
    assert own["minor_per_100m_vkm"]["count"] == 2
    assert own["per_100k_pop"]["low"] < own["per_100k_pop"]["value"] < own["per_100k_pop"]["high"]
    assert d["peers"] == []  # the fixture has one authority
    assert d["rates"]["rank"]["per_100k_pop"] == {"rank": 1, "of": 1}
    assert [y["year"] for y in d["by_year"]] == [2024, 2025]
    assert d["by_year"][0]["self"]["per_100k_pop"] == pytest.approx(1 / 820_000 * 1e5)
    assert d["rates"]["gb"]["per_100k_pop"]["count"] == 4


def test_casualty_choices_narrow_the_numerator(rates_api):
    pedestrians = get(
        rates_api,
        area=DEVON,
        fields=[{"table": "casualty", "field": "casualty_class", "values": [3]}],
    )
    killed_or_serious = get(rates_api, area=DEVON, severity=[1, 2])

    assert pedestrians["rates"]["self"]["per_100k_pop"]["count"] == 1  # not the driver too
    assert killed_or_serious["rates"]["self"]["per_100k_pop"]["count"] == 2


def test_other_areas_get_the_major_road_rate_and_no_area_gets_gb(rates_api):
    radius = get(rates_api, area={"type": "radius", "lon": -3.53, "lat": 50.72, "radius_m": 20_000})
    gb = get(rates_api)

    assert radius["scope"] == "area"
    assert set(radius["rates"]["self"]) == {"major_per_100m_vkm"}
    assert radius["rates"]["gb"]["per_100k_pop"]["count"] == 4
    assert gb["scope"] == "gb"
    assert gb["rates"]["self"]["per_100k_pop"]["count"] == 4


def test_unknown_authority_is_not_found(rates_api):
    r = rates_api.get(
        "/api/rates",
        params={"f": json.dumps({"area": DEVON | {"code": "E10000099"}})},
    )

    assert r.status_code == 404


def test_a_recording_gap_year_is_left_out_of_rates_but_shown_on_the_trend(rates_api, db_conn):
    # FU-047: B&NES 2023 had 76 collisions against ~190 either side, in DfT's own file
    db_conn.execute(
        "UPDATE geo.authority_year SET recording_gap = 0.4 WHERE code = 'E10000008' AND year = 2024"
    )
    db_conn.commit()

    d = get(rates_api, area=DEVON)

    assert d["gaps"] == [{"year": 2024, "ratio": pytest.approx(0.4)}]
    assert d["rates"]["self"]["per_100k_pop"]["count"] == 3  # 2025 only
    assert d["rates"]["self"]["per_100k_pop"]["value"] == pytest.approx(3 / 830_000 * 1e5)
    assert d["rates"]["gb"]["per_100k_pop"]["count"] == 3
    trend = {y["year"]: y for y in d["by_year"]}
    assert trend[2024]["gap"] == pytest.approx(0.4)
    assert trend[2024]["self"]["per_100k_pop"] == pytest.approx(1 / 820_000 * 1e5)  # still shown
