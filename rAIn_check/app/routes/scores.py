from __future__ import annotations

import io

import numpy as np
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from app import plots
from app.deps import rail_context, templates
from app.state import get_state
from engine import scores as sc
from engine.bootstrap import moving_block_bootstrap_ci
from engine.matching import build_pairs

router = APIRouter()

DEFAULT_THRESHOLDS = [1, 5, 20, 50]


def _compute(state, leads: list[int], thresholds: list[float]) -> dict:
    results = {}
    for lead in leads:
        pairs = build_pairs(state.obs, state.forecast, lead_day=lead)
        if len(pairs) == 0:
            continue
        members = np.stack(pairs["members"].to_numpy())
        y = pairs["obs_mm"].to_numpy()

        crps_vals = sc.crps_ensemble(y, members)
        lead_result = {
            "pairs": pairs, "members": members, "y": y,
            "crps_bootstrap": moving_block_bootstrap_ci(crps_vals, pairs["date"]),
            "rank_histogram": sc.rank_histogram(y, members),
            "spread_error": sc.spread_error_ratio(y, members),
        }
        lead_result["bias"], lead_result["mae"] = sc.bias_mae(y, members)

        thr_results = {}
        for t in thresholds:
            prob = sc.exceedance_probability(members, t)
            clim_p = sc.climatological_probability(state.obs["precip_mm"].to_numpy(), t)
            thr_results[t] = {
                "brier_score": sc.brier_score(y, prob, t),
                "bss": sc.brier_skill_score(y, prob, t, clim_p),
                "climatology_prob": clim_p,
                "reliability": sc.reliability_diagram(y, prob, t),
                "roc": sc.roc_curve(y, prob, t),
            }
        lead_result["thresholds"] = thr_results
        results[lead] = lead_result
    return results


@router.get("/scores")
def scores_page(request: Request):
    state = get_state()
    if not state.checks_ready():
        return RedirectResponse("/checks", status_code=303)

    ctx = {
        "request": request, "assistant_model": state.assistant_model,
        "chat_history": state.chat_history, "state": state,
        "available_leads": [int(x) for x in state.forecast["lead_day"].values],
        "default_thresholds": DEFAULT_THRESHOLDS,
        "results": state.score_results,
        **rail_context(state, "scores"),
    }
    return templates.TemplateResponse("scores.html", ctx)


@router.post("/scores/compute")
def scores_compute(request: Request, leads: list[int] = Form(...), thresholds: str = Form(...)):
    state = get_state()
    threshold_list = [float(t.strip()) for t in thresholds.split(",") if t.strip()]
    state.score_results = _compute(state, leads, threshold_list)
    state.score_params = {"leads": leads, "thresholds": threshold_list}
    return RedirectResponse("/scores", status_code=303)


@router.get("/scores/plot/{kind}")
def scores_plot(kind: str, lead: int, threshold: float | None = None):
    state = get_state()
    result = state.score_results[lead]

    if kind == "crps":
        fig = plots.plot_crps_by_lead({lead: result["crps_bootstrap"]})
    elif kind == "rank_histogram":
        fig = plots.plot_rank_histogram(result["rank_histogram"])
    elif kind == "reliability":
        fig = plots.plot_reliability_diagram(result["thresholds"][threshold]["reliability"], threshold)
    elif kind == "roc":
        fig = plots.plot_roc_curve(result["thresholds"][threshold]["roc"], threshold)
    elif kind == "bss":
        bss_by_t = {t: v["bss"] for t, v in result["thresholds"].items()}
        fig = plots.plot_bss_by_threshold(bss_by_t)
    elif kind == "spread_error":
        se = result["spread_error"]
        fig = plots.plot_spread_error_by_lead({lead: se.spread}, {lead: se.rmse})
    else:
        return Response(status_code=404)

    buf = io.BytesIO()
    plots.save_png(fig, buf)
    return Response(content=buf.getvalue(), media_type="image/png")
