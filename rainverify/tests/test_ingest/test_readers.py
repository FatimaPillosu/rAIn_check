from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from ingest.load import load_forecast, load_observations
from ingest.schema import SchemaError, validate_forecast_dataset


def _write_raw_netcdf(path, *, dim_names, units):
    ref_times = pd.date_range("2026-01-01", periods=2, freq="D")
    tp = np.random.default_rng(0).gamma(1.0, 2.0, size=(2, 2, 3, 4, 4)).astype("float32")
    if units == "m":
        tp = tp / 1000.0
    ds = xr.Dataset(
        {dim_names["var"]: (
            (dim_names["reftime"], dim_names["step"], dim_names["member"], dim_names["lat"], dim_names["lon"]), tp
        )},
        coords={
            dim_names["reftime"]: ref_times,
            dim_names["step"]: [24, 48],  # "step" conventionally means hours, not lead-days
            dim_names["member"]: np.arange(3),
            dim_names["lat"]: np.linspace(-4, -3, 4),
            dim_names["lon"]: np.linspace(36, 37, 4),
        },
        attrs={"accumulation_hours": 24},
    )
    ds[dim_names["var"]].attrs["units"] = units
    ds.to_netcdf(path, engine="h5netcdf")


def test_read_canonical_netcdf(tmp_path):
    path = tmp_path / "fc.nc"
    _write_raw_netcdf(path, dim_names={
        "reftime": "forecast_reference_time", "step": "lead_day", "member": "member",
        "lat": "lat", "lon": "lon", "var": "tp",
    }, units="mm")
    ds = load_forecast(path)
    validate_forecast_dataset(ds)
    assert set(ds.dims) == {"forecast_reference_time", "lead_day", "member", "lat", "lon"}


def test_read_netcdf_with_alternate_names_and_units(tmp_path):
    path = tmp_path / "fc_alt.nc"
    _write_raw_netcdf(path, dim_names={
        "reftime": "time", "step": "step", "member": "number",
        "lat": "latitude", "lon": "longitude", "var": "precipitation",
    }, units="m")
    ds = load_forecast(path)
    validate_forecast_dataset(ds)
    assert ds["tp"].attrs["units"] == "mm"
    # units were metres in the raw file -> values should have been scaled by 1000
    assert float(ds["tp"].max()) > 0.01


def test_read_observations_exact_schema(tmp_path):
    path = tmp_path / "obs.csv"
    path.write_text(
        "station_id,name,lat,lon,elevation_m,date,accum_hours,precip_mm,qc_flag\n"
        "TZ0042,Moshi,-3.35,37.33,890,2026-03-14,24,31.2,0\n"
    )
    df = load_observations(path)
    assert df.iloc[0]["precip_mm"] == 31.2
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_read_observations_unknown_schema_raises_with_guidance(tmp_path):
    path = tmp_path / "messy.csv"
    path.write_text("code,when,rain\nA,2026-01-01,1.0\n")
    with pytest.raises(SchemaError):
        load_observations(path)
