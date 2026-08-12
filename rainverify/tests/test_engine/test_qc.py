from __future__ import annotations

import pandas as pd

from engine import qc


def _obs(rows):
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_check_range_flags_impossible_values():
    obs = _obs([
        {"station_id": "A", "date": "2026-01-01", "precip_mm": 10.0, "accum_hours": 24},
        {"station_id": "A", "date": "2026-01-02", "precip_mm": 999.0, "accum_hours": 24},
    ])
    result = qc.check_range(obs)
    assert result.flagged_count == 1
    assert result.status == "fail"


def test_check_range_passes_clean_data():
    obs = _obs([{"station_id": "A", "date": "2026-01-01", "precip_mm": 10.0, "accum_hours": 24}])
    result = qc.check_range(obs)
    assert result.status == "pass"
    assert result.flagged_count == 0


def test_check_duplicates():
    obs = _obs([
        {"station_id": "A", "date": "2026-01-01", "precip_mm": 1.0, "accum_hours": 24},
        {"station_id": "A", "date": "2026-01-01", "precip_mm": 1.0, "accum_hours": 24},
        {"station_id": "B", "date": "2026-01-01", "precip_mm": 1.0, "accum_hours": 24},
    ])
    result = qc.check_duplicates(obs)
    assert result.flagged_count == 2
    assert result.status in ("warn", "fail")


def test_check_gaps_counts_missing_days():
    obs = _obs([
        {"station_id": "A", "date": "2026-01-01", "precip_mm": 1.0, "accum_hours": 24},
        {"station_id": "A", "date": "2026-01-03", "precip_mm": 1.0, "accum_hours": 24},  # Jan 2 missing
    ])
    result = qc.check_gaps(obs)
    assert result.flagged_count == 1


def test_check_accumulation_window_fails_on_mismatch():
    obs = _obs([{"station_id": "A", "date": "2026-01-01", "precip_mm": 1.0, "accum_hours": 6}])
    result = qc.check_accumulation_window(obs, forecast_accum_hours=24)
    assert result.status == "fail"
    assert result.flagged_count == 1


def test_check_accumulation_window_passes_on_match():
    obs = _obs([{"station_id": "A", "date": "2026-01-01", "precip_mm": 1.0, "accum_hours": 24}])
    result = qc.check_accumulation_window(obs, forecast_accum_hours=24)
    assert result.status == "pass"
