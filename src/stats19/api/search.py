"""/api/search: postcodes (Code-Point Open) and places/roads (Open Names)."""

from __future__ import annotations

import re
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Query

from stats19.api.deps import get_conn
from stats19.api.envelope import ok
from stats19.reference.postcodes import postcode_key

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]

# Full or partial UK postcode, e.g. "EX1 1AE", "ex11ae", "EX1 1".
_POSTCODE_LIKE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9]?[A-Z]{0,2}$", re.I)

_BBOX_WGS84 = """ARRAY[ST_XMin(b), ST_YMin(b), ST_XMax(b), ST_YMax(b)]
                 FROM (SELECT ST_Transform({geom}, 4326)::box2d AS b) bb"""


def _postcodes(conn: psycopg.Connection, q: str, limit: int) -> list[dict]:
    key = postcode_key(q)
    return conn.execute(
        f"""SELECT 'postcode' AS type, postcode AS label, NULL AS sublabel,
                   ST_X(ST_Transform(geom_bng, 4326)) AS lon,
                   ST_Y(ST_Transform(geom_bng, 4326)) AS lat,
                   (SELECT {_BBOX_WGS84.format(geom="ST_Buffer(geom_bng, 150)")}) AS bbox
            FROM geo.postcode
            WHERE postcode_key LIKE %(key)s || '%%'
            ORDER BY postcode_key <> %(key)s, postcode_key
            LIMIT %(limit)s""",
        {"key": key, "limit": limit},
    ).fetchall()


# Fuzzy (trigram) matching is a fallback for typos only: when the typed text prefixes
# some name, fuzzy hits are just noise (e.g. "Sidwell Street" -> the village "Street").
MIN_SIMILARITY = 0.45

_CATEGORY_RANK = "CASE category WHEN 'place' THEN 0 WHEN 'road' THEN 1 ELSE 2 END"

_PLACE_SELECT = f"""SELECT category AS type, name AS label,
           nullif(concat_ws(', ', populated_place, county), '') AS sublabel,
           ST_X(ST_Transform(geom_bng, 4326)) AS lon,
           ST_Y(ST_Transform(geom_bng, 4326)) AS lat,
           (SELECT {_BBOX_WGS84.format(geom="bbox_bng")}) AS bbox
    FROM geo.place"""


def _places(conn: psycopg.Connection, q: str, limit: int) -> list[dict]:
    params = {
        "q": q.lower(),
        "prefix": q.lower().replace("%", "") + "%",
        "limit": limit,
        "min_sim": MIN_SIMILARITY,
    }
    prefixed = conn.execute(
        f"""{_PLACE_SELECT}
            WHERE lower(name) LIKE %(prefix)s
            ORDER BY lower(name) = %(q)s DESC, {_CATEGORY_RANK}, length(name), name
            LIMIT %(limit)s""",
        params,
    ).fetchall()
    if prefixed:
        return prefixed
    return conn.execute(
        f"""{_PLACE_SELECT}
            WHERE lower(name) %% %(q)s AND similarity(lower(name), %(q)s) >= %(min_sim)s
            ORDER BY similarity(lower(name), %(q)s) DESC, {_CATEGORY_RANK}, name
            LIMIT %(limit)s""",
        params,
    ).fetchall()


@router.get("/search")
def search(
    conn: Conn,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> dict:
    q = q.strip()
    results: list[dict] = []
    if _POSTCODE_LIKE.match(q):
        results += _postcodes(conn, q, limit)
    if len(results) < limit:
        results += _places(conn, q, limit - len(results))
    return ok(results)
