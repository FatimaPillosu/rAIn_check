"""GRIB forecast reader -> canonical schema (plan §4.2), via cfgrib/eccodes.

ECMWF ensemble GRIB files commonly split the control forecast (dataType='cf', no
'number' dim) from the perturbed members (dataType='pf', has 'number') into separate
"hypercubes" that cfgrib cannot open in one call. We try the simple path first and
fall back to opening control and perturbed separately, then concatenating them into a
single 'member' dimension (control = member 0).
"""
from __future__ import annotations

from pathlib import Path

import xarray as xr

from ..forecast_common import to_canonical


def _open_simple(path: str | Path) -> xr.Dataset:
    return xr.open_dataset(path, engine="cfgrib", chunks="auto")


def _open_control_plus_perturbed(path: str | Path) -> xr.Dataset:
    cf = xr.open_dataset(
        path, engine="cfgrib", chunks="auto",
        backend_kwargs={"filter_by_keys": {"dataType": "cf"}},
    )
    pf = xr.open_dataset(
        path, engine="cfgrib", chunks="auto",
        backend_kwargs={"filter_by_keys": {"dataType": "pf"}},
    )
    cf = cf.expand_dims(number=[0])
    combined = xr.concat([cf, pf], dim="number")
    return combined.sortby("number")


def read_forecast_grib(path: str | Path, *, accumulation_hours: int = 24) -> xr.Dataset:
    try:
        ds = _open_simple(path)
    except Exception:
        ds = _open_control_plus_perturbed(path)
    return to_canonical(ds, accumulation_hours=accumulation_hours)
