from __future__ import annotations

import numpy as np
import pandas as pd

from engine.bootstrap import moving_block_bootstrap_ci


def test_bootstrap_ci_contains_point_estimate():
    rng = np.random.default_rng(3)
    values = rng.normal(5.0, 1.0, size=100)
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    result = moving_block_bootstrap_ci(values, dates, n_resamples=200, seed=1)
    assert result.ci_low <= result.estimate <= result.ci_high


def test_bootstrap_flags_small_sample():
    values = np.array([1.0, 2.0, 3.0])
    dates = pd.date_range("2026-01-01", periods=3, freq="D")
    result = moving_block_bootstrap_ci(values, dates, n_resamples=50, seed=1)
    assert result.small_sample_warning is True


def test_bootstrap_no_warning_for_large_sample():
    rng = np.random.default_rng(4)
    values = rng.normal(size=40)
    dates = pd.date_range("2026-01-01", periods=40, freq="D")
    result = moving_block_bootstrap_ci(values, dates, n_resamples=50, seed=1)
    assert result.small_sample_warning is False
