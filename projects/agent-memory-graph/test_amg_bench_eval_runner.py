"""Cycle 454 tests — run_eval() per-question-haystack evaluation.

Each LongMemEval-cleaned question ships its own haystack; run_eval()
builds a fresh adapter + graph per question (isolation guarantee) and
aggregates single-question evaluate() reports, optionally running the
C448 entropy sweep on the same graphs. Backs the ``--mode eval`` CLI.
"""

import json
from pathlib import Path

import pytest

from amg_bench_quality import main, run_eval

HAY1 = [{"session_id": "s1", "messages": [
    {"role": "user", "content": "My favorite color is teal."},
    {"role": "assistant", "content": "Noted, teal is a great color."},
]}]
HAY2 = [{"session_id": "s2", "messages": [
    {"role": "user", "content": "I adopted a beagle puppy named Rex."},
    {"role": "assistant", "content": "Rex the beagle sounds lovely."},
]}]
Q1 = {"id": "q1", "question": "What is my favorite color?",
      "answer": "teal", "haystack_sessions": HAY1}
Q2 = {"id": "q2_abs", "question": "What is my favorite color?",
      "answer": "", "abstention": True, "haystack_sessions": HAY2}


def test_run_eval_isolation_and_scoring():
    """q1 answered from ITS haystack; q2_abs abstains (its haystack has
    no color facts). Shared-graph contamination would make q2_abs find
    teal → answer → incorrect; isolation keeps accuracy at 1.0."""
    rep = run_eval([Q1, Q2])
    assert rep["total_questions"] == 2
    assert rep["overall_accuracy"] == 1.0
    assert rep["abstention_rate"] == 0.5
    rows = {r["question_id"]: r for r in rep["results"]}
    assert rows["q1"]["correct"] and rows["q1"]["retrieval_hit"]
    assert rows["q2_abs"]["correct"] and rows["q2_abs"]["abstained"]


def test_run_eval_categories_aggregate():
    rep = run_eval([Q1, Q2])
    cats = rep["categories"]
    # neither question carries a category suffix/keyword → default
    assert cats["single_session_user"]["total"] == 2
    assert cats["single_session_user"]["correct"] == 2


def test_run_eval_limit():
    rep = run_eval([Q1, Q2], limit=1)
    assert rep["total_questions"] == 1
    assert rep["results"][0]["question_id"] == "q1"


def test_run_eval_sweep_labels_and_rows():
    rep = run_eval([Q1, Q2], entropies=[None, 0.9])
    assert rep["sweep"]["thresholds"] == ["None", "0.9"]
    assert len(rep["sweep"]["rows"]) == 2
    for lab in ("None", "0.9"):
        s = rep["sweep"]["summary"][lab]
        assert s["total"] == 2
        assert 0.0 <= s["accuracy"] <= 1.0
    # both thresholds keep accuracy 1.0 on this fixture
    assert rep["sweep"]["summary"]["None"]["accuracy"] == 1.0


def test_run_eval_no_haystack_uses_empty_graph():
    rep = run_eval([{"id": "q3", "question": "anything at all?",
                     "answer": "zzz"}])
    assert rep["total_questions"] == 1
    assert rep["results"][0]["abstained"]  # empty gate


def test_cli_eval_mode(tmp_path: Path):
    data = tmp_path / "d.json"
    data.write_text(json.dumps([Q1, Q2]), encoding="utf-8")
    out = tmp_path / "rep.json"
    rc = main(["--data", str(data), "--mode", "eval", "--limit", "2",
               "--output", str(out)])
    assert rc == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["overall_accuracy"] == 1.0
    assert rep["sweep"] is None


def test_cli_eval_mode_with_sweep(tmp_path: Path):
    data = tmp_path / "d.json"
    data.write_text(json.dumps([Q1]), encoding="utf-8")
    out = tmp_path / "rep.json"
    rc = main(["--data", str(data), "--mode", "eval",
               "--sweep-entropies", "none,0.90,0.95",
               "--output", str(out)])
    assert rc == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["sweep"]["thresholds"] == ["None", "0.9", "0.95"]


def test_cli_default_mode_unchanged(tmp_path: Path):
    """Pre-C454 extract mode stays the default (backward compat)."""
    data = tmp_path / "d.json"
    data.write_text(json.dumps([Q1]), encoding="utf-8")
    out = tmp_path / "rows.json"
    rc = main(["--data", str(data), "--limit", "1", "--output", str(out)])
    assert rc == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert "rows" in rep and len(rep["rows"]) == 1
    assert "overall_accuracy" not in rep
