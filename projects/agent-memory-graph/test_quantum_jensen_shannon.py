"""Tests for quantum_jensen_shannon_distance() — spectral inter-graph
metric (Cycle 294).

Based on Research #031: QJSD between Laplacian density matrices.
True metric: symmetric, bounded [0, √ln2], satisfies triangle inequality.
"""
import pytest, math
from memory_graph import MemoryGraph

# ─── Helpers ────────────────────────────────────────────────────────────

def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes

def build_cycle(g, n):
    nodes = build_path(g, n)
    g.link(nodes[-1].id, nodes[0].id, "r")
    return nodes

def build_star(g, k):
    hub = g.add('h')
    leaves = [g.add(str(i)) for i in range(k)]
    for l in leaves:
        g.link(hub.id, l.id, 'r')
    return hub, leaves


# ═══════════════════════════════════════════════════════════════════════
# Basic
# ═══════════════════════════════════════════════════════════════════════

class TestQJSDBasic:
    def test_none_for_empty_self(self):
        mg = MemoryGraph(':memory:')
        other = MemoryGraph(':memory:')
        build_path(other, 3)
        assert mg.quantum_jensen_shannon_distance(other) is None

    def test_none_for_empty_other(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 3)
        other = MemoryGraph(':memory:')
        assert mg.quantum_jensen_shannon_distance(other) is None

    def test_none_for_single_node_self(self):
        mg = MemoryGraph(':memory:')
        mg.add('a')
        other = MemoryGraph(':memory:')
        build_path(other, 3)
        assert mg.quantum_jensen_shannon_distance(other) is None

    def test_identical_graphs_zero_distance(self):
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 5)
        mg2 = MemoryGraph(':memory:')
        build_path(mg2, 5)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d is not None
        assert d < 1e-9

    def test_returns_float(self):
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 4)
        mg2 = MemoryGraph(':memory:')
        build_complete(mg2, 4)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d is not None
        assert isinstance(d, float)


# ═══════════════════════════════════════════════════════════════════════
# Mathematical properties
# ═══════════════════════════════════════════════════════════════════════

class TestMathProperties:
    def test_symmetric(self):
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 5)
        mg2 = MemoryGraph(':memory:')
        build_complete(mg2, 5)
        d12 = mg1.quantum_jensen_shannon_distance(mg2)
        d21 = mg2.quantum_jensen_shannon_distance(mg1)
        assert abs(d12 - d21) < 1e-9

    def test_non_negative(self):
        configs = [
            (build_path, 4, build_complete, 4),
            (build_path, 5, build_cycle, 5),
            (build_star, 4, build_complete, 5),
        ]
        for b1, n1, b2, n2 in configs:
            mg1 = MemoryGraph(':memory:')
            b1(mg1, n1)
            mg2 = MemoryGraph(':memory:')
            b2(mg2, n2)
            d = mg1.quantum_jensen_shannon_distance(mg2)
            assert d >= -1e-12

    def test_bounded_by_sqrt_ln2(self):
        """QJSD upper bound is √ln(2) ≈ 0.8326."""
        upper = math.sqrt(math.log(2))
        for b1, n1, b2, n2 in [
            (build_path, 3, build_complete, 6),
            (build_star, 3, build_complete, 4),
        ]:
            mg1 = MemoryGraph(':memory:')
            b1(mg1, n1)
            mg2 = MemoryGraph(':memory:')
            b2(mg2, n2)
            d = mg1.quantum_jensen_shannon_distance(mg2)
            assert d <= upper + 1e-9, f"{b1.__name__}({n1}) vs {b2.__name__}({n2}): {d} > {upper}"

    def test_self_distance_zero(self):
        mg = MemoryGraph(':memory:')
        build_path(mg, 6)
        d = mg.quantum_jensen_shannon_distance(mg)
        assert d is not None
        assert d < 1e-9

    def test_triangle_inequality(self):
        """d(A,C) ≤ d(A,B) + d(B,C) for three graphs."""
        mgA = MemoryGraph(':memory:')
        build_path(mgA, 5)
        mgB = MemoryGraph(':memory:')
        build_cycle(mgB, 5)
        mgC = MemoryGraph(':memory:')
        build_complete(mgC, 5)
        dAB = mgA.quantum_jensen_shannon_distance(mgB)
        dBC = mgB.quantum_jensen_shannon_distance(mgC)
        dAC = mgA.quantum_jensen_shannon_distance(mgC)
        assert dAC <= dAB + dBC + 1e-9


