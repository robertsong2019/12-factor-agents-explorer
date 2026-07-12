"""Tests for subgraph_by_edge_type() — Cycle 229.

MAGMA (ACL 2026) inspired multi-orthogonal graph views.
Extracts a subgraph containing only edges of a specific relation type.
"""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def mixed_graph(mg):
    """Create a graph with multiple edge types."""
    a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
    # Causal edges
    mg.link(a.id, b.id, "causes")
    mg.link(b.id, c.id, "causes")
    # Temporal edges
    mg.link(a.id, c.id, "before")
    # Evidence edges
    mg.link(d.id, b.id, "evidence")
    return {"a": a, "b": b, "c": c, "d": d, "mg": mg}


class TestSubgraphByEdgeType:
    """subgraph_by_edge_type: filter graph to a single relation type."""

    def test_empty_graph(self, mg):
        result = mg.subgraph_by_edge_type("causes")
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["stats"]["node_count"] == 0

    def test_no_matching_edges(self, mg):
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "causes")
        result = mg.subgraph_by_edge_type("evidence")
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_single_edge_type_filtered(self, mixed_graph):
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        assert len(result["edges"]) == 2
        for e in result["edges"]:
            assert e["relation"] == "causes"
        assert result["stats"]["edge_count"] == 2

    def test_nodes_filtered_correctly(self, mixed_graph):
        """Only nodes participating in 'causes' edges should appear."""
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        node_ids = {n["id"] for n in result["nodes"]}
        # A→B and B→C, so nodes A, B, C but NOT D
        assert mixed_graph["a"].id in node_ids
        assert mixed_graph["b"].id in node_ids
        assert mixed_graph["c"].id in node_ids
        assert mixed_graph["d"].id not in node_ids
        assert result["stats"]["node_count"] == 3

    def test_different_relation(self, mixed_graph):
        """Evidence relation should only return D→B."""
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("evidence")
        assert len(result["edges"]) == 1
        assert result["edges"][0]["source"] == mixed_graph["d"].id
        assert result["edges"][0]["target"] == mixed_graph["b"].id
        assert result["stats"]["node_count"] == 2

    def test_temporal_relation(self, mixed_graph):
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("before")
        assert len(result["edges"]) == 1
        assert result["stats"]["node_count"] == 2

    def test_include_isolated(self, mixed_graph):
        """include_isolated=True should include all nodes."""
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes", include_isolated=True)
        # All 4 nodes even though D has no 'causes' edge
        assert result["stats"]["node_count"] == 4
        assert len(result["edges"]) == 2

    def test_stats_density(self, mixed_graph):
        """Density should be edge_count / (n * (n-1)) for directed."""
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        n = result["stats"]["node_count"]  # 3
        m = result["stats"]["edge_count"]  # 2
        expected_density = m / (n * (n - 1)) if n > 1 else 0.0
        assert result["stats"]["density"] == round(expected_density, 4)

    def test_node_data_preserved(self, mixed_graph):
        """Node objects in subgraph should have full data."""
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        for node in result["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "kind" in node
            assert "data" in node
            assert "weight" in node

    def test_edge_data_preserved(self, mixed_graph):
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        for edge in result["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge
            assert "weight" in edge

    def test_relation_in_result(self, mixed_graph):
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        assert result["relation"] == "causes"

    def test_single_node_graph(self, mg):
        mg.add("A")
        result = mg.subgraph_by_edge_type("causes")
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_density_zero_no_edges(self, mg):
        a, b = mg.add("A"), mg.add("B")
        # No edges of type 'causes'
        result = mg.subgraph_by_edge_type("causes")
        assert result["stats"]["density"] == 0.0

    def test_density_complete_graph(self, mg):
        """K₃ all with same relation → density = 6/(3*2) = 1.0."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "rel")
        mg.link(b.id, a.id, "rel")
        mg.link(b.id, c.id, "rel")
        mg.link(c.id, b.id, "rel")
        mg.link(a.id, c.id, "rel")
        mg.link(c.id, a.id, "rel")
        result = mg.subgraph_by_edge_type("rel")
        assert result["stats"]["density"] == 1.0

    def test_two_relation_types_disjoint(self, mg):
        """Two edge types on completely disjoint node sets."""
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "type1")
        mg.link(c.id, d.id, "type2")
        r1 = mg.subgraph_by_edge_type("type1")
        r2 = mg.subgraph_by_edge_type("type2")
        assert r1["stats"]["node_count"] == 2
        assert r2["stats"]["node_count"] == 2
        r1_ids = {n["id"] for n in r1["nodes"]}
        r2_ids = {n["id"] for n in r2["nodes"]}
        assert r1_ids.isdisjoint(r2_ids)

    def test_same_nodes_different_relations(self, mg):
        """Same node pair can have multiple edge types — each view sees its own."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "causes")
        mg.link(a.id, b.id, "before")
        r1 = mg.subgraph_by_edge_type("causes")
        r2 = mg.subgraph_by_edge_type("before")
        assert len(r1["edges"]) == 1
        assert len(r2["edges"]) == 1
        assert r1["edges"][0]["relation"] == "causes"
        assert r2["edges"][0]["relation"] == "before"

    def test_result_format_consistent_with_subgraph(self, mixed_graph):
        """Result format should match subgraph() output structure."""
        mg = mixed_graph["mg"]
        result = mg.subgraph_by_edge_type("causes")
        assert "nodes" in result
        assert "edges" in result
        # subgraph() has 'center', we have 'relation' and 'stats' instead
        assert "relation" in result
        assert "stats" in result

    def test_large_graph_performance(self, mg):
        """Should handle moderate graph sizes efficiently."""
        nodes = [mg.add(f"N{i}") for i in range(20)]
        for i in range(19):
            mg.link(nodes[i].id, nodes[i + 1].id, "chain")
        # Add some other edges
        for i in range(0, 20, 5):
            mg.link(nodes[i].id, nodes[(i + 7) % 20].id, "skip")
        result = mg.subgraph_by_edge_type("chain")
        assert result["stats"]["edge_count"] == 19
        assert result["stats"]["node_count"] == 20
