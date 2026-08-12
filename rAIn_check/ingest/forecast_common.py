"""Shared coercion from a raw xarray Dataset (however it names things) to the canonical
forecast schema (plan §4.1). Used by both the NetCDF and GRIB readers so neither format
knows about the other, and both converge on the same schema.

Known limitation (documented, not hidden): this assumes each time step in the input
already represents the accumulation over `accumulation_hours` (e.g. a genuine 24-h total
per step), not a cumulative-since-forecast-start value that needs decumulating. ECMWF
open-data GRIB/NetCDF ships cumulative `tp`; turning that into per-step accumulations is
a pre-processing step outside this reader (plan §2 anticipates forecasts being
pre-processed before they reach the canonical schema). See README "Known limitations".
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from .schema import FORECAST_VAR, SchemaError

_DIM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "forecast_reference_time": ("forecast_reference_time", "time", "init_time", "reftime"),
    "member": ("member", "number", "realization", "ensemble_member"),
    "lat": ("lat", "latitude", "y"),
    "lon": ("lon", "longitude", "x"),
}
_STEP_SYNONYMS = ("lead_day", "step", "lead_time", "forecast_period")
_VAR_SYNONYMS = (FORECAST_VAR, "precipitation", "precip", "rainfall", "tp_mm", "tp24")

_METRE_UNITS = {"m", "meter", "meters", "metre", "metres"}
_MM_UNITS = {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}


def _find_name(ds: xr.Dataset, candidates: tuple[str, ...]) -> str | None:
    names = set(ds.dims) | set(ds.coords) | set(ds.data_vars)
    for c in candidates:
        if c in names:
            return c
    return None


def _coerce_lead_day(ds: xr.Dataset, accumulation_hours: int) -> xr.Dataset:
    step_name = _find_name(ds, _STEP_SYNONYMS)
    if step_name is None:
        raise SchemaError(
            f"Could not find a lead-time dimension among {_STEP_SYNONYMS}. "
            f"Dataset has: {list(ds.dims)}."
        )
    if step_name == "lead_day":
        return ds

    step_vals = ds[step_name].values
    if np.issubdtype(step_vals.dtype, np.timedelta64):
        hours = step_vals / np.timedelta64(1, "h")
    else:
        hours = step_vals.astype("float64")

    lead_day = np.round(hours / accumulation_hours).astype("int64")
    if np.any(lead_day * accumulation_hours != np.round(hours)):
        raise SchemaError(
            f"Lead-time steps {hours.tolist()} (hours) are not exact multiples of the "
            f"declared accumulation_hours={accumulation_hours}; cannot map to whole lead days."
        )
    ds = ds.rename({step_name: "lead_day"})
    ds = ds.assign_coords(lead_day=("lead_day", lead_day))
    return ds


def to_canonical(ds: xr.Dataset, *, accumulation_hours: int = 24, accumulation_end_utc: str | None = None) -> xr.Dataset:
    """Rename/reshape a raw xarray Dataset onto the canonical forecast schema."""
    rename = {}
    for canonical, synonyms in _DIM_SYNONYMS.items():
        found = _find_name(ds, synonyms)
        if found is None:
            raise SchemaError(
                f"Could not find a '{canonical}' dimension among {synonyms}. "
                f"Dataset has: {list(ds.dims)}."
            )
        if found != canonical:
            rename[found] = canonical
    if rename:
        ds = ds.rename(rename)

    ds = _coerce_lead_day(ds, accumulation_hours)

    var_name = _find_name(ds, _VAR_SYNONYMS)
    if var_name is None:
        raise SchemaError(
            f"Could not find a precipitation variable among {_VAR_SYNONYMS}. "
            f"Dataset variables: {list(ds.data_vars)}."
        )
    if var_name != FORECAST_VAR:
        ds = ds.rename({var_name: FORECAST_VAR})

    units = str(ds[FORECAST_VAR].attrs.get("units", "")).strip().lower()
    if units in _METRE_UNITS:
        ds[FORECAST_VAR] = ds[FORECAST_VAR] * 1000.0
    elif units in _MM_UNITS or units == "":
        pass  # already mm, or unlabelled — canonical schema assumes mm
    else:
        raise SchemaError(f"Unrecognised precipitation units '{units}'; expected metres or mm.")

    ds[FORECAST_VAR] = ds[FORECAST_VAR].astype("float32")
    ds[FORECAST_VAR].attrs["units"] = "mm"

    order = ["forecast_reference_time", "lead_day", "member", "lat", "lon"]
    ds = ds.transpose(*[d for d in order if d in ds[FORECAST_VAR].dims])

    ds.attrs["accumulation_hours"] = accumulation_hours
    if accumulation_end_utc is not None:
        ds.attrs["accumulation_end_utc"] = accumulation_end_utc
    elif "accumulation_end_utc" not in ds.attrs:
        ds.attrs["accumulation_end_utc"] = ""

    return ds[[FORECAST_VAR]]
