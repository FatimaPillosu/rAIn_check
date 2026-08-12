"""The run manifest (plan §7.1): every run writes manifest.json recording exactly which
input files (by content hash, not just filename), which code, and which parameters
produced a result. This is what lets a partner's report be trusted and reproduced
without their raw observations ever leaving their machine — the manifest travels, the
data doesn't.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CODE_VERSION_FALLBACK = "0.1.0-prototype"


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _code_version() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=Path(__file__).parent,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return CODE_VERSION_FALLBACK


def build_manifest(
    input_files: list[str | Path],
    parameters: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "code_version": _code_version(),
        "inputs": [
            {"path": str(p), "sha256": _sha256(p), "bytes": Path(p).stat().st_size}
            for p in input_files
        ],
        "parameters": parameters,
    }


def write_manifest(manifest: dict[str, Any], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_path
