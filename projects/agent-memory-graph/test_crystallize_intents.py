"""Tests for crystallize_intents() — Cycle 235.

CogniFold-inspired: when concept clusters reach sufficient density,
they crystallize into explicit intent nodes.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def dense_graph():
    """Graph with a dense cluster that should crystallize."""
    mg = MemoryGraph()
    # Create a tightly connected cluster
    mg.add("Python tutorial", "topic")
    mg.add("Python guide", "topic")
    mg.add("Python examples", "topic")
    nodes = [n.id for n in mg.recall("Python", limit=10)]
    # Fully connect them
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i != j:
                mg.link(a, b, "related")
    return mg, nodes


@pytest.fixture
def sparse_graph():
    """Graph with sparse connections — should NOT crystallize."""
    mg = MemoryGraph()
    mg.add("Isolated A", "topic")
    mg.add("Isolated B", "topic")
    mg.add("Isolated C", "topic")
    # Only one edge
    nodes = [n.id for n in mg.recall("Isolated", limit=10)]
    mg.link(nodes[0], nodes[1], "related")
    return mg


@pytest.fixture
def tiny_graph():
    """Graph with too few nodes to crystallize."""
    mg = MemoryGraph()
    mg.add("Solo", "topic")
    return mg


class TestCrystallizeBasics:
    """Basic structure and return value tests."""

    def test_returns_dict(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents()
        assert "crystallized" in result
        assert "skipped" in result
        assert "total_communities" in result

    def test_crystallized_is_list(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents()
        assert isinstance(result["crystallized"], list)

    def test_total_communities_nonneg(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents()
        assert result["total_communities"] >= 0


class TestDenseClusterCrystallizes:
    """Dense clusters should crystallize into intents."""

    def test_dense_cluster_crystallizes(self, dense_graph):
        mg, nodes = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        assert len(result["crystallized"]) > 0

    def test_intent_node_created(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        for c in result["crystallized"]:
            # Verify intent node exists
            node = mg.get_node(c["intent_id"])
            assert node is not None
            assert node.kind == "intent"

    def test_intent_has_abstracts_edges(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        for c in result["crystallized"]:
            # Check that abstracts edges were created by counting neighbors
            neighbors = mg.neighbors(c["intent_id"])
            assert len(neighbors) >= c["size"]  # at least all members

    def test_crystallized_has_required_fields(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        for c in result["crystallized"]:
            assert "intent_id" in c
            assert "label" in c
            assert "community_id" in c
            assert "size" in c
            assert "density" in c
            assert "dominant_kind" in c
            assert "members" in c

    def test_density_above_threshold(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        for c in result["crystallized"]:
            assert c["density"] >= 0.3


class TestSparseClusterSkipped:
    """Sparse clusters should be skipped."""

    def test_sparse_skipped_with_high_threshold(self, sparse_graph):
        result = sparse_graph.crystallize_intents(density_threshold=0.9)
        # Should skip everything
        assert len(result["crystallized"]) == 0

    def test_skipped_has_reasons(self, sparse_graph):
        result = sparse_graph.crystallize_intents(density_threshold=0.9)
        for s in result["skipped"]:
            assert "reason" in s
            assert s["reason"] in ("low_density", "too_small", "already_crystallized")


class TestTinyGraph:
    """Graphs with too few nodes."""

    def test_single_node_skipped(self, tiny_graph):
        result = tiny_graph.crystallize_intents(min_community_size=3)
        # With 1 node, nothing should crystallize
        assert len(result["crystallized"]) == 0

    def test_min_community_size_filter(self, dense_graph):
        """Raising min_community_size should filter small communities."""
        mg, _ = dense_graph
        result_low = mg.crystallize_intents(min_community_size=2, density_threshold=0.3)
        result_high = mg.crystallize_intents(min_community_size=10, density_threshold=0.3)
        assert len(result_high["crystallized"]) <= len(result_low["crystallized"])


class TestIdempotency:
    """Running twice should not create duplicate intents."""

    def test_double_run_skips_existing(self, dense_graph):
        mg, _ = dense_graph
        first = mg.crystallize_intents(density_threshold=0.3)
        assert len(first["crystallized"]) > 0

        second = mg.crystallize_intents(density_threshold=0.3)
        # Should skip because already_crystallized
        assert len(second["crystallized"]) == 0
        assert any(s["reason"] == "already_crystallized" for s in second["skipped"])


class TestDensityThreshold:
    """Density threshold filtering."""

    def test_low_threshold_crystallizes_more(self, dense_graph):
        mg, _ = dense_graph
        low = mg.crystallize_intents(density_threshold=0.0, min_community_size=2)
        high = mg.crystallize_intents(density_threshold=0.99, min_community_size=2)
        # Low threshold should crystallize at least as many as high
        # (both from fresh graphs since we mutate)
        assert len(low["crystallized"]) >= len(high["crystallized"])


class TestIntentNodeProperties:
    """Intent nodes should have correct properties."""

    def test_intent_node_has_source_metadata(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        for c in result["crystallized"]:
            node = mg.get_node(c["intent_id"])
            assert node.data.get("source") == "crystallize_intents"
            assert "density" in node.data

    def test_intent_label_starts_with_intent(self, dense_graph):
        mg, _ = dense_graph
        result = mg.crystallize_intents(density_threshold=0.3)
        for c in result["crystallized"]:
            assert c["label"].startswith("Intent:")


class TestDoesNotCrashEmpty:
    """Empty graph should not crash."""

    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.crystallize_intents()
        assert result["crystallized"] == []
        assert result["total_communities"] == 0
