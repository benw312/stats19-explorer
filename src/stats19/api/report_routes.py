"""/api/reports/...: PDF reports rendered from the web app's print pages."""

from __future__ import annotations

import datetime as dt
import logging
import urllib.parse
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import Response

from stats19.api import limits
from stats19.api.deps import get_conn
from stats19.api.envelope import ApiError, NotFound
from stats19.api.filters import Filter, count_capped, filter_param
from stats19.api.hotspots import HotspotParams, cached_hotspots, params_param
from stats19.reports import ReportError, render_pdf

log = logging.getLogger(__name__)
router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

MAX_REPORT_COLLISIONS = 1000
MAX_TITLE = 120
MAX_NOTES = 2000
MAX_PACK_SITES = 25
SITE_PACK_TIMEOUT_S = 240  # one map snapshot per site, rendered one at a time


def _pdf_response(pdf: bytes, name: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}-{dt.date.today():%Y%m%d}.pdf"'
        },
    )


def _render(request: Request, path: str, query: dict[str, str], timeout_s: float = 90) -> bytes:
    base = request.app.state.report_base_url.rstrip("/")
    url = f"{base}{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
    try:
        with limits.PDF.slot():  # each render is a headless Chromium (PLAN-006 C5)
            return render_pdf(url, timeout_s=timeout_s)
    except ReportError as exc:
        log.error("report render failed for %s: %s", path, exc)
        raise ApiError(502, "report_failed", f"The report could not be generated: {exc}") from exc


@router.get("/reports/area.pdf")
def area_report(
    request: Request,
    conn: Conn,
    flt: Flt,
    title: Annotated[str, Query(max_length=MAX_TITLE)] = "",
    notes: Annotated[str, Query(max_length=MAX_NOTES)] = "",
    sticks: bool = True,
    list: bool = True,  # noqa: A002 - query parameter name
) -> Response:
    """Area report; sticks / list can be left out for long district-scale reports."""
    if count_capped(conn, flt, MAX_REPORT_COLLISIONS) > MAX_REPORT_COLLISIONS:
        raise ApiError(
            413,
            "too_large",
            f"Area reports cover up to {MAX_REPORT_COLLISIONS:,} collisions. "
            "Narrow the area, period or filters.",
        )
    conn.commit()  # release the connection's transaction before the (slow) render
    query = {"f": flt.model_dump_json(exclude_defaults=True), "title": title, "notes": notes}
    query |= {} if sticks else {"sticks": "0"}
    query |= {} if list else {"list": "0"}
    return _pdf_response(_render(request, "/print/area", query), "stats19-area-report")


@router.get("/reports/rates.pdf")
def rates_report(
    request: Request,
    conn: Conn,
    flt: Flt,
    title: Annotated[str, Query(max_length=MAX_TITLE)] = "",
    notes: Annotated[str, Query(max_length=MAX_NOTES)] = "",
) -> Response:
    """An authority's rates and benchmarking (V4). Aggregate figures only, so no collision cap."""
    conn.commit()  # release the connection's transaction before the (slow) render
    query = {"f": flt.model_dump_json(exclude_defaults=True), "title": title, "notes": notes}
    return _pdf_response(_render(request, "/print/rates", query), "stats19-rates")


@router.get("/reports/collision/{collision_index}.pdf")
def collision_report(
    request: Request,
    conn: Conn,
    collision_index: Annotated[str, Path(pattern=r"^[0-9A-Z]{4,20}$")],
) -> Response:
    exists = conn.execute(
        "SELECT 1 FROM core.collision WHERE collision_index = %s", (collision_index,)
    ).fetchone()
    if not exists:
        raise NotFound(f"no collision {collision_index}")
    conn.commit()
    pdf = _render(request, f"/print/collision/{collision_index}", {})
    return _pdf_response(pdf, f"stats19-collision-{collision_index}")


@router.get("/reports/sites.pdf")
def site_pack(
    request: Request,
    conn: Conn,
    flt: Flt,
    params: Annotated[HotspotParams, Depends(params_param)],
    top: Annotated[int, Query(ge=1, le=MAX_PACK_SITES)] = 10,
    rank: Annotated[int | None, Query(ge=1, le=200)] = None,
    title: Annotated[str, Query(max_length=MAX_TITLE)] = "",
    notes: Annotated[str, Query(max_length=MAX_NOTES)] = "",
) -> Response:
    """Cluster site pack (cover, ranked table, a section per site), or one site (rank)."""
    sites = cached_hotspots(conn, flt, params)["sites"]  # 413 when the selection is too big
    if rank is not None and rank > len(sites):
        raise NotFound(f"no site ranked {rank} for this selection")
    conn.commit()
    query = {
        "f": flt.model_dump_json(exclude_defaults=True),
        "p": params.model_dump_json(exclude_defaults=True),
        "title": title,
        "notes": notes,
    }
    query |= {"rank": str(rank)} if rank is not None else {"top": str(top)}
    pdf = _render(request, "/print/sites", query, timeout_s=SITE_PACK_TIMEOUT_S)
    name = f"stats19-site-{rank}" if rank is not None else "stats19-site-pack"
    return _pdf_response(pdf, name)


@router.get("/reports/junction/{junction_id}.pdf")
def junction_report(
    request: Request,
    conn: Conn,
    flt: Flt,
    junction_id: Annotated[str, Path(pattern=r"^[0-9A-Za-z_-]{1,64}$")],
    title: Annotated[str, Query(max_length=MAX_TITLE)] = "",
    notes: Annotated[str, Query(max_length=MAX_NOTES)] = "",
) -> Response:
    """One junction's site page as a PDF (PLAN-009 V3)."""
    exists = conn.execute("SELECT 1 FROM geo.junction WHERE id = %s", (junction_id,)).fetchone()
    if not exists:
        raise NotFound(f"no junction {junction_id}")
    conn.commit()
    query = {"f": flt.model_dump_json(exclude_defaults=True), "title": title, "notes": notes}
    pdf = _render(request, f"/print/junction/{junction_id}", query)
    return _pdf_response(pdf, "stats19-junction")


@router.get("/reports/road/{count_point_id}.pdf")
def road_report(
    request: Request,
    conn: Conn,
    flt: Flt,
    count_point_id: Annotated[int, Path(ge=0, le=999_999_999)],
    title: Annotated[str, Query(max_length=MAX_TITLE)] = "",
    notes: Annotated[str, Query(max_length=MAX_NOTES)] = "",
) -> Response:
    """One count point's road as a site page PDF (PLAN-009 V3)."""
    exists = conn.execute(
        "SELECT 1 FROM geo.traffic_count_point WHERE count_point_id = %s", (count_point_id,)
    ).fetchone()
    if not exists:
        raise NotFound(f"no count point {count_point_id}")
    conn.commit()
    query = {"f": flt.model_dump_json(exclude_defaults=True), "title": title, "notes": notes}
    pdf = _render(request, f"/print/road/{count_point_id}", query)
    return _pdf_response(pdf, f"stats19-road-{count_point_id}")
