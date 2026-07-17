"""Tests for knowledge_gap_report() — structural gap detection."""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def empty_graph():
    return MemoryGraph(":memory:")


@pytest.fixture
def dense_graph():
    """A well-connected graph — should have a high gap score."""
    mg = MemoryGraph(":memory:")
    a = mg.add("Alpha", "concept").id
    b = mg.add("Beta", "concept").id
    c = mg.add("Gamma", "concept").id
    d = mg.add("Delta", "concept").id
    for src, tgt in [(a, b), (a, c), (b, c), (b, d), (c, d), (a, d)]:
        mg.link(src, tgt, "relates_to")
    return mg


@pytest.fixture
def orphan_graph():
    """A graph with several orphan nodes."""
    mg = MemoryGraph(":memory:")
    a = mg.add("Connected A", "concept").id
    b = mg.add("Connected B", "concept").id
    mg.link(a, b, "relates_to")
    # Orphans — no edges
    mg.add("Orphan 1", "note", tags=["important"])
    mg.add("Orphan 2", "note", tags=["misc"])
    mg.add("Degree1 Node", "concept")
    return mg


@pytest.fixture
def multi_component_graph():
    """A graph with multiple disconnected components."""
    mg = MemoryGraph(":memory:")
    # Component 1
    a1 = mg.add("A1", "concept", tags=["cluster-a", "shared"]).id
    a2 = mg.add("A2", "concept", tags=["cluster-a"]).id
    mg.link(a1, a2, "relates_to")

    # Component 2
    b1 = mg.add("B1", "concept", tags=["cluster-b", "shared"]).id
    b2 = mg.add("B2", "concept", tags=["cluster-b"]).id
    mg.link(b1, b2, "relates_to")

    # Component 3 (single node)
    mg.add("Lonely", "note")
    return mg


