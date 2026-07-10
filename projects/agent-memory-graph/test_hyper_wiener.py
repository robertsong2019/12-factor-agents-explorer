"""Tests for hyper-Wiener index and Balaban J index."""

import pytest
import math
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


class TestHyperWienerIndex:
    """Hyper-Wiener index tests."""

    def test_path_graph_p3(self):
        """P_3: pairs (0,1): d=1, (1,2): d=1, (0,2): d=2.
        WW = 1/2 * [(1²+1) + (1²+1) + (2²+2)] = 1/2 * [2+2+6] = 5."""
        mg = _make_path_graph(3)
        result = mg.hyper_wiener_index()
        assert result == 5, f"P_3 WW should be 5, got {result}"

    def test_path_graph_p4(self):
        """P_4: pairs (0,1):1, (1,2):1, (2,3):1, (0,2):2, (1,3):2, (0,3):3.
        WW = 1/2 * [(1+1)*3 + (4+2)*2 + (9+3)] = 1/2 * [6+12+12] = 15."""
        mg = _make_path_graph(4)
        result = mg.hyper_wiener_index()
        assert result == 15, f"P_4 WW should be 15, got {result}"

    def test_complete_graph_k3(self):
        """K_3: all pairs d=1. 3 pairs.
        WW = 1/2 * 3 * (1+1) = 3."""
        mg = _make_complete_graph(3)
        result = mg.hyper_wiener_index()
        assert result == 3, f"K_3 WW should be 3, got {result}"

    def test_complete_graph_k4(self):
        """K_4: all pairs d=1. 6 pairs.
        WW = 1/2 * 6 * 2 = 6."""
        mg = _make_complete_graph(4)
        result = mg.hyper_wiener_index()
        assert result == 6, f"K_4 WW should be 6, got {result}"

    def test_cycle_graph_c4(self):
        """C_4: 4 adjacent pairs d=1, 2 opposite pairs d=2.
        WW = 1/2 * [4*(1+1) + 2*(4+2)] = 1/2 * [8+12] = 10."""
        mg = _make_cycle_graph(4)
        result = mg.hyper_wiener_index()
        assert result == 10, f"C_4 WW should be 10, got {result}"

    def test_too_few_nodes(self):
        """< 2 nodes returns None."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        assert mg.hyper_wiener_index() is None

    def test_positive_for_connected(self):
        """Hyper-Wiener should be positive for connected graphs."""
        mg = _make_path_graph(5)
        assert mg.hyper_wiener_index() > 0

    def test_complete_lt_path(self):
        """Complete graph has smaller WW than path (more compact)."""
        mg_complete = _make_complete_graph(5)
        mg_path = _make_path_graph(5)
        assert mg_complete.hyper_wiener_index() < mg_path.hyper_wiener_index()


class TestBalabanIndex:
    """Balaban J index tests."""

    def test_complete_graph_k3(self):
        """K_3: m=3, n=3, cycle_rank=3-3+2=2.
        Each node has transmission=2 (d=1 to both others).
        Each edge: 1/sqrt(2*2) = 1/2.  3 edges → 3/2.
        J = (3/2) * (3/2) = 9/4 = 2.25."""
        mg = _make_complete_graph(3)
        result = mg.balaban_index()
        assert result is not None
        assert abs(result - 2.25) < 0.01, f"K_3 J should be ~2.25, got {result}"

    def test_path_graph_p4(self):
        """P_4: m=3, n=4, cycle_rank=3-4+2=1.
        J = (3/1) * sum_edges(1/sqrt(d_u*d_v))."""
        mg = _make_path_graph(4)
        result = mg.balaban_index()
        assert result is not None
        assert result > 0

    def test_cycle_graph_c4(self):
        """C_4: m=4, n=4, cycle_rank=4-4+2=2."""
        mg = _make_cycle_graph(4)
        result = mg.balaban_index()
        assert result is not None
        assert result > 0

    def test_too_few_nodes(self):
        """< 2 nodes returns None."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        assert mg.balaban_index() is None

    def test_no_edges(self):
        """Graph with no edges returns 0."""
        mg = MemoryGraph()
        mg.add(label="a"); mg.add(label="b")
        result = mg.balaban_index()
        assert result == 0.0

    def test_positive_for_connected(self):
        """Balaban J should be positive for connected graphs with cycles."""
        mg = _make_cycle_graph(5)
        assert mg.balaban_index() > 0
