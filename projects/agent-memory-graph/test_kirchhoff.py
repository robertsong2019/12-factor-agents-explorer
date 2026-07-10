"""Tests for Kirchhoff index and spanning tree count."""

import pytest
from memory_graph import MemoryGraph


def _make_complete_graph(n):
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, relation="r", weight=1.0)
    return mg


def _make_path_graph(n):
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(n - 1):
        mg.link(nodes[i].id, nodes[i+1].id, relation="r", weight=1.0)
    return mg


def _make_cycle_graph(n):
    mg = MemoryGraph()
    nodes = [mg.add(label=f"n{i}", kind="test") for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i+1) % n].id, relation="r", weight=1.0)
    return mg


class TestKirchhoffIndex:
    """Kirchhoff index tests."""

    def test_complete_graph_k3(self):
        """K_3: Kf = n*(n-1) = 3*2 = 6. Each R(i,j) = 2/3, 3 pairs → 2.
        Actually Kf(K_n) = n-1 (each R = 2/n, n(n-1)/2 pairs → (n-1))."""
        mg = _make_complete_graph(3)
        result = mg.kirchhoff_index()
        # For K_n: R(i,j) = 2/n for each pair. Kf = (n choose 2) * 2/n = (n-1)
        assert abs(result - 2.0) < 0.01, f"K_3 Kf should be 2.0, got {result}"

    def test_complete_graph_k4(self):
        """K_4: Kf = n-1 = 3."""
        mg = _make_complete_graph(4)
        result = mg.kirchhoff_index()
        assert abs(result - 3.0) < 0.01, f"K_4 Kf should be 3.0, got {result}"

    def test_path_graph_p3(self):
        """P_3: R(0,1) = 1, R(1,2) = 1, R(0,2) = 2. Kf = 1+1+2 = 4."""
        mg = _make_path_graph(3)
        result = mg.kirchhoff_index()
        assert abs(result - 4.0) < 0.01, f"P_3 Kf should be 4.0, got {result}"

    def test_cycle_graph_c4(self):
        """C_4: R(adjacent) = 3/4, R(opposite) = 1. Kf = 4*(3/4) + 2*1 = 3+2 = 5.
        Wait: 4 adjacent pairs * 3/4 + 2 opposite pairs * 1 = 3 + 2 = 5."""
        mg = _make_cycle_graph(4)
        result = mg.kirchhoff_index()
        assert abs(result - 5.0) < 0.05, f"C_4 Kf should be 5.0, got {result}"

    def test_too_few_nodes(self):
        """< 2 nodes returns 0."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        assert mg.kirchhoff_index() == 0.0

    def test_positive_for_connected(self):
        """Kirchhoff index should be positive for any connected graph."""
        mg = _make_path_graph(5)
        assert mg.kirchhoff_index() > 0

    def test_include_quarantined(self):
        """include_quarantined includes all nodes."""
        mg = _make_complete_graph(4)
        # Quarantine one
        nid = [r["id"] for r in mg.conn.execute("SELECT id FROM nodes LIMIT 1").fetchall()][0]
        mg.node_quarantine(nid)
        default_result = mg.kirchhoff_index()
        all_result = mg.kirchhoff_index(include_quarantined=True)
        # Including quarantined gives different (larger graph) result
        assert all_result != default_result or abs(all_result - 3.0) < 0.01


class TestSpanningTreeCount:
    """Spanning tree count via Matrix-Tree theorem."""

    def test_complete_graph_k3(self):
        """K_3 has 3 spanning trees (Cayley: n^(n-2) = 3^1 = 3)."""
        mg = _make_complete_graph(3)
        assert mg.spanning_tree_count() == 3

    def test_complete_graph_k4(self):
        """K_4 has 4^2 = 16 spanning trees (Cayley's formula)."""
        mg = _make_complete_graph(4)
        assert mg.spanning_tree_count() == 16

    def test_complete_graph_k5(self):
        """K_5 has 5^3 = 125 spanning trees."""
        mg = _make_complete_graph(5)
        assert mg.spanning_tree_count() == 125

    def test_path_graph(self):
        """Path graph has exactly 1 spanning tree (the path itself)."""
        mg = _make_path_graph(4)
        assert mg.spanning_tree_count() == 1

    def test_cycle_graph_c4(self):
        """C_4 has 4 spanning trees (remove any one edge)."""
        mg = _make_cycle_graph(4)
        assert mg.spanning_tree_count() == 4

    def test_cycle_graph_c5(self):
        """C_5 has 5 spanning trees."""
        mg = _make_cycle_graph(5)
        assert mg.spanning_tree_count() == 5

    def test_disconnected(self):
        """Disconnected graph has 0 spanning trees."""
        mg = MemoryGraph()
        a = mg.add(label="a"); b = mg.add(label="b")
        c = mg.add(label="c"); d = mg.add(label="d")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.spanning_tree_count() == 0

    def test_too_few_nodes(self):
        """< 2 nodes returns 0."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        assert mg.spanning_tree_count() == 0

    def test_star_graph(self):
        """Star K_{1,3} has 1 spanning tree."""
        mg = MemoryGraph()
        nodes = [mg.add(label=f"n{i}") for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[0].id, nodes[2].id, "r")
        mg.link(nodes[0].id, nodes[3].id, "r")
        assert mg.spanning_tree_count() == 1
