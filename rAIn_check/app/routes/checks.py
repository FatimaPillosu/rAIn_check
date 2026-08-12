from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.deps import rail_context, templates
from app.state import get_state
from engine import qc as qc_module

router = APIRouter()


@router.get("/checks")
def checks_page(request: Request):
    state = get_state()
    if not state.data_ready():
        return RedirectResponse("/data", status_code=303)

    if state.qc_results is None:
        state.qc_results = qc_module.run_all_checks(state.obs, int(state.forecast.attrs["accumulation_hours"]))

    ctx = {
        "request": request, "assistant_model": state.assistant_model,
        "chat_history": state.chat_history, "state": state,
        "checks": {k: v.to_dict() for k, v in state.qc_results.items()},
        **rail_context(state, "checks"),
    }
    return templates.TemplateResponse("checks.html", ctx)
