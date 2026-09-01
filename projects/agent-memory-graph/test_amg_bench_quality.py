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
                         "entities": 0, "edges": 0,
                         "chunks_embedded": 0}   # Cycle 512 key

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
# C466 — honest attribution: question_id fallback + authoritative
# question_type/category (heuristics mislabeled full-500 LME_s 419/500
# as single_session_user; temporal 49 vs true 133)
# ---------------------------------------------------------------------------

class TestHonestAttribution:
    def test_question_id_fallback(self, adapter):
        """LongMemEval-cleaned ships question_id (no id) — must reach the
        result row instead of the loop index."""
        dataset = [dict(QUESTIONS[0], question_id="gpt4_59149c77")]
        del dataset[0]["id"]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["question_id"] == "gpt4_59149c77"

    def test_id_still_wins_over_question_id(self, adapter):
        dataset = [dict(QUESTIONS[0], question_id="loser")]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["question_id"] != "loser"  # explicit id contract kept

    def test_question_type_hyphen_maps_canonical(self, adapter):
        dataset = [dict(QUESTIONS[0], question_type="temporal-reasoning")]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["category"] == "temporal_reasoning"

    def test_question_type_canonical_kept(self, adapter):
        dataset = [dict(QUESTIONS[0], question_type="knowledge_update")]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["category"] == "knowledge_update"

    def test_category_field_also_honored(self, adapter):
        dataset = [dict(QUESTIONS[0], category="multi-session")]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["category"] == "multi_session"

    def test_unknown_type_passes_through_honestly(self, adapter):
        """An unseen type stays itself — mislabeling via heuristics would
        poison calibration_by_category."""
        dataset = [dict(QUESTIONS[0], question_type="hybrid-events")]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["category"] == "hybrid-events"

    def test_no_type_falls_back_to_heuristics(self, adapter):
        dataset = [dict(QUESTIONS[0])]
        row = adapter.evaluate(dataset)["results"][0]
        assert row["category"] == "single_session_user"  # default path

    def test_heuristic_overrides_respected(self, adapter):
        """Explicit type beats question-form heuristics even when the
        question text contains trigger words."""
        q = dict(QUESTIONS[0], question="When did I update my preference?",
                 question_type="single-session-preference")
        row = adapter.evaluate([q])["results"][0]
        assert row["category"] == "single_session_preference"


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


# ── Cycle 506: embedding side-channel (Research #083) ──────────────
# Hermetic stub engine — deterministic 4-dim vectors, no model
# downloads, no numpy. The probe tier labels survive as strings.


class _StubEngine:
    """Deterministic stub: sums hand-picked keyword direction vectors
    and L2-normalizes (mirrors SidechannelEngine.normalize contract)."""

    tier = "stub"

    def __init__(self, directions):
        self.directions = directions

    def embed(self, texts):
        out = []
        for text in texts:
            vec = [0.0, 0.0, 0.0, 0.0]
            for word, d in self.directions.items():
                if word in text:
                    for i in range(4):
                        vec[i] += d[i]
            norm = sum(x * x for x in vec) ** 0.5
            out.append([x / norm for x in vec] if norm > 0 else vec)
        return out


SIDECAR_SESSIONS = [
    {"session_id": "s_cooking", "messages": [
        {"role": "user", "content": "pasta sauce simmering tonight"},
        {"role": "assistant", "content": "olive oil and garlic basics"}]},
    {"session_id": "s_gear", "messages": [
        {"role": "user", "content": "stratocaster versus les paul tones"},
        {"role": "assistant",
         "content": "the single coil chime suits your playing"}]},
]


class TestChunkSessionText:
    def test_short_text_single_chunk(self):
        assert abq.chunk_session_text("hello world") == ["hello world"]

    def test_exact_150_word_boundary(self):
        words = [f"w{i}" for i in range(300)]
        chunks = abq.chunk_session_text(" ".join(words))
        assert len(chunks) == 2
        assert all(len(c.split()) == 150 for c in chunks)
        assert chunks[0].startswith("w0 ")

    def test_max_chunks_cap(self):
        words = [f"w{i}" for i in range(1000)]
        chunks = abq.chunk_session_text(" ".join(words))
        assert len(chunks) == abq.SIDECHANNEL_MAX_CHUNKS

    def test_empty(self):
        assert abq.chunk_session_text("") == []


class TestSidechannelForm:
    def test_advice_request_is_embed(self):
        assert abq.sidechannel_form(
            "any recommendations for a music store visit?") == "embed"

    def test_assistant_recall_is_hybrid(self):
        # pref_form must NOT claim recall forms (C498 census parity).
        assert abq.sidechannel_form(
            "remind me what you recommended for dinner") == "hybrid"

    def test_other_forms_untouched(self):
        assert abq.sidechannel_form(
            "when did the user start the new job?") is None