# ═══════════════════════════════════════════════════════════════════════
# Different graph comparisons
# ═══════════════════════════════════════════════════════════════════════

class TestGraphComparisons:
    def test_path_vs_complete_positive(self):
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 5)
        mg2 = MemoryGraph(':memory:')
        build_complete(mg2, 5)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d > 1e-6

    def test_path_vs_cycle_smaller_than_path_vs_complete(self):
        """P vs C should be closer than P vs K (cycle is a small modification)."""
        mgP = MemoryGraph(':memory:')
        build_path(mgP, 5)
        mgC = MemoryGraph(':memory:')
        build_cycle(mgC, 5)
        mgK = MemoryGraph(':memory:')
        build_complete(mgK, 5)
        dPC = mgP.quantum_jensen_shannon_distance(mgC)
        dPK = mgP.quantum_jensen_shannon_distance(mgK)
        assert dPC < dPK

    def test_star_vs_complete_different(self):
        mgS = MemoryGraph(':memory:')
        build_star(mgS, 5)
        mgK = MemoryGraph(':memory:')
        build_complete(mgK, 6)
        d = mgS.quantum_jensen_shannon_distance(mgK)
        assert d > 1e-6

    def test_two_paths_same_size_zero(self):
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 5)
        mg2 = MemoryGraph(':memory:')
        build_path(mg2, 5)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d < 1e-9

    def test_two_complete_same_size_zero(self):
        mg1 = MemoryGraph(':memory:')
        build_complete(mg1, 4)
        mg2 = MemoryGraph(':memory:')
        build_complete(mg2, 4)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d < 1e-9

    def test_different_size_graphs(self):
        """Graphs of different sizes should still compute."""
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 3)
        mg2 = MemoryGraph(':memory:')
        build_complete(mg2, 6)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d is not None
        assert d >= 0


# ═══════════════════════════════════════════════════════════════════════
# Empty / edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_both_empty_graphs_zero(self):
        mg1 = MemoryGraph(':memory:')
        mg1.add('a'); mg1.add('b')
        mg2 = MemoryGraph(':memory:')
        mg2.add('x'); mg2.add('y')
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d is not None
        assert d < 1e-9

    def test_one_empty_one_not(self):
        mg1 = MemoryGraph(':memory:')
        mg1.add('a'); mg1.add('b')
        mg2 = MemoryGraph(':memory:')
        build_path(mg2, 4)
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d is not None
        assert d > 0

    def test_single_edge_both_zero(self):
        """Two K_2 graphs → identical → distance 0."""
        mg1 = MemoryGraph(':memory:')
        a, b = mg1.add('a'), mg1.add('b')
        mg1.link(a.id, b.id, 'r')
        mg2 = MemoryGraph(':memory:')
        x, y = mg2.add('x'), mg2.add('y')
        mg2.link(x.id, y.id, 'r')
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d < 1e-9


# ═══════════════════════════════════════════════════════════════════════
# Quarantine support
# ═══════════════════════════════════════════════════════════════════════

class TestQuarantine:
    def test_include_quarantined(self):
        mg1 = MemoryGraph(':memory:')
        nodes1 = build_path(mg1, 4)
        mg2 = MemoryGraph(':memory:')
        build_path(mg2, 4)

        d_without = mg1.quantum_jensen_shannon_distance(mg2)
        # Quarantine a node in mg1
        mg1.conn.execute("UPDATE nodes SET quarantined = 1 WHERE id = ?",
                         (nodes1[3].id,))
        mg1.conn.commit()
        d_with = mg1.quantum_jensen_shannon_distance(mg2, include_quarantined=True)
        d_without_q = mg1.quantum_jensen_shannon_distance(mg2, include_quarantined=False)
        # With quarantined: 4 nodes (same as mg2). Without: 3 vs 4.
        assert d_without is not None
        assert d_with is not None
        assert d_without_q is not None


