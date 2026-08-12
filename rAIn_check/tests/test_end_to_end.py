"""Demo-pack smoke test: load -> recipe approval -> QC -> scores, the same path as the
plan's "Demo 1" walkthrough (§10 S4). Skips if the demo pack hasn't been generated yet
(run scripts/make_demo_pack.py first).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from engine import qc, scores as sc
from engine.matching import build_pairs
from ingest.load import load_forecast
from ingest.recipes import apply_recipe, propose_recipe
from ingest.readers.tabular import read_observations_csv

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples"
FORECAST_PATH = SAMPLES_DIR / "forecast_ensemble.nc"
STATIONS_PATH = SAMPLES_DIR / "pseudo_stations.csv"

pytestmark = pytest.mark.skipif(
    not (FORECAST_PATH.exists() and STATIONS_PATH.exists()),
    reason="demo pack not generated — run scripts/make_demo_pack.py",
)


def test_demo_pack_full_pipeline():
    forecast = load_forecast(FORECAST_PATH)
    assert forecast.attrs["accumulation_hours"] == 24

    recipe = propose_recipe(STATIONS_PATH)
    # the demo pack's awkward headers should all resolve without needing a human ASK,
    # except the date-format ambiguity, which is a genuine judgement call (see recipes.py)
    unresolved = [n for n in recipe.notes if n.startswith("ASK") and "date" not in n.lower()]
    assert not unresolved, f"demo pack recipe needed unexpected human input: {unresolved}"

    import pandas as pd
    df_raw = pd.read_csv(STATIONS_PATH)
    obs = apply_recipe(df_raw, recipe)

    checks = qc.run_all_checks(obs, forecast_accum_hours=int(forecast.attrs["accumulation_hours"]))
    assert checks["range"].flagged_count >= 0  # ran without error; outliers are expected by design

    pairs = build_pairs(obs, forecast, lead_day=1)
    assert len(pairs) > 100  # ~30 stations x ~55 days, minus gaps

    members = np.stack(pairs["members"].to_numpy())
    y = pairs["obs_mm"].to_numpy()
    crps = sc.crps_ensemble(y, members)
    assert np.all(crps >= 0)
    assert np.isfinite(crps).all()

    prob = sc.exceedance_probability(members, 5.0)
    clim_p = sc.climatological_probability(obs["precip_mm"].to_numpy(), 5.0)
    bss = sc.brier_skill_score(y, prob, 5.0, clim_p)
    assert np.isfinite(bss)
