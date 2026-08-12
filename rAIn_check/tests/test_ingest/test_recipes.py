from __future__ import annotations

import pandas as pd

from ingest.recipes import apply_recipe, propose_recipe
from ingest.schema import OBS_COLUMNS


def test_propose_recipe_matches_synonyms_and_flags_missing(tmp_path):
    csv_path = tmp_path / "messy.csv"
    csv_path.write_text(
        "StationCode,SiteName,Latitude,Longitude,ObsDate,RainfallMM\n"
        "A1,Alpha,-3.5,37.0,2026-01-01,5.2\n"
        "A1,Alpha,-3.5,37.0,2026-01-02,0.0\n"
    )
    recipe = propose_recipe(csv_path)

    assert recipe.column_map["StationCode"] == "station_id"
    assert recipe.column_map["SiteName"] == "name"
    assert recipe.column_map["Latitude"] == "lat"
    assert recipe.column_map["Longitude"] == "lon"
    assert recipe.column_map["ObsDate"] == "date"
    assert recipe.column_map["RainfallMM"] == "precip_mm"
    # elevation_m has no plausible column in this file -> should be flagged, not guessed
    assert any("elevation_m" in n for n in recipe.notes)
    # accum_hours / qc_flag are defaultable and absent -> should be assumed with a note
    assert recipe.constant_fill.get("accum_hours") == 24
    assert recipe.constant_fill.get("qc_flag") == 0


def test_apply_recipe_produces_canonical_schema(tmp_path):
    csv_path = tmp_path / "messy.csv"
    csv_path.write_text(
        "StationCode,SiteName,Latitude,Longitude,Elev,ObsDate,RainfallMM\n"
        "A1,Alpha,-3.5,37.0,900,2026-01-01,5.2\n"
    )
    df_raw = pd.read_csv(csv_path)
    recipe = propose_recipe(csv_path)
    recipe.column_map["Elev"] = "elevation_m"  # human resolves the one ASK item

    canonical = apply_recipe(df_raw, recipe)
    assert list(canonical.columns) == list(OBS_COLUMNS)
    assert canonical.iloc[0]["station_id"] == "A1"
    assert canonical.iloc[0]["precip_mm"] == 5.2
    assert canonical.iloc[0]["accum_hours"] == 24
    assert pd.api.types.is_datetime64_any_dtype(canonical["date"])


def test_apply_recipe_unit_conversion():
    df_raw = pd.DataFrame({
        "station_id": ["A"], "name": ["Alpha"], "lat": [-3.5], "lon": [37.0],
        "elevation_m": [900], "date": ["2026-01-01"], "accum_hours": [24],
        "precip_mm": [1.0], "qc_flag": [0],
    })
    from ingest.recipes import Recipe
    recipe = Recipe(column_map={c: c for c in df_raw.columns}, precip_unit_factor=25.4)  # inches -> mm
    canonical = apply_recipe(df_raw, recipe)
    assert canonical.iloc[0]["precip_mm"] == 25.4
