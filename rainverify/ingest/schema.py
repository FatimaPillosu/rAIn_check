"""The one canonical internal schema (plan §4.1).

Every input, whatever its native format, is converted on read into this
representation. Quality control, scores, plots and the report see only this.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

FORECAST_DIMS = ("forecast_reference_time", "lead_day", "member", "lat", "lon")
FORECAST_VAR = "tp"  # 24-h precipitation accumulation, mm, float32

OBS_COLUMNS = (
    "station_id",
    "name",
    "lat",
    "lon",
    "elevation_m",
    "date",
    "accum_hours",
    "precip_mm",
    "qc_flag",
)

OBS_DTYPES = {
    "station_id": "object",
    "name": "object",
    "lat": "float64",
    "lon": "float64",
    "elevation_m": "float64",
    "accum_hours": "int64",
    "precip_mm": "float64",
    "qc_flag": "int64",
}


class SchemaError(ValueError):
    """Raised when data cannot be made to fit the canonical schema, with a plain-language reason."""


def validate_forecast_dataset(ds: xr.Dataset) -> None:
    missing_dims = [d for d in FORECAST_DIMS if d not in ds.dims]
    if missing_dims:
        raise SchemaError(
            f"Forecast dataset is missing dimension(s) {missing_dims}. "
            f"Expected all of {FORECAST_DIMS}, found {tuple(ds.dims)}."
        )
    if FORECAST_VAR not in ds.data_vars:
        raise SchemaError(
            f"Forecast dataset has no '{FORECAST_VAR}' variable (24-h precipitation, mm). "
            f"Found variables: {list(ds.data_vars)}."
        )
    if "accumulation_hours" not in ds.attrs:
        raise SchemaError("Forecast dataset is missing the 'accumulation_hours' global attribute.")


def validate_obs_dataframe(df: pd.DataFrame) -> None:
    missing_cols = [c for c in OBS_COLUMNS if c not in df.columns]
    if missing_cols:
        raise SchemaError(
            f"Observation table is missing column(s) {missing_cols}. "
            f"Expected all of {OBS_COLUMNS}, found {list(df.columns)}."
        )
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        raise SchemaError("Observation table 'date' column must be parsed to datetime before use.")


def empty_obs_dataframe() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype=OBS_DTYPES.get(c, "object")) for c in OBS_COLUMNS})
    df["date"] = pd.to_datetime(df["date"])
    return df


def coerce_obs_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col, dtype in OBS_DTYPES.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    return df[list(OBS_COLUMNS)]
