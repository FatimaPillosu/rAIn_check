"""Quality control checks (plan §8.1): physical range, spikes, duplicates, gap counts,
and the accumulation-window check. Each returns a QCResult with a pass/warn/fail badge.
Warnings inform but never block progression through the GUI rail (plan §8.3, Figure 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

PHYSICAL_MIN_MM = 0.0
PHYSICAL_MAX_MM = 500.0
SPIKE_MAD_MULTIPLIER = 6.0
WARN_FRACTION = 0.01  # >1% of rows flagged -> warn
FAIL_FRACTION = 0.05  # >5% of rows flagged -> fail (range check only)


@dataclass
class QCResult:
    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    flagged_count: int
    total_count: int
    details: pd.DataFrame = field(default_factory=pd.DataFrame)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "flagged_count": self.flagged_count,
            "total_count": self.total_count,
        }


def _badge(flagged: int, total: int, fail_fraction: float | None) -> str:
    if total == 0 or flagged == 0:
        return "pass"
    frac = flagged / total
    if fail_fraction is not None and frac > fail_fraction:
        return "fail"
    if frac > WARN_FRACTION or flagged > 0:
        return "warn"
    return "pass"


def check_range(obs: pd.DataFrame, min_mm: float = PHYSICAL_MIN_MM, max_mm: float = PHYSICAL_MAX_MM) -> QCResult:
    bad = obs[(obs["precip_mm"] < min_mm) | (obs["precip_mm"] > max_mm)]
    status = _badge(len(bad), len(obs), FAIL_FRACTION)
    return QCResult(
        name="Physical range",
        status=status,
        message=f"{len(bad)} of {len(obs)} rows outside the physically plausible range [{min_mm}, {max_mm}] mm/24h.",
        flagged_count=len(bad),
        total_count=len(obs),
        details=bad,
    )


def check_duplicates(obs: pd.DataFrame) -> QCResult:
    dup_mask = obs.duplicated(subset=["station_id", "date"], keep=False)
    bad = obs[dup_mask]
    status = _badge(len(bad), len(obs), None)
    return QCResult(
        name="Duplicates",
        status=status,
        message=f"{dup_mask.sum()} rows share a (station, date) with another row.",
        flagged_count=len(bad),
        total_count=len(obs),
        details=bad,
    )


def check_spikes(obs: pd.DataFrame, mad_multiplier: float = SPIKE_MAD_MULTIPLIER) -> QCResult:
    """Flags a value as a spike if it is more than `mad_multiplier` robust deviations
    from that station's own median (median absolute deviation, scaled to be
    comparable to a standard deviation for a normal distribution: MAD * 1.4826).
    A simple, explainable rule — not a statistical model of rainfall extremes.
    """
    flagged_idx = []
    for station_id, g in obs.groupby("station_id"):
        vals = g["precip_mm"].to_numpy()
        med = np.median(vals)
        mad = np.median(np.abs(vals - med)) * 1.4826
        if mad == 0:
            continue
        z = np.abs(vals - med) / mad
        flagged_idx.extend(g.index[z > mad_multiplier].tolist())
    bad = obs.loc[flagged_idx]
    status = _badge(len(bad), len(obs), FAIL_FRACTION)
    return QCResult(
        name="Spikes",
        status=status,
        message=f"{len(bad)} of {len(obs)} rows are more than {mad_multiplier}x the station's robust "
                f"deviation from its own median.",
        flagged_count=len(bad),
        total_count=len(obs),
        details=bad,
    )


def check_gaps(obs: pd.DataFrame, expected_freq: str = "D") -> QCResult:
    rows = []
    total_missing = 0
    total_expected = 0
    for station_id, g in obs.groupby("station_id"):
        dates = g["date"].sort_values()
        if len(dates) < 2:
            continue
        full_range = pd.date_range(dates.min(), dates.max(), freq=expected_freq)
        missing = full_range.difference(dates)
        total_missing += len(missing)
        total_expected += len(full_range)
        if len(missing):
            rows.append({"station_id": station_id, "missing_days": len(missing), "expected_days": len(full_range)})
    details = pd.DataFrame(rows)
    status = _badge(total_missing, max(total_expected, 1), FAIL_FRACTION)
    return QCResult(
        name="Gaps",
        status=status,
        message=f"{total_missing} missing daily reports across all stations "
                f"({total_expected} expected day-station combinations).",
        flagged_count=total_missing,
        total_count=total_expected,
        details=details,
    )


def check_accumulation_window(obs: pd.DataFrame, forecast_accum_hours: int) -> QCResult:
    bad = obs[obs["accum_hours"] != forecast_accum_hours]
    status = "fail" if len(bad) > 0 else "pass"
    return QCResult(
        name="Accumulation window",
        status=status,
        message=(
            f"All observations use a {forecast_accum_hours}h accumulation window, matching the forecast."
            if status == "pass"
            else f"{len(bad)} observations use an accumulation window other than the forecast's "
                 f"{forecast_accum_hours}h. Scores cannot be computed for these rows until resolved."
        ),
        flagged_count=len(bad),
        total_count=len(obs),
        details=bad,
    )


def run_all_checks(obs: pd.DataFrame, forecast_accum_hours: int) -> dict[str, QCResult]:
    return {
        "range": check_range(obs),
        "spikes": check_spikes(obs),
        "duplicates": check_duplicates(obs),
        "gaps": check_gaps(obs),
        "accumulation_window": check_accumulation_window(obs, forecast_accum_hours),
    }
