"""Tests for entropy_weighted_retrieval() — entropy as retrieval signal.

Research #032 key insight: amg's unique advantage is connecting entropy
toolkit to retrieval scoring. While Mem0 uses vector similarity and Graphiti
uses graph traversal, amg can use *structural entropy* to boost nodes that
are informationally rich and well-connected.

This is a novel differentiator — no other agent memory system uses entropy
for retrieval weighting.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def populated_graph():
    """Create a graph with known structure for retrieval testing.

    Structure:
        Hub node (high degree) — high entropy contribution
        Leaf nodes (degree 1) — low entropy contribution
        Bridge node connecting two clusters
    """
    g = MemoryGraph()
    # Core cluster
    hub = g.add("Python Programming", kind="skill", data={"level": "expert"})
    a = g.add("FastAPI", kind="skill", data={"type": "framework"})
    b = g.add("Django", kind="skill", data={"type": "framework"})
    c = g.add("asyncio", kind="skill", data={"type": "library"})
    g.link(hub.id, a.id, "includes")
    g.link(hub.id, b.id, "includes")
    g.link(hub.id, c.id, "includes")
    # Hub has degree 3 — high entropy node
    g._hub_id = hub.id
    g._leaf_ids = [a.id, b.id, c.id]
    return g


class TestEntropyWeightedRetrieval:
    def test_returns_results(self, populated_graph):
        """Basic retrieval returns results with entropy weights."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=5
        )
        assert len(results) > 0
        for r in results:
            assert "node_id" in r
            assert "label" in r
            assert "score" in r
            assert "entropy_weight" in r

    def test_hub_gets_higher_weight(self, populated_graph):
        """High-degree hub node should get higher entropy weight than leaves."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=10
        )
        hub_result = next(r for r in results if r["node_id"] == populated_graph._hub_id)
        leaf_results = [r for r in results if r["node_id"] in populated_graph._leaf_ids]
        assert all(hub_result["entropy_weight"] >= r["entropy_weight"] for r in leaf_results)

    def test_score_combines_similarity_and_entropy(self, populated_graph):
        """Final score should be a blend of similarity and entropy weight."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=5
        )
        for r in results:
            # score should be between 0 and 1
            assert 0.0 <= r["score"] <= 1.0
            assert "similarity" in r
            assert r["similarity"] >= 0.0

    def test_alpha_parameter(self, populated_graph):
        """Alpha controls entropy vs similarity blend."""
        # Alpha=0: pure similarity, no entropy influence
        results_no_entropy = populated_graph.entropy_weighted_retrieval(
            "Python", limit=5, alpha=0.0
        )
        # Alpha=1: maximum entropy influence
        results_max_entropy = populated_graph.entropy_weighted_retrieval(
            "Python", limit=5, alpha=1.0
        )
        # With alpha=0, entropy_weight should not affect score
        for r in results_no_entropy:
            assert r["score"] == pytest.approx(r["similarity"], abs=0.01)

    def test_entropy_index_choice(self, populated_graph):
        """Different entropy indices produce valid results."""
        for idx in ["sombor", "randic", "abc"]:
            results = populated_graph.entropy_weighted_retrieval(
                "Python", limit=5, entropy_index=idx
            )
            assert len(results) > 0

    def test_unknown_index_raises(self, populated_graph):
        with pytest.raises(ValueError, match="Unknown entropy"):
            populated_graph.entropy_weighted_retrieval(
                "Python", entropy_index="nonexistent"
            )

    def test_empty_graph(self):
        g = MemoryGraph()
        results = g.entropy_weighted_retrieval("anything")
        assert results == []

    def test_limit_respected(self, populated_graph):
        """Results should respect the limit."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=2
        )
        assert len(results) <= 2

    def test_results_sorted_by_score(self, populated_graph):
        """Results should be sorted by score descending."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=10
        )
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_detail_flag_includes_node(self, populated_graph):
        """detail=True includes full node object."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=5, detail=True
        )
        for r in results:
            assert "node" in r

    def test_entropy_weight_bounded(self, populated_graph):
        """Entropy weight should be in [0, 1]."""
        results = populated_graph.entropy_weighted_retrieval(
            "Python", limit=10
        )
        for r in results:
            assert 0.0 <= r["entropy_weight"] <= 1.0
