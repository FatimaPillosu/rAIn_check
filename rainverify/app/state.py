"""In-memory workspace state for this single-user, single-machine prototype (plan §6:
"workspace/ directory created beside the installation on first run"). No database, no
multi-user auth — this app is one FastAPI process serving one person's browser tab.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

from ingest.recipes import Recipe

WORKSPACE_DIR = Path(__file__).resolve().parents[1] / "workspace"


def _default_assistant_model() -> str:
    try:
        from assistant.config import load_assistant_config
        config = load_assistant_config()
        model_key = config.active_model
        if model_key != "none" and model_key in config.models and config.models[model_key].available():
            return model_key
    except Exception:
        pass
    return "none"


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    text: str
    proposal: dict | None = None  # pending tool-call proposal awaiting approve/modify/skip


@dataclass
class WorkspaceState:
    forecast_path: Path | None = None
    forecast: xr.Dataset | None = None

    obs_path: Path | None = None
    obs_raw: pd.DataFrame | None = None
    recipe: Recipe | None = None
    recipe_needs_review: bool = False
    obs: pd.DataFrame | None = None

    qc_results: dict[str, Any] | None = None

    score_params: dict[str, Any] = field(default_factory=lambda: {
        "scores": ["crps", "bss", "rank_histogram", "reliability", "roc", "spread_error", "bias_mae"],
        "thresholds": [1, 5, 20, 50],
        "leads": [1],
    })
    score_results: dict[str, Any] | None = None

    map_ref_time: str | None = None
    map_lead: int | None = None
    map_threshold: float = 5.0

    chat_history: list[ChatMessage] = field(default_factory=list)
    assistant_model: str = field(default_factory=lambda: _default_assistant_model())  # "none" | "gemma" | "ministral"

    run_manifest: dict[str, Any] | None = None

    def data_ready(self) -> bool:
        return self.forecast is not None and self.obs is not None

    def checks_ready(self) -> bool:
        return self.qc_results is not None

    def scores_ready(self) -> bool:
        return self.score_results is not None

    def reset_downstream_of_data(self) -> None:
        self.qc_results = None
        self.score_results = None


_state = WorkspaceState()


def get_state() -> WorkspaceState:
    return _state


def workspace_subdir(name: str) -> Path:
    d = WORKSPACE_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d
