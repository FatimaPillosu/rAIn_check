"""Knowledge cards (plan §9): the assistant answers score questions solely by
summarising a card, and the UI shows the card title as the source. If no card matches,
the assistant says so and does not improvise.
"""
from __future__ import annotations

from pathlib import Path

CARDS_DIR = Path(__file__).resolve().parents[1] / "cards"

_ALIASES = {
    "crps": "crps", "continuous_ranked_probability_score": "crps",
    "rank_histogram": "rank_histogram", "talagrand": "rank_histogram",
    "brier": "brier_bss", "bss": "brier_bss", "brier_bss": "brier_bss", "brier_skill_score": "brier_bss",
    "reliability": "reliability_diagram", "reliability_diagram": "reliability_diagram", "calibration": "reliability_diagram",
    "roc": "roc_auc", "auc": "roc_auc", "roc_auc": "roc_auc",
    "spread": "spread_error", "spread_error": "spread_error", "spread_error_ratio": "spread_error",
    "climatology": "climatology_reference", "climatology_reference": "climatology_reference",
    "double_penalty": "double_penalty",
}

# A free-form model can send "spread-error ratio", "the ROC curve", "Brier Skill Score",
# etc. Stripped prefixes/suffixes are tried in combination after exact/alias matching
# fails, before giving up — better recall without hand-listing every phrasing.
_STRIP_PREFIXES = ("the_",)
_STRIP_SUFFIXES = ("_ratio", "_score", "_curve", "_diagram")


def list_topics() -> list[str]:
    return sorted(p.stem for p in CARDS_DIR.glob("*.md"))


def _normalize(topic: str) -> str:
    return topic.strip().lower().replace("-", "_").replace(" ", "_")


def _strip_variants(normed: str) -> list[str]:
    variants = {normed}
    for prefix in _STRIP_PREFIXES:
        if normed.startswith(prefix):
            variants.add(normed[len(prefix):])
    for suffix in _STRIP_SUFFIXES:
        if normed.endswith(suffix):
            variants.add(normed[: -len(suffix)])
    # both a prefix and a suffix stripped, e.g. "the_roc_curve" -> "roc"
    for prefix in _STRIP_PREFIXES:
        if normed.startswith(prefix):
            for suffix in _STRIP_SUFFIXES:
                if normed.endswith(suffix):
                    variants.add(normed[len(prefix): -len(suffix)])
    return list(variants)


def get_card(topic: str) -> str | None:
    normed = _normalize(topic)
    candidates: list[str] = []
    for variant in _strip_variants(normed):
        candidates += [variant, _ALIASES.get(variant, variant)]

    for key in candidates:
        path = CARDS_DIR / f"{key}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None
