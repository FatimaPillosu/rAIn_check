"""Format detection from file content (magic bytes), never from the filename (plan §4.2)."""
from __future__ import annotations

from pathlib import Path

_HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
_NETCDF_CLASSIC_MAGIC = b"CDF"
_GRIB_MAGIC = b"GRIB"


def sniff_format(path: str | Path) -> str:
    """Return 'netcdf', 'grib', or 'csv' by reading the first bytes of the file."""
    path = Path(path)
    with open(path, "rb") as fh:
        head = fh.read(8)

    if head.startswith(_GRIB_MAGIC):
        return "grib"
    if head.startswith(_HDF5_MAGIC) or head.startswith(_NETCDF_CLASSIC_MAGIC):
        return "netcdf"

    # Not a recognised binary format: treat as tabular text (CSV/TSV) and let the
    # tabular reader validate it further. A quick sanity check avoids silently
    # accepting genuinely unknown binaries.
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"'{path.name}' is not recognised NetCDF, GRIB, or UTF-8 text. "
            "Cannot determine its format from content."
        ) from exc
    return "csv"
