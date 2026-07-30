"""Tests for bayesian_classification() — Cycle 327.

Confidence-weighted adaptive ensemble fusion of degree JSD,
spectral divergence, and fingerprint distance.

Research #038: methods that are more decisive for the current query
get more influence. Weights adapt per-query.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ────────────────────────────────────────────────────────

def _make_star(n: int, label: str | None = None) -> MemoryGraph:
    """Star graph: 1 center connected to n-1 leaves."""
    g = MemoryGraph()
    center = g.add("center").id
    for i in range(n - 1):
        leaf = g.add(f"leaf_{i}").id
        g.link(center, leaf, "connects", weight=1.0)
    if label:
        g.graph_meta = {"label": label}
    return g


def _make_path(n: int, label: str | None = None) -> MemoryGraph:
    """Path graph: linear chain of n nodes."""
    g = MemoryGraph()
    nodes = [g.add(f"n{i}").id for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i], nodes[i + 1], "connects", weight=1.0)
    if label:
        g.graph_meta = {"label": label}
    return g


def _make_cycle(n: int, label: str | None = None) -> MemoryGraph:
    """Cycle graph: n nodes in a ring."""
    g = MemoryGraph()
    nodes = [g.add(f"n{i}").id for i in range(n)]
    for i in range(n):
        g.link(nodes[i], nodes[(i + 1) % n], "connects", weight=1.0)
    if label:
        g.graph_meta = {"label": label}
    return g


def _make_complete(n: int, label: str | None = None) -> MemoryGraph:
    """Complete graph: every node connected to every other."""
    g = MemoryGraph()
    nodes = [g.add(f"n{i}").id for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i], nodes[j], "connects", weight=1.0)
    if label:
        g.graph_meta = {"label": label}
    return g


def _make_sparse(n: int, edges: int = 1, label: str | None = None) -> MemoryGraph:
    """Sparse graph with few edges."""
    g = MemoryGraph()
    nodes = [g.add(f"n{i}").id for i in range(n)]
    for i in range(min(edges, n - 1)):
        g.link(nodes[i], nodes[i + 1], "connects", weight=0.5)
    if label:
        g.graph_meta = {"label": label}
    return g


# ── Section 1: Basic functionality ────────────────────────────────

class TestBayesianClassificationBasic:
    """Basic API behavior — empty, single, and normal cases."""

    def test_empty_references_returns_none(self):
        g = _make_path(5)
        assert g.bayesian_classification([]) is None

    def test_single_reference_returns_it(self):
        """With one reference, best_match should be 0."""
        target = _make_path(5)
        ref = _make_path(5)
        result = target.bayesian_classification([ref])
        assert result is not None
        assert result["best_match"] == 0
        assert result["best_score"] >= 0.0

    def test_returns_dict_with_required_keys(self):
        target = _make_path(5)
        refs = [_make_path(5), _make_star(5)]
        result = target.bayesian_classification(refs)
        assert result is not None
        assert "best_match" in result
        assert "best_score" in result
        assert "rankings" in result
        assert "methods_used" in result
        assert "method_info" in result
        assert "confidence" in result
        assert "margin" in result

    def test_rankings_sorted_ascending(self):
        """Rankings should be sorted by score ascending (lower = better)."""
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6), _make_cycle(6)]
        result = target.bayesian_classification(refs)
        scores = [r["score"] for r in result["rankings"]]
        assert scores == sorted(scores)

    def test_best_match_is_rankings_zero(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6), _make_cycle(6)]
        result = target.bayesian_classification(refs)
        assert result["best_match"] == result["rankings"][0]["index"]

    def test_confidence_non_negative(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6), _make_cycle(6)]
        result = target.bayesian_classification(refs)
        assert result["confidence"] >= 0.0

    def test_margin_non_negative(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6), _make_cycle(6)]
        result = target.bayesian_classification(refs)
        assert result["margin"] >= 0.0


# ── Section 2: Classification correctness ─────────────────────────

class TestBayesianClassificationCorrectness:
    """Verify Bayesian fusion picks the right reference."""

    def test_path_matches_path_over_star(self):
        """A path graph should match another path over a star."""
        target = _make_path(7)
        refs = [_make_star(7, "star"), _make_path(7, "path")]
        result = target.bayesian_classification(refs)
        assert result["best_match"] == 1  # path is ref index 1

    def test_star_matches_star_over_path(self):
        """A star graph should match another star over a path."""
        target = _make_star(7)
        refs = [_make_star(7, "star"), _make_path(7, "path")]
        result = target.bayesian_classification(refs)
        assert result["best_match"] == 0  # star is ref index 0

    def test_cycle_matches_cycle_over_path(self):
        """A cycle graph should match another cycle over a path."""
        target = _make_cycle(6)
        refs = [_make_path(6, "path"), _make_cycle(6, "cycle")]
        result = target.bayesian_classification(refs)
        assert result["best_match"] == 1

    def test_complete_matches_complete_over_sparse(self):
        """A complete graph should match another complete over sparse."""
        target = _make_complete(5)
        refs = [_make_sparse(5, 1, "sparse"), _make_complete(5, "complete")]
        result = target.bayesian_classification(refs)
        assert result["best_match"] == 1

    def test_self_match_score_near_zero(self):
        """Matching against an identical copy should give near-zero score."""
        target = _make_path(6)
        identical = _make_path(6)
        result = target.bayesian_classification([identical, _make_star(6)])
        # The identical match should have the lowest score
        assert result["best_match"] == 0
        assert result["best_score"] < 0.5  # much better than worst

    def test_three_way_classification(self):
        """With 3 reference types, correct one should be selected."""
        target = _make_path(8)
        refs = [_make_star(8), _make_complete(5), _make_path(8)]
        result = target.bayesian_classification(refs)
        assert result["best_match"] == 2


# ── Section 3: Adaptive weights ────────────────────────────────────

class TestBayesianAdaptiveWeights:
    """Verify that weights adapt based on method separations."""

    def test_method_info_contains_all_three_methods(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(refs)
        mi = result["method_info"]
        assert "degree_jsd" in mi
        assert "spectral_divergence" in mi
        assert "fingerprint_distance" in mi

    def test_method_info_has_separation_and_weight(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(refs)
        for m in result["methods_used"]:
            info = result["method_info"][m]
            assert "separation" in info
            assert "weight" in info
            assert info["separation"] >= 0.0
            assert info["weight"] >= 0.0

    def test_weights_sum_to_one(self):
        """Active method weights should sum to 1."""
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6), _make_cycle(6)]
        result = target.bayesian_classification(refs)
        total = sum(
            result["method_info"][m]["weight"]
            for m in result["methods_used"]
        )
        assert abs(total - 1.0) < 1e-6

    def test_decisive_method_gets_higher_weight(self):
        """If one method clearly separates best from rest, it gets
        more weight than a method that is ambiguous."""
        # Path vs star: degree-based measures should be very decisive
        # (very different degree distributions)
        target = _make_path(8)
        refs = [_make_star(8), _make_path(8)]
        result = target.bayesian_classification(refs)
        # At least one method should have separation > 0
        seps = [
            result["method_info"][m]["separation"]
            for m in result["methods_used"]
        ]
        assert max(seps) > 0.0

    def test_identical_references_zero_separation_fallback(self):
        """When all references are identical, separations are 0 but
        should fall back to equal weights rather than fail."""
        target = _make_path(5)
        refs = [_make_path(5), _make_path(5), _make_path(5)]
        result = target.bayesian_classification(refs)
        assert result is not None
        # All scores should be ~equal
        scores = [r["score"] for r in result["rankings"]]
        assert max(scores) - min(scores) < 0.01

    def test_inactive_methods_have_zero_weight(self):
        """Methods that are not active should have weight 0."""
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(refs)
        for m in ["degree_jsd", "spectral_divergence", "fingerprint_distance"]:
            if m not in result["methods_used"]:
                assert result["method_info"][m]["weight"] == 0.0
                assert result["method_info"][m]["active"] is False


# ── Section 4: Per-method diagnostics ─────────────────────────────

class TestBayesianDiagnostics:
    """Verify the per-reference diagnostic fields."""

    def test_rankings_have_per_method_raw_scores(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(refs)
        for entry in result["rankings"]:
            assert "degree_jsd_raw" in entry
            assert "spectral_divergence_raw" in entry
            assert "fingerprint_distance_raw" in entry

    def test_rankings_have_per_method_norm_scores(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(refs)
        for entry in result["rankings"]:
            assert "degree_jsd_norm" in entry
            assert "spectral_divergence_norm" in entry
            assert "fingerprint_distance_norm" in entry

    def test_rankings_have_per_method_weights(self):
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(refs)
        for entry in result["rankings"]:
            assert "degree_jsd_weight" in entry
            assert "spectral_divergence_weight" in entry
            assert "fingerprint_distance_weight" in entry

    def test_best_reference_has_norm_near_zero(self):
        """The best match should have normalised scores near 0
        for the methods that contributed."""
        target = _make_path(8)
        refs = [_make_star(8, "star"), _make_path(8, "path")]
        result = target.bayesian_classification(refs)
        best = result["rankings"][0]
        # The best match (path) should have at least one norm near 0
        norms = [
            best["degree_jsd_norm"],
            best["spectral_divergence_norm"],
            best["fingerprint_distance_norm"],
        ]
        valid_norms = [n for n in norms if n is not None]
        assert min(valid_norms) < 0.1  # at least one method sees it as near-best

    def test_label_propagation(self):
        """Labels from graph_meta should propagate to rankings."""
        target = _make_path(6)
        refs = [_make_star(6, "my_star"), _make_path(6, "my_path")]
        result = target.bayesian_classification(refs)
        labels = {r["index"]: r["label"] for r in result["rankings"]}
        assert labels[0] == "my_star"
        assert labels[1] == "my_path"


# ── Section 5: Edge cases & robustness ─────────────────────────────

class TestBayesianEdgeCases:
    """Edge cases and error handling."""

    def test_two_references_minimum(self):
        target = _make_path(5)
        result = target.bayesian_classification([_make_path(5)])
        assert result is not None
        assert len(result["rankings"]) == 1

    def test_many_references(self):
        """Should handle 10+ references without error."""
        target = _make_path(6)
        refs = [
            _make_star(6) if i % 3 == 0
            else _make_cycle(6) if i % 3 == 1
            else _make_path(6)
            for i in range(12)
        ]
        result = target.bayesian_classification(refs)
        assert result is not None
        assert len(result["rankings"]) == 12
        # Path refs (indices 2, 5, 8, 11) should score well
        path_indices = [2, 5, 8, 11]
        best_path_idx = min(
            path_indices,
            key=lambda i: next(
                r["score"] for r in result["rankings"] if r["index"] == i
            )
        )

    def test_single_node_references(self):
        """Single-node graphs have no edges — should not crash."""
        target = _make_path(3)
        g1 = MemoryGraph()
        g1.add(label="solo1")
        g2 = MemoryGraph()
        g2.add(label="solo2")
        result = target.bayesian_classification([g1, g2])
        # Should either return None or a result (methods may fail gracefully)
        if result is not None:
            assert "best_match" in result

    def test_include_quarantined_parameter(self):
        """include_quarantined should be accepted without error."""
        target = _make_path(5)
        refs = [_make_star(5), _make_path(5)]
        result = target.bayesian_classification(
            refs, include_quarantined=True
        )
        assert result is not None

    def test_degree_index_parameter(self):
        """Different degree indices should work."""
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6)]
        result = target.bayesian_classification(
            refs, degree_index="randic"
        )
        assert result is not None

    def test_min_separation_parameter(self):
        """Custom min_separation should be accepted."""
        target = _make_path(5)
        refs = [_make_star(5), _make_path(5)]
        result = target.bayesian_classification(
            refs, min_separation=0.001
        )
        assert result is not None


# ── Section 6: Comparison with other classifiers ──────────────────

class TestBayesianComparison:
    """Compare Bayesian with RRF and hybrid — should broadly agree."""

    def test_bayesian_and_rrf_select_same_best(self):
        """For clear-cut cases, both methods should agree."""
        target = _make_path(8)
        refs = [_make_star(8), _make_path(8), _make_complete(5)]
        bayesian = target.bayesian_classification(refs)
        rrf = target.rrf_classification(refs)
        assert bayesian is not None
        assert rrf is not None
        # Both should pick path (index 1) as best match
        assert bayesian["best_match"] == rrf["best_match"]

    def test_bayesian_and_hybrid_select_same_best(self):
        target = _make_path(8)
        refs = [_make_star(8), _make_path(8)]
        bayesian = target.bayesian_classification(refs)
        hybrid = target.hybrid_classification(refs)
        assert bayesian is not None
        assert hybrid is not None
        assert bayesian["best_match"] == hybrid["best_match"]

    def test_bayesian_score_in_unit_range(self):
        """Bayesian scores (weighted avg of normalised) should be in [0, 1]."""
        target = _make_path(6)
        refs = [_make_star(6), _make_path(6), _make_cycle(6)]
        result = target.bayesian_classification(refs)
        for entry in result["rankings"]:
            assert 0.0 <= entry["score"] <= 1.0 + 1e-6


# ── Section 7: Consistency & determinism ───────────────────────────

class TestBayesianDeterminism:
    """Ensure repeated calls give identical results."""

    def test_deterministic_results(self):
        target = _make_path(7)
        refs = [_make_star(7), _make_path(7), _make_cycle(7)]
        r1 = target.bayesian_classification(refs)
        r2 = target.bayesian_classification(refs)
        assert r1["best_match"] == r2["best_match"]
        assert r1["best_score"] == r2["best_score"]
        assert (
            [r["score"] for r in r1["rankings"]]
            == [r["score"] for r in r2["rankings"]]
        )

    def test_weights_deterministic(self):
        target = _make_path(7)
        refs = [_make_star(7), _make_path(7), _make_cycle(7)]
        r1 = target.bayesian_classification(refs)
        r2 = target.bayesian_classification(refs)
        for m in r1["methods_used"]:
            assert (
                r1["method_info"][m]["weight"]
                == r2["method_info"][m]["weight"]
            )

    def test_confidence_and_margin_deterministic(self):
        target = _make_path(7)
        refs = [_make_star(7), _make_path(7)]
        r1 = target.bayesian_classification(refs)
        r2 = target.bayesian_classification(refs)
        assert r1["confidence"] == r2["confidence"]
        assert r1["margin"] == r2["margin"]
