"""Parsers for OS Code-Point Open, OS Open Names, ONS boundaries and DfT RAS4001."""

import io
import zipfile

import pytest

from stats19.reference.boundaries import latest_service, parse_vintage
from stats19.reference.names import KEEP_LOCAL_TYPES, parse_names
from stats19.reference.ods import read_ods_sheet
from stats19.reference.postcodes import parse_postcodes, postcode_key
from stats19.reference.prevention import parse_prevention

# ------------------------------------------------------------------ postcodes


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def test_postcode_key_normalises_spacing_and_case():
    assert postcode_key(" ex1  1ae ") == "EX11AE"


def test_parse_postcodes_reads_all_area_files_and_skips_unlocated(tmp_path):
    path = tmp_path / "codepo.zip"
    path.write_bytes(
        _zip(
            {
                "Data/CSV/ex.csv": '"EX1 1AE",10,291966,92583,"E92000001","","","E10000008","E07000041","E05011020"\n'
                '"EX1 9ZZ",90,0,0,"E92000001","","","","",""\n',
                "Data/CSV/ab.csv": '"AB1 0AA",10,385386,801193,"S92000003","","","","S12000033","S13002843"\n',
                "Doc/Code-Point_Open_Column_Headers.csv": "PC,PQ\n",
            }
        )
    )

    rows = list(parse_postcodes(path))

    assert rows == [
        ("AB1 0AA", "AB10AA", 10, "S12000033", 385386, 801193),
        ("EX1 1AE", "EX11AE", 10, "E07000041", 291966, 92583),
    ]


# ------------------------------------------------------------------ open names

NAMES_ROW = (
    "osgb4000000074564391,http://x,{name},,,,{type},{local},291800,92500,,,"
    "291700,92400,291900,92600,EX1,,Exeter,,City,Exeter,,District,Devon,,County,"
    "South West,,England,,,,"
)


def test_parse_names_keeps_useful_types_only(tmp_path):
    lines = [
        NAMES_ROW.format(name="Sidwell Street", type="transportNetwork", local="Named Road"),
        NAMES_ROW.format(name="A30", type="transportNetwork", local="Numbered Road"),
        NAMES_ROW.format(name="Exeter", type="populatedPlace", local="City"),
        NAMES_ROW.format(name="EX1 1AE", type="other", local="Postcode"),
        NAMES_ROW.format(name="Haldon Forest", type="landcover", local="Woodland Or Forest"),
        NAMES_ROW.format(name="St Sidwell's School", type="other", local="Primary Education"),
    ]
    path = tmp_path / "opnames.zip"
    path.write_bytes(_zip({"Data/SX99.csv": "\n".join(lines) + "\n"}))

    rows = list(parse_names(path))

    assert [(r[1], r[2]) for r in rows] == [
        ("Sidwell Street", "Named Road"),
        ("A30", "Numbered Road"),
        ("Exeter", "City"),
        ("St Sidwell's School", "Primary Education"),
    ]
    assert rows[0][3:] == ("Exeter", "Exeter", "Devon", 291800, 92500, 291700, 92400, 291900, 92600)


def test_keep_types_exclude_postcodes():
    assert "Postcode" not in KEEP_LOCAL_TYPES


# ------------------------------------------------------------------ boundaries


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Counties_and_Unitary_Authorities_December_2024_Boundaries_UK_BGC", (2024, 12)),
        ("Local_Authority_Districts_May_2026_Boundaries_UK_BGC", (2026, 5)),
    ],
)
def test_parse_vintage(name, expected):
    assert parse_vintage(name) == expected


def test_latest_service_orders_by_date_not_alphabet():
    names = [
        "Local_Authority_Districts_December_2025_Boundaries_UK_BGC",
        "Local_Authority_Districts_May_2026_Boundaries_UK_BGC",
        "Local_Authority_Districts_May_2024_Boundaries_UK_BGC",
        "Local_Authority_Districts_May_2026_Boundaries_UK_BFC",
    ]

    assert (
        latest_service(names, "Local_Authority_Districts", "UK_BGC")
        == "Local_Authority_Districts_May_2026_Boundaries_UK_BGC"
    )


# ------------------------------------------------------------------ ODS / RAS4001

CONTENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
 <office:body><office:spreadsheet>
  <table:table table:name="Cover_sheet"><table:table-row><table:table-cell><text:p>x</text:p></table:table-cell></table:table-row></table:table>
  <table:table table:name="Average_value">
   <table:table-row><table:table-cell><text:p>Average value of prevention</text:p></table:table-cell></table:table-row>
   <table:table-row>
    <table:table-cell><text:p>Collision data year</text:p></table:table-cell>
    <table:table-cell><text:p>Price year</text:p></table:table-cell>
    <table:table-cell><text:p>Severity</text:p></table:table-cell>
    <table:table-cell><text:p>Cost per casualty (£)</text:p></table:table-cell>
    <table:table-cell><text:p>Cost per collision (£)</text:p></table:table-cell>
   </table:table-row>
   <table:table-row>
    <table:table-cell office:value-type="float" office:value="2025"><text:p>2025</text:p></table:table-cell>
    <table:table-cell office:value-type="float" office:value="2025"><text:p>2025</text:p></table:table-cell>
    <table:table-cell><text:p>Fatal</text:p></table:table-cell>
    <table:table-cell office:value-type="float" office:value="2613524.2"><text:p>2,613,524</text:p></table:table-cell>
    <table:table-cell office:value-type="float" office:value="2896024.2"><text:p>2,896,024</text:p></table:table-cell>
   </table:table-row>
   <table:table-row>
    <table:table-cell table:number-columns-repeated="2" office:value-type="float" office:value="2025"><text:p>2025</text:p></table:table-cell>
    <table:table-cell><text:p>Damage only</text:p></table:table-cell>
    <table:table-cell><text:p>-</text:p></table:table-cell>
    <table:table-cell office:value-type="float" office:value="3125.1"><text:p>3,125</text:p></table:table-cell>
   </table:table-row>
  </table:table>
 </office:spreadsheet></office:body>
</office:document-content>"""


@pytest.fixture
def ras_ods(tmp_path):
    path = tmp_path / "ras4001.ods"
    path.write_bytes(
        _zip(
            {
                "mimetype": "application/vnd.oasis.opendocument.spreadsheet",
                "content.xml": CONTENT_XML,
            }
        )
    )
    return path


def test_read_ods_sheet_expands_repeated_cells(ras_ods):
    rows = read_ods_sheet(ras_ods, "Average_value")

    assert rows[3] == [2025.0, 2025.0, "Damage only", "-", 3125.1]


def test_parse_prevention_finds_header_and_reads_values(ras_ods):
    rows = parse_prevention(ras_ods)

    assert rows == [
        (2025, 2025, "Fatal", 2613524.2, 2896024.2),
        (2025, 2025, "Damage only", None, 3125.1),
    ]
