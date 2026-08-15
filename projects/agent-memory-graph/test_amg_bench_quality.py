"""Tests for amg_bench_quality.py — LongMemEval memory-quality adapter.

Research #061 (2026-08-12) design promoted to the real repo lineage in
Cycle 447, on top of Cycle 446's repatriated amg_bench.py.

The fixture is a mini-LongMemEval (3 sessions / 6 messages / 2 entities)
covering the four behaviors the adapter must demonstrate:

* single-session recall ("What activity does the user love?")
* knowledge update ("switched from hiking to cycling" — the answer must
  come from the LATER session)
* temporal mention ("cycling trip to Portland in April")
* abstention ("What did the user say about sushi?" → "I don't know")
"""

import json

import pytest

import amg_bench_quality as abq
from amg_bench_quality import (
    ABSTAIN_ANSWER,
    LongMemEvalAdapter,
    _keyword_hits,
    _keywords,
    _token_matches,
    exact_judge,
    load_longmemeval_data,
    main,
)

# ---------------------------------------------------------------------------
# Fixture: mini-LongMemEval (Research #061 smoke scenario, extended)
# ---------------------------------------------------------------------------

SESSIONS = [
    {"session_id": "s1", "messages": [
        {"role": "user", "content": "I love hiking and rock climbing"},
        {"role": "assistant", "content": "That is great! I can recommend trails."},
    ]},
    {"session_id": "s2", "messages": [
        {"role": "user", "content": "Actually I switched from hiking to cycling"},
        {"role": "assistant", "content": "Got it! I will update your preferences to cycling."},
    ]},
    {"session_id": "s3", "messages": [
        {"role": "user", "content": "I am planning a cycling trip to Portland in April"},
        {"role": "assistant", "content": "Portland in April sounds lovely."},
    ]},
]

QUESTIONS = [
    {"id": "q_single-session-user_1",
     "question": "What activity does the user love?",
     "answer": "hiking and rock climbing"},
    {"id": "q_knowledge-update_1",
     "question": "What activity did the user switch to?",
     "answer": "cycling"},
    {"id": "q_temporal-reasoning_1",
     "question": "Where is the user planning a cycling trip?",
     "answer": "Portland"},
    # Abstention question: sushi never appears in any session.
    {"id": "q_sushi_abs",
     "question": "What did the user say about sushi?",
     "answer": "never mentioned"},
]

DATASET = [
    {"id": q["id"], "question": q["question"], "answer": q["answer"],
     "haystack_sessions": SESSIONS}
    for q in QUESTIONS
]


@pytest.fixture()
def adapter() -> LongMemEvalAdapter:
    a = LongMemEvalAdapter()
    a.ingest_sessions(SESSIONS)
    return a


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

class TestLoadData:
    def test_happy_path(self, tmp_path):
        p = tmp_path / "lme.json"
        p.write_text(json.dumps(DATASET), encoding="utf-8")
        data = load_longmemeval_data(p)
        assert len(data) == 4
        assert data[0]["question"].startswith("What activity")

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_longmemeval_data(tmp_path / "nope.json")

    def test_non_list_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"questions": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="expected JSON list"):
            load_longmemeval_data(p)

    def test_missing_question_key(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps([{"id": "x", "answer": "y"}]),
                     encoding="utf-8")
        with pytest.raises(ValueError, match="missing 'question'"):
            load_longmemeval_data(p)

    def test_limit_slices(self, tmp_path):
        p = tmp_path / "lme.json"
        p.write_text(json.dumps(DATASET), encoding="utf-8")
        assert len(load_longmemeval_data(p, limit=2)) == 2
        assert len(load_longmemeval_data(p, limit=0)) == 4
        assert len(load_longmemeval_data(p, limit=99)) == 4


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