class TestSessionEmbeddingScores:
    def test_chunk_max_beats_flat_mediocre(self):
        # One on-topic chunk among noise must win via chunk-max.
        engine = _StubEngine({"stratocaster": [1, 0, 0, 0],
                              "pasta": [0, 1, 0, 0]})
        noise = " ".join(f"filler{i}" for i in range(400)) + \
            " pasta sauce simmering"  # session A: off-topic max
        sessions = [
            {"session_id": "a", "turns": [
                {"role": "user", "content": noise}]},
            {"session_id": "b", "turns": [
                {"role": "user", "content": "stratocaster versus les paul"}]},
        ]
        scores = abq.session_embedding_scores(
            "stratocaster advice", sessions, engine)
        assert scores["b"] > scores["a"]
        assert 0.0 <= scores["a"] <= 1.0

    def test_empty_sessions(self):
        engine = _StubEngine({})
        assert abq.session_embedding_scores("q", [], engine) == {}


class TestProbeSidechannelEngine:
    def test_degrades_to_none_and_caches(self, monkeypatch):
        calls = {"n": 0}

        def _miss():
            calls["n"] += 1
            return None

        monkeypatch.setattr(abq, "_probe_fastembed", _miss)
        monkeypatch.setattr(abq, "_probe_model2vec", _miss)
        monkeypatch.setattr(abq, "_SIDECHANNEL_PROBE", [])
        assert abq.probe_sidechannel_engine() is None
        assert abq.probe_sidechannel_engine() is None
        assert calls["n"] == 2  # one probe per tier, then cached

    def test_quality_tier_wins_over_fast(self, monkeypatch):
        stub = abq.SidechannelEngine(lambda texts: [[1, 0]] * len(texts),
                                     "quality")
        monkeypatch.setattr(abq, "_SIDECHANNEL_PROBE", [])
        monkeypatch.setattr(abq, "_probe_fastembed", lambda: stub)
        monkeypatch.setattr(abq, "_probe_model2vec",
                            lambda: pytest.fail("must not be reached"))
        assert abq.probe_sidechannel_engine() is stub


class TestRetrieveContextSidechannel:
    def _adapter(self, **kw):
        a = LongMemEvalAdapter(max_context_tokens=2000, **kw)
        a.ingest_sessions(SIDECAR_SESSIONS)
        return a

    def _stub(self):
        return _StubEngine({"guitar": [1, 0, 0, 0],
                            "stratocaster": [1, 0, 0, 0],
                            "pasta": [0, 1, 0, 0]})

    def _install(self, adapter, engine):
        adapter.sidechannel = True
        adapter._side_engine = engine
        adapter._side_probed = True

    def test_embed_switch_pulls_lexically_unreachable_session(self):
        # Lexical bridge is closed: the evidence session shares ZERO
        # question keywords (Research #083 arm F: unique-best 4/30).
        q = "any recommendations for guitar shopping?"
        base = self._adapter()
        ctx0, meta0 = base.retrieve_context(q)
        assert "stratocaster" not in ctx0
        assert meta0.get("sidechannel") is None

        adapter = self._adapter()
        self._install(adapter, self._stub())
        ctx, meta = adapter.retrieve_context(q)
        assert meta.get("sidechannel") == "embed"
        assert "stratocaster" in ctx

    def test_hybrid_rerank_prefers_semantic_session(self):
        q = "remind me what you suggested about guitar tone"
        # Both sessions hold an assistant line with equal lexical
        # distance; embedding must order the guitar session first.
        adapter = self._adapter()
        self._install(adapter, self._stub())
        ctx, meta = adapter.retrieve_context(q)
        assert meta.get("sidechannel") == "hybrid"
        first_line = ctx.splitlines()[0]
        # The guitar session wins the re-rank; within it the lexical
        # tie-break may legitimately prefer the user line ("tone"
        # keyword hit) — hybrid reorders SESSIONS, not intra-session
        # lexical evidence.
        assert "stratocaster" in first_line

    def test_disabled_flag_keeps_lexical_path(self):
        q = "any recommendations for guitar shopping?"
        adapter = self._adapter(sidechannel=False)
        ctx, meta = adapter.retrieve_context(q)
        assert "stratocaster" not in ctx
        assert meta.get("sidechannel") is None

    def test_non_gated_form_ignores_engine(self):
        adapter = self._adapter()
        self._install(adapter, self._stub())
        ctx, meta = adapter.retrieve_context("pasta sauce details")
        assert meta.get("sidechannel") is None


