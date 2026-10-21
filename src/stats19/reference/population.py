"""ONS mid-year population estimates per local authority, from Nomis (PLAN-009 §10).

Dataset NM_2002_1 (population estimates, local authority based), all persons, all ages,
for every county and unitary authority (geography type 423, April 2023 boundaries), which
covers all highway authorities in GB on today's boundaries back to 2011. OGL.
"""

from __future__ import annotations

import csv
import io

NOMIS_DATA = "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv"
YEARS = 20

# Nomis still publishes these two under their pre-2023 codes (as DfT's traffic tables do);
# the boundaries and STATS19's current-authority field use the new ones.
CODE_UPDATES = {
    "E08000016": "E08000038",  # Barnsley
    "E08000019": "E08000039",  # Sheffield
}

PopulationRow = tuple[str, int, int]  # (authority code, year, population)


def population_url(years: int = YEARS) -> str:
    return (
        f"{NOMIS_DATA}?geography=TYPE423&date=latestMINUS{years - 1}-latest"
        "&gender=0&c_age=200&measures=20100&select=date_name,geography_code,obs_value"
    )


def parse_population(text: str) -> list[PopulationRow]:
    reader = csv.DictReader(io.StringIO(text))
    needed = {"DATE_NAME", "GEOGRAPHY_CODE", "OBS_VALUE"}
    if not needed <= set(reader.fieldnames or []):
        raise ValueError(f"Nomis population CSV: expected columns {sorted(needed)}")
    rows = []
    for r in reader:
        if not r["OBS_VALUE"]:
            continue
        code = CODE_UPDATES.get(r["GEOGRAPHY_CODE"], r["GEOGRAPHY_CODE"])
        rows.append((code, int(r["DATE_NAME"]), int(float(r["OBS_VALUE"]))))
    return rows
