from __future__ import annotations

import pytest

from ingest.detect import sniff_format


def test_sniff_netcdf(tmp_path):
    f = tmp_path / "no_extension_hint"
    f.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 20)
    assert sniff_format(f) == "netcdf"


def test_sniff_grib(tmp_path):
    f = tmp_path / "no_extension_hint"
    f.write_bytes(b"GRIB" + b"\x00" * 20)
    assert sniff_format(f) == "grib"


def test_sniff_csv(tmp_path):
    f = tmp_path / "no_extension_hint"
    f.write_text("station_id,date,precip_mm\nA,2026-01-01,1.0\n")
    assert sniff_format(f) == "csv"


def test_sniff_rejects_unknown_binary(tmp_path):
    f = tmp_path / "mystery.bin"
    f.write_bytes(bytes(range(200, 256)))
    with pytest.raises(ValueError):
        sniff_format(f)
