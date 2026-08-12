"""Station-to-grid-point matching (plan §7): nearest grid point, chosen point recorded
per station; hard-fail if forecast and observation accumulation windows disagree.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

EARTH_RADIUS_KM = 6371.0088


class AccumulationMismatchError(ValueError):
    pass


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def nearest_grid_point(station_lat: float, station_lon: float, grid_lat: np.ndarray, grid_lon: np.ndarray) -> tuple[int, int, float]:
    """Return (lat_index, lon_index, distance_km) of the nearest grid point to a station."""
    lat_idx = int(np.argmin(np.abs(grid_lat - station_lat)))
    lon_idx = int(np.argmin(np.abs(grid_lon - station_lon)))
    dist_km = float(_haversine_km(station_lat, station_lon, grid_lat[lat_idx], grid_lon[lon_idx]))
    return lat_idx, lon_idx, dist_km


def match_stations_to_grid(obs: pd.DataFrame, forecast: xr.Dataset) -> pd.DataFrame:
    """One row per station with its matched grid indices/coords and distance (km)."""
    grid_lat = forecast["lat"].values
    grid_lon = forecast["lon"].values
    stations = obs[["station_id", "lat", "lon"]].drop_duplicates("station_id").reset_index(drop=True)

    rows = []
    for _, s in stations.iterrows():
        lat_idx, lon_idx, dist_km = nearest_grid_point(s["lat"], s["lon"], grid_lat, grid_lon)
        rows.append({
            "station_id": s["station_id"],
            "station_lat": s["lat"],
            "station_lon": s["lon"],
            "grid_lat_index": lat_idx,
            "grid_lon_index": lon_idx,
            "grid_lat": float(grid_lat[lat_idx]),
            "grid_lon": float(grid_lon[lon_idx]),
            "distance_km": dist_km,
        })
    return pd.DataFrame(rows)


def build_pairs(obs: pd.DataFrame, forecast: xr.Dataset, lead_day: int) -> pd.DataFrame:
    """Forecast-observation pairs for one lead day: one row per (station, date) with the
    full ensemble as a list column 'members', plus the matched observation.

    Hard-fails with a plain message if any observation's accumulation window does not
    match the forecast's declared accumulation_hours (plan §7).
    """
    fc_accum = int(forecast.attrs["accumulation_hours"])
    bad = obs.loc[obs["accum_hours"] != fc_accum, "accum_hours"].unique()
    if len(bad) > 0:
        raise AccumulationMismatchError(
            f"Forecast accumulation window is {fc_accum}h but observations include "
            f"accum_hours={bad.tolist()}h. Forecast and observations must use the same "
            "accumulation window before matching."
        )

    match = match_stations_to_grid(obs, forecast)
    fc_lead = forecast.sel(lead_day=lead_day)

    rows = []
    for _, m in match.iterrows():
        station_obs = obs[obs["station_id"] == m["station_id"]].sort_values("date")
        member_vals = fc_lead["tp"].isel(lat=int(m["grid_lat_index"]), lon=int(m["grid_lon_index"]))
        for _, orow in station_obs.iterrows():
            ref_time = orow["date"] - pd.Timedelta(days=int(lead_day))
            try:
                ens = member_vals.sel(forecast_reference_time=ref_time).values
            except KeyError:
                continue
            ens = np.asarray(ens, dtype="float64").ravel()
            if np.all(np.isnan(ens)):
                continue
            rows.append({
                "station_id": m["station_id"],
                "date": orow["date"],
                "lead_day": lead_day,
                "obs_mm": float(orow["precip_mm"]),
                "members": ens,
                "distance_km": m["distance_km"],
            })
    return pd.DataFrame(rows)
