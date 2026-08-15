"""Tests for the Cycle 448 entropy confidence gate — amg_bench_quality.

Builds on Cycle 447 (LongMemEval quality adapter). The abstention
gate now has a second axis: Shannon entropy over the keyword-hit
evidence distribution. The gate fires on **weak scattered evidence**
(best candidate <= weak score AND flat distribution AND ≥3
candidates) — the regime where the extractive answer is a guess.

Protected behaviors (must NOT regress, tested below):
* two-way weak ties keep the C437/C447 ``-seq`` recency semantics
  (latest wins — the knowledge-update signature);
* strong ties never fire the gate (knowledge-update protection);
* ``abstain_entropy=None`` reproduces Cycle 447 behavior exactly.

``sweep_abstention()`` reuses ONE retrieval per question and gates at
every threshold — the abstention-tuning entry point (C447 Next
Step #2).
"""

import json
import math

import pytest

import amg_bench_quality as abq
from amg_bench_quality import (
    ABSTAIN_ANSWER,
    LongMemEvalAdapter,
    entropy_gate_fires,
    exact_judge,
    main,
    score_confidence,
)
from test_amg_bench_quality import DATASET, QUESTIONS, SESSIONS

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Three UNRELATED one-hit mentions — flat weak evidence [1, 1, 1].
AMBIG_SESSIONS = [
    {"session_id": "a1", "messages": [
        {"role": "user", "content": "The cafe on Fifth street has good espresso"}]},
    {"session_id": "a2", "messages": [
        {"role": "user", "content": "I often read at the cafe near the library"}]},
    {"session_id": "a3", "messages": [
        {"role": "user", "content": "The cafe by the train station closes early"}]},
]

AMBIG_Q = {"id": "q_cafe_abs",
           "question": "Tell me about the cafe",
           "answer": "not specified"}

# Old/new pair, 3 hits each — strong tie: recency must resolve it.
STRONG_TIE_SESSIONS = [
    {"session_id": "s_old", "messages": [
        {"role": "user", "content": "My hobby of gardening keeps me busy"}]},
    {"session_id": "s_new", "messages": [
        {"role": "user", "content": "My new hobby of pottery keeps me busy"}]},
]

STRONG_TIE_Q = "What hobby keeps me busy?"

# [3, 3, 1] evidence — mid-flat (norm_entropy ≈ 0.914): fires at
# threshold 0.8 but not 0.95 when the weak bar is raised to 3.
# Question keywords {hobby, keeps, busy} hit the old/new pair three
# times each and the chess message once.
MID_SESSIONS = STRONG_TIE_SESSIONS + [
    {"session_id": "s_other", "messages": [
        {"role": "user", "content": "My weekend hobby is chess"}]},
]

MID_Q = "What hobby keeps me busy?"


@pytest.fixture()
def adapter() -> LongMemEvalAdapter:
    a = LongMemEvalAdapter()
    a.ingest_sessions(SESSIONS)
    return a


@pytest.fixture()
def ambig_adapter() -> LongMemEvalAdapter:
    a = LongMemEvalAdapter()
    a.ingest_sessions(AMBIG_SESSIONS)
    return a


# ---------------------------------------------------------------------------
# score_confidence — pure entropy math
# ---------------------------------------------------------------------------

