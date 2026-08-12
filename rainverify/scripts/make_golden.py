"""Generate the golden dataset (plan §4.4): a small analytic case, already in canonical
form, with a fixed seed so it regenerates identically every time. 5 stations x 20 days x
10 members, on a 5x5 grid (East-Africa-scale spacing), leads 1-2 days.

This is not literally "worked out on paper" for every score — that is only realistic for
the small hand-computable degenerate cases covered separately in
tests/test_engine/test_scores.py (single member, all-zero rain, exact ties). What this
script buys instead: a fixed, reproducible dataset with genuine forecast skill (not
independent noise), used as (a) a properscoring cross-validation fixture for CRPS and
(b) a regression baseline recorded in expected.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import scores as sc
from engine.matching import build_pairs
from ingest.schema import OBS_COLUMNS

SEED = 20260811
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "golden"

N_STATIONS = 5
N_DAYS = 20
N_MEMBERS = 10
LEADS = [1, 2]
GRID_LAT = np.round(np.arange(-4.0, -2.99, 0.25), 2)  # 5 points
GRID_LON = np.round(np.arange(36.5, 37.51, 0.25), 2)  # 5 points

STATIONS = [
    {"station_id": "TZ0001", "name": "Moshi",      "lat": -3.35, "lon": 37.33, "elevation_m": 890},
    {"station_id": "TZ0002", "name": "Arusha",     "lat": -3.37, "lon": 36.68, "elevation_m": 1400},
    {"station_id": "TZ0003", "name": "Same",       "lat": -4.07, "lon": 37.73, "elevation_m": 900},
    {"station_id": "TZ0004", "name": "Marangu",    "lat": -3.28, "lon": 37.52, "elevation_m": 1400},
    {"station_id": "TZ0005", "name": "Loitokitok", "lat": -2.98, "lon": 37.51, "elevation_m": 1700},
]


def _nearest_idx(value: float, grid: np.ndarray) -> int:
    return int(np.argmin(np.abs(grid - value)))


def make_golden(seed: int = SEED):
    rng = np.random.default_rng(seed)

    n_dates_all = N_DAYS + max(LEADS) + 1  # 23: covers all needed ref_time/lead/date combos
    dates_all = pd.date_range("2026-03-01", periods=n_dates_all, freq="D")

    # "Truth" field: one Gamma draw per (date, lat, lon), shared by obs and forecast
    # generation so forecasts have genuine skill rather than being independent noise.
    true_field = rng.gamma(shape=1.2, scale=4.0, size=(n_dates_all, len(GRID_LAT), len(GRID_LON)))

    # --- Observations ---
    obs_rows = []
    obs_date_idx = range(2, 2 + N_DAYS)  # indices 2..21 -> valid for leads 1 and 2
    for s in STATIONS:
        lat_idx = _nearest_idx(s["lat"], GRID_LAT)
        lon_idx = _nearest_idx(s["lon"], GRID_LON)
        for di in obs_date_idx:
            station_noise = rng.normal(0, 0.5)
            precip = max(0.0, true_field[di, lat_idx, lon_idx] + station_noise)
            obs_rows.append({
                "station_id": s["station_id"], "name": s["name"],
                "lat": s["lat"], "lon": s["lon"], "elevation_m": s["elevation_m"],
                "date": dates_all[di], "accum_hours": 24,
                "precip_mm": round(precip, 1), "qc_flag": 0,
            })
    obs = pd.DataFrame(obs_rows)[list(OBS_COLUMNS)]
    obs["date"] = pd.to_datetime(obs["date"])

    # A handful of QC-worthy blemishes, deliberately introduced and known, so the QC
    # step has something honest to catch (kept out of the score-bearing rows above by
    # duplicating one date rather than corrupting the golden score fixture).
    blemish = obs.iloc[[0]].copy()
    blemish["precip_mm"] = 999.0  # physically impossible -> range check should fail it
    obs_with_blemishes = pd.concat([obs, blemish], ignore_index=True)

    # --- Forecast ensemble ---
    ref_time_idx = range(0, N_DAYS + 1)  # indices 0..20
    ref_times = dates_all[list(ref_time_idx)]
    tp = np.empty((len(ref_times), len(LEADS), N_MEMBERS, len(GRID_LAT), len(GRID_LON)), dtype="float32")
    for ri, r in enumerate(ref_time_idx):
        for li, lead in enumerate(LEADS):
            date_idx = r + lead
            base = true_field[date_idx] * (1.0 + 0.02 * lead)
            noise_scale = 1.0 + 0.5 * lead
            for mem in range(N_MEMBERS):
                noise = rng.normal(0, noise_scale, size=base.shape)
                tp[ri, li, mem] = np.clip(base + noise, 0, None)

    forecast = xr.Dataset(
        data_vars={"tp": (("forecast_reference_time", "lead_day", "member", "lat", "lon"), tp)},
        coords={
            "forecast_reference_time": ref_times,
            "lead_day": LEADS,
            "member": np.arange(N_MEMBERS),
            "lat": GRID_LAT,
            "lon": GRID_LON,
        },
        attrs={"accumulation_hours": 24, "accumulation_end_utc": "", "units": "mm"},
    )
    forecast["tp"].attrs["units"] = "mm"

    return forecast, obs_with_blemishes, obs  # (with blemishes for QC demo, clean for score fixture)


def compute_expected(forecast: xr.Dataset, obs: pd.DataFrame) -> dict:
    expected = {"seed": SEED, "leads": {}}
    for lead in LEADS:
        pairs = build_pairs(obs, forecast, lead_day=lead)
        members = np.stack(pairs["members"].to_numpy())
        y = pairs["obs_mm"].to_numpy()

        crps = sc.crps_ensemble(y, members)
        decomp = sc.crps_decomposition(y, members)
        rh = sc.rank_histogram(y, members, seed=0)
        bias, mae = sc.bias_mae(y, members)
        se = sc.spread_error_ratio(y, members)

        threshold_results = {}
        for thr in (1, 5, 20, 50):
            prob = sc.exceedance_probability(members, thr)
            clim_p = sc.climatological_probability(obs["precip_mm"].to_numpy(), thr)
            bs = sc.brier_score(y, prob, thr)
            bss = sc.brier_skill_score(y, prob, thr, clim_p)
            threshold_results[str(thr)] = {"brier_score": bs, "bss": bss, "climatology_prob": clim_p}

        expected["leads"][str(lead)] = {
            "n_pairs": int(len(pairs)),
            "crps_mean": float(crps.mean()),
            "crps_decomposition": {
                "reliability": decomp.reliability, "crps_potential": decomp.crps_potential,
            },
            "rank_histogram_chi2": rh.chi2_statistic,
            "rank_histogram_pvalue": rh.p_value,
            "bias": bias, "mae": mae,
            "spread": se.spread, "rmse": se.rmse, "spread_error_ratio": se.ratio,
            "thresholds": threshold_results,
        }
    return expected


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    forecast, obs_with_blemishes, obs_clean = make_golden()

    forecast.to_netcdf(OUT_DIR / "forecast.nc", engine="h5netcdf")
    obs_with_blemishes.to_csv(OUT_DIR / "observations.csv", index=False)

    expected = compute_expected(forecast, obs_clean)
    (OUT_DIR / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")

    print(f"Golden dataset written to {OUT_DIR}")
    print(f"  forecast.nc: {forecast.dims}")
    print(f"  observations.csv: {len(obs_with_blemishes)} rows ({len(obs_clean)} clean + "
          f"{len(obs_with_blemishes) - len(obs_clean)} deliberate blemish)")


if __name__ == "__main__":
    main()
