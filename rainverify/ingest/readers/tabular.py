"""Observation table reader -> canonical schema (plan §4.1, §4.3)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..recipes import Recipe, apply_recipe
from ..schema import OBS_COLUMNS, SchemaError, coerce_obs_dtypes


def read_observations_csv(path: str | Path, recipe: Recipe | None = None) -> pd.DataFrame:
    path = Path(path)
    df_raw = pd.read_csv(path)

    if recipe is not None:
        return apply_recipe(df_raw, recipe)

    raw_cols_lower = {c.lower().strip() for c in df_raw.columns}
    canonical_lower = {c.lower() for c in OBS_COLUMNS}
    if raw_cols_lower >= canonical_lower:
        rename = {c: c.lower().strip() for c in df_raw.columns if c.lower().strip() in canonical_lower}
        df = df_raw.rename(columns=rename)
        return coerce_obs_dtypes(df)

    missing = canonical_lower - raw_cols_lower
    raise SchemaError(
        f"'{path.name}' does not match the canonical observation schema "
        f"(missing/unrecognised: {sorted(missing)}). Propose an ingestion recipe "
        "for this file (see ingest.recipes.propose_recipe) instead of reading it directly."
    )