class TestIngest:
    def test_stats(self):
        a = LongMemEvalAdapter()
        stats = a.ingest_sessions(SESSIONS)
        assert stats["sessions"] == 3
        assert stats["messages"] == 6
        assert stats["entities"] == 2  # Portland, April
        # 6 contains + 3 follows (one per session after msg 1) +
        # 4 mentioned_in (Portland x2, April x2)
        assert stats["edges"] == 13

    def test_bookkeeping_kinds(self, adapter):
        kinds = {info["kind"] for info in adapter._nodes.values()}
        assert kinds == {"session", "message", "entity"}
        assert len(adapter._messages) == 6

    def test_entity_dedup_across_sessions(self, adapter):
        # "Portland" appears in both s3 messages → ONE entity node,
        # TWO mentioned_in edges.
        assert "Portland" in adapter._entities
        portland_id = adapter._entities["Portland"]
        mentions = adapter.mg.conn.execute(
            "SELECT * FROM edges WHERE source=? AND relation='mentioned_in'",
            (portland_id,)).fetchall()
        assert len(mentions) == 2

    def test_non_entities_filtered(self, adapter):
        # Sentence-initial grammar words must not become entities.
        for bad in ("Actually", "Got", "That", "What"):
            assert bad not in adapter._entities

    def test_empty_sessions(self):
        a = LongMemEvalAdapter()
        stats = a.ingest_sessions([])
        assert stats == {"sessions": 0, "messages": 0,
                         "entities": 0, "edges": 0}

    def test_seq_monotonic(self, adapter):
        seqs = [info["seq"] for info in adapter._nodes.values()]
        assert seqs == sorted(seqs)

    def test_graph_edges_materialized(self, adapter):
        rows = adapter.mg.conn.execute(
            "SELECT relation, COUNT(*) c FROM edges GROUP BY relation"
        ).fetchall()
        by_rel = {r["relation"]: r["c"] for r in rows}
        assert by_rel == {"contains": 6, "follows": 3, "mentioned_in": 4}

# ---------------------------------------------------------------------------
# Keyword extraction & morphology matching
# ---------------------------------------------------------------------------

class TestKeywordMatching:
    def test_keywords_stopwords_and_possessive(self):
        kws = _keywords("What is the user's current preferred outdoor activity?")
        assert "user" not in kws            # possessive stripped → stopped
        assert "activity" in kws
        assert "what" not in kws and "the" not in kws

    def test_token_matches_inflections(self):
        assert _token_matches("switched", "switch")
        assert _token_matches("hiking", "hike")
        assert _token_matches("running", "run")
        assert _token_matches("loves", "love")
        assert _token_matches("love", "love")

    def test_token_matches_rejects_derivational(self):
        # THE Cycle 447 smoke-run bug: substring "love" ⊂ "lovely".
        assert not _token_matches("lovely", "love")
        assert not _token_matches("trainer", "train")
        assert not _token_matches("portlander", "portland")

    def test_keyword_hits_word_boundary(self):
        label = "Portland in April sounds lovely."
        assert _keyword_hits(label, ["love"]) == 0
        assert _keyword_hits(label, ["portland", "april"]) == 2
        assert _keyword_hits("Actually I switched from hiking to cycling",
                             ["switch"]) == 1


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class TestRetrieve:
    def test_context_contains_relevant_message(self, adapter):
        ctx, meta = adapter.retrieve_context(
            "Where is the user planning a cycling trip?")
        assert "Portland in April" in ctx
        assert meta["best_score"] >= 3
        assert meta["messages_retrieved"] >= 1

    def test_budget_respected(self):
        a = LongMemEvalAdapter(max_context_tokens=10)
        a.ingest_sessions(SESSIONS)
        ctx, meta = a.retrieve_context(
            "Where is the user planning a cycling trip?")
        assert meta["tokens_est"] <= 10 + abq._estimate_tokens(
            "[user] I am planning a cycling trip to Portland in April")
        # Budget forces at most the first (best) line.
        assert ctx.count("\n") == 0

    def test_meta_fields(self, adapter):
        _, meta = adapter.retrieve_context("hiking")
        for key in ("candidates_found", "messages_retrieved",
                    "best_score", "latency_ms", "tokens_est", "keywords"):
            assert key in meta

    def test_empty_graph(self):
        a = LongMemEvalAdapter()
        ctx, meta = a.retrieve_context("anything")
        assert ctx == ""
        assert meta["messages_retrieved"] == 0
        assert meta["tokens_est"] == 0

    def test_ppr_toggle(self, adapter):
        a_off = LongMemEvalAdapter(use_ppr=False)
        a_off.ingest_sessions(SESSIONS)
        q = "Where is the user planning a cycling trip?"
        ctx_on, meta_on = adapter.retrieve_context(q)
        ctx_off, meta_off = a_off.retrieve_context(q)
        # Both modes must retrieve the relevant message; PPR may only
        # widen the candidate set, never lose the answer.
        assert "Portland in April" in ctx_on
        assert "Portland in April" in ctx_off
        assert meta_on["candidates_found"] >= meta_off["candidates_found"]
        assert meta_off["messages_retrieved"] >= 1

    def test_no_relevant_keywords_still_safe(self, adapter):
        ctx, meta = adapter.retrieve_context("quantum entanglement theorem")
        assert isinstance(ctx, str)
        assert meta["best_score"] == 0


