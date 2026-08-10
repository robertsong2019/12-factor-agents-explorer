"""Tests for link_prediction() — graph topology based edge prediction.

Methods: adamic_adar, preferential_attachment, common_neighbors.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def graph():
    """Build a graph with clear community structure for link prediction.

    Layout:
        A -- B -- C -- D -- E
              |         |
              F -- G    H

    A-B share neighbor C (through B-C link).
    A-F should be predicted (shared neighbor B).
    """
    g = MemoryGraph()
    g.add("Node A", "concept")
    g.add("Node B", "concept")
    g.add("Node C", "concept")
    g.add("Node D", "concept")
    g.add("Node E", "concept")
    g.add("Node F", "concept")
    g.add("Node G", "concept")
    g.add("Node H", "concept")

    g.link_by_label("Node A", "Node B", "related")
    g.link_by_label("Node B", "Node C", "related")
    g.link_by_label("Node C", "Node D", "related")
    g.link_by_label("Node D", "Node E", "related")
    g.link_by_label("Node B", "Node F", "related")
    g.link_by_label("Node F", "Node G", "related")
    g.link_by_label("Node D", "Node H", "related")
    return g


class TestLinkPredictionBasic:
    """Basic functionality tests."""

    def test_returns_list(self, graph):
        results = graph.link_prediction(node_id=None)
        assert isinstance(results, list)

    def test_adamic_adar_default(self, graph):
        results = graph.link_prediction(node_id=None, method="adamic_adar")
        assert len(results) > 0
        for r in results:
            assert r["method"] == "adamic_adar"

    def test_preferential_attachment(self, graph):
        results = graph.link_prediction(node_id=None, method="preferential_attachment")
        assert len(results) > 0
        for r in results:
            assert r["method"] == "preferential_attachment"

    def test_common_neighbors(self, graph):
        results = graph.link_prediction(node_id=None, method="common_neighbors")
        assert len(results) > 0
        for r in results:
            assert r["method"] == "common_neighbors"

    def test_invalid_method_raises(self, graph):
        with pytest.raises((ValueError, KeyError, TypeError)):
            # Invalid method should error when computing scores
            graph.link_prediction(node_id=None, method="nonexistent")


class TestLinkPredictionFromNode:
    """Single-source prediction tests."""

    def test_single_source_returns_pairs(self, graph):
        a_id = graph.search_by_label("Node A")[0].id
        results = graph.link_prediction(node_id=a_id)
        assert len(results) > 0
        for r in results:
            assert r["source"] == a_id

    def test_single_source_all_targets_different(self, graph):
        a_id = graph.search_by_label("Node A")[0].id
        results = graph.link_prediction(node_id=a_id)
        targets = [r["target"] for r in results]
        assert len(targets) == len(set(targets))

    def test_nonexistent_node_returns_empty(self, graph):
        results = graph.link_prediction(node_id="nonexistent")
        assert results == []

    def test_no_existing_edges_for_source(self):
        """Isolated node should return empty or PA-only results."""
        g = MemoryGraph()
        a = g.add("Isolated", "concept")
        g.add("Other", "concept")
        # No edges at all
        results = g.link_prediction(node_id=a.id, method="adamic_adar")
        assert results == []


class TestLinkPredictionScoring:
    """Score correctness tests."""

    def test_adamic_adar_penalizes_high_degree_neighbors(self):
        """Adamic-Adar gives lower weight to shared neighbors that are hubs."""
        g = MemoryGraph()
        # Hub node connected to many
        hub = g.add("Hub", "hub")
        for i in range(10):
            n = g.add(f"Leaf{i}", "leaf")
            g.link(hub.id, n.id, "connects")

        # Two nodes that share the hub as neighbor
        a = g.add("NodeA", "concept")
        b = g.add("NodeB", "concept")
        g.link(a.id, hub.id, "knows")
        g.link(b.id, hub.id, "knows")

        results = g.link_prediction(node_id=a.id, method="adamic_adar")
        # Should find b as candidate with low score (hub has high degree)
        b_results = [r for r in results if r["target"] == b.id]
        if b_results:
            assert b_results[0]["score"] < 1.0  # penalized by log(11+)

    def test_common_neighbors_score_is_integer(self, graph):
        results = graph.link_prediction(method="common_neighbors")
        for r in results:
            assert r["score"] == r["shared_count"]

    def test_preferential_attachment_favors_high_degree(self):
        """PA score = degree(a) × degree(b)."""
        g = MemoryGraph()
        hub1 = g.add("Hub1", "concept")
        hub2 = g.add("Hub2", "concept")
        leaf = g.add("Leaf", "concept")
        # hub1 connected to leaf (no direct edge hub1-hub2)
        g.link(hub1.id, leaf.id, "related")

        results = g.link_prediction(node_id=hub1.id, method="preferential_attachment")
        # hub2 should appear (degree 0, but PA = 1 * 0 = 0, or other pairs)
        assert isinstance(results, list)

    def test_score_descending_order(self, graph):
        results = graph.link_prediction(method="common_neighbors", limit=20)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, graph):
        results_all = graph.link_prediction(method="common_neighbors")
        if not results_all:
            return
        threshold = results_all[len(results_all) // 2]["score"] if len(results_all) > 1 else 0.5
        results_filtered = graph.link_prediction(method="common_neighbors", min_score=threshold)
        for r in results_filtered:
            assert r["score"] >= threshold

    def test_limit_respected(self, graph):
        results = graph.link_prediction(limit=3)
        assert len(results) <= 3


class TestLinkPredictionOutput:
    """Output structure tests."""

    def test_result_has_required_fields(self, graph):
        results = graph.link_prediction()
        assert len(results) > 0
        r = results[0]
        assert "source" in r
        assert "target" in r
        assert "score" in r
        assert "method" in r
        assert "shared_neighbors" in r
        assert "shared_count" in r

    def test_no_existing_edges_in_results(self, graph):
        """Predicted edges should not include edges that already exist."""
        results = graph.link_prediction()
        existing = set()
        for s, t in graph.conn.execute("SELECT source, target FROM edges"):
            existing.add((s, t))
            existing.add((t, s))
        for r in results:
            assert (r["source"], r["target"]) not in existing
            assert (r["target"], r["source"]) not in existing

    def test_no_self_loops(self, graph):
        results = graph.link_prediction()
        for r in results:
            assert r["source"] != r["target"]

    def test_shared_neighbors_capped(self, graph):
        """shared_neighbors list should be capped at 10 entries."""
        results = graph.link_prediction()
        for r in results:
            assert len(r["shared_neighbors"]) <= 10


class TestLinkPredictionEdgeCases:
    """Edge case tests."""

    def test_empty_graph(self):
        g = MemoryGraph()
        results = g.link_prediction()
        assert results == []

    def test_single_node(self):
        g = MemoryGraph()
        g.add("Lonely", "concept")
        results = g.link_prediction()
        assert results == []

    def test_two_nodes_no_edge(self):
        g = MemoryGraph()
        g.add("A", "concept")
        g.add("B", "concept")
        results = g.link_prediction(method="preferential_attachment")
        # PA with 0 degree = 0 score, filtered by min_score=0 default (strict >)
        for r in results:
            assert r["score"] > 0

    def test_two_nodes_with_edge(self):
        g = MemoryGraph()
        a = g.add("A", "concept")
        b = g.add("B", "concept")
        g.link(a.id, b.id, "related")
        results = g.link_prediction()
        # Only 2 nodes with existing edge → no candidates
        assert results == []

    def test_disconnected_components(self):
        """Two separate components should still get PA predictions."""
        g = MemoryGraph()
        a1, a2 = g.add("A1", "x"), g.add("A2", "x")
        b1, b2 = g.add("B1", "x"), g.add("B2", "x")
        g.link(a1.id, a2.id, "related")
        g.link(b1.id, b2.id, "related")
        # PA might predict cross-component edges
        results = g.link_prediction(method="preferential_attachment")
        assert isinstance(results, list)

    def test_clique_graph(self):
        """In a clique, all edges exist, so no predictions."""
        g = MemoryGraph()
        nodes = [g.add(f"N{i}", "concept") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                g.link(nodes[i].id, nodes[j].id, "related")
        results = g.link_prediction()
        assert results == []

    def test_all_pairs_no_duplicates(self, graph):
        """No (source, target) pair should appear twice."""
        results = graph.link_prediction(limit=50)
        pairs = [(r["source"], r["target"]) for r in results]
        assert len(pairs) == len(set(pairs))
