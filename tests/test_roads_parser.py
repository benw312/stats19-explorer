"""GeoPackage geometry -> EWKB for COPY into PostGIS."""

import struct

import pytest

from stats19.reference.roads import gpkg_to_ewkb

POINT_LE = struct.pack("<BIdd", 1, 1, 290000.0, 92000.0)


def test_adds_srid_to_little_endian_wkb_without_envelope():
    ewkb = bytes.fromhex(gpkg_to_ewkb(b"GP\x00\x01" + struct.pack("<i", 27700) + POINT_LE))

    assert ewkb[0] == 1
    assert struct.unpack("<II", ewkb[1:9]) == (0x20000001, 27700)
    assert ewkb[9:] == POINT_LE[5:]


def test_skips_a_32_byte_envelope():
    envelope = struct.pack("<4d", 0, 0, 1, 1)
    ewkb = bytes.fromhex(
        gpkg_to_ewkb(b"GP\x00\x03" + struct.pack("<i", 27700) + envelope + POINT_LE)
    )

    assert ewkb[9:] == POINT_LE[5:]


def test_big_endian_wkb():
    point_be = struct.pack(">BIdd", 0, 1, 1.0, 2.0)
    ewkb = bytes.fromhex(gpkg_to_ewkb(b"GP\x00\x00" + struct.pack(">i", 27700) + point_be))

    assert struct.unpack(">II", ewkb[1:9]) == (0x20000001, 27700)


@pytest.mark.parametrize(
    ("blob", "message"),
    [
        (b"XX\x00\x01" + b"\x00" * 30, "not a GeoPackage"),
        (b"GP\x00\x11" + b"\x00" * 30, "empty"),
        (b"GP\x00\x0f" + b"\x00" * 30, "envelope"),
    ],
)
def test_rejects_bad_blobs(blob, message):
    with pytest.raises(ValueError, match=message):
        gpkg_to_ewkb(blob)
