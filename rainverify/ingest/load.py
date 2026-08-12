"""Top-level entry points: detect format from content, route to the matching reader,
converge on the canonical schema (plan §4.2). Nothing downstream needs to know which
format arrived.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

from .detect import sniff_format
from .readers.grib import read_forecast_grib
from .readers.netcdf import read_forecast_netcdf
from .readers.tabular import read_observations_csv
from .recipes import Recipe


def load_forecast(path: str | Path, *, accumulation_hours: int = 24) -> xr.Dataset:
    fmt = sniff_format(path)
    if fmt == "netcdf":
        return read_forecast_netcdf(path, accumulation_hours=accumulation_hours)
    if fmt == "grib":
        return read_forecast_grib(path, accumulation_hours=accumulation_hours)
    raise ValueError(f"'{path}' looks like {fmt}, not a recognised forecast format (NetCDF or GRIB).")


def load_observations(path: str | Path, recipe: Recipe | None = None) -> pd.DataFrame:
    return read_observations_csv(path, recipe=recipe)
