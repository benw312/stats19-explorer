"""DfT's documented STATS19 data issues, curated (FU-049).

Source: "Road casualty statistics: known data issues" (gov.uk), last updated by DfT on
29 May 2025, checked 2026-10-08. Review each September, when DfT publishes the annual
statistics and updates the page. DfT's own words go in ``dft_text``; ``summary`` is ours.

The app keeps using the published data and marks any figure whose collisions include an
affected police force and year. These are separate from the *detected* recording gaps
(``geo.authority_year.recording_gap``), which are measured from the data and left out of
rates.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

SOURCE_URL = (
    "https://www.gov.uk/government/publications/reported-road-casualty-statistics-background-"
    "quality-report/road-casualty-statistics-known-data-issues"
)
SOURCE_UPDATED = "2025-05-29"  # DfT's "last updated" date for the page
CHECKED = "2026-10-08"

IssueKind = Literal["under_recording", "incomplete", "coding", "discrepancy"]


@dataclass(frozen=True)
class DataIssue:
    id: str
    title: str
    police_forces: tuple[int, ...]  # STATS19 police_force codes
    year_from: int
    year_to: int
    kind: IssueKind
    summary: str  # one line, ours
    dft_text: str  # DfT's words
    affects: str | None = None  # a single field, when the issue is about one field

    def covers(self, police_force: int, year: int) -> bool:
        return police_force in self.police_forces and self.year_from <= year <= self.year_to


WELSH_FORCES = (60, 61, 62, 63)  # North Wales, Gwent, South Wales, Dyfed-Powys

ISSUES: tuple[DataIssue, ...] = (
    DataIssue(
        id="staffordshire-2017-2023",
        title="Staffordshire Police under-reported collisions, 2017–2023",
        police_forces=(21,),
        year_from=2017,
        year_to=2023,
        kind="under_recording",
        summary="Some reportable collisions were left out of Staffordshire's returns, so counts "
        "are too low; compare with care.",
        dft_text="Staffordshire police have under-reported collisions between 2017 and 2023 due "
        "to issues with timely and completed processing, where reportable collisions within "
        "their systems were not included in STATS19 returns.",
    ),
    DataIssue(
        id="avon-somerset-2022",
        title="Avon and Somerset Police changed recording systems, 2022",
        police_forces=(52,),
        year_from=2022,
        year_to=2022,
        kind="incomplete",
        summary="Key data was missing after a change of recording system, so some records may "
        "be incomplete.",
        dft_text="Avon and Somerset police changed collision recording systems during 2022. The "
        "transition has exposed some formatting and export issues. Most notably key data was "
        "missing, which has impacted Local processing authorities (LPA) ability to process and "
        "validate the data.",
    ),
    DataIssue(
        id="greater-manchester-2022",
        title="Greater Manchester Police: late and deleted records, 2022",
        police_forces=(6,),
        year_from=2022,
        year_to=2022,
        kind="incomplete",
        summary="Some 2022 collisions were supplied too late to include, and some were deleted.",
        dft_text="Some collisions were not supplied in time for inclusion and some additional "
        "deletions were reported alongside the 2022 figures.",
    ),
    DataIssue(
        id="wales-speed-limit-2023",
        title="Wales: speed limits corrected after the September 2023 change",
        police_forces=WELSH_FORCES,
        year_from=2023,
        year_to=2023,
        kind="coding",
        summary="Welsh speed limits were corrected for Wales only, so speed limit figures aren't "
        "comparable with the rest of Great Britain.",
        dft_text="The changes made in Wales but not for Great Britain will impact on the "
        "comparability of figures for casualties or collisions by road speed limit.",
        affects="speed_limit",
    ),
    DataIssue(
        id="greater-manchester-2025",
        title="Greater Manchester and others: local figures differ, 2025",
        police_forces=(6,),
        year_from=2025,
        year_to=2025,
        kind="discrepancy",
        summary="Local authorities including Greater Manchester report different casualty "
        "figures from DfT's; under investigation.",
        dft_text="A number of local authorities - including Greater Manchester - have "
        "highlighted discrepancies between casualty data held by the Department and that held "
        "locally.",
    ),
)

BY_ID = {issue.id: issue for issue in ISSUES}


def issues_for(force_years: Iterable[tuple[int, int]]) -> dict[str, list[int]]:
    """Issue id -> the years it affects among these (police force, year) pairs."""
    out: dict[str, set[int]] = {}
    for force, year in force_years:
        for issue in ISSUES:
            if issue.covers(force, year):
                out.setdefault(issue.id, set()).add(year)
    return {i: sorted(years) for i, years in out.items()}
