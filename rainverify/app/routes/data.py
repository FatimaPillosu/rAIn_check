from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import rail_context, templates
from app.state import get_state
from ingest.detect import sniff_format
from ingest.load import load_forecast
from ingest.recipes import Recipe, apply_recipe, propose_recipe
from ingest.readers.tabular import read_observations_csv
from ingest.schema import SchemaError, OBS_COLUMNS

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRS = {"golden": REPO_ROOT / "data" / "golden", "samples": REPO_ROOT / "data" / "samples"}


def _available_files() -> dict[str, list[str]]:
    out = {}
    for label, d in DATA_DIRS.items():
        out[label] = sorted(p.name for p in d.glob("*") if p.is_file() and not p.name.endswith(".md"))
    return out


def _resolve(label_and_name: str) -> Path:
    label, name = label_and_name.split("/", 1)
    return DATA_DIRS[label] / name


@router.get("/data")
def data_page(request: Request):
    state = get_state()
    ctx = {
        "request": request, "assistant_model": state.assistant_model,
        "chat_history": state.chat_history, "available": _available_files(),
        "state": state,
        **rail_context(state, "data"),
    }
    if state.forecast is not None:
        fc = state.forecast
        ctx["forecast_summary"] = {
            "leads": [int(x) for x in fc["lead_day"].values],
            "members": int(fc.sizes["member"]),
            "period": (str(pd.Timestamp(fc["forecast_reference_time"].values.min()).date()),
                       str(pd.Timestamp(fc["forecast_reference_time"].values.max()).date())),
            "grid": f"{fc.sizes['lat']} x {fc.sizes['lon']}",
        }
    if state.obs is not None:
        ctx["obs_summary"] = {
            "stations": state.obs["station_id"].nunique(),
            "rows": len(state.obs),
            "period": (str(state.obs["date"].min().date()), str(state.obs["date"].max().date())),
        }
    return templates.TemplateResponse("data.html", ctx)


@router.post("/data/load")
def data_load(request: Request, forecast_choice: str = Form(...), obs_choice: str = Form(...)):
    state = get_state()
    state.reset_downstream_of_data()
    error = None

    forecast_path = _resolve(forecast_choice)
    obs_path = _resolve(obs_choice)
    try:
        state.forecast = load_forecast(forecast_path)
        state.forecast_path = forecast_path
    except Exception as exc:
        error = f"Could not load forecast: {exc}"

    if error is None:
        try:
            state.obs = read_observations_csv(obs_path)
            state.obs_path = obs_path
            state.recipe = None
            state.recipe_needs_review = False
        except SchemaError:
            state.obs_path = obs_path
            state.recipe = propose_recipe(obs_path)
            state.recipe_needs_review = True

    ctx = {
        "request": request, "assistant_model": state.assistant_model,
        "chat_history": state.chat_history, "available": _available_files(),
        "state": state, "error": error,
        **rail_context(state, "data"),
    }
    if state.recipe_needs_review:
        raw_columns = list(pd.read_csv(obs_path, nrows=1).columns)
        ctx["recipe"] = state.recipe
        ctx["raw_columns"] = raw_columns
        ctx["canonical_columns"] = list(OBS_COLUMNS)
        return templates.TemplateResponse("partials/recipe_review.html", ctx)

    return RedirectResponse("/data", status_code=303)


@router.post("/data/apply_recipe")
async def data_apply_recipe(request: Request):
    state = get_state()
    form = await request.form()
    column_map = {}
    constant_fill = {}
    for canonical in OBS_COLUMNS:
        raw = form.get(f"map__{canonical}")
        if raw and raw != "__none__":
            column_map[raw] = canonical
    date_format = form.get("date_format") or None
    try:
        precip_unit_factor = float(form.get("precip_unit_factor") or 1.0)
    except ValueError:
        precip_unit_factor = 1.0

    recipe = Recipe(column_map=column_map, constant_fill=constant_fill,
                     date_format=date_format, precip_unit_factor=precip_unit_factor)
    for canonical, default in (("accum_hours", 24), ("qc_flag", 0)):
        if canonical not in column_map.values():
            recipe.constant_fill[canonical] = default

    df_raw = pd.read_csv(state.obs_path)
    state.obs = apply_recipe(df_raw, recipe)
    state.recipe = recipe
    state.recipe_needs_review = False

    return RedirectResponse("/data", status_code=303)
