"""Real model load + grammar-constrained generation, against whichever configured
models are actually present on disk. Slower than the rest of the suite (a few seconds
per model to load and generate) but this is the only thing that proves the GGUF file,
the grammar, and llama-cpp-python actually agree with each other end to end — worth the
cost. Skips a model cleanly if its file isn't present (e.g. not yet downloaded).
"""
from __future__ import annotations

import pytest

from assistant.adapter import ToolCall, get_adapter
from assistant.config import load_assistant_config

CONFIG = load_assistant_config()


@pytest.mark.parametrize("model_key", list(CONFIG.models))
def test_model_produces_valid_tool_call(model_key):
    model_config = CONFIG.models[model_key]
    if not model_config.available():
        pytest.skip(f"{model_config.label} not downloaded at {model_config.path}")

    adapter = get_adapter(model_key, CONFIG)
    messages = [
        {"role": "system", "content": "Available tools: list_data (no args), run_qc (no args). "
                                       "Respond only with a JSON tool call."},
        {"role": "user", "content": "What data files are available?"},
    ]
    result = adapter.generate(messages, use_grammar=True)
    adapter.unload()

    assert isinstance(result, ToolCall)
    assert result.tool in ("list_data", "run_qc")
