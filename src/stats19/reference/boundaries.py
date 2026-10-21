"""ONS Open Geography boundaries via the ONS ArcGIS feature services (OGL)."""

from __future__ import annotations

import re
from dataclasses import dataclass

ARCGIS_ROOT = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"

_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        start=1,
    )
}
_VINTAGE = re.compile(r"_(" + "|".join(_MONTHS) + r")_(\d{4})_")


@dataclass(frozen=True)
class BoundarySet:
    boundary_type: str  # our name
    prefix: str  # ONS service name prefix
    suffix: str  # generalised, clipped variant


BOUNDARY_SETS = (
    # Counties and unitary authorities ~= highway authorities (local_authority_highway_current)
    BoundarySet("highway_authority", "Counties_and_Unitary_Authorities", "UK_BGC"),
    BoundarySet("district", "Local_Authority_Districts", "UK_BGC"),
    BoundarySet("police_force", "Police_Force_Areas", "EW_BGC"),
)


def parse_vintage(service_name: str) -> tuple[int, int] | None:
    m = _VINTAGE.search(service_name)
    return (int(m.group(2)), _MONTHS[m.group(1)]) if m else None


def latest_service(service_names: list[str], prefix: str, suffix: str) -> str | None:
    """Newest service '<prefix>_<Month>_<Year>_Boundaries_<suffix>' by date (not alphabet)."""
    candidates = [
        n
        for n in set(service_names)
        if n.startswith(prefix + "_") and n.endswith("_" + suffix) and parse_vintage(n)
    ]
    return max(candidates, key=parse_vintage, default=None)
