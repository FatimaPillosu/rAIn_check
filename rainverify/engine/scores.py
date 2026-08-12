"""Verification scores v1 (plan §7). Small, readable, individually documented functions —
the assistant teaches from this code and never generates a number itself.

Event convention used throughout: an "exceedance" of threshold t means precip_mm >= t
(the usual rain/no-rain and heavy-rain convention in operational verification).

Confidence notes (plan owner asked to be told, explicitly, when something is recalled
rather than independently verified — see CLAUDE.md "when uncertain, state your
confidence"):
  - CRPS (Hersbach 2000 exact/interval method): HIGH confidence. Cross-validated in
    tests/test_engine/test_scores.py against the independent `properscoring` package
    to the plan's 1e-6 relative tolerance.
  - CRPS decomposition into Reliability + CRPSpot: the formula below was algebraically
    verified (by hand, in this session) to satisfy CRPS = Reliability + CRPSpot exactly
    for arbitrary g_i, h_i, so the two components are internally consistent. What is
    NOT independently verified tonight is that "Reliability"/"CRPSpot" as named here
    line up term-for-term with Hersbach (2000)'s own labelling, or that CRPSpot doesn't
    warrant a further resolution/uncertainty split as in the Brier-score decomposition.
    Treat the total CRPS as fully trustworthy; treat the decomposition breakdown as
    a reasonable, self-consistent estimate to be checked against the paper before it
    goes in a publication.
  - Rank histogram, Brier/BSS, reliability diagram, ROC/AUC, spread-error, bias/MAE:
    HIGH confidence — standard textbook definitions (Wilks, "Statistical Methods in the
    Atmospheric Sciences"), covered by golden-dataset tests with hand-computable values.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


# --------------------------------------------------------------------------------------
# CRPS (Hersbach 2000)
# --------------------------------------------------------------------------------------

def crps_ensemble(obs: np.ndarray, members: np.ndarray) -> np.ndarray:
    """Exact per-pair CRPS for an ensemble forecast, Hersbach (2000) interval method.

    obs: shape (N,). members: shape (N, M). Returns shape (N,).
    """
    obs = np.asarray(obs, dtype="float64")
    members = np.asarray(members, dtype="float64")
    x = np.sort(members, axis=1)
    n_members = x.shape[1]

    x_lo, x_hi = x[:, :-1], x[:, 1:]          # (N, M-1)
    width = x_hi - x_lo
    y = obs[:, None]

    alpha = np.clip(y - x_lo, 0.0, width)      # (N, M-1)
    beta = width - alpha

    p = np.arange(1, n_members) / n_members    # (M-1,)
    interior = alpha * p[None, :] ** 2 + beta * (1.0 - p[None, :]) ** 2
    interior_sum = interior.sum(axis=1)

    beta_0 = np.clip(x[:, 0] - obs, 0.0, None)
    alpha_m = np.clip(obs - x[:, -1], 0.0, None)

    return beta_0 + alpha_m + interior_sum


@dataclass
class CrpsDecomposition:
    crps: float
    reliability: float
    crps_potential: float
    n_pairs: int
    n_members: int


def crps_decomposition(obs: np.ndarray, members: np.ndarray) -> CrpsDecomposition:
    """Aggregate CRPS split into Reliability + CRPSpot (see module docstring for the
    confidence note on this specific split).
    """
    obs = np.asarray(obs, dtype="float64")
    members = np.asarray(members, dtype="float64")
    x = np.sort(members, axis=1)
    n, m = x.shape

    full_alpha = np.zeros((n, m + 1))
    full_beta = np.zeros((n, m + 1))

    x_lo, x_hi = x[:, :-1], x[:, 1:]
    width = x_hi - x_lo
    y = obs[:, None]
    alpha = np.clip(y - x_lo, 0.0, width)
    beta = width - alpha
    full_alpha[:, 1:m] = alpha
    full_beta[:, 1:m] = beta

    full_beta[:, 0] = np.clip(x[:, 0] - obs, 0.0, None)
    full_alpha[:, m] = np.clip(obs - x[:, -1], 0.0, None)

    g = full_alpha.mean(axis=0)  # (M+1,)
    h = full_beta.mean(axis=0)
    p_i = np.arange(0, m + 1) / m
    s = g + h

    o_i = np.divide(h, s, out=p_i.copy(), where=s > 0)  # fall back to p_i (no info) where s==0

    crps_total = float(np.sum(g * p_i ** 2 + h * (1.0 - p_i) ** 2))
    reliability = float(np.sum(s * (p_i - o_i) ** 2))
    crps_potential = float(np.sum(s * o_i * (1.0 - o_i)))

    return CrpsDecomposition(
        crps=crps_total, reliability=reliability, crps_potential=crps_potential,
        n_pairs=n, n_members=m,
    )


# --------------------------------------------------------------------------------------
# Rank histogram
# --------------------------------------------------------------------------------------

@dataclass
class RankHistogram:
    counts: np.ndarray  # length M+1
    chi2_statistic: float
    p_value: float
    n_members: int
    rng_seed: int | None


def rank_histogram(obs: np.ndarray, members: np.ndarray, seed: int | None = 0) -> RankHistogram:
    """Talagrand/rank histogram with a chi-square flatness test. Ties between an
    observation and one or more members are broken at random (Hamill 2001 convention)
    using a seeded RNG so results are reproducible.
    """
    obs = np.asarray(obs, dtype="float64")
    members = np.asarray(members, dtype="float64")
    n, m = members.shape
    rng = np.random.default_rng(seed)

    ranks = np.empty(n, dtype="int64")
    for i in range(n):
        row = members[i]
        n_below = int(np.sum(row < obs[i]))
        n_equal = int(np.sum(row == obs[i]))
        ranks[i] = n_below + (rng.integers(0, n_equal + 1) if n_equal > 0 else 0) + 1

    counts = np.bincount(ranks, minlength=m + 2)[1:m + 2]
    expected = np.full(m + 1, n / (m + 1))
    chi2_stat, p_value = stats.chisquare(counts, expected)

    return RankHistogram(counts=counts, chi2_statistic=float(chi2_stat), p_value=float(p_value),
                          n_members=m, rng_seed=seed)


# --------------------------------------------------------------------------------------
# Brier score / BSS, reliability diagram
# --------------------------------------------------------------------------------------

def exceedance_probability(members: np.ndarray, threshold_mm: float) -> np.ndarray:
    """Ensemble forecast probability that precip_mm >= threshold_mm, per pair."""
    members = np.asarray(members, dtype="float64")
    return np.mean(members >= threshold_mm, axis=1)


def brier_score(obs: np.ndarray, forecast_prob: np.ndarray, threshold_mm: float) -> float:
    obs = np.asarray(obs, dtype="float64")
    outcome = (obs >= threshold_mm).astype("float64")
    return float(np.mean((forecast_prob - outcome) ** 2))


def climatological_probability(obs_climatology: np.ndarray, threshold_mm: float) -> float:
    """Sample climatology built from the observation series itself (plan §7)."""
    obs_climatology = np.asarray(obs_climatology, dtype="float64")
    return float(np.mean(obs_climatology >= threshold_mm))


def brier_skill_score(obs: np.ndarray, forecast_prob: np.ndarray, threshold_mm: float,
                       climatology_prob: float) -> float:
    bs = brier_score(obs, forecast_prob, threshold_mm)
    bs_clim = brier_score(obs, np.full_like(forecast_prob, climatology_prob), threshold_mm)
    if bs_clim == 0:
        return float("nan")
    return 1.0 - bs / bs_clim


@dataclass
class ReliabilityDiagram:
    bin_edges: np.ndarray
    mean_forecast_prob: np.ndarray
    observed_frequency: np.ndarray
    sample_count: np.ndarray


def reliability_diagram(obs: np.ndarray, forecast_prob: np.ndarray, threshold_mm: float,
                         n_bins: int = 10) -> ReliabilityDiagram:
    obs = np.asarray(obs, dtype="float64")
    forecast_prob = np.asarray(forecast_prob, dtype="float64")
    outcome = (obs >= threshold_mm).astype("float64")

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(forecast_prob, bin_edges[1:-1], right=True), 0, n_bins - 1)

    mean_fc = np.full(n_bins, np.nan)
    obs_freq = np.full(n_bins, np.nan)
    counts = np.zeros(n_bins, dtype="int64")
    for b in range(n_bins):
        mask = bin_idx == b
        counts[b] = int(mask.sum())
        if counts[b] > 0:
            mean_fc[b] = forecast_prob[mask].mean()
            obs_freq[b] = outcome[mask].mean()

    return ReliabilityDiagram(bin_edges=bin_edges, mean_forecast_prob=mean_fc,
                               observed_frequency=obs_freq, sample_count=counts)


# --------------------------------------------------------------------------------------
# ROC / AUC
# --------------------------------------------------------------------------------------

@dataclass
class RocCurve:
    thresholds: np.ndarray
    pod: np.ndarray   # probability of detection (hit rate)
    pofd: np.ndarray  # probability of false detection (false alarm rate)
    auc: float


def roc_curve(obs: np.ndarray, forecast_prob: np.ndarray, threshold_mm: float) -> RocCurve:
    obs = np.asarray(obs, dtype="float64")
    forecast_prob = np.asarray(forecast_prob, dtype="float64")
    outcome = (obs >= threshold_mm).astype("bool")

    prob_thresholds = np.unique(forecast_prob)[::-1]
    prob_thresholds = np.concatenate(([1.1], prob_thresholds, [-0.1]))

    n_pos = outcome.sum()
    n_neg = (~outcome).sum()
    pod = np.empty(len(prob_thresholds))
    pofd = np.empty(len(prob_thresholds))
    for i, t in enumerate(prob_thresholds):
        fc_yes = forecast_prob >= t
        hits = np.sum(fc_yes & outcome)
        false_alarms = np.sum(fc_yes & ~outcome)
        pod[i] = hits / n_pos if n_pos > 0 else np.nan
        pofd[i] = false_alarms / n_neg if n_neg > 0 else np.nan

    auc = float(np.trapz(pod, pofd)) if n_pos > 0 and n_neg > 0 else float("nan")
    return RocCurve(thresholds=prob_thresholds, pod=pod, pofd=pofd, auc=auc)


# --------------------------------------------------------------------------------------
# Spread-error ratio, bias, MAE
# --------------------------------------------------------------------------------------

@dataclass
class SpreadError:
    spread: float
    rmse: float
    ratio: float


def spread_error_ratio(obs: np.ndarray, members: np.ndarray) -> SpreadError:
    """Ensemble spread (mean of per-pair ensemble std, sample ddof=1) vs RMSE of the
    ensemble mean. Ratio near 1 indicates a well-calibrated ensemble spread; this uses
    the plain definition (no finite-ensemble-size inflation factor) — noted here so the
    convention is visible, not hidden, per the project's design principles.
    """
    obs = np.asarray(obs, dtype="float64")
    members = np.asarray(members, dtype="float64")
    ens_mean = members.mean(axis=1)
    ens_std = members.std(axis=1, ddof=1) if members.shape[1] > 1 else np.zeros(members.shape[0])
    spread = float(np.mean(ens_std))
    rmse = float(np.sqrt(np.mean((ens_mean - obs) ** 2)))
    ratio = spread / rmse if rmse > 0 else float("nan")
    return SpreadError(spread=spread, rmse=rmse, ratio=ratio)


def bias_mae(obs: np.ndarray, members: np.ndarray) -> tuple[float, float]:
    obs = np.asarray(obs, dtype="float64")
    ens_mean = np.asarray(members, dtype="float64").mean(axis=1)
    bias = float(np.mean(ens_mean - obs))
    mae = float(np.mean(np.abs(ens_mean - obs)))
    return bias, mae
