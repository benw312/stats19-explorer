"""ONS mid-year population estimates from Nomis (PLAN-009 §10)."""

import pytest

from stats19.reference.population import parse_population, population_url

NOMIS_CSV = (
    '"DATE_NAME","GEOGRAPHY_CODE","OBS_VALUE"\n'
    '"2024","E06000001",98000\n'
    '"2025","E06000001",99656\n'
    '"2025","E08000016",250000\n'  # Barnsley, under its pre-2023 code
    '"2025","S12000049",""\n'  # suppressed: skipped
)


def test_parse_population_reads_rows_and_maps_old_codes():
    rows = parse_population(NOMIS_CSV)

    assert rows == [
        ("E06000001", 2024, 98000),
        ("E06000001", 2025, 99656),
        ("E08000038", 2025, 250000),  # Barnsley's current code, as the boundaries use
    ]


def test_parse_population_rejects_an_unexpected_layout():
    with pytest.raises(ValueError, match="GEOGRAPHY_CODE"):
        parse_population('"DATE","AREA","VALUE"\n"2025","E06000001",1\n')


def test_population_url_asks_for_all_persons_in_every_authority():
    url = population_url(years=20)

    assert "NM_2002_1" in url
    assert "geography=TYPE423" in url
    assert "date=latestMINUS19-latest" in url
    assert "gender=0" in url and "c_age=200" in url
