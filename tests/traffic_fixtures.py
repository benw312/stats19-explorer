"""Small DfT traffic files for tests: AADF, count points, LA traffic and an MRDB shapefile.

Count points sit inside the Exeter/Devon test boundary (lon -3.6..-3.4, lat 50.7..50.8):
  1001 A30 major, counted in 2025            -> quality 0, has an MRDB link
  1002 A38 major, counted 2022, estimated on -> quality 1, has an MRDB link
  1003 U   minor, counted once in 2012       -> quality 3 (no longer published)
  1004 C   minor, counted 2015, estimated on -> quality 2 (old count)
"""

from __future__ import annotations

import io
import struct
import zipfile

from stats19.reference.traffic import VEHICLE_COLUMNS

AADF_HEADER = [
    "count_point_id",
    "year",
    "region_id",
    "region_name",
    "region_ons_code",
    "local_authority_id",
    "local_authority_name",
    "local_authority_code",
    "road_name",
    "road_category",
    "road_type",
    "start_junction_road_name",
    "end_junction_road_name",
    "easting",
    "northing",
    "latitude",
    "longitude",
    "link_length_km",
    "link_length_miles",
    "estimation_method",
    "estimation_method_detailed",
    *VEHICLE_COLUMNS,
]

# id, road, category, type, start, end, easting, northing, link km
POINTS = [
    (1001, "A30", "PA", "Major", "A377", "B3212", 291900, 92500, 2.0),
    (1002, "A38", "TA", "Major", "M5", "A380", 293000, 93000, 1.5),
    (1003, "U", "MCU", "Minor", "NA", "NA", 292500, 92800, None),
    (1004, "C", "MCU", "Minor", "NA", "NA", 292200, 93400, None),
]

COUNTED = ("Counted", "Manual count")
ESTIMATED = ("Estimated", "Estimated using AADF from previous year on this link")

# id, year, method, all motor vehicles (as written in the CSV)
AADF_ROWS = [
    (1001, 2024, ESTIMATED, "20000"),
    (1001, 2025, COUNTED, "21000"),
    (1002, 2022, COUNTED, "30000"),
    (1002, 2023, ESTIMATED, "30500"),
    (1002, 2024, ESTIMATED, "31000"),
    (1002, 2025, ESTIMATED, "31500"),
    (1003, 2012, COUNTED, "400"),
    (1004, 2015, COUNTED, "1200"),
    (1004, 2025, ESTIMATED, "1.3e+03"),  # DfT sometimes writes exponents
]

LA_CSV = (
    '"local_authority_id","local_authority_name","local_authority_code","year",'
    '"link_length_km","link_length_miles","cars_and_taxis","all_motor_vehicles"\n'
    '7,"Devon","E10000008",2024,13000,8078,5.1e+09,6900000000\n'
    '7,"Devon","E10000008",2025,13010,8084,5200000000,7.0e+09\n'
)


def _point(cp: int) -> tuple:
    return next(p for p in POINTS if p[0] == cp)


def _csv(rows: list[list]) -> str:
    return "\n".join(",".join(f'"{v}"' if isinstance(v, str) else str(v) for v in r) for r in rows)


def aadf_csv() -> str:
    rows = [AADF_HEADER]
    for cp, year, (method, detail), amv in AADF_ROWS:
        _, road, cat, typ, start, end, e, n, km = _point(cp)
        vehicles = ["10", "20", "15000", "100", "3000", "50", "", "NA", "0", "0", "0", "300", amv]
        rows.append(
            [cp, year, 1, "South West", "E12000009", 7, "Devon", "E10000008", road, cat, typ]
            + [start, end, e, n, 50.72, -3.53, "" if km is None else km, ""]
            + [method, detail, *vehicles]
        )
    return _csv(rows) + "\n"


def count_points_csv() -> str:
    header = AADF_HEADER[: AADF_HEADER.index("link_length_miles") + 1]
    rows = [header]
    for cp, road, cat, typ, start, end, e, n, km in POINTS:
        latest = max(y for c, y, *_ in AADF_ROWS if c == cp)
        rows.append(
            [cp, latest, 1, "South West", "E12000009", 7, "Devon", "E10000008", road, cat, typ]
            + [start, end, e, n, 50.72, -3.53, "" if km is None else km, ""]
        )
    rows.append([9999, 2025, 1, "", "", 7, "Devon", "E10000008", "U", "MCU", "Minor"] + [""] * 8)
    return _csv(rows) + "\n"


def zip_bytes(files: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


# ------------------------------------------------------------------ shapefile writer


def shp_bytes(shapes: list[list[list[tuple[float, float]]]]) -> bytes:
    """Polyline shapefile (.shp) for the given parts; an empty list is a null shape."""
    records = b""
    for i, parts in enumerate(shapes, start=1):
        if not parts:
            content = struct.pack("<i", 0)
        else:
            pts = [p for part in parts for p in part]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            starts, at = [], 0
            for part in parts:
                starts.append(at)
                at += len(part)
            content = struct.pack(
                "<i4d2i", 3, min(xs), min(ys), max(xs), max(ys), len(parts), len(pts)
            )
            content += struct.pack(f"<{len(starts)}i", *starts)
            content += struct.pack(f"<{2 * len(pts)}d", *[c for p in pts for c in p])
        records += struct.pack(">2i", i, len(content) // 2) + content
    header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(records)) // 2)
    header += struct.pack("<2i8d", 1000, 3, *([0.0] * 8))
    return header + records


def dbf_bytes(fields: list[tuple[str, str, int]], rows: list[list[str]]) -> bytes:
    """dBASE III table with fixed-width character/number fields."""
    record_len = 1 + sum(length for _, _, length in fields)
    header_len = 32 + 32 * len(fields) + 1
    out = struct.pack("<B3BIHH20x", 3, 126, 10, 6, len(rows), header_len, record_len)
    for name, kind, length in fields:
        out += struct.pack("<11sc4xBB14x", name.encode(), kind.encode(), length, 0)
    out += b"\r"
    for row in rows:
        out += b" " + b"".join(
            v.encode().ljust(length)[:length] for v, (_, _, length) in zip(row, fields, strict=True)
        )
    return out + b"\x1a"


MRDB_FIELDS = [("CP_Number", "F", 19), ("RoadNumber", "C", 20)]


def mrdb_zip() -> bytes:
    shapes = [
        [[(291000.0, 92000.0), (292800.0, 93000.0)]],  # 1001
        [[(292500.0, 92500.0), (293500.0, 93500.0)], [(293500.0, 93500.0), (293600.0, 93700.0)]],
        [],  # a null shape is skipped
    ]
    rows = [["1.00100000000e+03", "A30"], ["1002", "A38"], ["1003", ""]]
    return zip_bytes(
        {
            "MRDB_2024.shp": shp_bytes(shapes),
            "MRDB_2024.dbf": dbf_bytes(MRDB_FIELDS, rows),
            "MRDB_2024.prj": "PROJCS[British_National_Grid]",
        }
    )


def aadf_zip() -> bytes:
    return zip_bytes({"dft_traffic_counts_aadf.csv": aadf_csv()})


def count_points_zip() -> bytes:
    return zip_bytes({"count_points.csv": count_points_csv()})
