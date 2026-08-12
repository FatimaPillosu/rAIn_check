from __future__ import annotations

from assistant import cards, triage_rules


def test_all_eight_cards_present():
    topics = cards.list_topics()
    expected = {"crps", "rank_histogram", "brier_bss", "reliability_diagram", "roc_auc",
                "spread_error", "climatology_reference", "double_penalty"}
    assert expected <= set(topics)


def test_card_alias_resolution():
    assert cards.get_card("BSS") is not None
    assert cards.get_card("Rank Histogram") is not None
    assert cards.get_card("nonsense_topic_xyz") is None


def test_card_alias_handles_model_phrasing_with_suffix():
    # Regression: a live model asked for "spread-error ratio" (hyphen + trailing word)
    # and got no match before the normalizer/suffix-stripping was added.
    assert cards.get_card("spread-error ratio") is not None
    assert cards.get_card("Brier Skill Score") is not None
    assert cards.get_card("the ROC curve") is not None


def test_triage_at_least_15_rules():
    assert len(triage_rules.RULES) >= 15


def test_triage_classifies_file_not_found():
    result = triage_rules.classify("FileNotFoundError: [Errno 2] No such file or directory: 'x.csv'")
    assert result["matched"] is True
    assert "not found" in result["diagnosis"].lower()


def test_triage_classifies_date_format():
    result = triage_rules.classify("ValueError: time data '14/03/2026' doesn't match format '%Y-%m-%d'")
    assert result["matched"] is True
    assert "date" in result["diagnosis"].lower()


def test_triage_falls_back_to_unverified_tail():
    text = "\n".join(f"line {i}" for i in range(30)) + "\nSomeCompletelyNovelError: mystery"
    result = triage_rules.classify(text)
    assert result["matched"] is False
    assert "unverified_traceback_tail" in result
    assert len(result["unverified_traceback_tail"].splitlines()) <= 15


def test_record_and_get_last_error(tmp_path, monkeypatch):
    import app.state as state_module
    monkeypatch.setattr(state_module, "WORKSPACE_DIR", tmp_path)
    triage_rules.record_error("first error")
    triage_rules.record_error("second error")
    assert triage_rules.get_last_error() == "second error"
