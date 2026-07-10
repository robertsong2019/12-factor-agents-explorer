"""Tests for spectral gap and graph energy."""

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


class TestSpectralGap:
    """Spectral gap tests."""

    def test_complete_graph_k3(self):
        """K_3: eigenvalues of adjacency = {2, -1, -1}. Gap = 2-(-1) = 3."""
        mg = _make_complete_graph(3)
        gap = mg.spectral_gap()
        assert abs(gap - 3.0) < 0.05, f"K_3 gap should be ~3.0, got {gap}"

    def test_complete_graph_k4(self):
        """K_4: eigenvalues = {3, -1, -1, -1}. Gap = 3-(-1) = 4."""
        mg = _make_complete_graph(4)
        gap = mg.spectral_gap()
        assert abs(gap - 4.0) < 0.05, f"K_4 gap should be ~4.0, got {gap}"

    def test_path_graph_p3(self):
        """P_3: eigenvalues = {sqrt(2), 0, -sqrt(2)}. Gap = sqrt(2)-0 ≈ 1.414."""
        mg = _make_path_graph(3)
        gap = mg.spectral_gap()
        expected = math.sqrt(2)
        assert abs(gap - expected) < 0.05, f"P_3 gap should be ~{expected}, got {gap}"

    def test_cycle_graph_c4(self):
        """C_4: eigenvalues = {2, 0, 0, -2}. Gap = 2-0 = 2."""
        mg = _make_cycle_graph(4)
        gap = mg.spectral_gap()
        assert abs(gap - 2.0) < 0.05, f"C_4 gap should be ~2.0, got {gap}"

    def test_too_few_nodes(self):
        """< 2 nodes returns 0."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        assert mg.spectral_gap() == 0.0

    def test_positive_for_connected(self):
        """Spectral gap should be positive for connected graphs."""
        mg = _make_complete_graph(5)
        assert mg.spectral_gap() > 0

    def test_complete_gt_path(self):
        """Complete graph has larger spectral gap than path graph."""
        mg_complete = _make_complete_graph(5)
        mg_path = _make_path_graph(5)
        assert mg_complete.spectral_gap() > mg_path.spectral_gap()


class TestGraphEnergy:
    """Graph energy tests."""

    def test_complete_graph_k3(self):
        """K_3: |2| + |-1| + |-1| = 4."""
        mg = _make_complete_graph(3)
        energy = mg.graph_energy()
        assert abs(energy - 4.0) < 0.05, f"K_3 energy should be ~4.0, got {energy}"

    def test_complete_graph_k4(self):
        """K_4: |3| + |-1|*3 = 6."""
        mg = _make_complete_graph(4)
        energy = mg.graph_energy()
        assert abs(energy - 6.0) < 0.05, f"K_4 energy should be ~6.0, got {energy}"

    def test_path_graph_p3(self):
        """P_3: |sqrt(2)| + |0| + |-sqrt(2)| = 2*sqrt(2) ≈ 2.828."""
        mg = _make_path_graph(3)
        energy = mg.graph_energy()
        expected = 2 * math.sqrt(2)
        assert abs(energy - expected) < 0.05, f"P_3 energy should be ~{expected}, got {energy}"

    def test_cycle_graph_c4(self):
        """C_4: |2| + |0| + |0| + |-2| = 4."""
        mg = _make_cycle_graph(4)
        energy = mg.graph_energy()
        assert abs(energy - 4.0) < 0.05, f"C_4 energy should be ~4.0, got {energy}"

    def test_empty_graph(self):
        """Empty graph has 0 energy."""
        mg = MemoryGraph()
        assert mg.graph_energy() == 0.0

    def test_single_node(self):
        """Single node has 0 energy (eigenvalue = 0)."""
        mg = MemoryGraph()
        mg.add(label="a", kind="t")
        assert mg.graph_energy() == 0.0

    def test_two_nodes_one_edge(self):
        """Two nodes with 1 edge: eigenvalues = {1, -1}. Energy = 2."""
        mg = MemoryGraph()
        a = mg.add(label="a"); b = mg.add(label="b")
        mg.link(a.id, b.id, "r")
        energy = mg.graph_energy()
        assert abs(energy - 2.0) < 0.05

    def test_positive_for_connected(self):
        """Energy should be positive for any graph with edges."""
        mg = _make_path_graph(5)
        assert mg.graph_energy() > 0

    def test_complete_gt_path(self):
        """Complete graph has higher energy than path graph (same n)."""
        mg_complete = _make_complete_graph(5)
        mg_path = _make_path_graph(5)
        assert mg_complete.graph_energy() > mg_path.graph_energy()

    def test_lower_bound(self):
        """Energy >= 2*sqrt(m) for m edges. K_4 has m=6, so E >= 2*sqrt(6) ≈ 4.899."""
        mg = _make_complete_graph(4)  # 6 edges
        energy = mg.graph_energy()
        lower = 2 * math.sqrt(6)
        assert energy >= lower - 0.1
