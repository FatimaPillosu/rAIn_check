"""Conversation policy (plan §9): the assistant proposes exactly one action per turn
with a one-sentence reason; the UI renders Approve/Modify/Skip; after execution the
engine's summary is shown verbatim, then the assistant explains it in <=120 words and
asks one interpretation question back.

Capability ladder (plan §9): L3 (a model is loaded) gets free-form propose/explain text
constrained by tool calls and cards; L1 (no model — the default until the user picks one,
and the fallback if a model fails to load) uses fixed, deterministic guidance so the dock
is never empty, per the plan's "the assistant is never switched off" principle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.state import WorkspaceState
from .adapter import ModelAdapter, ModelLoadError, TextReply, ToolCall
from .tools import TOOL_SCHEMAS, call_tool

GUARDRAIL_SYSTEM_PROMPT = (
    "You are the rAIn_check verification assistant. You never invent a score, formula, "
    "or number from memory — you only call tools (which run the deterministic engine) "
    "and summarise the knowledge cards the get_card tool returns. If asked to explain a "
    "verification concept, call get_card first and summarise only what it says; if no "
    "card matches, say so plainly rather than improvising. Propose exactly one tool call "
    "per turn. Available tools:\n"
    + "\n".join(f"- {name}: {spec['description']}" for name, spec in TOOL_SCHEMAS.items())
)


@dataclass
class Proposal:
    reason: str
    tool: str | None
    args: dict[str, Any]
    is_free_text: bool = False
    text: str = ""


# --------------------------------------------------------------------------------------
# L1: deterministic fallback (no model loaded)
# --------------------------------------------------------------------------------------

_L1_KEYWORDS: list[tuple[tuple[str, ...], str, dict]] = [
    (("what data", "which files", "list data", "available data"), "list_data", {}),
    (("quality", "qc", "check the data", "any issues"), "run_qc", {}),
    (("score", "crps", "bss", "brier", "verify", "verification"), "compute_scores",
     {"scores": ["crps", "bss"], "thresholds_mm": [5, 20], "leads": [1]}),
    (("recipe", "messy", "doesn't match", "map the columns"), "propose_recipe", {}),
    (("error", "failed", "went wrong", "what happened"), "explain_last_error", {}),
]

_L1_CARD_TOPICS = ["crps", "rank_histogram", "brier_bss", "reliability_diagram", "roc_auc",
                    "spread_error", "climatology_reference", "double_penalty"]


def _l1_propose(state: WorkspaceState, user_message: str) -> Proposal:
    lowered = user_message.lower()
    for topic in _L1_CARD_TOPICS:
        if topic.replace("_", " ") in lowered or topic in lowered:
            return Proposal(reason=f"This sounds like a question about {topic.replace('_', ' ')}.",
                             tool="get_card", args={"topic": topic})
    for keywords, tool, args in _L1_KEYWORDS:
        if any(k in lowered for k in keywords):
            return Proposal(reason=f"This looks like a job for '{tool}'.", tool=tool, args=args)
    return Proposal(
        reason="No model is loaded, so I can only match fixed keywords — I didn't recognise this one.",
        tool=None, args={}, is_free_text=True,
        text=("I'm running in deterministic (no-model) mode right now, so I can only respond to a "
              "fixed set of requests: data/files, quality checks, scores, recipes, errors, or a "
              "named verification concept (CRPS, rank histogram, Brier/BSS, reliability, ROC, "
              "spread-error, climatology, double penalty). Try rephrasing, or switch on a model "
              "in the dock for free-form conversation."),
    )


def _l1_explain(tool: str, result: dict) -> str:
    if tool == "get_card":
        if result.get("found"):
            first_line = next((l for l in result["content"].splitlines() if l.strip()), "")
            return f"Source: {first_line.lstrip('# ').strip()} knowledge card. Full text is shown above."
        return f"No knowledge card matches '{result.get('topic')}'. Available: {', '.join(result.get('available', []))}."
    if tool == "run_qc":
        bad = [k for k, v in result.items() if v.get("status") != "pass"]
        return f"{len(bad)} of {len(result)} checks raised a warning or fail: {', '.join(bad) or 'none'}."
    if tool == "compute_scores":
        return "Scores computed for the requested leads/thresholds — see the tables and figures."
    if tool == "list_data":
        return "Listed the files currently available in the golden and demo-pack directories."
    if tool == "propose_recipe":
        n_ask = sum(1 for n in result.get("notes", []) if n.startswith("ASK"))
        return f"Proposed a column mapping with {n_ask} item(s) needing your confirmation."
    return "Done."


# --------------------------------------------------------------------------------------
# L3: model-driven (adapter loaded)
# --------------------------------------------------------------------------------------

def _l3_propose(adapter: ModelAdapter, state: WorkspaceState, user_message: str, history: list[dict]) -> Proposal:
    messages = [{"role": "system", "content": GUARDRAIL_SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_message},
    ]
    try:
        result = adapter.generate(messages, use_grammar=True)
    except ModelLoadError:
        return _l1_propose(state, user_message)

    if isinstance(result, ToolCall):
        return Proposal(reason=f"Proposing to call '{result.tool}'.", tool=result.tool, args=result.args)
    return Proposal(reason="", tool=None, args={}, is_free_text=True, text=result.text)


EXPLAIN_SYSTEM_PROMPT = (
    "You are the rAIn_check verification assistant, now in explanation mode: a tool has "
    "already run and you are narrating its result in plain English. Do NOT propose or "
    "format another tool call of any kind (no JSON, no <tool_call> tags, no function "
    "syntax) — write ordinary prose only. Never state a score, formula, or number that "
    "isn't in the result given to you. If the result includes a knowledge-card 'content' "
    "field, summarise only that card."
)

# A model-emitted tool-call-shaped response leaking into free-text mode (seen with
# Gemma 4 E2B during testing: it emitted its own "<|tool_call|>call:..." syntax instead
# of prose when the guardrail prompt still listed the tool registry). Treated as a
# failed generation, not shown to the user as-is.
_TOOL_CALL_LEAK_MARKERS = ("<tool_call", "<|tool_call", '"tool":', "{'tool':")


def _l3_explain(adapter: ModelAdapter, tool: str, args: dict, result: dict) -> str:
    prompt = (
        f"The tool '{tool}' was called with args {args} and returned:\n{result}\n\n"
        "In at most 120 words, explain this result in plain language for a meteorologist "
        "who knows regional climatology but is new to ensemble verification. End with "
        "exactly one interpretation question back to the user."
    )
    messages = [{"role": "system", "content": EXPLAIN_SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    try:
        reply = adapter.generate(messages, use_grammar=False)
    except ModelLoadError:
        return _l1_explain(tool, result)

    if not isinstance(reply, TextReply):
        return _l1_explain(tool, result)
    if any(marker in reply.text for marker in _TOOL_CALL_LEAK_MARKERS):
        return _l1_explain(tool, result)
    return reply.text


# --------------------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------------------

def propose(state: WorkspaceState, user_message: str, history: list[dict],
            adapter: ModelAdapter | None) -> Proposal:
    if adapter is not None:
        return _l3_propose(adapter, state, user_message, history)
    return _l1_propose(state, user_message)


def execute_and_explain(state: WorkspaceState, tool: str, args: dict,
                         adapter: ModelAdapter | None) -> tuple[dict, str]:
    result = call_tool(tool, args, state)
    if adapter is not None:
        explanation = _l3_explain(adapter, tool, args, result)
    else:
        explanation = _l1_explain(tool, result)
    return result, explanation
