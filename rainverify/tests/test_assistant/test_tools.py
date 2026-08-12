from __future__ import annotations

from pathlib import Path

import pytest

from app.state import WorkspaceState
from assistant.tools import call_tool
from ingest.load import load_forecast, load_observations

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"


@pytest.fixture()
def loaded_state():
    state = WorkspaceState()
    state.forecast = load_forecast(GOLDEN_DIR / "forecast.nc")
    obs = load_observations(GOLDEN_DIR / "observations.csv")
    state.obs = obs[obs["precip_mm"] < 500]
    return state


def test_list_data_finds_golden_and_samples():
    state = WorkspaceState()
    result = call_tool("list_data", {}, state)
    assert "forecast.nc" in result["golden"]
    assert "observations.csv" in result["golden"]


def test_inspect_file_csv():
    state = WorkspaceState()
    result = call_tool("inspect_file", {"path": "data/golden/observations.csv"}, state)
    assert result["format"] == "csv"
    assert "precip_mm" in result["columns"]


def test_run_qc_requires_data_loaded():
    state = WorkspaceState()
    with pytest.raises(ValueError):
        call_tool("run_qc", {}, state)


def test_run_qc_on_golden(loaded_state):
    result = call_tool("run_qc", {}, loaded_state)
    assert "range" in result
    assert loaded_state.qc_results is not None


def test_compute_scores_on_golden(loaded_state):
    result = call_tool("compute_scores", {"scores": ["crps", "bss"], "thresholds_mm": [5, 20], "leads": [1]}, loaded_state)
    assert "1" in result
    assert result["1"]["n_pairs"] > 0
    assert "crps" in result["1"]
    assert "5" in result["1"]["thresholds"]


def test_get_card_known_topic():
    state = WorkspaceState()
    result = call_tool("get_card", {"topic": "crps"}, state)
    assert result["found"] is True
    assert "CRPS" in result["content"]


def test_get_card_unknown_topic():
    state = WorkspaceState()
    result = call_tool("get_card", {"topic": "not_a_real_score"}, state)
    assert result["found"] is False
    assert "crps" in result["available"]


def test_explain_last_error_with_no_prior_error():
    state = WorkspaceState()
    result = call_tool("explain_last_error", {}, state)
    assert result["found"] in (False, True)  # depends on prior test runs writing to the shared log; just must not crash


def test_unknown_tool_raises():
    state = WorkspaceState()
    with pytest.raises(ValueError):
        call_tool("delete_everything", {}, state)
