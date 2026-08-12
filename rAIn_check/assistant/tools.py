"""The fixed tool registry (plan §9): read-only except plots/reports/recipes, which
write to the workspace. Every tool call is logged to runlog.jsonl (plan §9 guardrails).
The `quiz` tool from the plan is dropped per the descoping ladder (§11, item 1).
`fetch_forecasts` (§4.6) is intentionally not implemented tonight — it is the one
network-touching, opt-in tool and the plan itself treats it as lower priority than the
rest of the assistant.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from app.state import WorkspaceState, workspace_subdir
from engine import qc as qc_module
from engine import scores as sc
from engine.bootstrap import moving_block_bootstrap_ci
from engine.manifest import build_manifest, write_manifest
from engine.matching import build_pairs
from ingest.detect import sniff_format
from ingest.load import load_forecast, load_observations
from ingest.recipes import propose_recipe as _propose_recipe

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = {"golden": REPO_ROOT / "data" / "golden", "samples": REPO_ROOT / "data" / "samples"}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_data": {
        "description": "List available forecast and observation files in the golden and demo-pack directories.",
        "args_schema": {},
    },
    "inspect_file": {
        "description": "Read-only preview of a file: columns/dims and a small sample, without loading it fully.",
        "args_schema": {"path": "string"},
    },
    "propose_recipe": {
        "description": "Propose a mapping from a messy observation CSV onto the canonical schema.",
        "args_schema": {"path": "string"},
    },
    "run_qc": {
        "description": "Run the quality-control checks on the current workspace observations.",
        "args_schema": {},
    },
    "compute_scores": {
        "description": "Compute verification scores for the current workspace forecast/observations.",
        "args_schema": {"scores": "array", "thresholds_mm": "array", "leads": "array"},
    },
    "make_plot": {
        "description": "Render one of the standard figures for the current results.",
        "args_schema": {"kind": "string", "params": "object"},
    },
    "get_card": {
        "description": "Retrieve a knowledge card by topic (plain-language explanation, sourced, never improvised).",
        "args_schema": {"topic": "string"},
    },
    "explain_last_error": {
        "description": "Explain the most recent error using the triage rule table, or say if nothing matched.",
        "args_schema": {},
    },
}


def _runlog_path() -> Path:
    return workspace_subdir("logs") / "runlog.jsonl"


def log_tool_call(name: str, args: dict, outcome: str, detail: str = "") -> None:
    entry = {"ts": time.time(), "tool": name, "args": args, "outcome": outcome, "detail": detail[:2000]}
    with open(_runlog_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def tool_list_data(state: WorkspaceState, args: dict) -> dict:
    out = {}
    for label, d in DATA_DIRS.items():
        out[label] = sorted(p.name for p in d.glob("*") if p.is_file()) if d.exists() else []
    return out


def tool_inspect_file(state: WorkspaceState, args: dict) -> dict:
    path = Path(args["path"])
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"'{path}' does not exist.")
    fmt = sniff_format(path)
    if fmt == "csv":
        df = pd.read_csv(path, nrows=5)
        return {"format": fmt, "columns": list(df.columns), "sample_rows": df.astype(str).to_dict("records")}
    ds = load_forecast(path)
    return {"format": fmt, "dims": dict(ds.sizes), "variables": list(ds.data_vars),
            "attrs": {k: str(v) for k, v in ds.attrs.items()}}


def tool_propose_recipe(state: WorkspaceState, args: dict) -> dict:
    path = Path(args["path"])
    if not path.is_absolute():
        path = REPO_ROOT / path
    recipe = _propose_recipe(path)
    state.recipe = recipe
    state.recipe_needs_review = any(n.startswith("ASK") for n in recipe.notes)
    return recipe.to_json()


def tool_run_qc(state: WorkspaceState, args: dict) -> dict:
    if state.obs is None or state.forecast is None:
        raise ValueError("No data loaded yet — complete the Data step first.")
    results = qc_module.run_all_checks(state.obs, int(state.forecast.attrs["accumulation_hours"]))
    state.qc_results = results
    return {k: v.to_dict() for k, v in results.items()}


def tool_compute_scores(state: WorkspaceState, args: dict) -> dict:
    if state.obs is None or state.forecast is None:
        raise ValueError("No data loaded yet — complete the Data step first.")
    thresholds = args.get("thresholds_mm", [1, 5, 20, 50])
    leads = args.get("leads", [1])
    requested = set(args.get("scores", ["crps", "bss", "rank_histogram", "reliability", "roc", "spread_error", "bias_mae"]))

    results: dict[str, Any] = {}
    for lead in leads:
        pairs = build_pairs(state.obs, state.forecast, lead_day=int(lead))
        if len(pairs) == 0:
            results[str(lead)] = {"error": "no forecast-observation pairs for this lead"}
            continue
        members = np.stack(pairs["members"].to_numpy())
        y = pairs["obs_mm"].to_numpy()
        lead_result: dict[str, Any] = {"n_pairs": len(pairs)}

        if "crps" in requested:
            crps = sc.crps_ensemble(y, members)
            lead_result["crps"] = moving_block_bootstrap_ci(crps, pairs["date"]).__dict__
        if "bias_mae" in requested:
            bias, mae = sc.bias_mae(y, members)
            lead_result["bias"] = bias
            lead_result["mae"] = mae
        if "spread_error" in requested:
            lead_result["spread_error"] = sc.spread_error_ratio(y, members).__dict__
        if "rank_histogram" in requested:
            rh = sc.rank_histogram(y, members)
            lead_result["rank_histogram"] = {"counts": rh.counts.tolist(), "chi2": rh.chi2_statistic, "p_value": rh.p_value}
        if "bss" in requested or "reliability" in requested or "roc" in requested:
            lead_result["thresholds"] = {}
            for t in thresholds:
                prob = sc.exceedance_probability(members, t)
                clim_p = sc.climatological_probability(state.obs["precip_mm"].to_numpy(), t)
                t_result: dict[str, Any] = {}
                if "bss" in requested:
                    bs_err = (prob - (y >= t).astype(float)) ** 2
                    bss_ci = moving_block_bootstrap_ci(bs_err, pairs["date"])
                    t_result["brier_score"] = sc.brier_score(y, prob, t)
                    t_result["bss"] = sc.brier_skill_score(y, prob, t, clim_p)
                    t_result["climatology_prob"] = clim_p
                if "reliability" in requested:
                    rd = sc.reliability_diagram(y, prob, t)
                    t_result["reliability"] = {"mean_forecast_prob": rd.mean_forecast_prob.tolist(),
                                                "observed_frequency": rd.observed_frequency.tolist(),
                                                "sample_count": rd.sample_count.tolist()}
                if "roc" in requested:
                    roc = sc.roc_curve(y, prob, t)
                    t_result["auc"] = roc.auc
                lead_result["thresholds"][str(t)] = t_result
        results[str(lead)] = lead_result

    state.score_results = results
    state.score_params = {"scores": sorted(requested), "thresholds": thresholds, "leads": leads}
    return results


def tool_make_plot(state: WorkspaceState, args: dict) -> dict:
    # The actual figure objects are built by app/plots.py and served through the app's
    # own routes (a matplotlib Figure isn't JSON-serialisable); this tool just confirms
    # what would be plotted so the assistant can propose it before the user clicks.
    kind = args.get("kind")
    valid_kinds = {"crps_by_lead", "rank_histogram", "reliability", "roc", "bss_by_threshold",
                   "map_ensemble_mean", "map_exceedance", "map_postage_stamp"}
    if kind not in valid_kinds:
        raise ValueError(f"Unknown plot kind '{kind}'. Valid kinds: {sorted(valid_kinds)}")
    return {"kind": kind, "params": args.get("params", {}), "status": "ready to render — open the relevant step"}


def tool_get_card(state: WorkspaceState, args: dict) -> dict:
    from . import cards as cards_module
    topic = args["topic"]
    card = cards_module.get_card(topic)
    if card is None:
        return {"found": False, "topic": topic, "available": cards_module.list_topics()}
    return {"found": True, "topic": topic, "content": card}


def tool_explain_last_error(state: WorkspaceState, args: dict) -> dict:
    from . import triage_rules
    last = triage_rules.get_last_error()
    if last is None:
        return {"found": False, "message": "No recent error recorded."}
    diagnosis = triage_rules.classify(last)
    return {"found": True, "raw_error": last, "diagnosis": diagnosis}


TOOL_IMPLEMENTATIONS: dict[str, Callable[[WorkspaceState, dict], dict]] = {
    "list_data": tool_list_data,
    "inspect_file": tool_inspect_file,
    "propose_recipe": tool_propose_recipe,
    "run_qc": tool_run_qc,
    "compute_scores": tool_compute_scores,
    "make_plot": tool_make_plot,
    "get_card": tool_get_card,
    "explain_last_error": tool_explain_last_error,
}


def call_tool(name: str, args: dict, state: WorkspaceState) -> dict:
    if name not in TOOL_IMPLEMENTATIONS:
        raise ValueError(f"Unknown tool '{name}'. Registered tools: {sorted(TOOL_IMPLEMENTATIONS)}")
    try:
        result = TOOL_IMPLEMENTATIONS[name](state, args)
        log_tool_call(name, args, "success")
        return result
    except Exception as exc:
        log_tool_call(name, args, "error", str(exc))
        from . import triage_rules
        triage_rules.record_error(str(exc))
        raise