class TestScoreConfidence:
    def test_empty(self):
        c = score_confidence([])
        assert c == {"best": 0, "evidence": 0, "entropy": 0.0,
                     "norm_entropy": 0.0, "margin": 0.0}

    def test_single_candidate_zero_entropy_full_margin(self):
        c = score_confidence([3])
        assert c["best"] == 3 and c["evidence"] == 1
        assert c["entropy"] == 0.0 and c["norm_entropy"] == 0.0
        assert c["margin"] == 1.0

    def test_uniform_is_maximally_flat(self):
        c = score_confidence([1, 1, 1])
        assert c["entropy"] == pytest.approx(math.log2(3))
        assert c["norm_entropy"] == pytest.approx(1.0)
        assert c["margin"] == pytest.approx(0.0)

    def test_dominant_candidate(self):
        c = score_confidence([5, 1, 1])
        assert c["best"] == 5 and c["evidence"] == 3
        expected_h = (-(5 / 7) * math.log2(5 / 7)
                      - 2 * (1 / 7) * math.log2(1 / 7))
        assert c["entropy"] == pytest.approx(expected_h)
        assert c["norm_entropy"] == pytest.approx(expected_h / math.log2(3))
        assert c["norm_entropy"] < 1.0
        assert c["margin"] == pytest.approx(0.8)

    def test_two_way_tie_is_flat(self):
        c = score_confidence([2, 2])
        assert c["norm_entropy"] == pytest.approx(1.0)
        assert c["margin"] == pytest.approx(0.0)

    def test_zero_scores_are_not_evidence(self):
        assert score_confidence([0, 0, 3]) == score_confidence([3])
        assert score_confidence([0, 0])["evidence"] == 0

    def test_order_insensitive(self):
        assert score_confidence([1, 5, 1]) == score_confidence([5, 1, 1])

    def test_flat_distributes_more_entropy_than_dominant(self):
        flat = score_confidence([1, 1, 1, 1])["norm_entropy"]
        dom = score_confidence([4, 1, 1, 1])["norm_entropy"]
        assert flat > dom


# ---------------------------------------------------------------------------
# entropy_gate_fires — gate predicate
# ---------------------------------------------------------------------------

class TestEntropyGatePredicate:
    def test_none_disables_gate(self):
        flat_weak = score_confidence([1, 1, 1])
        assert entropy_gate_fires(flat_weak, None, 1) is False

    def test_two_candidates_never_fire(self):
        # Weak two-way tie → recency semantics, not ambiguity.
        tie2 = score_confidence([1, 1])
        assert entropy_gate_fires(tie2, 0.95, 1) is False

    def test_weak_flat_three_fires(self):
        flat = score_confidence([1, 1, 1])
        assert entropy_gate_fires(flat, 0.95, 1) is True
        assert entropy_gate_fires(flat, 1.0, 1) is True

    def test_strong_flat_never_fires(self):
        # best > weak score → knowledge-update tie, recency resolves.
        strong = score_confidence([2, 2, 2])
        assert entropy_gate_fires(strong, 0.95, 1) is False
        assert entropy_gate_fires(strong, 1.0, 1) is False

    def test_threshold_above_one_unreachable(self):
        flat = score_confidence([1, 1, 1])
        assert entropy_gate_fires(flat, 1.01, 1) is False

    def test_weak_bar_change_flips_strong_flat(self):
        strong = score_confidence([2, 2, 2])
        assert entropy_gate_fires(strong, 1.0, 2) is True


# ---------------------------------------------------------------------------
# Adapter gate behavior
# ---------------------------------------------------------------------------

