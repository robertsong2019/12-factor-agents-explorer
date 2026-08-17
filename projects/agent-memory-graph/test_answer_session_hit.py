"""Cycle 467 tests — answer_session_hit (evidence-session coverage).

``retrieval_hit`` is truth-containment: structurally impossible when
the dataset's truths are synthesized meta-descriptions ("The user
would prefer …" — preference slice hit 0.000 was a metric artifact).
``answer_session_hit`` scores whether retrieval surfaced ANY message
from a session the dataset itself marks as answer evidence
(``answer_session_ids`` hidden among ``haystack_session_ids``) — an
honest, dataset-grounded recall metric for every category. Unresolvable
items (no evidence pointers) score ``None`` and are excluded from
rates — never counted as misses (C466 lesson 3: honest unknown).
"""
import json
from pathlib import Path

from amg_bench_quality import (CategorySummary, LongMemEvalAdapter,
                               QuestionResult, evidence_session_ids,
                               main, run_eval)


# ── evidence_session_ids: pure resolution ──────────────────────────

def test_positional_bare_list_mapping():
    """Bare-list sessions → positional session_{j+1} (run_eval
    convention); only evidence sessions are kept."""
    item = {"answer_session_ids": ["noise_a", "answer_x"],
            "haystack_session_ids": ["noise_a", "noise_b", "answer_x"],
            "haystack_sessions": [[{"role": "user", "content": "1"}],
                                  [{"role": "user", "content": "2"}],
                                  [{"role": "user", "content": "3"}]]}
    assert evidence_session_ids(item) == {"session_1", "session_3"}


def test_dict_sessions_keep_own_ids():
    item = {"answer_session_ids": ["answer_x"],
            "haystack_session_ids": ["noise", "answer_x"],
            "haystack_sessions": [
                {"session_id": "s1", "messages": []},
                {"session_id": "s2", "messages": []}]}
    assert evidence_session_ids(item) == {"s2"}


def test_missing_pointers_yield_empty_set():
    """No evidence pointers → unresolvable (set()), never a miss."""
    assert evidence_session_ids({}) == set()
    assert evidence_session_ids({"answer_session_ids": ["a"]}) == set()
    assert evidence_session_ids({"haystack_session_ids": ["a"]}) == set()


def test_evidence_id_absent_from_haystack():
    item = {"answer_session_ids": ["ghost"],
            "haystack_session_ids": ["a", "b"],
            "haystack_sessions": [[], []]}
    assert evidence_session_ids(item) == set()


def test_length_mismatch_is_safe():
    """Sessions shorter than ids (defensive) — no IndexError."""
    item = {"answer_session_ids": ["a"],
            "haystack_session_ids": ["a", "b"],
            "haystack_sessions": [[]]}
    assert evidence_session_ids(item) == {"session_1"}


# ── dataclass plumbing ─────────────────────────────────────────────

def test_question_result_to_dict_roundtrip():
    r = QuestionResult(question_id="q", category="c", question="?",
                       ground_truth="t", predicted_answer="p",
                       answer_session_hit=None)
    d = r.to_dict()
    assert d["answer_session_hit"] is None
    r2 = QuestionResult(question_id="q", category="c", question="?",
                        ground_truth="t", predicted_answer="p",
                        answer_session_hit=True)
    assert r2.to_dict()["answer_session_hit"] is True


def test_category_summary_rate_over_resolved_only():
    cs = CategorySummary(category="c", total=5, answer_hits=2,
                         answer_resolved=3)
    assert abs(cs.answer_session_hit_rate - 2 / 3) < 1e-9
    d = cs.to_dict()
    assert d["answer_sessions_resolved"] == 3
    assert d["answer_session_hits"] == 2
    # zero resolved → rate 0.0, not ZeroDivisionError
    cs2 = CategorySummary(category="c")
    assert cs2.answer_session_hit_rate == 0.0


# ── evaluate(): per-question scoring ───────────────────────────────

HAY = [[{"role": "user", "content": "random chatter about the weather"}],
       [{"role": "user", "content": "My favorite color is teal."}]]


