from __future__ import annotations

from app.state import WorkspaceState
from assistant.adapter import TextReply
from assistant.policy import execute_and_explain, propose


def test_l1_recognises_data_question():
    state = WorkspaceState()
    p = propose(state, "What data files do we have available?", [], adapter=None)
    assert p.tool == "list_data"


def test_l1_recognises_qc_question():
    state = WorkspaceState()
    p = propose(state, "Can you check the data quality?", [], adapter=None)
    assert p.tool == "run_qc"


def test_l1_recognises_card_topic():
    state = WorkspaceState()
    p = propose(state, "What is CRPS?", [], adapter=None)
    assert p.tool == "get_card"
    assert p.args["topic"] == "crps"


def test_l1_falls_back_to_free_text_for_unrecognised_input():
    state = WorkspaceState()
    p = propose(state, "asdkfjhaslkdjfh nonsense gibberish", [], adapter=None)
    assert p.is_free_text is True
    assert "no model is loaded" in p.text.lower() or "deterministic" in p.text.lower()


class _LeakyAdapter:
    """Stub adapter simulating a model that leaks tool-call syntax into free-text mode
    (observed with Gemma 4 E2B during browser testing) — exercises the defensive
    fallback in policy._l3_explain without needing to load a real 3GB model.
    """
    def generate(self, messages, use_grammar=False):
        return TextReply(text='<|tool_call|>call:get_card{topic:<|"|>crps<|"|>}<tool_call|>')


def test_l3_explain_falls_back_to_l1_on_tool_call_leak():
    state = WorkspaceState()
    _, explanation = execute_and_explain(state, "get_card", {"topic": "crps"}, adapter=_LeakyAdapter())
    assert "<tool_call" not in explanation
    assert "<|tool_call" not in explanation
    assert "CRPS" in explanation or "crps" in explanation.lower()
