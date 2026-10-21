"""/api/data-issues: DfT's documented issues for the About page and for a selection (FU-049)."""

import json

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def issues_api(api, db_conn):
    for index, force, year in [("S1", 21, 2020), ("A1", 52, 2022), ("D1", 50, 2022)]:
        db_conn.execute(
            """INSERT INTO core.collision (collision_index, collision_year, police_force, geom_bng)
               VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(292000, 92500), 27700))""",
            (index, year, force),
        )
        # exports read the mart, which joins this per-collision summary
        db_conn.execute(
            "INSERT INTO mart.collision_summary (collision_index) VALUES (%s)", (index,)
        )
    db_conn.commit()
    return api


def selection(client, **flt):
    r = client.get("/api/data-issues/selection", params={"f": json.dumps(flt)})
    assert r.status_code == 200, r.text
    return {i["id"]: i["years"] for i in r.json()["data"]["issues"]}


def test_selection_lists_the_documented_issues_its_collisions_fall_in(issues_api):
    assert selection(issues_api, year_from=2019, year_to=2022) == {
        "staffordshire-2017-2023": [2020],
        "avon-somerset-2022": [2022],
    }
    assert selection(issues_api, year_from=2021, year_to=2022) == {"avon-somerset-2022": [2022]}
    assert selection(issues_api, year_from=2023, year_to=2025) == {}


def test_all_issues_with_dft_source_for_the_about_page(issues_api):
    d = issues_api.get("/api/data-issues").json()["data"]

    assert d["source_url"].startswith("https://www.gov.uk/")
    assert len(d["issues"]) == 5
    assert all(i["dft_text"] for i in d["issues"])
    assert d["recording_gaps"] == []  # none flagged in the fixture


def test_export_marks_each_collision_and_lists_the_issues(issues_api):
    import csv
    import io
    import zipfile

    r = issues_api.get(
        "/api/export/collisions.zip", params={"f": json.dumps({"year_from": 2019, "year_to": 2022})}
    )
    assert r.status_code == 200, r.text
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = next(n for n in z.namelist() if "collision" in n and n.endswith(".csv"))
    rows = {
        row["collision_index"]: row["dft_data_issue"]
        for row in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))
    }
    about = next(
        z.read(n).decode() for n in z.namelist() if "about" in n.lower() or n.endswith(".txt")
    )

    assert rows == {"S1": "staffordshire-2017-2023", "A1": "avon-somerset-2022", "D1": ""}
    assert "Staffordshire police have under-reported collisions" in about
