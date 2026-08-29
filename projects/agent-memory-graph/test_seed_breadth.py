"""Cycle 473 tests — speaker-recall seed breadth (recall_seed_k).

C473 forensics on single_session_assistant evhit misses: 10/12 had
``ev_in_candidates=0`` — the evidence messages scored 7–16 keyword
hits but never entered the candidate set, because per-keyword recall
is weight-ordered ``LIMIT 5``. ``recall_seed_k`` (default 40) broadens
seeding ONLY for recall-form questions; the same breadth on temporal
questions floods the window with question-echoing advice lines (A/B:
temporal exact 36→14/133), so non-recall questions keep breadth 5.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from amg_bench_quality import LongMemEvalAdapter, recall_form


RECALL_Q = ("In our previous chat, you suggested some mindfulness "
            "techniques. What were they again?")
PLAIN_Q = "What did I say about my favorite movie this month?"


def _adapter_with_recall_spy(**kw):
    """Adapter whose mg.recall records the limit it was called with."""
    ad = LongMemEvalAdapter(**kw)
    limits = []
    orig = ad.mg.recall

    def spy(query, limit=5, **kw):
        limits.append(limit)
        return orig(query, limit=limit, **kw)

    ad.mg.recall = spy
    return ad, limits


def test_default_breadths():
    """Operating point contract: pipeline 5, recall-form 40."""
    ad = LongMemEvalAdapter()
    assert ad.seed_recall_k == 5
    assert ad.recall_seed_k == 40


def test_recall_form_question_seeds_broad():
    ad, limits = _adapter_with_recall_spy()
    assert recall_form(RECALL_Q) == "assistant"
    ad.ingest_sessions([{"session_id": "s1", "messages": [
        {"role": "user", "content": "please suggest mindfulness techniques"},
        {"role": "assistant",
         "content": "Sure! Here are mindfulness techniques for you."}]}])
    ad.retrieve_context(RECALL_Q)
    assert limits and all(k == 40 for k in limits), limits


def test_plain_question_keeps_narrow_breadth():
    ad, limits = _adapter_with_recall_spy()
    assert recall_form(PLAIN_Q) is None
    ad.ingest_sessions([{"session_id": "s1", "messages": [
        {"role": "user", "content": "my favorite movie is Stalker"}]}])
    ad.retrieve_context(PLAIN_Q)
    assert limits and all(k == 5 for k in limits), limits


def test_explicit_narrow_recall_breadth_overrides():
    """recall_seed_k=5 restores pre-C473 seeding for recall forms."""
    ad, limits = _adapter_with_recall_spy(recall_seed_k=5)
    ad.ingest_sessions([{"session_id": "s1", "messages": [
        {"role": "user", "content": "please suggest mindfulness techniques"}]}])
    ad.retrieve_context(RECALL_Q)
    assert limits and all(k == 5 for k in limits), limits


def test_breadth_rescues_truncated_evidence_candidate():
    """Seed-stage contract: an assistant evidence message beyond the
    weight-ordered recall cut becomes a candidate (and, via the
    -seq tie-break among equal hits, ranks first) with recall_seed_k;
    at the old breadth it never enters the candidate set.

    BM25/PPR are neutralized (C472 lesson 3: synthetic fixtures
    shouldn't race the scored stages) — this isolates the per-keyword
    recall truncation the C473 forensics measured (ev_in_candidates=0).
    """
    sessions = []
    # 12 noise sessions whose assistant lines carry the SAME
    # keywords as the evidence — at breadth 5 the weight-ordered
    # LIMIT 5 returns only the earliest noise lines.
    for j in range(12):
        sessions.append({"session_id": f"noise_{j}", "messages": [
            {"role": "assistant",
             "content": f"mindfulness technique suggestion list #{j}"}]})
    sessions.append({"session_id": "evidence", "messages": [
        {"role": "assistant",
         "content": "mindfulness technique suggestion list #12: the real one"}]})

    narrow = LongMemEvalAdapter(use_ppr=False, recall_seed_k=5)
    broad = LongMemEvalAdapter(use_ppr=False)
    for ad in (narrow, broad):
        ad.ingest_sessions(sessions)
        ad.mg.search_graphrag = lambda *a, **k: []   # isolate seed stage
    _, meta_n = narrow.retrieve_context(RECALL_Q)
    _, meta_b = broad.retrieve_context(RECALL_Q)
    ev_n = {narrow._messages[n]["session_id"]
            for n in meta_n["retrieved_ids"]}
    ev_b = {broad._messages[n]["session_id"]
            for n in meta_b["retrieved_ids"]}
    assert "evidence" not in ev_n          # old breadth truncates
    assert "evidence" in ev_b              # C473 breadth rescues