class TestAdapterEntropyGate:
    def test_weak_scattered_abstains_by_default(self, ambig_adapter):
        ans, meta = ambig_adapter.answer_extractive(AMBIG_Q["question"])
        assert ans == ABSTAIN_ANSWER
        assert meta["abstained"] is True
        assert meta["gate"] == "entropy"

    def test_gate_disabled_answers_latest_c447_behavior(self, ambig_adapter):
        ambig_adapter.abstain_entropy = None
        ans, meta = ambig_adapter.answer_extractive(AMBIG_Q["question"])
        assert meta["abstained"] is False and meta["gate"] == "answer"
        # -seq tie-break → latest of the three one-hit mentions.
        assert ans == "The cafe by the train station closes early"

    def test_two_way_weak_tie_keeps_recency_semantics(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions([
            {"session_id": "t1", "messages": [
                {"role": "user", "content": "I love cycling"}]},
            {"session_id": "t2", "messages": [
                {"role": "user", "content": "I now love running instead"}]},
        ])
        ans, meta = a.answer_extractive("What exercise does the user love?")
        assert meta["abstained"] is False and meta["gate"] == "answer"
        assert ans == "I now love running instead"

    def test_strong_tie_knowledge_update_unaffected(self):
        a = LongMemEvalAdapter()
        a.ingest_sessions(STRONG_TIE_SESSIONS)
        ans, meta = a.answer_extractive(STRONG_TIE_Q)
        assert meta["abstained"] is False
        assert ans == "My new hobby of pottery keeps me busy"  # latest

    def test_confidence_telemetry_in_meta(self, adapter):
        _, meta = adapter.answer_extractive("What activity does the user love?")
        conf = meta["confidence"]
        assert set(conf) == {"best", "evidence", "entropy",
                             "norm_entropy", "margin"}
        assert conf["best"] >= 1
        assert meta["gate"] == "answer"

    def test_deterministic_gate_decision(self, ambig_adapter):
        a1 = ambig_adapter.answer_extractive(AMBIG_Q["question"])
        a2 = ambig_adapter.answer_extractive(AMBIG_Q["question"])
        assert a1[0] == a2[0]
        assert a1[1]["gate"] == a2[1]["gate"]
        assert a1[1]["abstained"] == a2[1]["abstained"]


# ---------------------------------------------------------------------------
# evaluate() with the entropy gate
# ---------------------------------------------------------------------------

class TestEvaluateWithEntropyGate:
    def test_c447_fixture_unchanged_with_default_gate(self, adapter):
        rep = adapter.evaluate(QUESTIONS)
        assert rep["overall_accuracy"] == 1.0
        assert rep["abstention_rate"] == 0.25
        assert rep["config"]["abstain_entropy"] == 0.95

    def test_ambiguity_abs_improves_with_gate(self, ambig_adapter):
        ambig_adapter.abstain_entropy = None  # C447 baseline
        off = ambig_adapter.evaluate([AMBIG_Q])
        assert off["results"][0]["correct"] is False  # guessed → wrong
        ambig_adapter.abstain_entropy = 0.95  # Cycle 448 default
        on = ambig_adapter.evaluate([AMBIG_Q])
        assert on["results"][0]["abstained"] is True
        assert on["results"][0]["correct"] is True

    def test_result_rows_carry_entropy_telemetry(self, ambig_adapter):
        rep = ambig_adapter.evaluate([AMBIG_Q])
        r = rep["results"][0]["retrieval"]
        assert r["gate"] == "entropy"
        assert r["norm_entropy"] == pytest.approx(1.0)
        assert r["margin"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# sweep_abstention — threshold tuning on one retrieval
# ---------------------------------------------------------------------------

class TestSweepAbstention:
    @pytest.fixture()
    def mid_adapter(self):
        a = LongMemEvalAdapter(entropy_weak_score=3)
        a.ingest_sessions(MID_SESSIONS)
        return a

    def test_structure_and_off_baseline(self, mid_adapter):
        dataset = [{"id": "q_mid_1", "question": MID_Q,
                    "answer": "My new hobby of pottery keeps me busy"}]
        sw = mid_adapter.sweep_abstention(dataset,
                                          entropies=[None, 0.95, 0.8])
        assert sw["thresholds"] == ["None", "0.95", "0.8"]
        assert set(sw["summary"]) == {"None", "0.95", "0.8"}
        assert len(sw["rows"]) == 1
        # Gate off → answered (correct).
        assert sw["rows"][0]["abstained"]["None"] is False
        assert sw["rows"][0]["correct"]["None"] is True

    def test_thresholds_discriminate(self, mid_adapter):
        # [3,3,1] evidence → norm_entropy ≈ 0.914: fires at 0.8,
        # not at 0.95 (weak bar = 3 makes the strong tie eligible).
        dataset = [{"id": "q_mid_1", "question": MID_Q,
                    "answer": "My new hobby of pottery keeps me busy"}]
        sw = mid_adapter.sweep_abstention(dataset,
                                          entropies=[0.95, 0.8])
        row = sw["rows"][0]
        assert row["abstained"]["0.95"] is False
        assert row["abstained"]["0.8"] is True

    def test_abstention_monotone_in_threshold(self):
        a = LongMemEvalAdapter(entropy_weak_score=2)
        a.ingest_sessions(AMBIG_SESSIONS + MID_SESSIONS)
        dataset = [
            {"id": "q_cafe_abs", "question": "Tell me about the cafe",
             "answer": "not specified"},
            {"id": "q_mid_1", "question": MID_Q,
             "answer": "My new hobby of pottery keeps me busy"},
        ]
        thresholds = [None, 0.95, 0.9, 0.8, 0.5]
        sw = a.sweep_abstention(dataset, entropies=thresholds)
        rates = [sw["summary"][t]["abstention_rate"] for t in sw["thresholds"]]
        # Lowering the threshold can only widen the abstention set.
        assert all(x <= y for x, y in zip(rates, rates[1:])), rates

    def test_equivalent_to_fresh_evaluate_per_threshold(self):
        dataset = DATASET + [{**AMBIG_Q, "haystack_sessions": AMBIG_SESSIONS}]
        thresholds = [None, 0.95, 1.0]
        shared = LongMemEvalAdapter()
        shared.ingest_sessions(SESSIONS + AMBIG_SESSIONS)
        sw = shared.sweep_abstention(dataset, entropies=thresholds)
        for thr, lab in zip(thresholds, sw["thresholds"]):
            fresh = LongMemEvalAdapter(abstain_entropy=thr)
            fresh.ingest_sessions(SESSIONS + AMBIG_SESSIONS)
            rep = fresh.evaluate(dataset)
            assert sw["summary"][lab]["accuracy"] == pytest.approx(
                rep["overall_accuracy"]), f"threshold {lab}"

    def test_abs_scoring_in_sweep(self, ambig_adapter):
        sw = ambig_adapter.sweep_abstention([AMBIG_Q],
                                            entropies=[None, 0.95])
        row = sw["rows"][0]
        assert row["correct"]["None"] is False   # answered → wrong
        assert row["correct"]["0.95"] is True    # abstained → correct
        assert sw["summary"]["0.95"]["accuracy"] == 1.0


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------

class TestCliEntropyFlags:
    def _write_data(self, tmp_path):
        data = tmp_path / "lme.json"
        data.write_text(json.dumps(
            DATASET + [{**AMBIG_Q, "haystack_sessions": AMBIG_SESSIONS}]),
            encoding="utf-8")
        return data

    def test_default_entropy_gate_on(self, tmp_path, capsys):
        data = self._write_data(tmp_path)
        out = tmp_path / "r1.json"
        assert main(["--data", str(data), "--output", str(out)]) == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        # Ambiguity question abstains under the default 0.95 gate …
        cafe = [r for r in report["rows"] if r["id"] == "q_cafe_abs"][0]
        assert cafe["abstained"] is True
        # … while the four C447 questions behave identically.
        assert sum(r["abstained"] for r in report["rows"]) == 2
        assert report["config"]["abstain_entropy"] == 0.95

    def test_negative_flag_disables_gate(self, tmp_path, capsys):
        data = self._write_data(tmp_path)
        out = tmp_path / "r2.json"
        rc = main(["--data", str(data), "--output", str(out),
                   "--abstain-entropy", "-1"])
        assert rc == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        cafe = [r for r in report["rows"] if r["id"] == "q_cafe_abs"][0]
        assert cafe["abstained"] is False  # C447 behavior restored
        assert report["config"]["abstain_entropy"] is None

    def test_entropy_weak_flag_accepted(self, tmp_path, capsys):
        data = self._write_data(tmp_path)
        out = tmp_path / "r3.json"
        rc = main(["--data", str(data), "--output", str(out),
                   "--entropy-weak", "1", "--abstain-entropy", "0.9"])
        assert rc == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["config"]["entropy_weak_score"] == 1
        assert report["config"]["abstain_entropy"] == 0.9
