from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from app import plots
from app.deps import rail_context, templates
from app.state import get_state

router = APIRouter()


@router.get("/maps")
def maps_page(request: Request):
    state = get_state()
    if not state.scores_ready():
        return RedirectResponse("/scores", status_code=303)

    ref_times = [pd.Timestamp(t) for t in state.forecast["forecast_reference_time"].values]
    if state.map_ref_time is None:
        state.map_ref_time = str(ref_times[len(ref_times) // 2].date())
    if state.map_lead is None:
        state.map_lead = int(state.forecast["lead_day"].values[0])

    ctx = {
        "request": request, "assistant_model": state.assistant_model,
        "chat_history": state.chat_history, "state": state,
        "ref_time_options": [str(t.date()) for t in ref_times],
        "lead_options": [int(x) for x in state.forecast["lead_day"].values],
        **rail_context(state, "maps"),
    }
    return templates.TemplateResponse("maps.html", ctx)


@router.post("/maps/select")
def maps_select(ref_time: str = Form(...), lead: int = Form(...), threshold: float = Form(5.0)):
    state = get_state()
    state.map_ref_time = ref_time
    state.map_lead = lead
    state.map_threshold = threshold
    return RedirectResponse("/maps", status_code=303)


@router.get("/maps/plot/{kind}")
def maps_plot(kind: str):
    state = get_state()
    ref_time = pd.Timestamp(state.map_ref_time)
    lead = state.map_lead

    if kind == "mean":
        fig = plots.map_ensemble_mean(state.forecast, ref_time, lead, obs=state.obs)
    elif kind == "exceedance":
        fig = plots.map_exceedance_probability(state.forecast, ref_time, lead, state.map_threshold, obs=state.obs)
    elif kind == "postage_stamp":
        fig = plots.map_postage_stamp(state.forecast, ref_time, lead)
    else:
        return Response(status_code=404)

    buf = io.BytesIO()
    plots.save_png(fig, buf)
    return Response(content=buf.getvalue(), media_type="image/png")
