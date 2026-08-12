from __future__ import annotations

import hashlib
import json

from engine.manifest import build_manifest, write_manifest


def test_manifest_records_sha256_and_params(tmp_path):
    f = tmp_path / "input.txt"
    f.write_bytes(b"hello world")
    expected_hash = hashlib.sha256(b"hello world").hexdigest()

    manifest = build_manifest([f], parameters={"scores": ["crps"], "leads": [1]})
    assert manifest["inputs"][0]["sha256"] == expected_hash
    assert manifest["parameters"]["scores"] == ["crps"]
    assert "created_utc" in manifest
    assert "code_version" in manifest


def test_manifest_roundtrips_to_json(tmp_path):
    f = tmp_path / "input.txt"
    f.write_bytes(b"data")
    manifest = build_manifest([f], parameters={})
    out = write_manifest(manifest, tmp_path / "manifest.json")
    reloaded = json.loads(out.read_text())
    assert reloaded == manifest


def test_manifest_same_inputs_reproduce_identical_hash(tmp_path):
    f = tmp_path / "input.txt"
    f.write_bytes(b"same content")
    m1 = build_manifest([f], parameters={"a": 1})
    m2 = build_manifest([f], parameters={"a": 1})
    assert m1["inputs"][0]["sha256"] == m2["inputs"][0]["sha256"]