class TestKnowledgeGapReportBasics:

    def test_empty_graph_returns_clean_result(self, empty_graph):
        result = empty_graph.knowledge_gap_report()
        assert result["orphan_nodes"] == []
        assert result["gap_score"] == 100.0
        assert result["total_nodes"] == 0
        assert len(result["recommendations"]) > 0

    def test_returns_all_required_keys(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        required = {
            "orphan_nodes", "isolated_clusters", "bridge_opportunities",
            "underconnected_hubs", "gap_score", "recommendations",
            "component_count", "total_nodes", "total_orphans",
            "total_isolated_clusters",
        }
        assert required.issubset(result.keys())

    def test_gap_score_in_range(self, dense_graph, orphan_graph):
        for g in [dense_graph, orphan_graph]:
            score = g.knowledge_gap_report()["gap_score"]
            assert 0.0 <= score <= 100.0

    def test_dense_graph_has_high_gap_score(self, dense_graph):
        """Well-connected graph should score ≥ 70."""
        result = dense_graph.knowledge_gap_report()
        assert result["gap_score"] >= 70.0

    def test_dense_graph_no_orphans(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        assert result["total_orphans"] == 0

    def test_dense_graph_single_component(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        assert result["component_count"] == 1


class TestOrphanNodes:

    def test_orphan_graph_detects_orphans(self, orphan_graph):
        result = orphan_graph.knowledge_gap_report()
        assert result["total_orphans"] >= 3
        labels = [o["label"] for o in result["orphan_nodes"]]
        assert "Orphan 1" in labels
        assert "Orphan 2" in labels

    def test_orphans_have_low_degree(self, orphan_graph):
        result = orphan_graph.knowledge_gap_report()
        for o in result["orphan_nodes"]:
            assert o["degree"] <= 1

    def test_orphan_node_fields(self, orphan_graph):
        result = orphan_graph.knowledge_gap_report()
        if result["orphan_nodes"]:
            o = result["orphan_nodes"][0]
            assert "node_id" in o
            assert "label" in o
            assert "kind" in o
            assert "degree" in o
            assert "weight" in o


class TestIsolatedClusters:

    def test_multi_component_detects_isolated(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report()
        assert result["component_count"] >= 3

    def test_isolated_cluster_fields(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report()
        for cluster in result["isolated_clusters"]:
            assert "component_id" in cluster
            assert "size" in cluster
            assert "cross_edges" in cluster
            assert "internal_edges" in cluster
            assert "total_weight" in cluster
            assert "avg_degree" in cluster

    def test_isolated_cluster_cross_edges(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report()
        for cluster in result["isolated_clusters"]:
            assert cluster["cross_edges"] < 2

    def test_no_isolated_clusters_in_dense_graph(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        assert result["total_isolated_clusters"] == 0


class TestBridgeOpportunities:

    def test_bridge_opportunities_in_multi_component(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report()
        # Multi-component graph should suggest bridges
        assert isinstance(result["bridge_opportunities"], list)

    def test_bridge_opportunity_fields(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report()
        for bridge in result["bridge_opportunities"]:
            assert "node_a" in bridge
            assert "node_b" in bridge
            assert "score" in bridge
            assert "shared_tags" in bridge
            assert "component_a_size" in bridge
            assert "component_b_size" in bridge

    def test_bridge_score_above_min(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report(min_score=0.0)
        for bridge in result["bridge_opportunities"]:
            assert bridge["score"] >= 0.0

    def test_max_gaps_limit(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report(max_gaps=2)
        assert len(result["bridge_opportunities"]) <= 2

    def test_no_bridges_in_dense_graph(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        assert result["bridge_opportunities"] == []


class TestUnderconnectedHubs:

    def test_underconnected_fields(self, orphan_graph):
        result = orphan_graph.knowledge_gap_report()
        for hub in result["underconnected_hubs"]:
            assert "node_id" in hub
            assert "label" in hub
            assert "weight" in hub
            assert "degree" in hub
            assert "gap" in hub

    def test_underconnected_capped(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        assert len(result["underconnected_hubs"]) <= 20


class TestNodeIdFilter:

    def test_node_ids_restricts_analysis(self, dense_graph):
        nodes = dense_graph.conn.execute("SELECT id FROM nodes LIMIT 2").fetchall()
        node_list = [n["id"] for n in nodes]
        sub_result = dense_graph.knowledge_gap_report(node_ids=node_list)
        assert sub_result["total_nodes"] == 2

    def test_nonexistent_node_ids(self, empty_graph):
        result = empty_graph.knowledge_gap_report(node_ids=["nonexistent"])
        assert result["total_nodes"] == 0


class TestRecommendations:

    def test_recommendations_non_empty(self, orphan_graph):
        result = orphan_graph.knowledge_gap_report()
        assert len(result["recommendations"]) > 0

    def test_recommendations_for_healthy_graph(self, dense_graph):
        result = dense_graph.knowledge_gap_report()
        assert len(result["recommendations"]) > 0

    def test_orphan_recommendation_mentions_count(self, orphan_graph):
        result = orphan_graph.knowledge_gap_report()
        orphan_rec = [r for r in result["recommendations"] if "orphan" in r.lower()]
        assert len(orphan_rec) > 0

    def test_gap_level_recommendation(self, multi_component_graph):
        result = multi_component_graph.knowledge_gap_report()
        # Should mention bridges, isolated clusters, or gaps
        relevant = [
            r for r in result["recommendations"]
            if any(kw in r.lower() for kw in ["bridge", "isolated", "cluster", "connect", "gap"])
        ]
        assert len(relevant) > 0


class TestNonMutating:

    def test_does_not_add_nodes(self, dense_graph):
        before = dense_graph.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        dense_graph.knowledge_gap_report()
        after = dense_graph.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        assert before == after

    def test_does_not_add_edges(self, dense_graph):
        before = dense_graph.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        dense_graph.knowledge_gap_report()
        after = dense_graph.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        assert before == after
