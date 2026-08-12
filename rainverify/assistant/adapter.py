"""Model-agnostic adapter (plan §3.3, §9): generate(messages, grammar=None) -> ToolCall
| Text over llama-cpp-python. Swappable between Gemma and Ministral via config.toml /
the UI toggle — the rest of the app never knows which model is loaded.

RAM sequencing (plan §2: "the model and heavy score computation must never run
simultaneously — free or suspend the model before large computations"): callers must
`unload()` the adapter before a heavy compute_scores/QC pass and `load()` it again
afterwards if the chat is going to be used. This module does not do that sequencing
itself — app/routes/assistant.py owns that decision, since it knows the GUI/workflow
state.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AssistantConfig, ModelConfig

GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar.gbnf"


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]


@dataclass
class TextReply:
    text: str


class ModelLoadError(RuntimeError):
    pass


class ModelAdapter:
    """Wraps one llama_cpp.Llama instance. Not thread-safe; the app serves one user."""

    def __init__(self, model_config: ModelConfig, context_length: int, n_threads: int, max_tokens: int):
        self.model_config = model_config
        self.context_length = context_length
        self.n_threads = n_threads
        self.max_tokens = max_tokens
        self._llm = None
        self._grammar = None

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def load(self) -> None:
        if self._llm is not None:
            return
        if not self.model_config.available():
            raise ModelLoadError(
                f"Model file not found at {self.model_config.path}. "
                "Run the model download step, or select a different model."
            )
        import llama_cpp

        try:
            self._llm = llama_cpp.Llama(
                model_path=str(self.model_config.path),
                n_ctx=self.context_length,
                n_threads=self.n_threads,
                verbose=False,
            )
        except Exception as exc:
            raise ModelLoadError(f"Failed to load model {self.model_config.label}: {exc}") from exc

    def unload(self) -> None:
        self._llm = None  # llama.cpp frees native memory when the object is garbage-collected

    def _grammar_obj(self):
        if self._grammar is None:
            import llama_cpp
            self._grammar = llama_cpp.LlamaGrammar.from_file(str(GRAMMAR_PATH))
        return self._grammar

    def generate(self, messages: list[dict[str, str]], use_grammar: bool = False) -> ToolCall | TextReply:
        if self._llm is None:
            self.load()

        kwargs: dict[str, Any] = {"max_tokens": self.max_tokens, "temperature": 0.2}
        if use_grammar:
            kwargs["grammar"] = self._grammar_obj()

        result = self._llm.create_chat_completion(messages=messages, **kwargs)
        content = result["choices"][0]["message"]["content"] or ""

        if use_grammar:
            try:
                parsed = json.loads(content)
                return ToolCall(tool=parsed["tool"], args=parsed.get("args", {}))
            except (json.JSONDecodeError, KeyError) as exc:
                raise ModelLoadError(
                    f"Model output did not match the tool-call grammar despite constrained "
                    f"decoding (unexpected): {content!r} ({exc})"
                )
        return TextReply(text=content)


_adapters: dict[str, ModelAdapter] = {}
_active_key: str | None = None


def get_adapter(key: str, config: AssistantConfig) -> ModelAdapter:
    if key not in config.models:
        raise ValueError(f"Unknown model key '{key}'. Configured models: {sorted(config.models)}")
    if key not in _adapters:
        _adapters[key] = ModelAdapter(
            config.models[key], config.context_length, config.n_threads, config.max_tokens_per_reply,
        )
    return _adapters[key]


def set_active(key: str | None) -> None:
    """Switch the active model, unloading any other loaded adapter first — the plan's
    RAM budget assumes at most one model resident at a time.
    """
    global _active_key
    for other_key, adapter in _adapters.items():
        if other_key != key and adapter.is_loaded:
            adapter.unload()
    _active_key = key


def get_active_key() -> str | None:
    return _active_key