class TestNegativeExistence:
    """C513: negative-existence abstention (#087 ABS_Q lineage).

    LME _abs near-miss traps: the question presupposes an entity
    whose confusable sibling IS in the corpus — retrieval is
    strong-but-tangent and everything downstream fabricates."""

    def test_near_miss_entity_fires(self):
        # Shinjuku asked, Harajuku present (the trap's driver).
        q = "How long have I been living in my current apartment in Shinjuku?"
        text = "I moved to Harajuku last April. The commute is fine."
        assert abq.negative_existence(q, text) == "Shinjuku"

    def test_present_entity_does_not_fire(self):
        q = "How long have I been living in Harajuku?"
        text = "I moved to Harajuku last April."
        assert abq.negative_existence(q, text) is None

    def test_quoted_title_not_an_artifact(self):
        # The 4th display-layer-bug family instance: quoted-phrase
        # regexes fabricate spans across apostrophes. Bare tokens
        # must match 'Ibotta' in the corpus without the quotes.
        q = "How many weeks ago did I start using the cashback app 'Ibotta'?"
        text = "I started using Ibotta for grocery cashback."
        assert abq.negative_existence(q, text) is None

    def test_possessive_apostrophes_dont_fabricate(self):
        q = "When was Jessica's wedding compared to Michael's birthday?"
        text = ("Jessica told me about her wedding plans. "
                "Michael's birthday party is next month.")
        assert abq.negative_existence(q, text) is None

    def test_months_and_weekdays_are_anchors_not_entities(self):
        q = "How many books did I finish reading in December?"
        text = "I finished two novels in late autumn."
        assert abq.negative_existence(q, text) is None

    def test_word_boundary_not_substring(self):
        # 'Spain' must not match 'Spainard'-like superstrings.
        q = "Did I ever visit Spain?"
        text = "We toured the Spainard vineyards last summer."
        assert abq.negative_existence(q, text) == "Spain"

    def test_case_insensitive_presence(self):
        q = "What did I think of the Porsche?"
        text = "The porsche handles beautifully on mountain roads."
        assert abq.negative_existence(q, text) is None

    def test_first_missing_entity_wins(self):
        q = ("Which did I attend first, my Paris trip or the "
             "Berlin conference?")
        text = "My Paris trip was wonderful."
        assert abq.negative_existence(q, text) == "Berlin"

    def test_no_entities_no_fire(self):
        q = "How many days did it take for my order to arrive?"
        text = "no proper nouns here at all"
        assert abq.negative_existence(q, text) is None

    def test_initial_word_ignored(self):
        # First token capitalized by sentence position, not entity.
        q = "Sacramento is where I booked what?"
        text = "I booked a hotel in San Francisco."
        assert abq.negative_existence(q, text) is None


class TestNegativeExistenceIntegration:
    _SESSIONS = [
        {"session_id": "s1", "messages": [
            {"role": "user", "content":
             "I've been living in Harajuku since last April and "
             "really enjoy the neighborhood."}]},
        {"session_id": "s2", "messages": [
            {"role": "user", "content":
             "Thinking about moving, but rent anywhere is pricey."}]},
    ]

    def _run(self, question, neg_exist=True):
        a = LongMemEvalAdapter(max_context_tokens=2000,
                               neg_exist=neg_exist)
        a.ingest_sessions(self._SESSIONS)
        pred, meta = a.answer_extractive(question, "")
        return pred, meta

    def test_gate_abstains_and_reports_entity(self):
        pred, meta = self._run(
            "How long have I been living in my Shinjuku apartment?")
        assert pred == abq.ABSTAIN_ANSWER
        assert meta["gate"] == "neg_exist"
        assert meta["abstained"] is True
        assert meta["neg_exist_entity"] == "Shinjuku"

    def test_flag_off_falls_through(self):
        pred, meta = self._run(
            "How long have I been living in my Shinjuku apartment?",
            neg_exist=False)
        assert meta.get("gate") != "neg_exist"

    def test_present_entity_unaffected(self):
        pred, meta = self._run(
            "How long have I been living in Harajuku?")
        assert meta.get("gate") != "neg_exist"

    def test_is_abs_scores_abstain_correct(self):
        # evaluate() contract: abstain on an _abs question = correct.
        a = LongMemEvalAdapter(max_context_tokens=2000)
        a.ingest_sessions(self._SESSIONS)
        rep = a.evaluate([{
            "question_id": "x_abs",
            "question": "How long have I lived in my Shinjuku place?",
            "answer": "The information provided is not enough.",
            "haystack_sessions": self._SESSIONS}])
        r = rep["results"][0]
        assert r["abstained"]
        assert r["correct"] is True

    def test_third_person_subject_exempt(self):
        # LoCoMo form: subject's own lines never self-name — absence
        # of "Caroline" in her own dialogue is normal, not a trap.
        q = "What class did Caroline start?"
        text = "I started a pottery class last month."
        assert abq.negative_existence(q, text) is None

    def test_first_person_required_to_fire(self):
        q = "How long has Caroline lived in Shinjuku?"
        text = "I moved to Harajuku last April."
        assert abq.negative_existence(q, text) is None


