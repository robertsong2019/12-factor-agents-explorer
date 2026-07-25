"""Tests for visualize_ascii and shortest_path_undirected."""
import pytest
from memory_graph import MemoryGraph


class TestVisualizeAscii:
    def test_empty_graph_returns_header(self):
        g = MemoryGraph()
        result = g.visualize_ascii()
        assert "📊 Memory Network:" in result

    def test_contains_node_label(self):
        g = MemoryGraph()
        g.add("alpha", kind="entity")
        result = g.visualize_ascii()
        assert "alpha" in result

    def test_contains_edge_info(self):
        g = MemoryGraph()
        a = g.add("nodeA", kind="entity")
        b = g.add("nodeB", kind="entity")
        g.link(a.id, b.id, "connects")
        result = g.visualize_ascii()
        assert "connects" in result
        assert "nodeB" in result

    def test_returns_string(self):
        g = MemoryGraph()
        g.add("solo", kind="concept")
        result = g.visualize_ascii()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_weight_bar_proportional(self):
        g = MemoryGraph()
        heavy = g.add("heavy", kind="entity")
        light = g.add("light", kind="entity")
        # Lower the weight of 'light' node
        g.reweight(light.id, -0.9)  # default 1.0 - 0.9 = 0.1
        result = g.visualize_ascii()
        # Heavy node should have more bar characters than light
        heavy_line = [l for l in result.split("\n") if "heavy" in l][0]
        light_line = [l for l in result.split("\n") if "light" in l][0]
        assert heavy_line.count("█") > light_line.count("█")


class TestShortestPathUndirected:
    def test_same_node_returns_single(self):
        g = MemoryGraph()
        a = g.add("A")
        result = g.shortest_path_undirected(a.id, a.id)
        assert result == [a.id]

    def test_direct_edge(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        g.link(a.id, b.id, "r")
        result = g.shortest_path_undirected(a.id, b.id)
        assert result == [a.id, b.id]

    def test_two_hop_path(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        c = g.add("C")
        g.link(a.id, b.id, "r")
        g.link(b.id, c.id, "r")
        result = g.shortest_path_undirected(a.id, c.id)
        assert result == [a.id, b.id, c.id]

    def test_no_path_returns_none(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        # No edges connecting them
        result = g.shortest_path_undirected(a.id, b.id)
        assert result is None

    def test_undirectional_traversal(self):
        """Path should work regardless of edge direction."""
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        # Edge only from b -> a, but path a->b should still work (undirected)
        g.link(b.id, a.id, "r")
        result = g.shortest_path_undirected(a.id, b.id)
        assert result is not None
        assert len(result) == 2

    def test_shortest_among_multiple_paths(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        c = g.add("C")
        d = g.add("D")
        # Short path: A-B-D
        g.link(a.id, b.id, "r")
        g.link(b.id, d.id, "r")
        # Long path: A-C-D
        g.link(a.id, c.id, "r")
        g.link(c.id, d.id, "r")
        result = g.shortest_path_undirected(a.id, d.id)
        assert len(result) == 3  # shortest is 3 nodes (2 hops)
