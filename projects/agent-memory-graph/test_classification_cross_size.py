"""Tests for classification_cross_size() — size generalization evaluation.

Tests that classification methods can identify topology types even when
query graphs have different node counts than reference graphs.

This is the 13th API in the classification suite.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph(":memory:")


# Helper: fast params to keep tests under 2s each
FAST = dict(
    topologies=["star", "path", "cycle"],
    query_sizes=[8, 10, 12],
    num_references_per_category=1,
    num_queries=1,
    methods=["rrf", "spectral"],
)
FAST_ALL_METHODS = dict(
    topologies=["star", "path", "cycle"],
    query_sizes=[8, 10, 12],
    num_references_per_category=1,
    num_queries=1,
)


# ── Basic Structure & Return Shape ─────────────────────────────

class TestCrossSizeBasicStructure:
    def test_returns_dict(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert isinstance(result, dict)

    def test_default_methods(self, mg):
        result = mg.classification_cross_size(
            topologies=["star"], query_sizes=[10],
            num_references_per_category=1, num_queries=1
        )
        expected = {"graph", "spectral", "hybrid", "rrf", "bayesian",
                    "knn", "weighted_average", "compare"}
        assert set(result["methods"]) == expected

    def test_default_query_sizes(self, mg):
        result = mg.classification_cross_size(
            topologies=["star"], num_references_per_category=1, num_queries=1
        )
        assert result["query_sizes"] == [6, 8, 10, 12, 14, 16]

    def test_default_reference_size(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert result["reference_size"] == 10

    def test_default_topologies(self, mg):
        result = mg.classification_cross_size(
            query_sizes=[10], num_references_per_category=1, num_queries=1,
            methods=["rrf"]
        )
        assert set(result["topologies"]) == {
            "star", "path", "cycle", "complete", "bipartite", "tree"
        }

    def test_has_size_accuracy_curves(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert "size_accuracy_curves" in result
        for method in result["methods"]:
            assert method in result["size_accuracy_curves"]
            for qs in result["query_sizes"]:
                assert qs in result["size_accuracy_curves"][method]

    def test_has_size_invariance_score(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert "size_invariance_score" in result
        for method in result["methods"]:
            assert isinstance(result["size_invariance_score"][method], float)
            assert 0.0 <= result["size_invariance_score"][method] <= 1.0

    def test_has_rankings(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert "rankings" in result
        assert len(result["rankings"]) == len(result["methods"])
        scores = [s for _, s in result["rankings"]]
        assert scores == sorted(scores, reverse=True)

    def test_has_summary(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 20

    def test_has_best_and_worst(self, mg):
        result = mg.classification_cross_size(**FAST_ALL_METHODS)
        assert result["best_method"] is not None
        assert result["worst_method"] is not None
        assert result["best_method"] != result["worst_method"]


# ── Accuracy Values ────────────────────────────────────────────

class TestCrossSizeAccuracy:
    def test_accuracy_values_in_range(self, mg):
        result = mg.classification_cross_size(**FAST)
        for method, curve in result["size_accuracy_curves"].items():
            for qs, acc in curve.items():
                assert 0.0 <= acc <= 1.0, f"{method}@{qs}: {acc}"

    def test_reference_size_has_high_accuracy(self, mg):
        """When query_size == reference_size, accuracy should be high."""
        result = mg.classification_cross_size(
            topologies=["star", "path", "cycle"],
            reference_size=10, query_sizes=[10],
            num_references_per_category=1, num_queries=1,
        )
        ref_accuracies = [
            curve[10] for curve in result["size_accuracy_curves"].values()
        ]
        assert max(ref_accuracies) > 0.5, \
            f"At same size, at least one method should be > 50%. Got: {ref_accuracies}"

    def test_invariance_score_is_mean(self, mg):
        """Invariance score should be mean of accuracy across sizes."""
        result = mg.classification_cross_size(**FAST)
        curve = result["size_accuracy_curves"]["rrf"]
        expected = round(sum(curve.values()) / len(curve), 4)
        assert result["size_invariance_score"]["rrf"] == expected


# ── Size Decay ─────────────────────────────────────────────────

class TestCrossSizeDecay:
    def test_has_size_decay(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert "size_decay" in result
        for method in result["methods"]:
            assert method in result["size_decay"]
            decay = result["size_decay"][method]
            assert "ref_accuracy" in decay
            assert "min_size" in decay
            assert "max_size" in decay
            assert "min_size_accuracy" in decay
            assert "max_size_accuracy" in decay
            assert "shrink_drop" in decay
            assert "grow_drop" in decay

    def test_decay_values_non_negative(self, mg):
        """Drop values should be non-negative (or 0 if accuracy improved)."""
        result = mg.classification_cross_size(**FAST)
        for method, decay in result["size_decay"].items():
            assert decay["shrink_drop"] >= 0.0, \
                f"{method}: shrink_drop={decay['shrink_drop']}"
            assert decay["grow_drop"] >= 0.0, \
                f"{method}: grow_drop={decay['grow_drop']}"


# ── Per-Topology Resilience ────────────────────────────────────

class TestCrossSizeTopologyResilience:
    def test_has_per_topology_resilience(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert "per_topology_resilience" in result
        for topo in result["topologies"]:
            assert topo in result["per_topology_resilience"]
            val = result["per_topology_resilience"][topo]
            assert 0.0 <= val <= 1.0

    def test_has_per_topology_at_size(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert "per_topology_at_size" in result
        for qs in result["query_sizes"]:
            assert qs in result["per_topology_at_size"]
            for topo in result["topologies"]:
                assert topo in result["per_topology_at_size"][qs]


# ── Custom Parameters ──────────────────────────────────────────

class TestCrossSizeCustomParams:
    def test_custom_reference_size(self, mg):
        result = mg.classification_cross_size(
            reference_size=8, topologies=["star"],
            query_sizes=[8], num_references_per_category=1, num_queries=1,
            methods=["rrf"],
        )
        assert result["reference_size"] == 8

    def test_custom_query_sizes(self, mg):
        result = mg.classification_cross_size(
            query_sizes=[5, 10, 15], topologies=["star"],
            num_references_per_category=1, num_queries=1, methods=["rrf"]
        )
        assert result["query_sizes"] == [5, 10, 15]

    def test_custom_topologies(self, mg):
        result = mg.classification_cross_size(
            topologies=["star", "path"], methods=["rrf"],
            query_sizes=[10], num_references_per_category=1, num_queries=1
        )
        assert result["topologies"] == ["star", "path"]

    def test_custom_methods(self, mg):
        result = mg.classification_cross_size(
            methods=["rrf", "spectral"],
            topologies=["star"], query_sizes=[10],
            num_references_per_category=1, num_queries=1
        )
        assert result["methods"] == ["rrf", "spectral"]

    def test_custom_num_references(self, mg):
        """More references per category = harder classification."""
        r1 = mg.classification_cross_size(
            num_references_per_category=1, methods=["rrf"],
            topologies=["star"], query_sizes=[10], num_queries=1
        )
        r3 = mg.classification_cross_size(
            num_references_per_category=3, methods=["rrf"],
            topologies=["star"], query_sizes=[10], num_queries=1
        )
        assert "rrf" in r1["size_accuracy_curves"]
        assert "rrf" in r3["size_accuracy_curves"]

    def test_custom_num_queries(self, mg):
        result = mg.classification_cross_size(
            num_queries=5, topologies=["star"],
            query_sizes=[10], num_references_per_category=1,
            methods=["rrf"]
        )
        assert len(result["query_sizes"]) == 1  # [10]


# ── Edge Cases ─────────────────────────────────────────────────

class TestCrossSizeEdgeCases:
    def test_single_query_size(self, mg):
        """Should work with only one query size."""
        result = mg.classification_cross_size(
            query_sizes=[10], topologies=["star", "path"],
            num_references_per_category=1, num_queries=1, methods=["rrf"]
        )
        assert result["query_sizes"] == [10]
        assert len(result["rankings"]) > 0

    def test_single_topology(self, mg):
        """Should work with only one topology (trivially 100% accuracy)."""
        result = mg.classification_cross_size(
            topologies=["star"], query_sizes=[8, 10],
            num_references_per_category=1, num_queries=1, methods=["rrf"]
        )
        assert result["topologies"] == ["star"]
        for qs in result["query_sizes"]:
            acc = result["size_accuracy_curves"]["rrf"].get(qs, 0.0)
            assert acc == 1.0, f"Single-topology: rrf@{qs} should be 1.0, got {acc}"

    def test_single_method(self, mg):
        """Should work with only one method."""
        result = mg.classification_cross_size(
            methods=["graph"], topologies=["star", "path"],
            query_sizes=[10], num_references_per_category=1, num_queries=1
        )
        assert result["methods"] == ["graph"]
        assert result["best_method"] == "graph"
        assert result["worst_method"] == "graph"

    def test_empty_methods(self, mg):
        """Should handle empty methods list gracefully."""
        result = mg.classification_cross_size(
            methods=[], topologies=["star"],
            query_sizes=[10], num_references_per_category=1, num_queries=1
        )
        assert result["size_accuracy_curves"] == {}

    def test_unknown_method_skipped(self, mg):
        """Unknown method names should not crash."""
        result = mg.classification_cross_size(
            methods=["rrf", "nonexistent"], topologies=["star"],
            query_sizes=[10], num_references_per_category=1, num_queries=1
        )
        assert "rrf" in result["size_accuracy_curves"]
        assert "nonexistent" in result["size_accuracy_curves"]

    def test_very_small_query_size(self, mg):
        """Should handle very small graphs (3 nodes)."""
        result = mg.classification_cross_size(
            reference_size=8, query_sizes=[3, 8],
            topologies=["star", "path"],
            num_references_per_category=1, num_queries=1, methods=["rrf"]
        )
        assert 3 in result["size_accuracy_curves"]["rrf"]


# ── Determinism ────────────────────────────────────────────────

class TestCrossSizeDeterminism:
    def test_same_result_twice(self, mg):
        """Same parameters should give same accuracy values."""
        params = dict(
            methods=["rrf", "spectral"], query_sizes=[8, 10, 12],
            topologies=["star", "path", "cycle"],
            num_references_per_category=1, num_queries=1
        )
        r1 = mg.classification_cross_size(**params)
        r2 = mg.classification_cross_size(**params)
        assert r1["size_accuracy_curves"] == r2["size_accuracy_curves"]

    def test_different_mg_instances(self):
        """Different MemoryGraph instances should produce same results."""
        mg1 = MemoryGraph(":memory:")
        mg2 = MemoryGraph(":memory:")
        params = dict(
            methods=["rrf"], query_sizes=[10],
            topologies=["star"], num_references_per_category=1, num_queries=1
        )
        r1 = mg1.classification_cross_size(**params)
        r2 = mg2.classification_cross_size(**params)
        assert r1["size_accuracy_curves"] == r2["size_accuracy_curves"]


# ── Integration with Existing Suite ────────────────────────────

class TestCrossSizeIntegration:
    def test_summary_mentions_methods_or_sizes(self, mg):
        result = mg.classification_cross_size(**FAST)
        assert len(result["summary"]) > 20
        assert "size" in result["summary"].lower() or "method" in result["summary"].lower()

    def test_complement_with_benchmark(self, mg):
        """Cross-size and benchmark both classify graphs."""
        cross = mg.classification_cross_size(
            reference_size=10, query_sizes=[10], methods=["rrf"],
            topologies=["star", "path"],
            num_references_per_category=1, num_queries=1
        )
        assert "rrf" in cross["size_accuracy_curves"]

    def test_ranking_best_is_consistent(self, mg):
        """Best method by invariance score should have highest mean."""
        result = mg.classification_cross_size(**FAST_ALL_METHODS)
        best = result["best_method"]
        best_score = result["size_invariance_score"][best]
        for m in result["methods"]:
            assert result["size_invariance_score"][m] <= best_score, \
                f"{m} ({result['size_invariance_score'][m]}) > {best} ({best_score})"
