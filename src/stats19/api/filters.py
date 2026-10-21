"""One filter model for map tiles, tables, summaries, reports and exports (PLAN-004 §3).

Every identifier that reaches SQL comes from a whitelist (the column spec or the
mart road-user groups). Every value is a bound parameter. The compiled clause
expects the collision relation aliased as ``c`` (mart.collision).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Annotated, Literal

from fastapi import Query
from fastapi.exceptions import RequestValidationError
from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from stats19.columns import TABLES, Kind, core_name
from stats19.marts import INVOLVES_GROUPS

_FILTERABLE_KINDS = (Kind.CODE, Kind.MEASURE, Kind.COUNT, Kind.KEY_INT)
INVOLVES = ("pedestrian", *INVOLVES_GROUPS)
_INVOLVES_COLUMN = {
    "pedestrian": "has_pedestrian_casualty",
    **{g: f"involves_{g}" for g in INVOLVES_GROUPS},
}
MAX_POLYGON_POINTS = 5000
MAX_COLLISION_IDS = 1000  # e.g. one cluster site
CollisionId = Annotated[str, Field(pattern=r"^[0-9A-Za-z]{1,20}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldCondition(_Model):
    table: Literal["collision", "vehicle", "casualty"]
    field: str
    op: Literal["in", "not_in", "between"] = "in"
    values: list[int] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _check(self) -> FieldCondition:
        spec = TABLES[self.table]
        column = next((c for c in spec.columns if c.name == self.field), None)
        if column is None or column.kind not in _FILTERABLE_KINDS:
            raise ValueError(f"{self.table}.{self.field} is not a filterable numeric field")
        if self.op == "between" and len(self.values) != 2:
            raise ValueError("between needs exactly two values [low, high]")
        return self


class RadiusArea(_Model):
    type: Literal["radius"]
    lon: float = Field(ge=-9.0, le=3.0)
    lat: float = Field(ge=49.0, le=61.5)
    radius_m: int = Field(ge=10, le=20_000)


class PolygonArea(_Model):
    type: Literal["polygon"]
    geometry: dict

    @field_validator("geometry")
    @classmethod
    def _geojson(cls, g: dict) -> dict:
        if g.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError("geometry must be a GeoJSON Polygon or MultiPolygon")
        if json.dumps(g).count(",") > 2 * MAX_POLYGON_POINTS:
            raise ValueError(f"polygon too detailed (max ~{MAX_POLYGON_POINTS} points)")
        return g


class AuthorityArea(_Model):
    type: Literal["authority"]
    boundary_type: Literal["highway_authority", "district", "police_force"]
    code: str = Field(pattern=r"^[A-Z][0-9]{8}$")


Area = Annotated[RadiusArea | PolygonArea | AuthorityArea, Field(discriminator="type")]


class Filter(_Model):
    year_from: int | None = Field(default=None, ge=1979, le=2100)
    year_to: int | None = Field(default=None, ge=1979, le=2100)
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    severity: list[Literal[1, 2, 3]] | None = None
    involves: list[Literal[INVOLVES]] | None = None  # type: ignore[valid-type]
    day_of_week: list[Annotated[int, Field(ge=1, le=7)]] | None = None
    time_from: dt.time | None = None
    time_to: dt.time | None = None
    fields: list[FieldCondition] = Field(default_factory=list, max_length=30)
    area: Area | None = None
    collision_ids: list[CollisionId] | None = Field(default=None, max_length=MAX_COLLISION_IDS)


def _condition(i: int, cond: FieldCondition, alias: str) -> tuple[sql.Composable, dict]:
    # alias is an internal constant ("c" / "x"); the column comes from the validated spec.
    col = sql.SQL(alias + ".") + sql.Identifier(core_name(cond.table, cond.field))
    key = f"f{i}"
    if cond.op == "between":
        lo, hi = sorted(cond.values)
        expr = sql.SQL("{} BETWEEN {} AND {}").format(
            col, sql.Placeholder(f"{key}_lo"), sql.Placeholder(f"{key}_hi")
        )
        return expr, {f"{key}_lo": lo, f"{key}_hi": hi}
    template = "{} = ANY({})" if cond.op == "in" else "NOT ({} = ANY({}))"
    return sql.SQL(template).format(col, sql.Placeholder(key)), {key: cond.values}


def area_condition(area: Area) -> tuple[sql.Composable, dict]:
    if isinstance(area, RadiusArea):
        return sql.SQL(
            "ST_DWithin(c.geom_bng, ST_Transform(ST_SetSRID(ST_MakePoint("
            "%(area_lon)s, %(area_lat)s), 4326), 27700), %(area_radius_m)s)"
        ), {"area_lon": area.lon, "area_lat": area.lat, "area_radius_m": area.radius_m}
    if isinstance(area, PolygonArea):
        return sql.SQL(
            "ST_Intersects(c.geom_bng, ST_Transform(ST_SetSRID("
            "ST_GeomFromGeoJSON(%(area_geojson)s), 4326), 27700))"
        ), {"area_geojson": json.dumps(area.geometry)}
    # Scalar subquery runs once (initplan), so the GIST index on c.geom_bng is used.
    return sql.SQL(
        "ST_Intersects(c.geom_bng, (SELECT b.geom_bng FROM geo.boundary b "
        "WHERE b.boundary_type = %(area_boundary_type)s AND b.code = %(area_code)s))"
    ), {"area_boundary_type": area.boundary_type, "area_code": area.code}


def area_geometry(area: Area) -> tuple[sql.Composable, dict]:
    """The area as a BNG geometry expression, for clipping lines to it (FU-047 #6)."""
    if isinstance(area, RadiusArea):
        return sql.SQL(
            "ST_Buffer(ST_Transform(ST_SetSRID(ST_MakePoint(%(area_lon)s, %(area_lat)s), 4326),"
            " 27700), %(area_radius_m)s)"
        ), {"area_lon": area.lon, "area_lat": area.lat, "area_radius_m": area.radius_m}
    if isinstance(area, PolygonArea):
        return sql.SQL(
            "ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(area_geojson)s), 4326), 27700)"
        ), {"area_geojson": json.dumps(area.geometry)}
    return sql.SQL(
        "(SELECT b.geom_bng FROM geo.boundary b "
        "WHERE b.boundary_type = %(area_boundary_type)s AND b.code = %(area_code)s)"
    ), {"area_boundary_type": area.boundary_type, "area_code": area.code}


def compile_filter(
    f: Filter, extra: list[sql.Composable] | None = None
) -> tuple[sql.Composable, dict]:
    """WHERE-clause body (no 'WHERE') and its parameters."""
    parts: list[sql.Composable] = []
    params: dict = {}

    def add(text: str, **values) -> None:
        parts.append(sql.SQL(text))
        params.update(values)

    if f.year_from is not None:
        add("c.collision_year >= %(year_from)s", year_from=f.year_from)
    if f.year_to is not None:
        add("c.collision_year <= %(year_to)s", year_to=f.year_to)
    if f.date_from is not None:
        add("c.collision_date >= %(date_from)s", date_from=f.date_from)
    if f.date_to is not None:
        add("c.collision_date <= %(date_to)s", date_to=f.date_to)
    if f.collision_ids is not None:
        add("c.collision_index = ANY(%(collision_ids)s)", collision_ids=list(f.collision_ids))
    if f.severity:
        add("c.collision_severity = ANY(%(severity)s)", severity=list(f.severity))
    if f.day_of_week:
        add("c.day_of_week = ANY(%(day_of_week)s)", day_of_week=list(f.day_of_week))
    if f.time_from is not None and f.time_to is not None:
        op = "AND" if f.time_from <= f.time_to else "OR"  # e.g. 22:00-04:00 wraps
        add(
            f"(c.collision_time >= %(time_from)s {op} c.collision_time < %(time_to)s)",
            time_from=f.time_from,
            time_to=f.time_to,
        )
    if f.involves:
        flags = sql.SQL(" OR ").join(
            sql.SQL("c.{}").format(sql.Identifier(_INVOLVES_COLUMN[g])) for g in f.involves
        )
        parts.append(sql.SQL("({})").format(flags))

    for i, cond in enumerate(f.fields):
        if cond.table == "collision":
            expr, p = _condition(i, cond, "c")
            parts.append(expr)
        else:
            expr, p = _condition(i, cond, "x")
            parts.append(
                # cond.table is Literal-validated to vehicle/casualty.
                sql.SQL(
                    f"EXISTS (SELECT 1 FROM core.{cond.table} x "
                    "WHERE x.collision_index = c.collision_index AND {})"
                ).format(expr)
            )
        params.update(p)

    if f.area is not None:
        expr, p = area_condition(f.area)
        parts.append(expr)
        params.update(p)

    parts += extra or []
    if not parts:
        return sql.SQL("TRUE"), params
    return sql.SQL(" AND ").join(parts), params


def parse_filter(f: str | None) -> Filter:
    """Decode the ?f=<json> query parameter shared by every endpoint."""
    if not f:
        return Filter()
    try:
        return Filter.model_validate_json(f)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


def filter_param(f: Annotated[str | None, Query(max_length=20_000)] = None) -> Filter:
    """FastAPI dependency: ``flt: Annotated[Filter, Depends(filter_param)]``."""
    return parse_filter(f)


def collision_relation(f: Filter) -> sql.Composable:
    """core.collision is enough unless the filter needs mart summary columns."""
    return sql.SQL("mart.collision" if f.involves else "core.collision")


def count_capped(conn, f: Filter, cap: int) -> int:
    """Number of matching collisions, counting no further than cap + 1."""
    where, params = compile_filter(f)
    return conn.execute(
        sql.SQL(
            "SELECT count(*) AS n FROM (SELECT 1 FROM {rel} c WHERE {where} LIMIT %(cap)s) s"
        ).format(rel=collision_relation(f), where=where),
        params | {"cap": cap + 1},
    ).fetchone()["n"]


def selected_ids(conn, f: Filter, order: str = "c.collision_index") -> list[str]:
    """Matching collision ids. Decoded views must be queried with ``= ANY(ids)``:
    a sub-select join makes Postgres decode every row before filtering (15 s vs 7 ms).
    ``order`` is an internal constant, never client input."""
    where, params = compile_filter(f)
    rows = conn.execute(
        sql.SQL("SELECT c.collision_index FROM {rel} c WHERE {where} ORDER BY " + order).format(
            rel=collision_relation(f), where=where
        ),
        params,
    ).fetchall()
    return [r["collision_index"] for r in rows]
