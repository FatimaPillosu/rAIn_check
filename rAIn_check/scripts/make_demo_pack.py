"""Generate the demo pack (plan §4.5): synthetic ECMWF-ENS-shaped 24-h precipitation over
a 10x10deg East Africa domain, ~60 daily runs, leads 1-5 days, 51 members, plus ~30
pseudo-stations sampled from a held-out member with added noise, gaps and outliers.

Honesty note: this is SYNTHETIC data, not a real ECMWF download. The plan's demo pack
(§4.5) describes real ECMWF open-data ENS precipitation, but ECMWF's free open-data feed
only carries the last few days, not the 60-90 day archive a demo needs — that requires
MARS access under the user's own API key (plan §4.6), which this build does not have.
The station file is deliberately shipped with awkward column names/date format so the
demo exercises the same ingestion-recipe flow (plan §4.3) real data would need.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SEED = 20260811001
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "samples"

N_RUNS = 60
N_MEMBERS = 51
LEADS = [1, 2, 3, 4, 5]
LAT = np.round(np.arange(-5.0, 5.01, 0.25), 2)   # 41 points
LON = np.round(np.arange(33.0, 43.01, 0.25), 2)  # 41 points
N_STATIONS = 30


def _smooth_positive_field(rng: np.random.Generator, n_dates: int, n_lat: int, n_lon: int) -> np.ndarray:
    """Spatially-correlated, right-skewed synthetic rainfall field, one per day."""
    raw = rng.normal(size=(n_dates, n_lat, n_lon))
    smoothed = gaussian_filter(raw, sigma=(0, 2.5, 2.5))
    positive = np.clip(smoothed, 0, None)
    return (positive ** 2) * 6.0  # arbitrary scaling to a plausible daily-mm range


def make_demo_pack(seed: int = SEED):
    rng = np.random.default_rng(seed)

    n_dates_all = N_RUNS + max(LEADS) + 1
    dates_all = pd.date_range("2025-12-01", periods=n_dates_all, freq="D")
    true_field = _smooth_positive_field(rng, n_dates_all, len(LAT), len(LON))

    # --- Forecast ensemble (written as NetCDF; see module docstring on why not GRIB) ---
    ref_time_idx = range(0, N_RUNS)
    ref_times = dates_all[list(ref_time_idx)]
    tp = np.empty((len(ref_times), len(LEADS), N_MEMBERS, len(LAT), len(LON)), dtype="float32")
    for ri, r in enumerate(ref_time_idx):
        for li, lead in enumerate(LEADS):
            date_idx = r + lead
            base = true_field[date_idx] * (1.0 + 0.015 * lead)
            noise_scale = 1.5 + 0.6 * lead
            noise = rng.normal(0, noise_scale, size=(N_MEMBERS, len(LAT), len(LON)))
            tp[ri, li] = np.clip(base[None, :, :] + noise, 0, None)

    forecast = xr.Dataset(
        data_vars={"tp": (("forecast_reference_time", "lead_day", "member", "lat", "lon"), tp)},
        coords={
            "forecast_reference_time": ref_times, "lead_day": LEADS,
            "member": np.arange(N_MEMBERS), "lat": LAT, "lon": LON,
        },
        attrs={
            "accumulation_hours": 24, "accumulation_end_utc": "",
            "source": "SYNTHETIC — not real ECMWF data. Shaped like ECMWF open-data ENS "
                      "tp for demo/smoke-test purposes only. See scripts/make_demo_pack.py.",
        },
    )
    forecast["tp"].attrs["units"] = "mm"

    # --- Pseudo-stations: sample a held-out member (member index 0), add station noise,
    # gaps and a few deliberate outliers, per plan §4.5. ---
    rng_stations = np.random.default_rng(seed + 1)
    station_lat = rng_stations.uniform(LAT.min() + 0.5, LAT.max() - 0.5, N_STATIONS)
    station_lon = rng_stations.uniform(LON.min() + 0.5, LON.max() - 0.5, N_STATIONS)
    station_names = [f"Site {i+1:02d}" for i in range(N_STATIONS)]

    obs_date_idx = list(range(2, 2 + N_RUNS - max(LEADS) + 1))  # keep well inside the truth range
    rows = []
    for i in range(N_STATIONS):
        lat_idx = int(np.argmin(np.abs(LAT - station_lat[i])))
        lon_idx = int(np.argmin(np.abs(LON - station_lon[i])))
        for di in obs_date_idx:
            if rng_stations.random() < 0.05:
                continue  # simulate a reporting gap
            value = true_field[di, lat_idx, lon_idx] + rng_stations.normal(0, 1.0)
            value = max(0.0, value)
            if rng_stations.random() < 0.02:
                value *= rng_stations.uniform(8, 15)  # deliberate spike/outlier
            rows.append({
                "Station Code": f"STN{i+1:03d}",
                "Site": station_names[i],
                "Lat (deg)": round(station_lat[i], 4),
                "Lon (deg)": round(station_lon[i], 4),
                "Elev (m)": int(rng_stations.uniform(400, 2200)),
                "Obs Date": dates_all[di].strftime("%d/%m/%Y"),  # awkward format on purpose
                "24h Rainfall (mm)": round(value, 1),
            })
    stations_df = pd.DataFrame(rows)

    return forecast, stations_df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    forecast, stations_df = make_demo_pack()

    fc_path = OUT_DIR / "forecast_ensemble.nc"
    forecast.to_netcdf(fc_path, engine="h5netcdf")

    obs_path = OUT_DIR / "pseudo_stations.csv"
    stations_df.to_csv(obs_path, index=False)

    size_mb = (fc_path.stat().st_size + obs_path.stat().st_size) / 1e6
    print(f"Demo pack written to {OUT_DIR}")
    print(f"  {fc_path.name}: {dict(forecast.sizes)}")
    print(f"  {obs_path.name}: {len(stations_df)} rows across {stations_df['Station Code'].nunique()} stations")
    print(f"  total size: {size_mb:.1f} MB (budget: <=300 MB)")


if __name__ == "__main__":
    main()
