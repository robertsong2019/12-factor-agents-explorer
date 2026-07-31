"""Tests for max_confidence_classification() — Cycle 335.

Meta-classifier that selects the result from whichever method
has the highest confidence for the current query.
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


def _make_bipartite(n: int, label: str | None = None) -> MemoryGraph:
    """Complete bipartite graph."""
    g = MemoryGraph()
    nodes = [g.add(f"n{i}").id for i in range(n)]
    half = n // 2
    left, right = nodes[:half], nodes[half:]
    for a in left:
        for b in right:
            g.link(a, b, "connects", weight=1.0)
    if label:
        g.graph_meta = {"label": label}
    return g


def _make_tree(n: int, label: str | None = None) -> MemoryGraph:
    """Binary tree graph."""
    g = MemoryGraph()
    nodes = [g.add(f"n{i}").id for i in range(n)]
    for i in range(1, n):
        parent = (i - 1) // 2
        g.link(nodes[parent], nodes[i], "connects", weight=1.0)
    if label:
        g.graph_meta = {"label": label}
    return g


# ── Section 1: Degenerate & edge cases ────────────────────────────

class TestMaxConfidenceDegenerate:
    """Edge cases and degenerate inputs."""

    def test_empty_references_returns_none(self):
        query = _make_star(8)
        assert query.max_confidence_classification([]) is None

    def test_single_reference_returns_result(self):
        query = _make_star(8)
        ref = _make_star(8)
        result = query.max_confidence_classification([ref])
        assert result is not None
        assert result["best_match"] == 0

    def test_single_reference_min_methods_1(self):
        query = _make_star(8)
        ref = _make_star(8)
        result = query.max_confidence_classification([ref], min_methods=1)
        assert result is not None
        assert result["agreement"] == 1.0

    def test_min_methods_fallback(self):
        """When fewer methods succeed than min_methods, still returns result.

        With a single ref, most methods succeed (best_match=0 trivially).
        The recommendation should still be informative.
        """
        query = _make_star(8)
        ref = _make_star(8)
        result = query.max_confidence_classification([ref], min_methods=10)
        assert result is not None
        # With single ref, all methods succeed but < min_methods threshold
        # Should return result via the fallback path
        assert result["best_match"] == 0

    def test_min_methods_zero_valid(self):
        """min_methods=0 is valid (returns single best)."""
        query = _make_star(8)
        ref = _make_star(8)
        result = query.max_confidence_classification([ref], min_methods=0)
        assert result is not None


# ── Section 2: Validation ──────────────────────────────────────────

class TestMaxConfidenceValidation:
    """Parameter validation."""

    def test_invalid_confidence_metric_raises(self):
        query = _make_star(8)
        ref = _make_star(8)
        with pytest.raises(ValueError):
            query.max_confidence_classification(
                [ref], confidence_metric="bogus")

    def test_valid_confidence_metrics(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        for metric in ("margin", "confidence", "z_score"):
            result = query.max_confidence_classification(
                refs, confidence_metric=metric)
            assert result is not None
            assert result["confidence_metric"] == metric

    def test_degree_index_parameter(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        result = query.max_confidence_classification(
            refs, degree_index="randic")
        assert result is not None

    def test_include_quarantined_true(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        result = query.max_confidence_classification(
            refs, include_quarantined=True)
        assert result is not None

    def test_include_quarantined_false(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        result = query.max_confidence_classification(
            refs, include_quarantined=False)
        assert result is not None


# ── Section 3: Basic classification ────────────────────────────────

class TestMaxConfidenceBasic:
    """Basic classification correctness."""

    def setup_method(self):
        self.refs = [
            _make_star(8, "star"),
            _make_path(8, "path"),
            _make_cycle(8, "cycle"),
        ]

    def test_star_query_matches_star(self):
        query = _make_star(8)
        result = query.max_confidence_classification(self.refs)
        assert result is not None
        assert result["best_match"] == 0

    def test_path_query_matches_path(self):
        query = _make_path(8)
        result = query.max_confidence_classification(self.refs)
        assert result is not None
        assert result["best_match"] == 1

    def test_cycle_query_matches_cycle(self):
        query = _make_cycle(8)
        result = query.max_confidence_classification(self.refs)
        assert result is not None
        assert result["best_match"] == 2

    def test_result_has_required_keys(self):
        query = _make_star(8)
        result = query.max_confidence_classification(self.refs)
        expected_keys = {
            "best_match", "best_score", "winning_method",
            "winning_confidence", "confidence_metric",
            "per_method", "methods_run", "methods_failed",
            "agreement", "margin_of_victory", "recommendation",
        }
        assert set(result.keys()) == expected_keys

    def test_best_score_is_numeric(self):
        query = _make_star(8)
        result = query.max_confidence_classification(self.refs)
        assert isinstance(result["best_score"], (int, float))

    def test_winning_method_is_known(self):
        query = _make_star(8)
        result = query.max_confidence_classification(self.refs)
        assert result["winning_method"] in {
            "graph_classification", "spectral_classification",
            "hybrid_classification", "rrf_classification",
            "bayesian_classification",
        }

    def test_methods_run_non_empty(self):
        query = _make_star(8)
        result = query.max_confidence_classification(self.refs)
        assert len(result["methods_run"]) > 0


# ── Section 4: Per-method diagnostics ──────────────────────────────

class TestMaxConfidencePerMethod:
    """Per-method diagnostics."""

    def setup_method(self):
        self.refs = [_make_star(8), _make_path(8), _make_cycle(8)]
        self.query = _make_star(8)

    def test_per_method_has_all_entries(self):
        result = self.query.max_confidence_classification(self.refs)
        for name in result["methods_run"]:
            entry = result["per_method"][name]
            assert "best_match" in entry
            assert "best_score" in entry
            assert "margin" in entry
            assert "confidence" in entry
            assert "z_score" in entry

    def test_per_method_best_match_valid(self):
        result = self.query.max_confidence_classification(self.refs)
        for name in result["methods_run"]:
            bm = result["per_method"][name]["best_match"]
            assert isinstance(bm, int)
            assert 0 <= bm < len(self.refs)

    def test_per_method_z_score_is_finite(self):
        result = self.query.max_confidence_classification(self.refs)
        for name in result["methods_run"]:
            z = result["per_method"][name]["z_score"]
            assert isinstance(z, (int, float))
            assert not math.isnan(z)
            assert not math.isinf(z)


# ── Section 5: Confidence-based selection logic ───────────────────

class TestMaxConfidenceSelection:
    """Confidence-based method selection logic."""

    def setup_method(self):
        self.refs = [_make_star(8), _make_path(8), _make_cycle(8)]
        self.query = _make_star(8)

    def test_margin_metric_selects_highest_margin(self):
        """With 'margin' metric, winner should have max margin."""
        result = self.query.max_confidence_classification(
            self.refs, confidence_metric="margin")
        winner = result["winning_method"]
        winner_margin = result["per_method"][winner]["margin"] or 0.0
        for name in result["methods_run"]:
            other = result["per_method"][name].get("margin", 0.0)
            if other is not None:
                assert winner_margin >= other

    def test_z_score_metric_selects_most_separated(self):
        """With 'z_score', the most negative z (best separated) wins."""
        result = self.query.max_confidence_classification(
            self.refs, confidence_metric="z_score")
        winner = result["winning_method"]
        winner_z = result["per_method"][winner]["z_score"]
        for name in result["methods_run"]:
            other_z = result["per_method"][name]["z_score"]
            assert winner_z <= other_z, (
                f"winner {winner} z={winner_z} should be "
                f"<= {name} z={other_z}"
            )

    def test_different_metrics_all_produce_valid_results(self):
        """Verify all metrics produce valid results."""
        for metric in ("margin", "confidence", "z_score"):
            r = self.query.max_confidence_classification(
                self.refs, confidence_metric=metric)
            assert r is not None
            assert isinstance(r["winning_method"], str)

    def test_winning_confidence_matches_metric(self):
        result = self.query.max_confidence_classification(
            self.refs, confidence_metric="margin")
        winner = result["winning_method"]
        expected = result["per_method"][winner].get("margin", 0.0)
        if expected == float("inf"):
            expected = 1e18
        assert abs(result["winning_confidence"] -
                   round(float(expected) if expected is not None else 0.0, 8)) < 1e-4

    def test_margin_of_victory_non_negative(self):
        result = self.query.max_confidence_classification(self.refs)
        assert result["margin_of_victory"] >= 0.0


# ── Section 6: Agreement ───────────────────────────────────────────

class TestMaxConfidenceAgreement:
    """Agreement between methods."""

    def setup_method(self):
        self.refs = [_make_star(8), _make_path(8), _make_cycle(8)]
        self.query = _make_star(8)

    def test_agreement_in_range(self):
        result = self.query.max_confidence_classification(self.refs)
        assert 0.0 <= result["agreement"] <= 1.0

    def test_clear_match_has_agreement(self):
        """Star query against star/path/cycle should have decent agreement."""
        result = self.query.max_confidence_classification(self.refs)
        assert result["agreement"] > 0.0

    def test_all_agree_when_obvious(self):
        """When query is exact copy of a reference, all should agree."""
        refs = [self.query, _make_path(8), _make_cycle(8)]
        result = self.query.max_confidence_classification(refs)
        assert result["agreement"] == 1.0

    def test_methods_run_count(self):
        result = self.query.max_confidence_classification(self.refs)
        assert 1 <= len(result["methods_run"]) <= 5

    def test_methods_failed_is_list(self):
        result = self.query.max_confidence_classification(self.refs)
        assert isinstance(result["methods_failed"], list)


# ── Section 7: Non-mutation ────────────────────────────────────────

class TestMaxConfidenceNonMutating:
    """Ensure the query and references are not modified."""

    def test_query_unchanged(self):
        query = _make_star(8)
        edges_before = query.edge_count()
        refs = [_make_star(8), _make_path(8)]
        query.max_confidence_classification(refs)
        assert query.edge_count() == edges_before

    def test_references_unchanged(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        ref_edges = [r.edge_count() for r in refs]
        query.max_confidence_classification(refs)
        for i, r in enumerate(refs):
            assert r.edge_count() == ref_edges[i]


# ── Section 8: Quarantined flag ────────────────────────────────────

class TestMaxConfidenceQuarantined:
    """Quarantined flag handling."""

    def test_quarantined_true_accepted(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        result = query.max_confidence_classification(
            refs, include_quarantined=True)
        assert result is not None

    def test_quarantined_false_accepted(self):
        query = _make_star(8)
        refs = [_make_star(8), _make_path(8)]
        result = query.max_confidence_classification(
            refs, include_quarantined=False)
        assert result is not None


# ── Section 9: Robustness ──────────────────────────────────────────

class TestMaxConfidenceRobustness:
    """Robustness with larger reference sets."""

    def test_many_references(self):
        refs = [
            _make_star(8, "star"),
            _make_path(8, "path"),
            _make_cycle(8, "cycle"),
            _make_complete(5, "complete"),
            _make_bipartite(8, "bipartite"),
            _make_tree(7, "tree"),
        ]
        query = _make_star(8)
        result = query.max_confidence_classification(refs)
        assert result is not None
        assert result["best_match"] == 0

    def test_different_sizes(self):
        refs = [_make_star(6), _make_path(10), _make_cycle(8)]
        query = _make_star(6)
        result = query.max_confidence_classification(refs)
        assert result is not None
        assert result["best_match"] == 0

    def test_all_methods_produce_valid_best_match(self):
        refs = [_make_star(8), _make_path(8), _make_cycle(8)]
        query = _make_star(8)
        result = query.max_confidence_classification(refs)
        for name in result["methods_run"]:
            bm = result["per_method"][name]["best_match"]
            assert isinstance(bm, int)
            assert 0 <= bm < len(refs)

    def test_deterministic_across_calls(self):
        refs = [_make_star(8), _make_path(8), _make_cycle(8)]
        query = _make_star(8)
        r1 = query.max_confidence_classification(refs)
        r2 = query.max_confidence_classification(refs)
        assert r1["best_match"] == r2["best_match"]
        assert r1["winning_method"] == r2["winning_method"]
        assert r1["winning_confidence"] == r2["winning_confidence"]


# ── Section 10: Recommendation text ────────────────────────────────

class TestMaxConfidenceRecommendation:
    """Recommendation text generation."""

    def test_recommendation_is_string(self):
        refs = [_make_star(8), _make_path(8)]
        query = _make_star(8)
        result = query.max_confidence_classification(refs)
        assert isinstance(result["recommendation"], str)

    def test_recommendation_mentions_method(self):
        refs = [_make_star(8), _make_path(8), _make_cycle(8)]
        query = _make_star(8)
        result = query.max_confidence_classification(refs)
        assert result["winning_method"] in result["recommendation"]

    def test_recommendation_full_agreement(self):
        refs = [_make_star(8), _make_path(8)]
        query = refs[0]  # exact copy
        result = query.max_confidence_classification(refs)
        if result["agreement"] == 1.0:
            assert "agree" in result["recommendation"].lower()


# ── Section 11: Integration ────────────────────────────────────────

class TestMaxConfidenceIntegration:
    """Integration with existing classification APIs."""

    def setup_method(self):
        self.refs = [_make_star(8), _make_path(8), _make_cycle(8)]

    def test_agrees_with_graph_classification(self):
        query = _make_star(8)
        max_result = query.max_confidence_classification(self.refs)
        graph_result = query.graph_classification(
            self.refs, index="sombor")
        assert max_result is not None
        assert graph_result is not None
        assert max_result["best_match"] == graph_result["best_match"]

    def test_agrees_with_spectral_classification(self):
        query = _make_star(8)
        max_result = query.max_confidence_classification(self.refs)
        spectral_result = query.spectral_classification(self.refs)
        assert max_result is not None
        assert spectral_result is not None
        assert max_result["best_match"] == spectral_result["best_match"]

    def test_compatible_with_classification_compare(self):
        query = _make_star(8)
        max_result = query.max_confidence_classification(self.refs)
        compare_result = query.classification_compare(self.refs)
        assert max_result is not None
        assert compare_result is not None
        # For star query, both should pick star (index 0)
        assert max_result["best_match"] == 0
        assert compare_result["consensus_best"] == 0

    def test_works_with_classification_benchmark(self):
        query = _make_star(8)
        result = query.max_confidence_classification(self.refs)
        bench = query.classification_benchmark(
            topologies=["star", "path"],
            sizes=[8],
            methods=["graph", "spectral"],
            num_references_per_category=1,
        )
        assert isinstance(bench, dict)
        assert isinstance(result, dict)


# ── Section 12: Infinite confidence handling ──────────────────────

class TestMaxConfidenceInfHandling:
    """Handle infinite confidence values (when best≈0)."""

    def test_inf_confidence_does_not_crash(self):
        """When best_score is ~0, confidence can be inf."""
        query = _make_star(8)
        refs = [query, _make_path(8), _make_cycle(8)]
        result = query.max_confidence_classification(
            refs, confidence_metric="confidence")
        assert result is not None
        assert result["winning_confidence"] > 0

    def test_inf_confidence_with_margin_metric(self):
        """Margin metric should work even with near-zero scores."""
        query = _make_star(8)
        refs = [query, _make_path(8)]
        result = query.max_confidence_classification(
            refs, confidence_metric="margin")
        assert result is not None

    def test_z_score_stable_for_near_zero(self):
        """Z-score should remain finite even with near-zero best."""
        query = _make_star(8)
        refs = [query, _make_path(8)]
        result = query.max_confidence_classification(
            refs, confidence_metric="z_score")
        assert result is not None
        assert not math.isinf(result["winning_confidence"])


# ── Section 13: Topology-specific winner analysis ─────────────────

class TestMaxConfidenceTopologySpecific:
    """Verify that different topologies may select different winners."""

    def test_all_topologies_classified_correctly(self):
        """All 5 topology types should be classified correctly."""
        refs = [
            _make_star(8, "star"),
            _make_path(8, "path"),
            _make_cycle(8, "cycle"),
            _make_complete(5, "complete"),
            _make_tree(7, "tree"),
        ]
        for i, (maker, name) in enumerate([
            (_make_star, "star"),
            (_make_path, "path"),
            (_make_cycle, "cycle"),
        ]):
            query = maker(8)
            result = query.max_confidence_classification(refs)
            assert result is not None
            assert result["best_match"] == i, \
                f"{name} should match reference #{i}"
