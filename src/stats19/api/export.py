"""Exports of the filtered selection: CSV (zip of three files) and Excel.

CSV is streamed straight out of Postgres with COPY (all codes + labels). Excel is
for people rather than tools: one human-readable column per field (the label
where there is one) and an About sheet describing the selection.
"""

from __future__ import annotations

import datetime as dt
import tempfile
import zipfile
from collections.abc import Iterator
from typing import IO, Annotated

import psycopg
import xlsxwriter
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from psycopg import sql
from psycopg.rows import tuple_row

from stats19 import known_issues as ki
from stats19.api import limits
from stats19.api.data_issues import selection_issues
from stats19.api.deps import get_conn
from stats19.api.describe import describe_filter
from stats19.api.envelope import ApiError
from stats19.api.filters import Filter, count_capped, filter_param, selected_ids

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

MAX_EXPORT_COLLISIONS = 100_000
MAX_XLSX_COLLISIONS = 25_000
_TIME_OID = 1083  # PostgreSQL type OIDs: time
_TIMESTAMP_OIDS = (1114, 1184)  # timestamp, timestamptz
_GEOMETRY = {"geom_bng", "geom_wgs84", "geom_3857"}
_TABLES = (
    ("collisions", "collision_decoded", "d.collision_date, d.collision_index"),
    ("vehicles", "vehicle_decoded", "d.collision_index, d.vehicle_reference"),
    ("casualties", "casualty_decoded", "d.collision_index, d.casualty_reference, d.casualty_seq"),
)
CAVEATS = [
    "STATS19 records personal-injury collisions reported to the police; damage-only "
    "collisions and uninjured pedestrians are not included.",
    "Contributory / road safety factors are not published in the open data.",
    "Some fields changed coding in 2024; the 2024-coded columns are back-filled by DfT "
    "for earlier years. Fields not recorded in some years are blank for those years.",
]
LICENCE = (
    "Contains public sector information licensed under the Open Government Licence v3.0 "
    "(Department for Transport, STATS19 road safety open data)."
)


def _columns(conn: psycopg.Connection, view: str, human: bool) -> list[sql.Composable]:
    names = [
        r["column_name"]
        for r in conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = 'mart' AND table_name = %s ORDER BY ordinal_position""",
            (view,),
        )
        if r["column_name"] not in _GEOMETRY
    ]
    available = set(names)
    out: list[sql.Composable] = []
    for name in names:
        if human and name.endswith("_label"):
            continue  # emitted in place of its code column below
        if human and f"{name}_label" in available:
            out.append(
                sql.SQL("d.{} AS {}").format(sql.Identifier(f"{name}_label"), sql.Identifier(name))
            )
        else:
            out.append(sql.SQL("d.{}").format(sql.Identifier(name)))
    if view == "collision_decoded":
        out += [
            sql.SQL("ST_Y(d.geom_wgs84) AS latitude_wgs84"),
            sql.SQL("ST_X(d.geom_wgs84) AS longitude_wgs84"),
            _issue_column(),
        ]
    return out


def _issue_column() -> sql.Composable:
    """The DfT documented issue(s) a collision's police force and year fall in (FU-049)."""
    cases = [
        sql.SQL(
            "CASE WHEN d.police_force = ANY({forces}) AND d.collision_year BETWEEN {a} AND {b} "
            "THEN {id} END"
        ).format(
            forces=sql.Literal(list(i.police_forces)),
            a=sql.Literal(i.year_from),
            b=sql.Literal(i.year_to),
            id=sql.Literal(i.id),
        )
        for i in ki.ISSUES
    ]
    return sql.SQL("nullif(concat_ws('; ', {}), '') AS dft_data_issue").format(
        sql.SQL(", ").join(cases)
    )


def _queries(conn: psycopg.Connection, human: bool) -> list[tuple[str, sql.Composable]]:
    """One query per output table, each restricted with ``= ANY(%(ids)s)``."""
    return [
        (
            name,
            sql.SQL(
                "SELECT {cols} FROM mart.{view} d "
                "WHERE d.collision_index = ANY(%(ids)s) ORDER BY {order}"
            ).format(
                cols=sql.SQL(", ").join(_columns(conn, view, human)),
                view=sql.Identifier(view),
                order=sql.SQL(order),
            ),
        )
        for name, view, order in _TABLES
    ]


def _selected(conn: psycopg.Connection, flt: Filter, limit: int) -> list[str]:
    if count_capped(conn, flt, limit) > limit:
        raise ApiError(
            413,
            "too_large",
            f"The selection has more than {limit:,} collisions. Narrow the area, period "
            "or filters and try again.",
        )
    return selected_ids(conn, flt)


def _about_lines(conn: psycopg.Connection, flt: Filter, n: int) -> list[str]:
    coverage = conn.execute(
        """SELECT min(collision_year) AS y0, max(collision_year) AS y1 FROM core.collision"""
    ).fetchone()
    run = conn.execute(
        """SELECT run_id, finished_at FROM etl.run
           WHERE status = 'success' ORDER BY run_id DESC LIMIT 1"""
    ).fetchone()
    loaded = f"run {run['run_id']} on {run['finished_at']:%d %b %Y}" if run else "unknown"
    return [
        "STATS19 collision export",
        f"Generated: {dt.datetime.now():%d %b %Y %H:%M}",
        f"Data: DfT STATS19 {coverage['y0']}–{coverage['y1']} (loaded {loaded})",
        f"Collisions in selection: {n:,}",
        "",
        "Selection:",
        *[f"  {line}" for line in describe_filter(conn, flt)],
        "",
        "Notes:",
        *[f"  - {c}" for c in CAVEATS],
        *_issue_lines(conn, flt),
        "",
        LICENCE,
    ]


def _issue_lines(conn: psycopg.Connection, flt: Filter) -> list[str]:
    """DfT documented issues touching the selection, in DfT's words (FU-049)."""
    issues = selection_issues(conn, flt)
    if not issues:
        return []
    return [
        "",
        "DfT documented data issues in this selection (column dft_data_issue marks each "
        "collision):",
        *[f"  - {i['title']}: {i['dft_text']}" for i in issues],
        f"  Source: {ki.SOURCE_URL}",
    ]


def _stream(file: IO[bytes]) -> Iterator[bytes]:
    file.seek(0)
    while chunk := file.read(1024 * 1024):
        yield chunk
    file.close()


def _filename(ext: str) -> str:
    return f"stats19-collisions-{dt.date.today():%Y%m%d}.{ext}"


@router.get("/export/collisions.zip")
def export_csv_zip(conn: Conn, flt: Flt) -> StreamingResponse:
    with limits.EXPORT.slot():  # building the file is the heavy part (PLAN-006 C5)
        return _csv_zip(conn, flt)


def _csv_zip(conn: psycopg.Connection, flt: Filter) -> StreamingResponse:
    ids = _selected(conn, flt, MAX_EXPORT_COLLISIONS)
    n, params = len(ids), {"ids": ids}
    queries = _queries(conn, human=False)
    # Not a context manager on purpose: _stream() closes it after the response is sent.
    spool = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)  # noqa: SIM115
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as z:
        for name, query in queries:
            with z.open(f"{name}.csv", "w") as out, conn.cursor() as cur:
                out.write(b"\xef\xbb\xbf")  # BOM so Excel opens UTF-8 correctly
                copy_sql = sql.SQL("COPY ({}) TO STDOUT WITH (FORMAT csv, HEADER true)").format(
                    query
                )
                with cur.copy(copy_sql, params) as copy:
                    for data in copy:
                        out.write(bytes(data))
        z.writestr(
            "README.txt",
            "\n".join(
                [
                    *_about_lines(conn, flt, n),
                    "",
                    "Files: collisions.csv, vehicles.csv, casualties.csv "
                    "(join on collision_index).",
                    "Coded fields are given as the DfT code plus a <field>_label column.",
                ]
            ),
        )
    conn.commit()
    return StreamingResponse(
        _stream(spool),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_filename("zip")}"'},
    )