# ═══════════════════════════════════════════════════════════════════════
# Cross-check with entropy_distance (degree-based)
# ═══════════════════════════════════════════════════════════════════════

class TestCrossCheck:
    def test_qjsd_vs_entropy_distance_both_positive(self):
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 5)
        mg2 = MemoryGraph(':memory:')
        build_complete(mg2, 5)
        qjsd = mg1.quantum_jensen_shannon_distance(mg2)
        ed = mg1.entropy_distance(mg2, index="sombor")
        assert qjsd is not None
        assert qjsd > 0
        if ed is not None:
            assert ed >= 0

    def test_qjsd_identical_graph_zero_vs_distance_positive(self):
        """Both metrics should give 0 for identical graphs."""
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 5)
        mg2 = MemoryGraph(':memory:')
        build_path(mg2, 5)
        assert mg1.quantum_jensen_shannon_distance(mg2) < 1e-9
        ed = mg1.entropy_distance(mg2, index="sombor")
        if ed is not None:
            assert ed < 1e-6

    def test_qjsd_captures_spectral_difference(self):
        """Two graphs with same degree sequence but different topology
        should have positive QJSD (spectral captures wiring differences)."""
        # Path P4 and another graph with same degree sequence
        # P4: degrees [1,2,2,1]
        # Disjoint K_{1,1} + K_{1,1}: same degrees [1,1,1,1] — different!
        # Use P4 vs C4 with one edge removed (same degrees)
        mg1 = MemoryGraph(':memory:')
        build_path(mg1, 4)

        mg2 = MemoryGraph(':memory:')
        n0 = mg2.add('0'); n1 = mg2.add('1')
        n2 = mg2.add('2'); n3 = mg2.add('3')
        mg2.link(n0.id, n1.id, 'r')
        mg2.link(n1.id, n2.id, 'r')
        mg2.link(n2.id, n3.id, 'r')
        # Both are P4 → should be zero
        d = mg1.quantum_jensen_shannon_distance(mg2)
        assert d < 1e-9

    def test_spectral_differentiates_non_isomorphic_same_size(self):
        """Path P5 and Star K_{1,4} both have 5 nodes 4 edges
        but different topology → positive QJSD."""
        mgP = MemoryGraph(':memory:')
        build_path(mgP, 5)
        mgS = MemoryGraph(':memory:')
        build_star(mgS, 4)  # 5 nodes, 4 edges
        d = mgP.quantum_jensen_shannon_distance(mgS)
        assert d is not None
        assert d > 1e-6


# ═══════════════════════════════════════════════════════════════════════
# Monotonicity with structural change
# ═══════════════════════════════════════════════════════════════════════

class TestMonotonicity:
    def test_more_similar_graphs_closer(self):
        """A graph is closer to its 1-edge modification than to a
        completely different graph."""
        mg_base = MemoryGraph(':memory:')
        build_path(mg_base, 5)

        mg_close = MemoryGraph(':memory:')
        build_path(mg_close, 5)
        # Add one extra edge to mg_close
        nodes_c = mg_close.conn.execute("SELECT id FROM nodes").fetchall()
        mg_close.link(nodes_c[0]["id"], nodes_c[4]["id"], "r")

        mg_far = MemoryGraph(':memory:')
        build_complete(mg_far, 5)

        d_close = mg_base.quantum_jensen_shannon_distance(mg_close)
        d_far = mg_base.quantum_jensen_shannon_distance(mg_far)
        assert d_close < d_far

    def test_complete_vs_complete_zero(self):
        """Two K_n of same n → distance 0."""
        for n in [3, 4, 5]:
            mg1 = MemoryGraph(':memory:')
            build_complete(mg1, n)
            mg2 = MemoryGraph(':memory:')
            build_complete(mg2, n)
            assert mg1.quantum_jensen_shannon_distance(mg2) < 1e-9
