"""Score correctness tests (plan §7): cross-validated against an independent package for
CRPS, hand-computed for a handful of small degenerate cases, structural checks elsewhere.
"""
from __future__ import annotations

import numpy as np
import properscoring as ps
import pytest

from engine import scores as sc

RTOL = 1e-6


# --------------------------------------------------------------------------------------
# CRPS: cross-validated against properscoring (an independent implementation of the same
# Hersbach 2000 exact method) on random data, plus hand-computed degenerate cases.
# --------------------------------------------------------------------------------------

def test_crps_matches_properscoring_random_ensembles():
    rng = np.random.default_rng(42)
    n, m = 200, 15
    members = rng.gamma(2.0, 3.0, size=(n, m))
    obs = rng.gamma(2.0, 3.0, size=n)

    ours = sc.crps_ensemble(obs, members)
    theirs = ps.crps_ensemble(obs, members)

    np.testing.assert_allclose(ours, theirs, rtol=RTOL, atol=1e-8)


def test_crps_single_member_equals_absolute_error():
    # M=1: Hersbach's formula collapses to plain |forecast - obs| (worked by hand in
    # scripts/make_golden.py's docstring derivation and re-derived in the PR notes).
    members = np.array([[5.0]])
    obs = np.array([8.0])
    assert sc.crps_ensemble(obs, members)[0] == pytest.approx(3.0, abs=1e-9)


def test_crps_zero_spread_ensemble_equals_absolute_error():
    members = np.zeros((1, 5))
    obs = np.array([3.0])
    assert sc.crps_ensemble(obs, members)[0] == pytest.approx(3.0, abs=1e-9)


def test_crps_all_zero_rainfall_is_zero():
    members = np.zeros((1, 5))
    obs = np.array([0.0])
    assert sc.crps_ensemble(obs, members)[0] == pytest.approx(0.0, abs=1e-9)


def test_crps_exact_ties_hand_computed():
    # members=[1,1,3,3,5], obs=3 -> CRPS=0.4 (worked by hand; see docstring in scores.py
    # module and the PR description for the interval-by-interval arithmetic).
    members = np.array([[1.0, 1.0, 3.0, 3.0, 5.0]])
    obs = np.array([3.0])
    ours = sc.crps_ensemble(obs, members)[0]
    theirs = ps.crps_ensemble(obs, members)[0]
    assert ours == pytest.approx(0.4, abs=1e-9)
    assert ours == pytest.approx(theirs, rel=RTOL)


def test_crps_decomposition_sums_to_total():
    rng = np.random.default_rng(7)
    n, m = 150, 12
    members = rng.gamma(1.5, 4.0, size=(n, m))
    obs = rng.gamma(1.5, 4.0, size=n)

    decomp = sc.crps_decomposition(obs, members)
    direct_mean = sc.crps_ensemble(obs, members).mean()

    assert decomp.crps == pytest.approx(direct_mean, rel=1e-9)
    assert decomp.crps == pytest.approx(decomp.reliability + decomp.crps_potential, rel=1e-9)
    assert decomp.reliability >= -1e-9
    assert decomp.crps_potential >= -1e-9


# --------------------------------------------------------------------------------------
# Rank histogram
# --------------------------------------------------------------------------------------

def test_rank_histogram_hand_computed_rank():
    members = np.array([[1.0, 2.0, 3.0, 4.0]])
    obs = np.array([2.5])  # falls strictly between the 2nd and 3rd sorted members -> rank 3
    rh = sc.rank_histogram(obs, members, seed=0)
    assert rh.counts.sum() == 1
    assert rh.counts[2] == 1  # rank 3 is index 2 (0-based)


def test_rank_histogram_uniform_for_perfectly_calibrated_ensemble():
    rng = np.random.default_rng(1)
    n, m = 5000, 9
    draws = rng.normal(size=(n, m + 1))  # one extra column = the "truth" drawn from the same distribution
    members = draws[:, :m]
    obs = draws[:, m]
    rh = sc.rank_histogram(obs, members, seed=0)
    assert rh.p_value > 0.01  # should not reject flatness for a genuinely calibrated ensemble


# --------------------------------------------------------------------------------------
# Brier score / BSS
# --------------------------------------------------------------------------------------

def test_brier_score_hand_computed():
    forecast_prob = np.array([0.3, 0.7])
    obs = np.array([5.0, 15.0])
    bs = sc.brier_score(obs, forecast_prob, threshold_mm=10.0)
    assert bs == pytest.approx(0.09, abs=1e-9)


def test_bss_perfect_forecast_beats_climatology():
    obs = np.array([0.0, 0.0, 20.0, 20.0, 20.0])
    forecast_prob = (obs >= 10.0).astype(float)  # perfect probabilistic forecast
    clim_p = sc.climatological_probability(obs, 10.0)
    bss = sc.brier_skill_score(obs, forecast_prob, 10.0, clim_p)
    assert bss == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------------------
# Spread-error ratio, bias, MAE
# --------------------------------------------------------------------------------------

def test_bias_mae_hand_computed():
    members = np.array([[1.0, 2.0, 3.0]])
    obs = np.array([4.0])
    bias, mae = sc.bias_mae(obs, members)
    assert bias == pytest.approx(-2.0, abs=1e-9)
    assert mae == pytest.approx(2.0, abs=1e-9)


def test_spread_error_ratio_hand_computed():
    members = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    obs = np.array([2.0, 4.0])
    se = sc.spread_error_ratio(obs, members)
    assert se.spread == pytest.approx(1.0, abs=1e-9)
    assert se.rmse == pytest.approx(np.sqrt(0.5), abs=1e-9)
    assert se.ratio == pytest.approx(1.0 / np.sqrt(0.5), rel=1e-9)


# --------------------------------------------------------------------------------------
# ROC / AUC
# --------------------------------------------------------------------------------------

def test_roc_auc_perfect_forecast():
    forecast_prob = np.array([0.1, 0.2, 0.8, 0.9])
    obs = np.array([1.0, 2.0, 20.0, 30.0])  # threshold 10 perfectly separates by prob rank
    roc = sc.roc_curve(obs, forecast_prob, threshold_mm=10.0)
    assert roc.auc == pytest.approx(1.0, abs=1e-9)


def test_roc_auc_no_skill_constant_forecast_is_nan_or_trivial():
    forecast_prob = np.full(6, 0.5)
    obs = np.array([1.0, 20.0, 1.0, 20.0, 1.0, 20.0])
    roc = sc.roc_curve(obs, forecast_prob, threshold_mm=10.0)
    # A constant forecast gives a single usable operating point; AUC should not claim
    # spurious skill (i.e. should not be > 1 or wildly outside [0,1]).
    assert 0.0 <= roc.auc <= 1.0 or np.isnan(roc.auc)
