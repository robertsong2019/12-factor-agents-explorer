"""Cycle 520 tests — risk-coverage / selective-prediction metrics.

Research #089 ported into amg_bench_quality: AURC / E-AURC /
Risk@coverage upgrade the abstention stack from one operating point
per A/B to a full curve evaluation. Oracle cross-check is mandatory
(the #089 lesson: a direction-convention bug in a self-written
evaluator makes Gate comparisons invert silently).
"""
import math
from types import SimpleNamespace

import pytest

from amg_bench_quality import (
    _aurc,
    _risk_coverage_curve,
    risk_at_coverage,
    risk_coverage_report,
    run_eval,
)


def _row(score, correct, category="single_session_user", abstained=False):
    return {"score": score, "correct": correct, "abstained": abstained,
            "category": category}


def _result_row(norm_entropy, correct, category="multi_session",
                abstained=False):
    """Serialized report-row shape (run_eval ``results`` entries)."""
    return {"correct": correct, "abstained": abstained, "category": category,
            "retrieval": {"norm_entropy": norm_entropy, "margin": 0.5}}


# ── Core curve math ─────────────────────────────────────────────────

class TestCurveMath:
    def test_oracle_cross_check_eaurc_zero(self):
        """All-correct ranked strictly above all wrong → E-AURC = 0.

        This is the #089 oracle closed-form cross-check: AURC of the
        perfect ordering must equal k²/2n² exactly (trapezoid integral
        of the same arrangement), else the closed form or the curve is
        wrong and every E-AURC reading inverts.
        """
        scored = [_row(0.9, True) for _ in range(6)] + \
                 [_row(0.1, False) for _ in range(4)]
        pts = _risk_coverage_curve(scored)
        n, k = 10, 4
        # hand-integrated trapezoid: 1/140 + 11/560 + 7/240 + 11/300
        # = 389/4200 — the k²/2n² "closed form" from #089 notes is its
        # small-k Taylor approximation (0.0800 vs exact 0.0926); it
        # UNDERESTIMATES, flattering every E-AURC it touches
        assert _aurc(pts) == pytest.approx(389 / 4200)
        assert _aurc(pts) - k * k / (2 * n * n) == pytest.approx(0.0126190, abs=1e-6)
        rep = risk_coverage_report(
            [_result_row(1 - s["score"], s["correct"]) for s in scored])
        assert abs(rep["e_aurc"]) < 1e-9

    def test_anti_oracle_positive_eaurc(self):
        # wrong answers ranked ABOVE correct ones → strictly worse
        # than oracle ordering
        scored = [_row(0.9, False) for _ in range(4)] + \
                 [_row(0.1, True) for _ in range(6)]
        rep = risk_coverage_report(
            [_result_row(1 - s["score"], s["correct"]) for s in scored])
        assert rep["e_aurc"] > 0.05

    def test_risk_at_full_coverage_is_error_rate(self):
        scored = [_row(0.9, True), _row(0.7, False), _row(0.5, True),
                  _row(0.3, False)]
        pts = _risk_coverage_curve(scored)
        assert risk_at_coverage(pts, 1.0) == pytest.approx(0.5)
        assert risk_at_coverage(pts, 1.0) == pytest.approx(
            risk_at_coverage(pts, 0.999))

    def test_curve_empty(self):
        assert _risk_coverage_curve([]) == []
        assert _aurc([]) == 0.0
        assert risk_at_coverage([], 0.9) == 0.0

    def test_curve_monotone_coverage(self):
        scored = [_row(0.1 * i, i % 2 == 0) for i in range(20)]
        covs = [c for c, _ in _risk_coverage_curve(scored)]
        assert covs == sorted(covs)
        assert covs[0] == pytest.approx(1 / 20)


# ── Report shape ────────────────────────────────────────────────────

class TestReport:
    def test_shape_and_categories(self):
        rows = ([_result_row(0.1, True, "multi_session") for _ in range(3)]
                + [_result_row(0.9, False, "temporal") for _ in range(2)])
        rep = risk_coverage_report(rows)
        assert rep["total"] == 5
        assert rep["errors"] == 2
        assert rep["overall_risk"] == 0.4
        assert set(rep["risk_at"]) == {"50%", "70%", "80%", "90%", "95%"}
        assert rep["per_category"]["multi_session"]["total"] == 3
        assert rep["per_category"]["multi_session"]["e_aurc"] == 0.0
        assert rep["per_category"]["temporal"]["total"] == 2
        assert len(rep["curve_deciles"]) == 10
        # per-category totals sum to the overall total
        assert (sum(c["total"] for c in rep["per_category"].values())
                == rep["total"])

    def test_duck_typed_attr_access(self):
        # QuestionResult-style attribute rows
        rows = [SimpleNamespace(correct=True, abstained=False,
                                category="kupdate",
                                retrieval={"norm_entropy": 0.2})]
        rep = risk_coverage_report(rows)
        assert rep["total"] == 1
        assert rep["per_category"]["kupdate"]["accuracy"] == 1.0

    def test_unresolved_score_counts_rows_without_signal(self):
        rows = [_result_row(0.3, True),
                {"correct": False, "abstained": False,
                 "category": "x"}]  # no retrieval dict
        rep = risk_coverage_report(rows)
        assert rep["total"] == 1
        assert rep["unresolved_score"] == 1

    def test_empty_results_zero_report(self):
        rep = risk_coverage_report([])
        assert rep["total"] == 0
        assert rep["e_aurc"] == 0.0
        assert rep["per_category"] == {}

    def test_abstained_flag_counted(self):
        rows = [_result_row(0.9, True),
                _result_row(0.8, True, abstained=True),
                _result_row(0.1, False)]
        rep = risk_coverage_report(rows)
        assert rep["answered"] == 2
        assert rep["abstained"] == 1

    def test_confidence_inverts_entropy(self):
        # LOW norm-entropy = high confidence: correct low-entropy
        # answers must lead the curve → small E-AURC
        rows = ([_result_row(0.05, True) for _ in range(8)]
                + [_result_row(0.95, False) for _ in range(2)])
        rep = risk_coverage_report(rows)
        assert rep["e_aurc"] == pytest.approx(0.0, abs=1e-9)


# ── Integration: run_eval wiring ────────────────────────────────────

class TestRunEvalWiring:
    def test_report_carries_risk_coverage(self):
        sessions = [{"session_id": "s1", "messages": [
            {"role": "user", "content": "I love hiking and rock climbing"},
            {"role": "assistant", "content": "Noted your hobbies!"},
        ]}, {"session_id": "s2", "messages": [
            {"role": "user", "content": "Actually I switched to cycling"},
            {"role": "assistant", "content": "Updated to cycling."},
        ]}]
        dataset = [
            {"id": "q_single-session-user_1",
             "question": "What activity does the user love?",
             "answer": "hiking and rock climbing",
             "haystack_sessions": sessions},
            {"id": "q_sushi_abs",
             "question": "What did the user say about sushi?",
             "answer": "never mentioned",
             "haystack_sessions": sessions},
        ]
        rep = run_eval(dataset)
        rc = rep["risk_coverage"]
        assert rc["total"] == 2
        assert rc["total"] == rc["answered"] + rc["abstained"]
        assert 0.0 <= rc["aurc"] <= 1.0
        assert rc["unresolved_score"] == 0
        # every per-question row the curve consumed carries the signal
        for r in rep["results"]:
            assert r["retrieval"]["norm_entropy"] is not None
