"""Tests for classification_with_rejection() — Cycle 320.

Post-processing method that adds threshold-based rejection to any
classification result (graph_classification, spectral_classification,
hybrid_classification). Enables production-safe fallback strategies.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──

def _complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g

def _path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g

def _cycle(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g

def _star(k):
    g = MemoryGraph()
    center = g.add("c")
    leaves = [g.add(f"l{i}") for i in range(k)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "r")
    return g

def _paw():
    g = MemoryGraph()
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return g


def _make_classification_result(best_score=0.3, margin=0.1, rankings=None):
    """Create a minimal classification result dict for testing."""
    if rankings is None:
        rankings = [
            {"index": 0, "score": best_score, "label": "ref_0"},
            {"index": 1, "score": best_score + margin, "label": "ref_1"},
            {"index": 2, "score": best_score + margin + 0.3, "label": "ref_2"},
        ]
    return {
        "best_match": 0,
        "best_score": best_score,
        "rankings": rankings,
        "margin": margin,
        "confidence": margin / best_score if best_score > 0 else float("inf"),
    }


class TestClassificationWithRejectionDegenerate:
    """Degenerate and malformed inputs."""

    def test_none_input(self):
        g = _complete(3)
        assert g.classification_with_rejection(None) is None

    def test_non_dict_input(self):
        g = _complete(3)
        assert g.classification_with_rejection("not a dict") is None
        assert g.classification_with_rejection(42) is None
        assert g.classification_with_rejection([]) is None

    def test_missing_best_score(self):
        g = _complete(3)
        result = {"margin": 0.1, "rankings": []}
        assert g.classification_with_rejection(result) is None

    def test_missing_margin_computes_from_rankings(self):
        """If margin is missing, it should be computed from rankings."""
        g = _complete(3)
        result = {
            "best_match": 0,
            "best_score": 0.2,
            "rankings": [
                {"index": 0, "score": 0.2},
                {"index": 1, "score": 0.5},
            ],
        }
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected is not None
        assert rejected["decision"] == "accept"

    def test_none_best_score(self):
        g = _complete(3)
        result = {"best_score": None, "margin": 0.1}
        assert g.classification_with_rejection(result) is None

    def test_none_margin_computes_from_rankings(self):
        """If margin is None but rankings exist, compute it."""
        g = _complete(3)
        result = {
            "best_match": 0,
            "best_score": 0.2,
            "margin": None,
            "rankings": [
                {"index": 0, "score": 0.2},
                {"index": 1, "score": 0.4},
            ],
        }
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected is not None
        assert rejected["decision"] == "accept"

    def test_empty_dict(self):
        g = _complete(3)
        assert g.classification_with_rejection({}) is None


class TestClassificationWithRejectionAccept:
    """Acceptance scenarios."""

    def test_score_below_threshold_accepted(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.05)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected["decision"] == "accept"

    def test_exact_score_at_threshold_accepted(self):
        """Score == threshold is accepted (≤ comparison)."""
        g = _complete(3)
        result = _make_classification_result(best_score=0.5, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected["decision"] == "accept"

    def test_exact_match_always_accepted(self):
        """Score = 0 (exact match) overrides any threshold."""
        g = _complete(3)
        result = _make_classification_result(best_score=0.0, margin=0.0)
        rejected = g.classification_with_rejection(result, threshold=0.001)
        assert rejected["decision"] == "accept"
        assert "exact match" in rejected["reason"]

    def test_near_zero_score_accepted(self):
        """Very small score treated like exact match."""
        g = _complete(3)
        result = _make_classification_result(best_score=1e-16, margin=0.0)
        rejected = g.classification_with_rejection(result, threshold=0.001)
        assert rejected["decision"] == "accept"

    def test_margin_meets_minimum(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.15)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.15)
        assert rejected["decision"] == "accept"

    def test_margin_exceeds_minimum(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.2)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.1)
        assert rejected["decision"] == "accept"


class TestClassificationWithRejectionReject:
    """Rejection scenarios."""

    def test_score_above_threshold_rejected(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.8, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected["decision"] == "reject"
        assert "score" in rejected["reason"]
        assert "threshold" in rejected["reason"]

    def test_margin_below_minimum_rejected(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.05)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.1)
        assert rejected["decision"] == "reject"
        assert "margin" in rejected["reason"]

    def test_both_criteria_fail(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.9, margin=0.01)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.05)
        assert rejected["decision"] == "reject"

    def test_reason_contains_score_value(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.8, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert "0.8000" in rejected["reason"]
        assert "0.5000" in rejected["reason"]


class TestClassificationWithRejectionStructure:
    """Result structure preservation and augmentation."""

    def test_original_keys_preserved(self):
        g = _complete(3)
        original = _make_classification_result(best_score=0.2, margin=0.1)
        original["extra_key"] = "extra_value"
        rejected = g.classification_with_rejection(original, threshold=0.5)
        assert rejected["extra_key"] == "extra_value"
        assert rejected["best_score"] == 0.2
        assert rejected["margin"] == 0.1
        assert rejected["rankings"] == original["rankings"]

    def test_new_keys_added(self):
        g = _complete(3)
        original = _make_classification_result(best_score=0.2, margin=0.1)
        rejected = g.classification_with_rejection(original, threshold=0.5)
        assert "decision" in rejected
        assert "reason" in rejected
        assert "threshold" in rejected
        assert "min_margin" in rejected
        assert "calibrated_confidence" in rejected

    def test_threshold_echoed(self):
        g = _complete(3)
        original = _make_classification_result(best_score=0.2, margin=0.1)
        rejected = g.classification_with_rejection(original, threshold=0.35)
        assert rejected["threshold"] == 0.35

    def test_min_margin_echoed(self):
        g = _complete(3)
        original = _make_classification_result(best_score=0.2, margin=0.15)
        rejected = g.classification_with_rejection(original, threshold=0.5, min_margin=0.12)
        assert rejected["min_margin"] == 0.12

    def test_original_not_mutated(self):
        """The input dict should not be modified."""
        g = _complete(3)
        original = _make_classification_result(best_score=0.2, margin=0.1)
        original_copy = dict(original)
        g.classification_with_rejection(original, threshold=0.5)
        assert original == original_copy
        assert "decision" not in original


class TestClassificationWithRejectionCalibratedConfidence:
    """Calibrated confidence computation."""

    def test_perfect_match_confidence_one(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.0, margin=0.0)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected["calibrated_confidence"] == 1.0

    def test_score_at_threshold_confidence_zero(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.5, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert abs(rejected["calibrated_confidence"] - 0.0) < 1e-9

    def test_score_above_threshold_negative_confidence(self):
        """When score > threshold, calibrated confidence is negative."""
        g = _complete(3)
        result = _make_classification_result(best_score=0.8, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected["calibrated_confidence"] < 0

    def test_confidence_linear_midpoint(self):
        """At threshold/2, confidence should be ~0.5."""
        g = _complete(3)
        result = _make_classification_result(best_score=0.25, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert abs(rejected["calibrated_confidence"] - 0.5) < 1e-4

    def test_confidence_range(self):
        """For accepted results, confidence is in [0, 1]."""
        g = _complete(3)
        for score in [0.01, 0.1, 0.2, 0.3, 0.4, 0.49]:
            result = _make_classification_result(best_score=score, margin=0.1)
            rejected = g.classification_with_rejection(result, threshold=0.5)
            assert 0.0 - 1e-9 <= rejected["calibrated_confidence"] <= 1.0 + 1e-9


class TestClassificationWithRejectionThresholdValues:
    """Different threshold values."""

    def test_zero_threshold_rejects_non_exact(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.001, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.0)
        assert rejected["decision"] == "reject"

    def test_zero_threshold_accepts_exact(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.0, margin=0.0)
        rejected = g.classification_with_rejection(result, threshold=0.0)
        assert rejected["decision"] == "accept"

    def test_high_threshold_accepts_everything(self):
        g = _complete(3)
        result = _make_classification_result(best_score=10.0, margin=0.001)
        rejected = g.classification_with_rejection(result, threshold=100.0)
        assert rejected["decision"] == "accept"


class TestClassificationWithRejectionRealPipeline:
    """End-to-end: classification_with_rejection applied to real classification results."""

    def test_graph_classification_accepted(self):
        """Apply rejection to graph_classification result."""
        query = _cycle(5)
        refs = [_cycle(5), _complete(4), _path(5)]
        cls = query.graph_classification(refs)
        assert cls is not None
        rejected = query.classification_with_rejection(cls, threshold=0.5)
        assert rejected["decision"] == "accept"
        assert rejected["best_match"] == cls["best_match"]

    def test_graph_classification_rejected(self):
        """No similar reference → rejection."""
        query = _paw()
        refs = [_complete(8), _cycle(8)]
        cls = query.graph_classification(refs)
        assert cls is not None
        # Use very tight threshold
        rejected = query.classification_with_rejection(cls, threshold=0.01)
        # Paw vs complete/cycle should likely be rejected with tight threshold
        # (depends on score, but with threshold=0.01, very likely rejected)
        if cls["best_score"] > 0.01:
            assert rejected["decision"] == "reject"

    def test_spectral_classification_accepted(self):
        """Apply rejection to spectral_classification result."""
        query = _cycle(5)
        refs = [_cycle(5), _complete(4), _star(4)]
        cls = query.spectral_classification(refs)
        assert cls is not None
        rejected = query.classification_with_rejection(cls, threshold=0.5)
        assert rejected["decision"] == "accept"

    def test_hybrid_classification_accepted(self):
        """Apply rejection to hybrid_classification result."""
        query = _cycle(5)
        refs = [_cycle(5), _complete(4), _path(5)]
        cls = query.hybrid_classification(refs)
        assert cls is not None
        rejected = query.classification_with_rejection(cls, threshold=0.5)
        assert rejected["decision"] == "accept"

    def test_self_classification_exact_match(self):
        """Classifying a graph against itself → exact match → always accepted."""
        g = _cycle(6)
        refs = [g]
        cls = g.spectral_classification(refs)
        assert cls is not None
        assert cls["best_score"] == 0.0  # exact match
        rejected = g.classification_with_rejection(cls, threshold=0.001)
        assert rejected["decision"] == "accept"
        assert rejected["calibrated_confidence"] == 1.0


class TestClassificationWithRejectionMinMargin:
    """min_margin criterion behavior."""

    def test_zero_min_margin_default(self):
        """Default min_margin=0.0 means margin criterion is always satisfied."""
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.0)
        rejected = g.classification_with_rejection(result, threshold=0.5)
        assert rejected["decision"] == "accept"

    def test_large_min_margin_rejects(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.1)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.5)
        assert rejected["decision"] == "reject"
        assert "margin" in rejected["reason"]

    def test_margin_exactly_at_minimum_accepted(self):
        """margin == min_margin is accepted (≥ comparison)."""
        g = _complete(3)
        result = _make_classification_result(best_score=0.2, margin=0.2)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.2)
        assert rejected["decision"] == "accept"

    def test_reason_mentions_both_criteria_when_both_fail(self):
        g = _complete(3)
        result = _make_classification_result(best_score=0.9, margin=0.01)
        rejected = g.classification_with_rejection(result, threshold=0.5, min_margin=0.05)
        assert "score" in rejected["reason"]
        assert "margin" in rejected["reason"]


class TestClassificationWithRejectionNonMutating:
    """Method does not modify the graph."""

    def test_graph_unchanged(self):
        g = _paw()
        before_nodes = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        before_edges = len(g.conn.execute("SELECT * FROM edges").fetchall())
        result = _make_classification_result(best_score=0.3, margin=0.1)
        g.classification_with_rejection(result, threshold=0.5)
        after_nodes = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        after_edges = len(g.conn.execute("SELECT * FROM edges").fetchall())
        assert before_nodes == after_nodes
        assert before_edges == after_edges
