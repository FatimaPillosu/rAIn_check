from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.deps import templates
from app.state import ChatMessage, get_state
from assistant import adapter as adapter_module
from assistant.config import load_assistant_config
from assistant.policy import execute_and_explain, propose

router = APIRouter()
CONFIG = load_assistant_config()


def _get_active_adapter(state):
    if state.assistant_model == "none":
        return None
    return adapter_module.get_adapter(state.assistant_model, CONFIG)


def _history_for_llm(state) -> list[dict]:
    # Most local chat templates (Ministral's included) require strict user/assistant
    # alternation after the system message. Our own chat log doesn't respect that —
    # a proposal message and its explanation are both role="assistant" back to back —
    # so consecutive same-role turns are merged into one before handing history to the
    # model, rather than sent as-is and rejected by the template.
    merged: list[dict] = []
    for m in state.chat_history[-8:]:  # keep the context window small (plan: 2k ctx)
        role = "assistant" if m.role == "assistant" else "user"
        if merged and merged[-1]["role"] == role:
            merged[-1]["content"] += "\n" + m.text
        else:
            merged.append({"role": role, "content": m.text})
    # Most local chat templates also require the first turn after the system message to
    # be "user" — drop any leading assistant-only notices (e.g. the "switched model"
    # confirmation) that have no preceding user turn.
    while merged and merged[0]["role"] == "assistant":
        merged.pop(0)
    return merged


def _render_dock(request: Request) -> HTMLResponse:
    state = get_state()
    ctx = {"request": request, "chat_history": state.chat_history, "assistant_model": state.assistant_model}
    return templates.TemplateResponse("partials/dock_body.html", ctx)


@router.post("/chat/model")
def chat_model(request: Request, model: str = Form(...)):
    state = get_state()
    state.assistant_model = model
    adapter_module.set_active(None if model == "none" else model)
    state.chat_history.append(ChatMessage(
        role="assistant",
        text=f"Switched to {'deterministic (no model)' if model == 'none' else CONFIG.models[model].label}.",
    ))
    return _render_dock(request)


@router.post("/chat/send")
def chat_send(request: Request, message: str = Form(...)):
    state = get_state()
    if not message.strip():
        return _render_dock(request)

    state.chat_history.append(ChatMessage(role="user", text=message))
    history = _history_for_llm(state)[:-1]  # exclude the message we're about to send as the prompt

    try:
        adapter = _get_active_adapter(state)
    except Exception:
        adapter = None

    result = propose(state, message, history, adapter)

    if result.is_free_text:
        state.chat_history.append(ChatMessage(role="assistant", text=result.text))
    else:
        state.chat_history.append(ChatMessage(
            role="assistant",
            text=f"I'd like to call `{result.tool}`.",
            proposal={"reason": result.reason, "tool": result.tool, "args": result.args, "executed": False},
        ))
    return _render_dock(request)


@router.post("/chat/approve")
async def chat_approve(request: Request):
    state = get_state()
    form = await request.form()
    index = int(form["index"])
    skip = form.get("action") == "skip"

    msg = state.chat_history[index]
    if msg.proposal is None or msg.proposal.get("executed"):
        return _render_dock(request)

    if skip:
        msg.proposal["executed"] = True
        state.chat_history.append(ChatMessage(role="assistant", text="Skipped, as requested."))
        return _render_dock(request)

    try:
        adapter = _get_active_adapter(state)
    except Exception:
        adapter = None

    try:
        result, explanation = execute_and_explain(state, msg.proposal["tool"], msg.proposal["args"], adapter)
        msg.proposal["executed"] = True
        state.chat_history.append(ChatMessage(role="assistant", text=explanation))
    except Exception as exc:
        msg.proposal["executed"] = True
        state.chat_history.append(ChatMessage(role="assistant", text=f"That failed: {exc}"))

    return _render_dock(request)