def _adapter_with_haystack():
    a = LongMemEvalAdapter()
    a.ingest_sessions([
        {"session_id": "session_1", "messages": HAY[0]},
        {"session_id": "session_2", "messages": HAY[1]}])
    return a


def test_evaluate_hit_true_when_evidence_retrieved():
    a = _adapter_with_haystack()
    item = {"id": "q1", "question": "What is my favorite color?",
            "answer": "teal", "haystack_sessions": HAY,
            "haystack_session_ids": ["noise", "ev"],
            "answer_session_ids": ["ev"]}
    rep = a.evaluate([item])
    row = rep["results"][0]
    assert row["answer_session_hit"] is True
    assert rep["answer_session_hit_rate"] == 1.0
    assert rep["answer_sessions_resolved"] == 1


def test_evaluate_none_when_unresolvable():
    a = _adapter_with_haystack()
    item = {"id": "q2", "question": "What is my favorite color?",
            "answer": "teal", "haystack_sessions": HAY}
    rep = a.evaluate([item])
    row = rep["results"][0]
    assert row["answer_session_hit"] is None
    assert rep["answer_sessions_resolved"] == 0
    assert rep["answer_session_hit_rate"] == 0.0  # 0 resolved, no crash


def test_evaluate_miss_when_evidence_not_retrieved():
    """Question keywords only match the NOISE session AND the token
    budget only fits the top-ranked noise line → evidence session
    never enters the context → honest miss."""
    a = LongMemEvalAdapter(max_context_tokens=12)  # fits one short line
    a.ingest_sessions([
        {"session_id": "session_1",
         "messages": [{"role": "user", "content": "weather noise"}]},
        {"session_id": "session_2",
         "messages": [{"role": "user",
                       "content": "My favorite color is teal today."}]}])
    item = {"id": "q3", "question": "What about the weather noise?",
            "answer": "sunny", "haystack_sessions": HAY,
            "haystack_session_ids": ["noise", "ev"],
            "answer_session_ids": ["ev"]}
    rep = a.evaluate([item])
    assert rep["results"][0]["answer_session_hit"] is False
    assert rep["answer_session_hit_rate"] == 0.0
    assert rep["answer_sessions_resolved"] == 1


# ── run_eval end-to-end + CLI smoke ────────────────────────────────

def test_run_eval_evidence_coverage_aggregate():
    ds = [{"id": "q1", "question": "What is my favorite color?",
           "answer": "teal",
           "haystack_sessions": [[
               {"role": "user", "content": "My favorite color is teal."}]],
           "haystack_session_ids": ["ev1"],
           "answer_session_ids": ["ev1"]},
          {"id": "q2", "question": "What is my favorite color?",
           "answer": "teal",
           "haystack_sessions": [[
               {"role": "user", "content": "My favorite color is teal."}]]}]
    rep = run_eval(ds)
    assert rep["answer_sessions_resolved"] == 1
    assert rep["answer_session_hit_rate"] == 1.0
    cats = rep["categories"]["single_session_user"]
    assert cats["answer_sessions_resolved"] == 1
    assert cats["answer_session_hits"] == 1
    assert cats["answer_session_hit_rate"] == 1.0


def test_cli_eval_mode_prints_evidence_hit(tmp_path: Path):
    data = tmp_path / "ds.json"
    data.write_text(json.dumps([
        {"id": "q1", "question": "What is my favorite color?",
         "answer": "teal",
         "haystack_sessions": [[
             {"role": "user", "content": "My favorite color is teal."}]],
         "haystack_session_ids": ["ev1"],
         "answer_session_ids": ["ev1"]}]))
    out = tmp_path / "out.json"
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--data", str(data), "--mode", "eval",
                   "--limit", "1", "--output", str(out)])
    assert rc == 0
    assert "evidence_hit" in buf.getvalue()
    rep = json.loads(out.read_text())
    assert rep["answer_session_hit_rate"] == 1.0
    assert rep["answer_sessions_resolved"] == 1
