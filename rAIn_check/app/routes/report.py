from __future__ import annotations

import base64
import io
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, RedirectResponse

from app import plots
from app.deps import rail_context, templates
from app.state import get_state, workspace_subdir
from engine.manifest import build_manifest, write_manifest

router = APIRouter()


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    plots.save_png(fig, buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


@router.get("/report")
def report_page(request: Request):
    state = get_state()
    if not state.scores_ready():
        return RedirectResponse("/scores", status_code=303)
    ctx = {
        "request": request, "assistant_model": state.assistant_model,
        "chat_history": state.chat_history, "state": state,
        **rail_context(state, "report"),
    }
    return templates.TemplateResponse("report.html", ctx)


@router.post("/report/generate")
def report_generate(interpretation: str = Form("")):
    state = get_state()

    manifest = build_manifest(
        [state.forecast_path, state.obs_path],
        parameters={"score_params": state.score_params, "map": {
            "ref_time": state.map_ref_time, "lead": state.map_lead, "threshold": state.map_threshold,
        }},
    )

    figures: dict[str, str] = {}
    for lead, r in state.score_results.items():
        figures[f"crps_lead{lead}"] = _fig_to_base64(plots.plot_crps_by_lead({lead: r["crps_bootstrap"]}))
        figures[f"rank_lead{lead}"] = _fig_to_base64(plots.plot_rank_histogram(r["rank_histogram"]))
        bss_by_t = {t: v["bss"] for t, v in r["thresholds"].items()}
        figures[f"bss_lead{lead}"] = _fig_to_base64(plots.plot_bss_by_threshold(bss_by_t))

    if state.map_ref_time:
        ref_time = pd.Timestamp(state.map_ref_time)
        figures["map_mean"] = _fig_to_base64(plots.map_ensemble_mean(state.forecast, ref_time, state.map_lead, obs=state.obs))
        figures["map_exceedance"] = _fig_to_base64(
            plots.map_exceedance_probability(state.forecast, ref_time, state.map_lead, state.map_threshold, obs=state.obs))

    ctx = {
        "request": None, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest, "results": state.score_results, "figures": figures,
        "interpretation": interpretation,
    }
    html = templates.get_template("report_standalone.html").render(ctx)

    reports_dir = workspace_subdir("reports")
    out_path = reports_dir / f"{manifest['run_id']}.html"
    out_path.write_text(html, encoding="utf-8")
    write_manifest(manifest, reports_dir / f"{manifest['run_id']}.manifest.json")
    state.run_manifest = manifest

    return FileResponse(out_path, media_type="text/html", filename=out_path.name)
