from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def rail_context(state, active_step: str) -> dict:
    steps = [
        ("data", "Data", True),
        ("checks", "Checks", state.data_ready()),
        ("scores", "Scores", state.checks_ready()),
        ("maps", "Maps & case studies", state.scores_ready()),
        ("report", "Report", state.scores_ready()),
    ]
    return {"rail_steps": steps, "active_step": active_step}
