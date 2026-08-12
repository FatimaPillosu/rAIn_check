"""Error triage, rules first (plan §9): a table of regex-classified failure modes, each
mapping to a fixed diagnosis and fix suggestion. The LLM only narrates the matched
diagnosis — it never improvises a cause. If nothing matches, only the last 15 traceback
lines are surfaced, clearly labelled as unverified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.state import workspace_subdir

MAX_UNMATCHED_LINES = 15


@dataclass
class TriageRule:
    pattern: re.Pattern
    diagnosis: str
    fix: str


RULES: list[TriageRule] = [
    TriageRule(re.compile(r"No such file or directory|FileNotFoundError|does not exist"),
               "File not found.", "Check the file path is correct and the file hasn't been moved or renamed."),
    TriageRule(re.compile(r"UnicodeDecodeError|codec can't decode"),
               "The file's text encoding isn't UTF-8.", "Re-save the file as UTF-8, or tell the assistant its encoding so it can be added to the recipe."),
    TriageRule(re.compile(r"does not match format|time data .* doesn't match|Unknown datetime string format"),
               "The date column doesn't match the assumed date format.", "Set the recipe's date_format explicitly (e.g. '%d/%m/%Y') — this is a genuine ambiguity the system won't guess at."),
    TriageRule(re.compile(r"Unrecognised precipitation units|unrecognised units"),
               "The precipitation variable's units aren't recognised (expected mm or metres).", "Check the forecast file's 'units' attribute, or convert the file before loading."),
    TriageRule(re.compile(r"MemoryError|Unable to allocate"),
               "The machine ran out of memory for this operation.", "Close other applications, or reduce the date/lead range being processed at once."),
    TriageRule(re.compile(r"did not find a match in any of xarray|Unknown file format|HDF error|NetCDF: Not a valid"),
               "The file isn't a NetCDF file the reader understands (or it's corrupted).", "Confirm the file opens in another tool (e.g. Panoply); it may need re-exporting."),
    TriageRule(re.compile(r"no valid message|DatasetBuildError|ecCodes.*error|eccodes.*error", re.IGNORECASE),
               "The file isn't a GRIB file the reader understands (or it's corrupted).", "Confirm the file is genuinely GRIB (not renamed) and wasn't partially downloaded."),
    TriageRule(re.compile(r"AccumulationMismatchError|accumulation window"),
               "The forecast and observations use different accumulation windows (e.g. 6h vs 24h).", "Re-aggregate one side to match the other before matching stations to the grid."),
    TriageRule(re.compile(r"is missing column|missing/unrecognised|does not account for required column"),
               "The observation file is missing one or more required columns.", "Propose an ingestion recipe for this file rather than reading it directly — the assistant can map its columns."),
    TriageRule(re.compile(r"KeyError"),
               "A requested date, lead time, or member wasn't found in the forecast.", "Check the Data step summary for the actual available range before requesting scores or maps."),
    TriageRule(re.compile(r"PermissionError|Access is denied|Permission denied"),
               "The file couldn't be opened — permission denied.", "Check the file isn't open in another program, and that you have read access to it."),
    TriageRule(re.compile(r"EmptyDataError|No columns to parse|file is empty"),
               "The file is empty or has no readable data.", "Confirm the file downloaded/exported completely."),
    TriageRule(re.compile(r"could not convert string to float|ValueError: invalid literal for"),
               "A value that should be numeric contains text (e.g. 'trace' for rainfall).", "Check for non-numeric placeholder values in the source file and handle them in the recipe."),
    TriageRule(re.compile(r"ZeroDivisionError|invalid value encountered in (true_)?divide"),
               "A score calculation divided by zero — usually a stratum with no variance or no cases.", "This often means too few forecast-observation pairs in that lead/threshold/station combination."),
    TriageRule(re.compile(r"Failed to load model|error loading model|llama_model_load"),
               "The local AI model failed to load.", "Check the model file wasn't partially downloaded and that config.toml points at the right path."),
    TriageRule(re.compile(r"JSONDecodeError|Expecting value"),
               "A recipe or config file is not valid JSON (likely corrupted or hand-edited incorrectly).", "Regenerate the recipe via propose_recipe, or check the file for a stray comma/bracket."),
    TriageRule(re.compile(r"basemap unavailable|cartopy.*download", re.IGNORECASE),
               "The map basemap (coastlines) isn't cached and this machine is offline.", "This is cosmetic only — the data underneath the map is still correct; connect once to cache the basemap for future offline use."),
]


def classify(error_text: str) -> dict:
    for rule in RULES:
        if rule.pattern.search(error_text):
            return {"matched": True, "diagnosis": rule.diagnosis, "fix": rule.fix}
    tail = "\n".join(error_text.strip().splitlines()[-MAX_UNMATCHED_LINES:])
    return {"matched": False, "diagnosis": None, "fix": None,
            "unverified_traceback_tail": tail,
            "note": "No triage rule matched. This is the raw error text (last "
                    f"{MAX_UNMATCHED_LINES} lines), not a verified diagnosis."}


def _errors_log_path():
    return workspace_subdir("logs") / "errors.log"


def record_error(error_text: str) -> None:
    with open(_errors_log_path(), "a", encoding="utf-8") as fh:
        fh.write(error_text.strip() + "\n---\n")


def get_last_error() -> str | None:
    path = _errors_log_path()
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    parts = [p.strip() for p in content.split("\n---\n") if p.strip()]
    return parts[-1] if parts else None
