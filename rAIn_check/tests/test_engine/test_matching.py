from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from engine.matching import AccumulationMismatchError, build_pairs, nearest_grid_point


def _tiny_forecast():
    lat = np.array([-4.0, -3.5, -3.0])
    lon = np.array([36.5, 37.0, 37.5])
    ref_times = pd.date_range("2026-01-01", periods=3, freq="D")
    tp = np.ones((3, 1, 4, 3, 3), dtype="float32") * 5.0
    return xr.Dataset(
        {"tp": (("forecast_reference_time", "lead_day", "member", "lat", "lon"), tp)},
        coords={"forecast_reference_time": ref_times, "lead_day": [1], "member": np.arange(4), "lat": lat, "lon": lon},
        attrs={"accumulation_hours": 24},
    )


def test_nearest_grid_point_picks_closest():
    lat = np.array([-4.0, -3.5, -3.0])
    lon = np.array([36.5, 37.0, 37.5])
    lat_idx, lon_idx, dist = nearest_grid_point(-3.4, 37.1, lat, lon)
    assert lat_idx == 1
    assert lon_idx == 1
    assert dist >= 0


def test_build_pairs_matches_by_reference_time_plus_lead():
    fc = _tiny_forecast()
    obs = pd.DataFrame({
        "station_id": ["S1"], "name": ["Test"], "lat": [-3.5], "lon": [37.0],
        "elevation_m": [0], "date": pd.to_datetime(["2026-01-02"]),
        "accum_hours": [24], "precip_mm": [7.0], "qc_flag": [0],
    })
    pairs = build_pairs(obs, fc, lead_day=1)
    assert len(pairs) == 1
    assert pairs.iloc[0]["obs_mm"] == 7.0
    assert len(pairs.iloc[0]["members"]) == 4
    assert (pairs.iloc[0]["members"] == 5.0).all()


def test_build_pairs_hard_fails_on_accumulation_mismatch():
    fc = _tiny_forecast()
    obs = pd.DataFrame({
        "station_id": ["S1"], "name": ["Test"], "lat": [-3.5], "lon": [37.0],
        "elevation_m": [0], "date": pd.to_datetime(["2026-01-02"]),
        "accum_hours": [6], "precip_mm": [7.0], "qc_flag": [0],
    })
    with pytest.raises(AccumulationMismatchError):
        build_pairs(obs, fc, lead_day=1)