# ---------------------------------------------------------------------------
# Extractive answering + abstention
# ---------------------------------------------------------------------------

class TestAnswer:
    def test_single_session_recall(self, adapter):
        ans, meta = adapter.answer_extractive(
            "What activity does the user love?")
        assert ans == "I love hiking and rock climbing"
        assert not meta["abstained"]

    def test_knowledge_update_prefers_latest(self, adapter):
        ans, meta = adapter.answer_extractive(
            "What activity did the user switch to?")
        assert "switched from hiking to cycling" in ans
        assert not meta["abstained"]

    def test_abstention_on_unmentioned_topic(self, adapter):
        ans, meta = adapter.answer_extractive(
            "What did the user say about sushi?")
        assert ans == ABSTAIN_ANSWER
        assert meta["abstained"]
        # Abstaining still reports the (empty) context for hit scoring.
        assert meta["context"] == ""

    def test_abstain_score_gate_semantics(self, adapter):
        # The score gate only fires when SOMETHING was retrieved:
        # abstain_score=2 forces abstention on a 1-hit question …
        a = LongMemEvalAdapter(abstain_score=2)
        a.ingest_sessions(SESSIONS)
        ans, meta = a.answer_extractive("What activity does the user love?")
        assert meta["abstained"] and ans == ABSTAIN_ANSWER
        # … while abstain_score=0 lets the same 1-hit question through.
        b = LongMemEvalAdapter(abstain_score=0)
        b.ingest_sessions(SESSIONS)
        ans, meta = b.answer_extractive("What activity does the user love?")
        assert not meta["abstained"]
        assert ans == "I love hiking and rock climbing"

    def test_zero_candidates_always_abstains(self):
        # No retrieval → abstention regardless of the score gate.
        a = LongMemEvalAdapter(abstain_score=0)
        a.ingest_sessions(SESSIONS)
        ans, meta = a.answer_extractive(
            "What did the user say about sushi?")
        assert meta["abstained"] and ans == ABSTAIN_ANSWER

    def test_latest_session_wins_tie(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "s1", "messages": [
                {"role": "user", "content": "I love cycling"}]},
            {"session_id": "s2", "messages": [
                {"role": "user", "content": "I now love running instead"}]},
        ])
        ans, meta = a.answer_extractive(
            "What exercise does the user love?")
        assert ans == "I now love running instead"


# ---------------------------------------------------------------------------
# Evaluation loop
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_full_fixture(self, adapter):
        rep = adapter.evaluate(QUESTIONS)
        assert rep["total_questions"] == 4
        assert rep["overall_accuracy"] == 1.0
        assert rep["abstention_rate"] == 0.25
        assert rep["avg_tokens"] > 0

    def test_abs_question_correct_via_abstention(self, adapter):
        rep = adapter.evaluate([QUESTIONS[3]])
        row = rep["results"][0]
        assert row["abstained"] is True
        assert row["correct"] is True
        # abstention questions never count toward retrieval hits
        assert row["retrieval_hit"] is False

    def test_retrieval_hit_rate(self, adapter):
        rep = adapter.evaluate(QUESTIONS)
        assert rep["retrieval_hit_rate"] == 0.75  # 3 of 3 non-abs

    def test_category_summaries(self, adapter):
        rep = adapter.evaluate(QUESTIONS)
        cats = rep["categories"]
        assert cats["knowledge_update"]["total"] == 1
        assert cats["knowledge_update"]["accuracy"] == 1.0
        assert cats["temporal_reasoning"]["accuracy"] == 1.0
        # The _abs question classifies into single_session_user via the
        # heuristic path (its id carries no category suffix).
        assert cats["single_session_user"]["total"] == 2
        assert cats["single_session_user"]["accuracy"] == 1.0
        assert cats["single_session_user"]["abstention_rate"] == 0.5

    def test_limit(self, adapter):
        rep = adapter.evaluate(QUESTIONS, limit=2)
        assert rep["total_questions"] == 2

    def test_judge_fn_override(self, adapter):
        calls = []

        def judge(question, truth, predicted):
            calls.append(question)
            return True

        rep = adapter.evaluate(QUESTIONS[:1], judge_fn=judge)
        assert rep["overall_accuracy"] == 1.0
        assert len(calls) == 1

    def test_config_echoed(self, adapter):
        rep = adapter.evaluate(QUESTIONS[:1])
        assert rep["config"]["use_ppr"] is True
        assert rep["config"]["abstain_score"] == 1.0

    def test_result_rows_shape(self, adapter):
        rep = adapter.evaluate(QUESTIONS[:1])
        row = rep["results"][0]
        for key in ("question_id", "category", "question", "ground_truth",
                    "predicted_answer", "abstained", "correct",
                    "retrieval_hit", "latency_ms", "tokens_est",
                    "retrieval"):
            assert key in row

    def test_abstention_flag_field(self, adapter):
        dataset = [dict(QUESTIONS[3], id="plain_id", abstention=True)]
        rep = adapter.evaluate(dataset)
        assert rep["results"][0]["correct"] is True