# ── C536: ordinal-item face ("the fifth bottle you recommended") ───

class TestOrdinalItemFace:
    GT_NODE = (
        "To make the widest variety of gin-based cocktails, I would "
        "recommend purchasing the following five bottles of liquors, "
        "aperitifs, and digestifs:\n"
        "1. Sweet Vermouth: Sweet vermouth is a fortified wine used in "
        "classic cocktails like the Negroni.\n"
        "2. Dry Vermouth: Dry vermouth is also a fortified wine.\n"
        "3. Campari: Campari is a bitter aperitif.\n"
        "4. Elderflower Liqueur: Elderflower liqueur is a sweet and "
        "floral liqueur for gin-based cocktails.\n"
        "5. Absinthe: Absinthe is a strong herbal liqueur used in "
        "classic cocktails like the Sazerac."
    )

    @staticmethod
    def _nodes(labels):
        return {f"n{i}": {"role": "assistant", "label": lab,
                           "session_id": f"s{i}"}
                for i, lab in enumerate(labels)}

    def test_form_detector_positive(self):
        assert abq.ordinal_item_form(
            "You recommended five bottles for gin cocktails. What was "
            "the fifth bottle?") is True
        assert abq.ordinal_item_form(
            "Can you remind me what the 7th work from home job you "
            "listed was?") is True

    def test_form_detector_negative(self):
        # narrative "first" with no you-addressed list act
        assert abq.ordinal_item_form(
            "First I helped my friend, then I fixed the fence.") is False
        # no ordinal word at all
        assert abq.ordinal_item_form(
            "You recommended a restaurant in Rome. What was its name?"
        ) is False
        # ordinal but user's own act, not the assistant's
        assert abq.ordinal_item_form(
            "What was the first city I visited on my trip?") is False

    def test_answer_ordinal_returns_head_term(self):
        nodes = self._nodes(["I talked about cocktails once.",
                             self.GT_NODE])
        ans, detail = abq.answer_ordinal(
            "What was the fifth bottle you recommended for gin "
            "cocktails?", nodes)
        assert ans == "Absinthe"
        assert detail["ordinal"] == 5
        assert detail["session_id"] == "s1"

    def test_answer_ordinal_prefers_relevant_node(self):
        # decoy with a "5." item but no question-keyword relevance
        decoy = ("Pack list:\n5. Tent: bring the rain fly too.")
        nodes = self._nodes([decoy, self.GT_NODE])
        ans, _ = abq.answer_ordinal(
            "What was the fifth bottle you recommended for gin "
            "cocktails?", nodes)
        assert ans == "Absinthe"

    def test_answer_ordinal_none_when_no_item(self):
        nodes = self._nodes(["I would recommend some bottles of "
                             "vermouth for cocktails, five or so."])
        ans, detail = abq.answer_ordinal(
            "What was the fifth bottle you recommended?", nodes)
        assert ans is None

    def test_extractive_gate_does_not_wire_ordinal_face(self):
        # C536 census-negative pin: the tight form detector fires
        # (population 3/500, all frozen-wrong), the mechanics work on
        # clean fixtures, but the gate stays UNWIRED — frozen-500
        # forensics showed node-level lexical joins hit adversarial
        # twin lists (3249768e, kh tied 12/12) and bare GT lists die
        # under relevance floors (1903aded, kh=1). Wiring this face
        # would have banked "Triple Sec"/"Encourage Questions" as
        # answers. Unwiring = pipeline byte-identical on frozen 500.
        ad = abq.LongMemEvalAdapter()
        ad.ingest_sessions([{
            "session_id": "s1",
            "messages": [
                {"role": "user", "content":
                 "I'm building a cocktail bar. Which bottles should I "
                 "buy to make the widest variety of gin-based "
                 "cocktails?"},
                {"role": "assistant", "content": self.GT_NODE},
            ],
        }], session_dates=None)
        q = ("You recommended five bottles for gin cocktails. What "
             "was the fifth bottle?")
        assert abq.ordinal_item_form(q) is True   # detector fires...
        ans, meta = ad.answer_extractive(q, "")
        assert meta.get("gate") != "ordinal"      # ...but gate never claims
        assert "ordinal" not in meta
