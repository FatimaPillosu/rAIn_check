from __future__ import annotations

from pathlib import Path

import llama_cpp

GRAMMAR_PATH = Path(__file__).resolve().parents[2] / "assistant" / "grammar.gbnf"


def test_grammar_file_parses():
    grammar = llama_cpp.LlamaGrammar.from_file(str(GRAMMAR_PATH))
    assert grammar is not None


def test_grammar_bounded_whitespace_not_kleene_star():
    # Regression test for the Gemma runaway-whitespace bug found during the model
    # gate benchmark (see grammar.gbnf comment): ws must not be an unbounded [ \t\n]*.
    text = GRAMMAR_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("ws") and "::=" in line:
            assert "*" not in line, f"ws rule reintroduced unbounded repetition: {line}"
