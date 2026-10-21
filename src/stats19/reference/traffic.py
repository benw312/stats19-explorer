"""DfT road traffic statistics: AADF by count point, count points, MRDB links, LA traffic.

All published under the Open Government Licence at roadtraffic.dft.gov.uk/downloads.
"""

from __future__ import annotations

import csv
import io
import struct
import zipfile
from collections.abc import Iterator
from pathlib import Path

_BASE = "https://storage.googleapis.com/dft-statistics/road-traffic"
AADF_URL = f"{_BASE}/downloads/data-gov-uk/dft_traffic_counts_aadf.zip"
COUNT_POINTS_URL = f"{_BASE}/downloads/data-gov-uk/count_points.zip"
LA_TRAFFIC_URL = f"{_BASE}/downloads/data-gov-uk/local_authority_traffic.csv"
MRDB_URL = _BASE + "/mrdb-{year}.zip"

# AADF vehicle columns kept, in table order (CSV header names, lower-cased for the table).
VEHICLE_COLUMNS = (
    "pedal_cycles",
    "two_wheeled_motor_vehicles",
    "cars_and_taxis",
    "buses_and_coaches",
    "LGVs",
    "HGVs_2_rigid_axle",
    "HGVs_3_rigid_axle",
    "HGVs_4_or_more_rigid_axle",
    "HGVs_3_or_4_articulated_axle",
    "HGVs_5_articulated_axle",
    "HGVs_6_articulated_axle",
    "all_HGVs",
    "all_motor_vehicles",
)

AadfRow = tuple  # (count_point_id, year, method, method_detailed, *vehicles, link_length_km)
CountPointRow = tuple  # see COUNT_POINT_FIELDS
LaRow = tuple[str, str, int, float | None, float | None, float | None]


def _int(value: str) -> int | None:
    """DfT CSVs mix plain integers with exponent forms such as '9e+05'."""
    value = value.strip()
    if not value or value.upper() == "NA":
        return None
    return int(float(value))


def _float(value: str) -> float | None:
    value = value.strip()
    if not value or value.upper() == "NA":
        return None
    return float(value)


def _text(value: str) -> str | None:
    value = value.strip()
    return None if not value or value.upper() == "NA" else value


def _csv_in_zip(path: Path, suffix: str) -> Iterator[dict]:
    with zipfile.ZipFile(path) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(suffix)), None)
        if name is None:
            raise ValueError(f"{path.name}: no member ending {suffix}")
        with z.open(name) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def parse_aadf(path: Path) -> Iterator[AadfRow]:
    """One row per count point and year: method, then the AADF by vehicle type."""
    for r in _csv_in_zip(path, ".csv"):
        yield (
            int(r["count_point_id"]),
            int(r["year"]),
            _text(r["estimation_method"]),
            _text(r["estimation_method_detailed"]),
            *(_int(r[c]) for c in VEHICLE_COLUMNS),
            _float(r.get("link_length_km", "")),  # that year's length: DfT re-measures links
        )


COUNT_POINT_FIELDS = (
    "count_point_id",
    "road_name",
    "road_category",
    "road_type",
    "start_junction_road_name",
    "end_junction_road_name",
    "local_authority_code",
    "local_authority_name",
    "region_name",
    "link_length_km",
    "easting",
    "northing",
)


def parse_count_points(path: Path) -> Iterator[CountPointRow]:
    """Latest attributes of every count point (one row each), located in BNG."""
    for r in _csv_in_zip(path, ".csv"):
        e, n = _float(r["easting"]), _float(r["northing"])
        if e is None or n is None:
            continue
        yield (
            int(r["count_point_id"]),
            _text(r["road_name"]),
            _text(r["road_category"]),
            _text(r["road_type"]),
            _text(r["start_junction_road_name"]),
            _text(r["end_junction_road_name"]),
            _text(r["local_authority_code"]),
            _text(r["local_authority_name"]),
            _text(r["region_name"]),
            _float(r["link_length_km"]),
            e,
            n,
        )


def parse_la_traffic(path: Path) -> Iterator[LaRow]:
    """(code, name, year, road length km, car vehicle-miles, all motor vehicle-miles)."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            yield (
                r["local_authority_code"].strip(),
                r["local_authority_name"].strip(),
                int(r["year"]),
                _float(r["link_length_km"]),
                _float(r["cars_and_taxis"]),
                _float(r["all_motor_vehicles"]),
            )


# ------------------------------------------------------------------ MRDB shapefile


def _dbf_records(data: bytes) -> list[dict]:
    """Minimal dBASE III reader: enough for the MRDB's two attribute columns."""
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        name = data[pos : pos + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[pos + 16]))
        pos += 32
    records = []
    for i in range(count):
        rec = data[header_len + i * record_len : header_len + (i + 1) * record_len]
        out, offset = {}, 1  # byte 0 is the deletion flag
        for name, length in fields:
            out[name] = rec[offset : offset + length].decode("latin-1").strip()
            offset += length
        records.append(out)
    return records


def _shp_lines(data: bytes) -> list[list[list[tuple[float, float]]]]:
    """Polyline (type 3) shapes as parts of (x, y); null shapes become []."""
    shapes, pos = [], 100
    while pos < len(data):
        content_len = struct.unpack(">i", data[pos + 4 : pos + 8])[0] * 2
        c = data[pos + 8 : pos + 8 + content_len]
        pos += 8 + content_len
        if struct.unpack("<i", c[:4])[0] == 0:
            shapes.append([])
            continue
        n_parts, n_points = struct.unpack("<ii", c[36:44])
        starts = struct.unpack(f"<{n_parts}i", c[44 : 44 + 4 * n_parts])
        at = 44 + 4 * n_parts
        flat = struct.unpack(f"<{2 * n_points}d", c[at : at + 16 * n_points])
        pts = list(zip(flat[0::2], flat[1::2], strict=True))
        bounds = [*starts, n_points]
        shapes.append([pts[a:b] for a, b in zip(bounds, bounds[1:], strict=False)])
    return shapes


def parse_mrdb(path: Path) -> Iterator[tuple[int, str | None, str]]:
    """(count_point_id, road number, EWKT multilinestring in BNG) per major-road link."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shp = next((n for n in names if n.lower().endswith(".shp")), None)
        dbf = next((n for n in names if n.lower().endswith(".dbf")), None)
        if shp is None or dbf is None:
            raise ValueError(f"{path.name}: no .shp/.dbf pair")
        shapes, records = _shp_lines(z.read(shp)), _dbf_records(z.read(dbf))
    if len(shapes) != len(records):
        raise ValueError(f"{path.name}: {len(shapes)} shapes but {len(records)} records")
    for parts, rec in zip(shapes, records, strict=True):
        cp = _int(rec.get("CP_Number", ""))
        parts = [p for p in parts if len(p) >= 2]
        if cp is None or not parts:
            continue
        lines = ",".join("(" + ",".join(f"{x} {y}" for x, y in p) + ")" for p in parts)
        yield cp, _text(rec.get("RoadNumber", "")), f"SRID=27700;MULTILINESTRING({lines})"
