"""Ingestion recipes (plan §4.3) — the deterministic half of the flagship AI capability.

A recipe is a small JSON document mapping a raw observation table onto the canonical
schema. `propose_recipe` is the heuristic, non-LLM proposer: it does its best with
column-name matching and flags anything it isn't confident about with an "ASK" note,
exactly the shape the assistant's `propose_recipe` tool later wraps with an LLM-written
explanation. The mapping is applied by `apply_recipe`, and is otherwise identical
whether a human or the assistant produced it — the engine only ever executes recipes,
it never guesses at runtime.
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .schema import OBS_COLUMNS, SchemaError, coerce_obs_dtypes

_SYNONYMS: dict[str, tuple[str, ...]] = {
    "station_id": ("station_id", "id", "station", "code", "stn_id", "stationid", "station_code"),
    "name": ("name", "station_name", "site", "site_name"),
    "lat": ("lat", "latitude", "y"),
    "lon": ("lon", "longitude", "long", "x"),
    "elevation_m": ("elevation_m", "elevation", "elev", "alt", "altitude", "height_m"),
    "date": ("date", "datetime", "time", "obs_date", "valid_date"),
    "accum_hours": ("accum_hours", "accumulation_hours", "window_hours", "acc_hours"),
    "precip_mm": ("precip_mm", "precipitation", "rain_mm", "rainfall_mm", "precip", "value", "rainfall"),
    "qc_flag": ("qc_flag", "flag", "quality_flag", "qc"),
}

# Columns that reasonably default to a constant when genuinely absent from the source.
_DEFAULTABLE = {"accum_hours": 24, "qc_flag": 0}


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


_CANDIDATE_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _sniff_date_format(sample_values: pd.Series) -> tuple[str | None, str]:
    """Try a short list of common formats against the sample; return (format_or_None, note).

    Deliberately does NOT guess between day-first and month-first when both parse
    cleanly (e.g. every day-of-month in the sample happens to be <=12) — that
    ambiguity is exactly the kind of judgement call the ingestion-recipe design
    (plan §4.3) wants surfaced to a human, not silently resolved.
    """
    values = sample_values.dropna().astype(str).tolist()
    if not values:
        return None, "ASK: date column sample is empty; cannot infer its format."

    working = []
    for fmt in _CANDIDATE_DATE_FORMATS:
        try:
            pd.to_datetime(values, format=fmt, errors="raise")
            working.append(fmt)
        except (ValueError, TypeError):
            continue

    if not working:
        return None, ("ASK: could not confidently parse the date column against any of "
                       f"{_CANDIDATE_DATE_FORMATS}; set date_format explicitly.")
    if len(working) == 1:
        return working[0], f"ASSUMED date format '{working[0]}' (unambiguous on the sample)."

    day_first = "%d/%m/%Y" if "%d/%m/%Y" in working else ("%d-%m-%Y" if "%d-%m-%Y" in working else working[0])
    return day_first, (
        f"ASK: date column is ambiguous — formats {working} all parse the sample cleanly "
        f"(every day-of-month value is <=12). Defaulting to day-first ('{day_first}'); "
        "confirm or change before trusting the dates."
    )


@dataclass
class Recipe:
    column_map: dict[str, str] = field(default_factory=dict)  # raw_col -> canonical_col
    constant_fill: dict[str, Any] = field(default_factory=dict)  # canonical_col -> constant value
    date_format: str | None = None
    precip_unit_factor: float = 1.0  # multiply raw precip values by this to get mm
    notes: list[str] = field(default_factory=list)  # human-readable ASK / assumption notes
    source_sample: list[str] = field(default_factory=list)  # provenance: header + first rows seen

    def to_json(self) -> dict:
        return {
            "column_map": self.column_map,
            "constant_fill": self.constant_fill,
            "date_format": self.date_format,
            "precip_unit_factor": self.precip_unit_factor,
            "notes": self.notes,
            "source_sample": self.source_sample,
        }

    @classmethod
    def from_json(cls, d: dict) -> "Recipe":
        return cls(
            column_map=d.get("column_map", {}),
            constant_fill=d.get("constant_fill", {}),
            date_format=d.get("date_format"),
            precip_unit_factor=d.get("precip_unit_factor", 1.0),
            notes=d.get("notes", []),
            source_sample=d.get("source_sample", []),
        )


def propose_recipe(path: str | Path, sample_n: int = 20) -> Recipe:
    """Heuristic, deterministic first guess at a mapping. Marks anything uncertain."""
    path = Path(path)
    sample = pd.read_csv(path, nrows=sample_n)
    raw_columns = list(sample.columns)
    raw_lower = {c.lower().strip(): c for c in raw_columns}
    raw_normed = {_norm(c): c for c in raw_columns}

    column_map: dict[str, str] = {}
    constant_fill: dict[str, Any] = {}
    notes: list[str] = []

    for canonical, synonyms in _SYNONYMS.items():
        matched_raw = None
        for syn in synonyms:
            if syn in raw_lower:
                matched_raw = raw_lower[syn]
                break
        if matched_raw is None:
            for syn in synonyms:
                if _norm(syn) in raw_normed:
                    matched_raw = raw_normed[_norm(syn)]
                    break
        if matched_raw is None:
            # Substring containment on normalized forms, so unit suffixes like "Lat
            # (deg)" or "24h Rainfall (mm)" still match "lat" / "rainfall". Only for
            # synonyms of 3+ characters, to avoid short tokens matching unrelated text.
            for syn in sorted(synonyms, key=len, reverse=True):
                norm_syn = _norm(syn)
                if len(norm_syn) < 3:
                    continue
                hit = next((raw for norm_raw, raw in raw_normed.items() if norm_syn in norm_raw), None)
                if hit is not None:
                    matched_raw = hit
                    break
        if matched_raw is None:
            close = difflib.get_close_matches(canonical, raw_columns, n=3, cutoff=0.6)
            if close:
                notes.append(
                    f"ASK: no confident match for '{canonical}'; closest column name(s) in the "
                    f"file: {close}. Confirm or pick the right one."
                )
            elif canonical in _DEFAULTABLE:
                constant_fill[canonical] = _DEFAULTABLE[canonical]
                notes.append(
                    f"ASSUMED: '{canonical}' not found in the file; defaulting every row to "
                    f"{_DEFAULTABLE[canonical]!r}. Confirm this is correct."
                )
            else:
                notes.append(f"ASK: no column found for required field '{canonical}'.")
        else:
            column_map[matched_raw] = canonical

    date_format = None
    date_raw_col = next((raw for raw, canon in column_map.items() if canon == "date"), None)
    if date_raw_col is not None:
        date_format, date_note = _sniff_date_format(sample[date_raw_col])
        notes.append(date_note)

    return Recipe(
        column_map=column_map,
        constant_fill=constant_fill,
        date_format=date_format,
        notes=notes,
        source_sample=[",".join(raw_columns)] + sample.head(5).astype(str).apply(",".join, axis=1).tolist(),
    )


def apply_recipe(df_raw: pd.DataFrame, recipe: Recipe) -> pd.DataFrame:
    df = df_raw.rename(columns=recipe.column_map)

    for col, val in recipe.constant_fill.items():
        df[col] = val

    missing = [c for c in OBS_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(
            f"Recipe does not account for required column(s) {missing}. "
            "Add them to column_map or constant_fill before applying."
        )

    df = df[list(OBS_COLUMNS)].copy()

    if recipe.date_format:
        df["date"] = pd.to_datetime(df["date"], format=recipe.date_format)
    else:
        df["date"] = pd.to_datetime(df["date"])

    if recipe.precip_unit_factor != 1.0:
        df["precip_mm"] = pd.to_numeric(df["precip_mm"]) * recipe.precip_unit_factor

    return coerce_obs_dtypes(df)


def save_recipe(recipe: Recipe, workspace_dir: str | Path, name: str) -> Path:
    workspace_dir = Path(workspace_dir)
    recipes_dir = workspace_dir / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    out_path = recipes_dir / f"{name}.json"
    out_path.write_text(json.dumps(recipe.to_json(), indent=2), encoding="utf-8")
    return out_path


def load_recipe(path: str | Path) -> Recipe:
    return Recipe.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