# ---------------------------------------------------------------------------
# Judge + classification + prompts
# ---------------------------------------------------------------------------

class TestJudgeAndClassify:
    def test_exact_judge_containment(self):
        assert exact_judge("q", "cycling",
                           "Actually I switched from hiking to cycling")
        assert exact_judge("q", "Portland", "Portland")
        assert not exact_judge("q", "Portland", "I love hiking")

    def test_exact_judge_punctuation(self):
        assert exact_judge("q", "portland, or.", "Portland OR")

    def test_exact_judge_empty(self):
        assert not exact_judge("q", "", "anything")
        assert not exact_judge("q", "truth", "")

    @pytest.mark.parametrize("qid,suffix_cat", [
        ("x_single-session-user_1", "single_session_user"),
        ("x_single-session-assistant_1", "single_session_assistant"),
        ("x_single-session-preference_1", "single_session_preference"),
        ("x_multi-session_1", "multi_session"),
        ("x_knowledge-update_1", "knowledge_update"),
        ("x_temporal-reasoning_1", "temporal_reasoning"),
    ])
    def test_classify_by_suffix(self, qid, suffix_cat):
        assert LongMemEvalAdapter._classify_question("any", qid) == suffix_cat

    def test_classify_heuristics(self):
        c = LongMemEvalAdapter._classify_question
        assert c("Did the user change jobs?", "plain") == "knowledge_update"
        assert c("When did that happen?", "plain") == "temporal_reasoning"
        assert c("What did the assistant suggest?", "plain") == \
            "single_session_assistant"
        assert c("What does the user prefer on weekends?", "plain") == \
            "single_session_preference"
        assert c("Something", "plain") == "single_session_user"

    def test_answer_prompt(self):
        p = LongMemEvalAdapter.format_answer_prompt(
            "Q?", "[user] ctx", "2024-05-01")
        assert "Q?" in p and "[user] ctx" in p and "2024-05-01" in p
        assert "I don't know" in p

    def test_judge_prompt(self):
        p = LongMemEvalAdapter.format_judge_prompt("Q?", "truth", "pred")
        assert all(s in p for s in ("Q?", "truth", "pred", "'1'"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def test_main_writes_report(self, tmp_path, capsys):
        data = tmp_path / "lme.json"
        data.write_text(json.dumps(DATASET), encoding="utf-8")
        out = tmp_path / "report.json"
        rc = main(["--data", str(data), "--output", str(out)])
        assert rc == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert len(report["rows"]) == 4
        ids = {r["id"] for r in report["rows"]}
        assert "q_sushi_abs" in ids
        abst = [r for r in report["rows"] if r["abstained"]]
        assert len(abst) == 1
        assert report["config"]["use_ppr"] is True

    def test_main_limit(self, tmp_path, capsys):
        data = tmp_path / "lme.json"
        data.write_text(json.dumps(DATASET), encoding="utf-8")
        out = tmp_path / "report.json"
        rc = main(["--data", str(data), "--limit", "2",
                   "--output", str(out)])
        assert rc == 0
        assert len(json.loads(out.read_text(encoding="utf-8"))["rows"]) == 2

    def test_main_no_haystack_question(self, tmp_path, capsys):
        data = tmp_path / "lme.json"
        data.write_text(json.dumps([{"id": "q1", "question": "hiking?",
                                     "answer": "yes"}]),
                        encoding="utf-8")
        out = tmp_path / "report.json"
        rc = main(["--data", str(data), "--output", str(out)])
        assert rc == 0
        rows = json.loads(out.read_text(encoding="utf-8"))["rows"]
        # No haystack ingested → nothing retrieved → abstention.
        assert rows[0]["abstained"] is True
