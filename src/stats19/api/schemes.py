"""Saved road safety schemes (V5, PLAN-011 S1): list, create, read, edit, delete.

A scheme records a measure at a site, its works dates and cost, and the FYRR assumptions
used to justify it. Its footprint is stored as drawn or saved, so its evaluation (S3)
counts collisions in the same place whatever the pipeline rebuilds later.

Writes go through stats19.api.writes (same-site JSON only, rate-limited, read-only role
except on ``app``). Every query is scoped to the request's organisation.
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from stats19.api.deps import get_conn
from stats19.api.envelope import ApiError, NotFound, ok
from stats19.api.org import current_org
from stats19.api.scheme_periods import Period, Periods, chart_years, scheme_periods
from stats19.api.writes import check_write, editor, read_write
from stats19.reference.junction_build import COLLISION_RADIUS_M, JUNCTION_COLLISION
from stats19.reference.swap import tables_exist

router = APIRouter()
log = logging.getLogger(__name__)

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Org = Annotated[UUID, Depends(current_org)]

# PLAN-011 D2. The codes are stored; the labels can change freely.
MEASURES: dict[str, str] = {
    "signals": "Traffic signals (new or upgraded)",
    "roundabout": "Roundabout or mini-roundabout",
    "junction_layout": "Junction layout or priority change",
    "crossing": "Pedestrian or cycle crossing",
    "speed_limit": "Speed limit change",
    "traffic_calming": "Traffic calming",
    "surfacing": "Surfacing / anti-skid",
    "signing_lining": "Signing and lining",
    "lighting": "Street lighting",
    "camera": "Safety camera",
    "other": "Other",
}
Measure = Literal[
    "signals",
    "roundabout",
    "junction_layout",
    "crossing",
    "speed_limit",
    "traffic_calming",
    "surfacing",
    "signing_lining",
    "lighting",
    "camera",
    "other",
]
SiteType = Literal["junction", "link", "cluster", "route", "area"]

# What each site's footprint is: an area for junctions (the match area), clusters (the
# circle) and drawn areas; a line for a link's stretch or a route section.
POLYGONAL = ("Polygon", "MultiPolygon")
LINEAR = ("LineString", "MultiLineString")
FOOTPRINT_TYPES: dict[str, tuple[str, ...]] = {
    "junction": POLYGONAL,
    "cluster": POLYGONAL,
    "area": POLYGONAL,
    "link": LINEAR,
    "route": LINEAR,
}

MAX_VERTICES = 20_000  # a detailed drawn area; Wales's outline simplified is well under this
# all of Wales (the 20 mph default) is ~21,000 km², and Highland, the largest authority, ~26,000
MAX_AREA_KM2 = 40_000.0
MAX_LENGTH_KM = 500.0
# Great Britain in British National Grid metres, with a margin
GB_BOUNDS = (-10_000.0, -10_000.0, 670_000.0, 1_230_000.0)
EARLIEST = date(1979, 1, 1)  # the first STATS19 year

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Years = Annotated[int, Field(ge=1, le=5)]


class Geometry(BaseModel):
    """A GeoJSON geometry in WGS84 (longitude, latitude), as the map draws it."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["Polygon", "MultiPolygon", "LineString", "MultiLineString"]
    coordinates: list[Any]

    @model_validator(mode="after")
    def _well_formed(self) -> Geometry:
        if _positions(self.coordinates, _DEPTH[self.type]) > MAX_VERTICES:
            raise ValueError(f"the footprint has more than {MAX_VERTICES:,} points")
        return self


