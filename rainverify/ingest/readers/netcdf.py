"""NetCDF forecast reader -> canonical schema (plan §4.2)."""
from __future__ import annotations

from pathlib import Path

import xarray as xr

from ..forecast_common import to_canonical


def read_forecast_netcdf(path: str | Path, *, accumulation_hours: int = 24) -> xr.Dataset:
    # h5netcdf engine: no libnetcdf C dependency, pure-Python-friendly on Windows.
    # chunks="auto" keeps this lazy — the file is never fully loaded into memory (plan §2).
    ds = xr.open_dataset(path, engine="h5netcdf", chunks="auto")
    return to_canonical(ds, accumulation_hours=accumulation_hours)
