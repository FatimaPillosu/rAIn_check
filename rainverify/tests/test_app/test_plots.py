from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app import plots
from engine import scores as sc
from engine.bootstrap import moving_block_bootstrap_ci
from engine.matching import build_pairs
from ingest.load import load_forecast, load_observations

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"


@pytest.fixture(scope="module")
def golden_pairs():
    forecast = load_forecast(GOLDEN_DIR / "forecast.nc")
    obs = load_observations(GOLDEN_DIR / "observations.csv")
    obs = obs[obs["precip_mm"] < 500]
    pairs = build_pairs(obs, forecast, lead_day=1)
    return forecast, obs, pairs


def test_plot_crps_by_lead(golden_pairs):
    forecast, obs, pairs = golden_pairs
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()
    crps = sc.crps_ensemble(y, members)
    result = moving_block_bootstrap_ci(crps, pairs["date"], n_resamples=50)
    fig = plots.plot_crps_by_lead({1: result})
    assert fig is not None


def test_plot_rank_histogram(golden_pairs):
    _, _, pairs = golden_pairs
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()
    rh = sc.rank_histogram(y, members)
    fig = plots.plot_rank_histogram(rh)
    assert fig is not None


def test_plot_reliability_and_roc(golden_pairs):
    _, obs, pairs = golden_pairs
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()
    prob = sc.exceedance_probability(members, 5.0)
    rd = sc.reliability_diagram(y, prob, 5.0)
    fig1 = plots.plot_reliability_diagram(rd, 5.0)
    assert fig1 is not None

    roc = sc.roc_curve(y, prob, 5.0)
    fig2 = plots.plot_roc_curve(roc, 5.0)
    assert fig2 is not None


def test_plot_bss_by_threshold(golden_pairs):
    _, obs, pairs = golden_pairs
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()
    bss = {}
    for t in (1, 5, 20, 50):
        prob = sc.exceedance_probability(members, t)
        clim_p = sc.climatological_probability(obs["precip_mm"].to_numpy(), t)
        bss[t] = sc.brier_skill_score(y, prob, t, clim_p)
    fig = plots.plot_bss_by_threshold(bss)
    assert fig is not None


def test_maps_render_without_error(golden_pairs, tmp_path):
    forecast, obs, pairs = golden_pairs
    ref_time = forecast["forecast_reference_time"].values[5]

    fig1 = plots.map_ensemble_mean(forecast, ref_time, 1, obs=obs)
    plots.save_png(fig1, tmp_path / "mean.png")
    assert (tmp_path / "mean.png").exists()

    fig2 = plots.map_exceedance_probability(forecast, ref_time, 1, 5.0, obs=obs)
    plots.save_png(fig2, tmp_path / "exceedance.png")
    assert (tmp_path / "exceedance.png").exists()

    fig3 = plots.map_postage_stamp(forecast, ref_time, 1, max_members=6)
    plots.save_png(fig3, tmp_path / "stamps.png")
    assert (tmp_path / "stamps.png").exists()