@router.get("/export/collisions.xlsx")
def export_xlsx(conn: Conn, flt: Flt) -> StreamingResponse:
    with limits.EXPORT.slot():
        return _xlsx(conn, flt)


def _xlsx(conn: psycopg.Connection, flt: Filter) -> StreamingResponse:
    ids = _selected(conn, flt, MAX_XLSX_COLLISIONS)
    n, params = len(ids), {"ids": ids}
    queries = _queries(conn, human=True)
    # Not a context manager on purpose: _stream() closes it after the response is sent.
    spool = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)  # noqa: SIM115
    # xlsxwriter in constant-memory mode is ~1.7x faster than openpyxl here (FU-015).
    wb = xlsxwriter.Workbook(
        spool,
        {"constant_memory": True, "default_date_format": "yyyy-mm-dd", "remove_timezone": True},
    )
    time_format = wb.add_format({"num_format": "hh:mm"})
    datetime_format = wb.add_format({"num_format": "yyyy-mm-dd hh:mm"})
    about = wb.add_worksheet("About")
    for i, line in enumerate(_about_lines(conn, flt, n)):
        about.write_string(i, 0, line)
    # Server-side cursors are planned for fast first rows by default, which picks a
    # plan ~7x slower for reading everything; we read everything (FU-015).
    conn.execute("SET LOCAL cursor_tuple_fraction = 1.0")
    for name, query in queries:
        ws = wb.add_worksheet(name.capitalize())
        with conn.cursor(name=f"export_{name}", row_factory=tuple_row) as cur:
            cur.itersize = 2000
            cur.execute(query, params)
            ws.write_row(0, 0, [d.name for d in cur.description])
            # dates use the default format; time and timestamp columns need their own
            special = [
                (j, time_format if d.type_code == _TIME_OID else datetime_format)
                for j, d in enumerate(cur.description)
                if d.type_code in (_TIME_OID, *_TIMESTAMP_OIDS)
            ]
            for i, row in enumerate(cur, start=1):
                ws.write_row(i, 0, row)
                for j, fmt in special:
                    if row[j] is not None:
                        ws.write_datetime(i, j, row[j], fmt)
    conn.commit()
    wb.close()
    spool.seek(0)
    return StreamingResponse(
        _stream(spool),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_filename("xlsx")}"'},
    )
