"""Cycle 527 tests — run_eval lineage fingerprint (data_source).

The oracle-vs-s_cleaned dataset mixup (0.526 vs 0.484 on identical
code) and ±2-question PYTHONHASHSEED jitter both produce silent,
unreproducible diffs in full-500 lineage comparisons. The fingerprint
(data_file + data_sha256_12 + pythonhashseed) recorded in the report
config makes every comparison auditable.
"""

import hashlib
import os
from pathlib import Path

from amg_bench_quality import run_eval

HAY = [{"session_id": "s1", "messages": [
    {"role": "user", "content": "My favorite color is teal."},
    {"role": "assistant", "content": "Noted, teal is a great color."},
]}]
Q = {"id": "q1", "question": "What is my favorite color?",
     "answer": "teal", "haystack_sessions": HAY}


def test_no_data_source_no_fingerprint(tmp_path):
    """Backward compat: data_source omitted → config untouched."""
    rep = run_eval([Q])
    assert "data_file" not in rep["config"]
    assert "data_sha256_12" not in rep["config"]
    assert "pythonhashseed" not in rep["config"]


def test_fingerprint_fields_recorded(tmp_path):
    data = tmp_path / "longmemeval_s_cleaned.json"
    data.write_text('[{"id": "q1"}]', encoding="utf-8")
    rep = run_eval([Q], data_source=str(data))
    cfg = rep["config"]
    assert cfg["data_file"] == "longmemeval_s_cleaned.json"
    want = hashlib.sha256(data.read_bytes()).hexdigest()[:12]
    assert cfg["data_sha256_12"] == want
    seed = os.environ.get("PYTHONHASHSEED") or "unpinned"
    assert cfg["pythonhashseed"] == seed


def test_fingerprint_survives_dual_mode(tmp_path):
    """Dual-mode overwrites report['config'] wholesale; the
    fingerprint must be applied after that overwrite."""
    data = tmp_path / "ds.json"
    data.write_text("[]", encoding="utf-8")
    rep = run_eval([Q], data_source=str(data), judge_mode="dual")
    assert rep["config"]["data_file"] == "ds.json"
    assert "data_sha256_12" in rep["config"]
    assert rep["config"]["judge_mode"] == "dual"


def test_fingerprint_distinguishes_datasets(tmp_path):
    """The C527 trap: oracle.json vs s_cleaned.json must never be
    confusable — different content ⇒ different fingerprint."""
    a = tmp_path / "longmemeval_oracle.json"
    b = tmp_path / "longmemeval_s_cleaned.json"
    a.write_text("[]", encoding="utf-8")
    b.write_text("[1]", encoding="utf-8")
    ra = run_eval([Q], data_source=str(a))
    rb = run_eval([Q], data_source=str(b))
    assert ra["config"]["data_sha256_12"] != rb["config"]["data_sha256_12"]
    assert ra["config"]["data_file"] != rb["config"]["data_file"]


def test_fingerprint_pathlib_roundtrip(tmp_path):
    """Relative vs absolute path to the SAME file → same fingerprint
    (identity comes from content, not invocation cwd)."""
    data = tmp_path / "ds.json"
    data.write_text("[]", encoding="utf-8")
    r1 = run_eval([Q], data_source=str(data))
    r2 = run_eval([Q], data_source=str(data.resolve()))
    assert (r1["config"]["data_sha256_12"]
            == r2["config"]["data_sha256_12"] == hashlib.sha256(
                b"[]").hexdigest()[:12])
    assert Path(r1["config"]["data_file"]).name == "ds.json"