# how deeply each type nests its positions: a line is a list of positions, a polygon a list
# of rings (lists of positions), and the multi- types a list of those
_DEPTH = {"LineString": 1, "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3}


def _positions(value: Any, depth: int) -> int:
    """The number of positions, checking the nesting and that each is [lon, lat]."""
    if not isinstance(value, list) or not value:
        raise ValueError("the footprint's coordinates aren't nested correctly")
    if depth == 0:
        if len(value) not in (2, 3) or not all(
            isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
            for v in value
        ):
            raise ValueError("each point must be [longitude, latitude]")
        return 1
    return sum(_positions(v, depth - 1) for v in value)


class Fyrr(BaseModel):
    """The FYRR assumptions when the scheme was saved (web/src/lib/economics.ts)."""

    model_config = ConfigDict(extra="forbid")
    collisions_per_year: Annotated[float, Field(ge=0, le=10_000)]
    value_per_collision: Annotated[float, Field(gt=0, le=100_000_000)]
    reduction_pct: Annotated[float, Field(gt=0, le=100)]
    # e.g. "Empirical Bayes estimate" or "5-year average"; and the RAS4001 price year
    basis: Annotated[str | None, Field(max_length=200)] = None
    prices_year: Annotated[int | None, Field(ge=2000, le=2100)] = None


class SchemeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Text = ""
    measure: Measure
    site_type: SiteType
    site_ref: Ref | None = None
    geometry: Geometry
    works_start: date | None = None
    works_end: date | None = None
    before_years: Years = 3
    after_years: Years = 3
    cost: Annotated[float | None, Field(ge=0, le=1_000_000_000)] = None
    fyrr: Fyrr | None = None

    @model_validator(mode="after")
    def _consistent(self) -> SchemeIn:
        if self.geometry.type not in FOOTPRINT_TYPES[self.site_type]:
            kind = "an area" if FOOTPRINT_TYPES[self.site_type] is POLYGONAL else "a line"
            raise ValueError(f"a {self.site_type} scheme's footprint must be {kind}")
        for d in (self.works_start, self.works_end):
            if d is not None and not EARLIEST <= d <= date(date.today().year + 10, 12, 31):
                raise ValueError("works dates must be between 1979 and ten years from now")
        if self.works_start and self.works_end and self.works_end < self.works_start:
            raise ValueError("the works can't end before they start")
        return self


class SchemeEdit(SchemeIn):
    version: Annotated[int, Field(ge=1)]  # the version the edit started from


_FIELDS = """
    s.id, s.name, s.description, s.measure, s.site_type, s.site_ref,
    s.works_start, s.works_end, s.before_years, s.after_years, s.cost::float AS cost,
    s.fyrr, s.version, s.created_at, s.created_by, s.updated_at, s.updated_by,
    ST_AsGeoJSON(ST_Transform(ST_PointOnSurface(s.geom_bng), 4326), 6)::json
        -> 'coordinates' AS point
"""

_LIVE = "s.org_id = %(org)s AND s.deleted_at IS NULL"


def _footprint(conn: psycopg.Connection, geometry: Geometry) -> None:
    """Check the footprint in the database, which has the geometry library: valid, in
    Great Britain, and not absurdly large. Raises a 422 ApiError otherwise."""
    try:
        row = conn.execute(
            """WITH g AS (
                   SELECT ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326),
                                       27700) AS geom)
               SELECT ST_IsValid(geom) AS valid, ST_IsValidReason(geom) AS reason,
                      ST_IsEmpty(geom) AS empty,
                      ST_XMin(geom) AS x0, ST_YMin(geom) AS y0,
                      ST_XMax(geom) AS x1, ST_YMax(geom) AS y1,
                      ST_Area(geom) / 1e6 AS km2, ST_Length(geom) / 1e3 AS km
               FROM g""",
            {"geojson": geometry.model_dump_json()},
        ).fetchone()
    except (psycopg.errors.DataException, psycopg.errors.InternalError_) as exc:  # PostGIS
        raise ApiError(422, "invalid_footprint", "The footprint isn't a readable shape.") from exc
    if row["empty"]:
        raise ApiError(422, "invalid_footprint", "The footprint is empty.")
    if not row["valid"]:
        raise ApiError(422, "invalid_footprint", f"The footprint isn't a valid shape{_why(row)}.")
    x0, y0, x1, y1 = GB_BOUNDS
    if row["x0"] < x0 or row["y0"] < y0 or row["x1"] > x1 or row["y1"] > y1:
        raise ApiError(422, "invalid_footprint", "The footprint must be in Great Britain.")
    if row["km2"] > MAX_AREA_KM2 or row["km"] > MAX_LENGTH_KM:
        raise ApiError(422, "invalid_footprint", "The footprint is too large.")


def _why(row: dict) -> str:
    """GEOS's reason, e.g. "Self-intersection[412 103]" → " (self-intersection)"; nothing
    when it's an internal error message rather than a reason."""
    reason = " ".join((row["reason"] or "").split("[")[0].split())
    if not reason or "Exception" in reason:
        return ""
    return f" ({reason[0].lower()}{reason[1:]})"


def _values(body: SchemeIn) -> dict:
    return {
        "name": body.name,
        "description": body.description,
        "measure": body.measure,
        "site_type": body.site_type,
        "site_ref": body.site_ref,
        "geojson": body.geometry.model_dump_json(),
        "works_start": body.works_start,
        "works_end": body.works_end,
        "before_years": body.before_years,
        "after_years": body.after_years,
        "cost": body.cost,
        "fyrr": body.fyrr.model_dump_json() if body.fyrr else None,
    }


def _name_taken() -> ApiError:
    return ApiError(409, "name_taken", "There's already a scheme with that name.")


def _get(conn: psycopg.Connection, org: UUID, scheme_id: UUID) -> dict:
    row = conn.execute(
        f"""SELECT {_FIELDS},
                   ST_AsGeoJSON(ST_Transform(s.geom_bng, 4326), 6)::json AS geometry
            FROM app.scheme s WHERE s.id = %(id)s AND {_LIVE}""",
        {"id": scheme_id, "org": org},
    ).fetchone()
    if row is None:
        raise NotFound("No such scheme.")
    return _with_status(row, _last_year(conn))


# Collisions count for a line footprint (a link or route) when they're this close to it: the
# radius collisions are matched to OS road links within (stats19.reference.collision_links).
LINE_MATCH_M = 25.0

# Which collisions a scheme counts (FU-057), the safety models' own rules: a junction counts
# the collisions STATS19 records at a junction; a link the rest (those not at a junction it
# passes); every other site, all of them.
_NOT_AT_A_JUNCTION = f"""NOT ({JUNCTION_COLLISION} AND EXISTS (
    SELECT 1 FROM geo.junction j
    WHERE ST_DWithin(j.match_geom, c.geom_bng, {COLLISION_RADIUS_M})))"""


def counted(conn: psycopg.Connection, site_type: str) -> tuple[str, str]:
    """(SQL condition on core.collision c, rule name) for a site type's collisions."""
    if site_type == "junction":
        return JUNCTION_COLLISION, "junction"
    if site_type == "link" and tables_exist(conn, "geo.junction"):
        return _NOT_AT_A_JUNCTION, "not_junction"
    return "TRUE", "all"


def year_span(conn: psycopg.Connection) -> tuple[int | None, int | None]:
    """The first and latest years loaded (none before the first load). The after-data runs
    to 31 December of the latest."""
    if conn.execute("SELECT to_regclass('core.collision') AS t").fetchone()["t"] is None:
        return None, None
    row = conn.execute(
        "SELECT min(collision_year) AS lo, max(collision_year) AS hi FROM core.collision"
    ).fetchone()
    return row["lo"], row["hi"]


def _last_year(conn: psycopg.Connection) -> int | None:
    return year_span(conn)[1]


def _periods(row: dict, last_year: int | None) -> Periods:
    return scheme_periods(
        row["works_start"], row["works_end"], row["before_years"], row["after_years"], last_year
    )


def _with_status(row: dict, last_year: int | None) -> dict:
    p = _periods(row, last_year)
    return row | {
        "status": {
            "stage": p.stage,
            "after_months": p.after_months,
            "after_months_wanted": p.after_months_wanted,
            "data_end": p.data_end,
        }
    }


@router.get("/schemes/options")
def options() -> dict:
    """The choices a scheme form offers."""
    return ok(
        {
            "measures": [{"code": c, "label": label} for c, label in MEASURES.items()],
            "site_types": list(FOOTPRINT_TYPES),
            "years": {"min": 1, "max": 5, "default": 3},
        }
    )


@router.get("/schemes")
def list_schemes(conn: Conn, org: Org) -> dict:
    rows = conn.execute(
        f"SELECT {_FIELDS} FROM app.scheme s WHERE {_LIVE} ORDER BY s.updated_at DESC",
        {"org": org},
    ).fetchall()
    last_year = _last_year(conn)
    return ok([_with_status(r, last_year) for r in rows], meta={"count": len(rows)})


@router.get("/schemes/{scheme_id}")
def get_scheme(scheme_id: UUID, conn: Conn, org: Org) -> dict:
    return ok(_get(conn, org, scheme_id))


@router.get("/schemes/{scheme_id}/collisions")
def scheme_collisions(scheme_id: UUID, conn: Conn, org: Org) -> dict:
    """Collisions in the scheme's footprint by year and severity, with its periods.

    Counted from the stored footprint (PLAN-011 §2): inside an area, or within
    LINE_MATCH_M of a line, by the site type's rule (``counted``), as the evaluation counts.
    """
    scheme = conn.execute(
        f"""SELECT s.works_start, s.works_end, s.before_years, s.after_years, s.site_type,
                   ST_Dimension(s.geom_bng) AS dim
            FROM app.scheme s WHERE s.id = %(id)s AND {_LIVE}""",
        {"id": scheme_id, "org": org},
    ).fetchone()
    if scheme is None:
        raise NotFound("No such scheme.")
    first_year, last_year = year_span(conn)
    p = _periods(scheme, last_year)
    years = range(0) if last_year is None else chart_years(p, first_year, last_year)
    within = 0.0 if scheme["dim"] == 2 else LINE_MATCH_M
    condition, rule = counted(conn, scheme["site_type"])
    return ok(
        {
            "by_year": _by_year(conn, scheme_id, within, condition, years),
            "before": period_json(p.before),
            "after": period_json(p.after),
            "match": {
                "kind": "area" if within == 0 else "line",
                "within_m": within,
                "rule": rule,
            },
        }
    )


def _by_year(
    conn: psycopg.Connection, scheme_id: UUID, within: float, condition: str, years: range
) -> list:
    """Collisions within ``within`` metres of the footprint, by year and severity."""
    if not years:
        return []
    rows = conn.execute(
        f"""SELECT c.collision_year AS year,
                  count(*) FILTER (WHERE c.collision_severity = 1) AS fatal,
                  count(*) FILTER (WHERE c.collision_severity = 2) AS serious,
                  count(*) FILTER (WHERE c.collision_severity = 3) AS slight
           FROM core.collision c, app.scheme s
           WHERE s.id = %(id)s
             AND ST_DWithin(c.geom_bng, s.geom_bng, %(within)s)
             AND c.collision_year BETWEEN %(lo)s AND %(hi)s
             AND {condition}
           GROUP BY 1""",
        {"id": scheme_id, "within": within, "lo": years.start, "hi": years.stop - 1},
    ).fetchall()
    counts = {r["year"]: r for r in rows}
    zero = {"fatal": 0, "serious": 0, "slight": 0}
    return [{"year": y} | {k: counts.get(y, zero)[k] for k in zero} for y in years]


def period_json(period: Period | None) -> dict | None:
    return None if period is None else {"start": period.start, "end": period.end}


@router.post("/schemes", status_code=201, dependencies=[Depends(check_write)])
def create_scheme(body: SchemeIn, request: Request, conn: Conn, org: Org) -> dict:
    who = editor(request)
    try:
        with read_write(conn):
            _footprint(conn, body.geometry)
            scheme_id = conn.execute(
                """INSERT INTO app.scheme
                       (org_id, name, description, measure, site_type, site_ref, geom_bng,
                        works_start, works_end, before_years, after_years, cost, fyrr,
                        created_by, updated_by)
                   VALUES (%(org)s, %(name)s, %(description)s, %(measure)s, %(site_type)s,
                           %(site_ref)s,
                           ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326),
                                        27700),
                           %(works_start)s, %(works_end)s, %(before_years)s, %(after_years)s,
                           %(cost)s, %(fyrr)s, %(who)s, %(who)s)
                   RETURNING id""",
                _values(body) | {"org": org, "who": who},
            ).fetchone()["id"]
    except psycopg.errors.UniqueViolation as exc:
        raise _name_taken() from exc
    log.info("scheme created id=%s", scheme_id)
    return ok(_get(conn, org, scheme_id))


@router.put("/schemes/{scheme_id}", dependencies=[Depends(check_write)])
def edit_scheme(scheme_id: UUID, body: SchemeEdit, request: Request, conn: Conn, org: Org) -> dict:
    try:
        with read_write(conn):
            _footprint(conn, body.geometry)
            row = conn.execute(
                f"""UPDATE app.scheme s SET
                        name = %(name)s, description = %(description)s,
                        measure = %(measure)s, site_type = %(site_type)s,
                        site_ref = %(site_ref)s,
                        geom_bng = ST_Transform(
                            ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326), 27700),
                        works_start = %(works_start)s, works_end = %(works_end)s,
                        before_years = %(before_years)s, after_years = %(after_years)s,
                        cost = %(cost)s, fyrr = %(fyrr)s,
                        version = s.version + 1, updated_at = now(), updated_by = %(who)s
                    WHERE s.id = %(id)s AND {_LIVE} AND s.version = %(version)s
                    RETURNING s.id""",
                _values(body)
                | {"id": scheme_id, "org": org, "who": editor(request), "version": body.version},
            ).fetchone()
            if row is None:
                _missing_or_stale(conn, org, scheme_id)
    except psycopg.errors.UniqueViolation as exc:
        raise _name_taken() from exc
    log.info("scheme edited id=%s", scheme_id)
    return ok(_get(conn, org, scheme_id))


@router.delete("/schemes/{scheme_id}", dependencies=[Depends(check_write)])
def delete_scheme(scheme_id: UUID, request: Request, conn: Conn, org: Org) -> dict:
    with read_write(conn):
        row = conn.execute(
            f"""UPDATE app.scheme s SET deleted_at = now(), deleted_by = %(who)s
                WHERE s.id = %(id)s AND {_LIVE} RETURNING s.id""",
            {"id": scheme_id, "org": org, "who": editor(request)},
        ).fetchone()
    if row is None:
        raise NotFound("No such scheme.")
    log.info("scheme deleted id=%s", scheme_id)
    return ok({"id": scheme_id})


def _missing_or_stale(conn: psycopg.Connection, org: UUID, scheme_id: UUID) -> None:
    exists = conn.execute(
        f"SELECT 1 FROM app.scheme s WHERE s.id = %(id)s AND {_LIVE}",
        {"id": scheme_id, "org": org},
    ).fetchone()
    if exists is None:
        raise NotFound("No such scheme.")
    raise ApiError(
        409, "stale", "Someone else changed this scheme. Reload it, then make your edit again."
    )
