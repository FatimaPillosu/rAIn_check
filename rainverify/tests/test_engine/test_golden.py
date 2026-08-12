"""Golden self-test (plan §4.4): recompute all scores on the golden dataset and compare
to the recorded expected.json, to the plan's 1e-6 relative tolerance.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from engine import scores as sc
from engine.matching import build_pairs
from ingest.load import load_forecast, load_observations

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"
RTOL = 1e-6


@pytest.fixture(scope="module")
def golden():
    forecast = load_forecast(GOLDEN_DIR / "forecast.nc")
    obs = load_observations(GOLDEN_DIR / "observations.csv")
    obs_clean = obs[obs["precip_mm"] < 500]  # drop the deliberate QC blemish row
    expected = json.loads((GOLDEN_DIR / "expected.json").read_text())
    return forecast, obs_clean, expected


@pytest.mark.parametrize("lead", [1, 2])
def test_golden_crps_matches_expected(golden, lead):
    forecast, obs, expected = golden
    pairs = build_pairs(obs, forecast, lead_day=lead)
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()

    crps_mean = sc.crps_ensemble(y, members).mean()
    exp = expected["leads"][str(lead)]
    assert exp["n_pairs"] == len(pairs)
    assert crps_mean == pytest.approx(exp["crps_mean"], rel=RTOL)


@pytest.mark.parametrize("lead", [1, 2])
def test_golden_bias_mae_matches_expected(golden, lead):
    forecast, obs, expected = golden
    pairs = build_pairs(obs, forecast, lead_day=lead)
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()

    bias, mae = sc.bias_mae(y, members)
    exp = expected["leads"][str(lead)]
    assert bias == pytest.approx(exp["bias"], rel=RTOL, abs=1e-9)
    assert mae == pytest.approx(exp["mae"], rel=RTOL, abs=1e-9)


@pytest.mark.parametrize("lead", [1, 2])
@pytest.mark.parametrize("threshold", [1, 5, 20, 50])
def test_golden_bss_matches_expected(golden, lead, threshold):
    forecast, obs, expected = golden
    pairs = build_pairs(obs, forecast, lead_day=lead)
    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()

    prob = sc.exceedance_probability(members, threshold)
    clim_p = sc.climatological_probability(obs["precip_mm"].to_numpy(), threshold)
    bss = sc.brier_skill_score(y, prob, threshold, clim_p)

    exp = expected["leads"][str(lead)]["thresholds"][str(threshold)]
    if np.isnan(bss) and np.isnan(exp["bss"]):
        return
    assert bss == pytest.approx(exp["bss"], rel=RTOL, abs=1e-9)
