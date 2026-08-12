"""Moving-block bootstrap for confidence intervals (plan §7): block length 5 days,
1,000 resamples by default. Warns whenever a stratum has fewer than 30 pairs.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_PAIRS_WARNING = 30


@dataclass
class BootstrapResult:
    estimate: float
    ci_low: float
    ci_high: float
    n_pairs: int
    n_resamples: int
    block_length: int
    small_sample_warning: bool


def _moving_block_indices(n: int, block_length: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = int(np.ceil(n / block_length))
    starts = rng.integers(0, max(n - block_length + 1, 1), size=n_blocks)
    idx = np.concatenate([np.arange(s, s + block_length) for s in starts])
    return np.clip(idx[:n], 0, n - 1)


def moving_block_bootstrap_ci(
    values: np.ndarray,
    dates: pd.Series | np.ndarray,
    statistic_fn=np.mean,
    block_length: int = 5,
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int | None = 0,
) -> BootstrapResult:
    """`values` is one number per forecast-observation pair (e.g. per-pair CRPS or
    per-pair squared Brier error), ordered by `dates` ascending. Resamples blocks of
    consecutive days with replacement, recomputes `statistic_fn` each time.
    """
    order = np.argsort(np.asarray(dates))
    values = np.asarray(values, dtype="float64")[order]
    n = len(values)

    point_estimate = float(statistic_fn(values))
    if n == 0:
        return BootstrapResult(float("nan"), float("nan"), float("nan"), 0, n_resamples, block_length, True)

    rng = np.random.default_rng(seed)
    resample_stats = np.empty(n_resamples)
    for r in range(n_resamples):
        idx = _moving_block_indices(n, block_length, rng)
        resample_stats[r] = statistic_fn(values[idx])

    alpha = 1.0 - ci
    ci_low, ci_high = np.percentile(resample_stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])

    return BootstrapResult(
        estimate=point_estimate,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        n_pairs=n,
        n_resamples=n_resamples,
        block_length=block_length,
        small_sample_warning=n < MIN_PAIRS_WARNING,
    )
