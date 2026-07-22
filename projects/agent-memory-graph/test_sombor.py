"""Tests for sombor_index() and reduced_sombor_index().

Cycle 276 — Sombor index family (Gutman 2021).

SO = Σ √(d_u² + d_v²)                    (Sombor index)
RS = Σ √((d_u-1)² + (d_v-1)²)            (Reduced Sombor)
"""

import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def build_complete(g, n):
    """Complete graph K_n."""
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes


def build_path(g, n):
    """Path graph P_n."""
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes


def build_cycle(g, n):
    """Cycle graph C_n."""
    nodes = build_path(g, n)
    g.link(nodes[-1].id, nodes[0].id, "r")
    return nodes


def build_star(g, k):
    """Star graph K_{1,k}."""
    center = g.add("c")
    leaves = [g.add(f"l{i}") for i in range(k)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "r")
    return center, leaves


# ─── Sombor index: edge cases ─────────────────────────────────────────────────

class TestSomborEdgeCases:
    def test_empty_graph(self, mg):
        assert mg.sombor_index() is None

    def test_single_node(self, mg):
        mg.add("a")
        assert mg.sombor_index() is None

    def test_two_nodes_no_edge(self, mg):
        mg.add("a")
        mg.add("b")
        assert mg.sombor_index() is None

    def test_non_mutating(self, mg):
        build_complete(mg, 4)
        before = mg.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        mg.sombor_index()
        after = mg.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        assert before == after


# ─── Sombor index: basic graphs ───────────────────────────────────────────────

class TestSomborBasic:
    def test_k2(self, mg):
        """K₂: SO = √(1+1) = √2."""
        build_complete(mg, 2)
        result = mg.sombor_index()
        assert result is not None
        assert math.isclose(result, math.sqrt(2), rel_tol=1e-9)

    def test_k3(self, mg):
        """K₃: SO = 3 · √(4+4) = 3 · 2√2 = 6√2."""
        build_complete(mg, 3)
        result = mg.sombor_index()
        expected = 6 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_k4(self, mg):
        """K₄: SO = 6 · √(9+9) = 6 · 3√2 = 18√2."""
        build_complete(mg, 4)
        result = mg.sombor_index()
        expected = 18 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_c4(self, mg):
        """C₄: SO = 4 · √(4+4) = 4 · 2√2 = 8√2."""
        build_cycle(mg, 4)
        result = mg.sombor_index()
        expected = 8 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_c5(self, mg):
        """C₅: SO = 5 · 2√2 = 10√2."""
        build_cycle(mg, 5)
        result = mg.sombor_index()
        expected = 10 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_p3(self, mg):
        """P₃: SO = 2·√(1+4) + √(4+4) = 2√5 + 2√2. Wait, P₃ has 2 edges only."""
        build_path(mg, 3)
        result = mg.sombor_index()
        # P₃: edges (1,2) and (2,3). Degrees: 1,2,1.
        # SO = √(1+4) + √(4+1) = 2√5
        expected = 2 * math.sqrt(5)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_p4(self, mg):
        """P₄: SO = 2·√(1+4) + √(4+4) = 2√5 + 2√2."""
        build_path(mg, 4)
        result = mg.sombor_index()
        expected = 2 * math.sqrt(5) + math.sqrt(8)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_star_k3(self, mg):
        """K_{1,3}: SO = 3·√(9+1) = 3√10."""
        build_star(mg, 3)
        result = mg.sombor_index()
        expected = 3 * math.sqrt(10)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_star_k4(self, mg):
        """K_{1,4}: SO = 4·√(16+1) = 4√17."""
        build_star(mg, 4)
        result = mg.sombor_index()
        expected = 4 * math.sqrt(17)
        assert math.isclose(result, expected, rel_tol=1e-9)


# ─── Sombor index: parametric verification ────────────────────────────────────

class TestSomborParametric:
    def test_kn_formula(self, mg):
        """K_n: SO = n(n-1)²√2 / 2 for n=2..7."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_complete(g, n)
            result = g.sombor_index()
            expected = n * (n - 1) ** 2 * math.sqrt(2) / 2
            assert math.isclose(result, expected, rel_tol=1e-9), f"K_{n}: {result} != {expected}"

    def test_cn_formula(self, mg):
        """C_n: SO = 2n√2 for n=3..8."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            result = g.sombor_index()
            expected = 2 * n * math.sqrt(2)
            assert math.isclose(result, expected, rel_tol=1e-9), f"C_{n}: {result} != {expected}"

    def test_pn_formula(self, mg):
        """P_n: SO = 2√5 + (n-3)·2√2 for n≥3."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_path(g, n)
            result = g.sombor_index()
            expected = 2 * math.sqrt(5) + (n - 3) * 2 * math.sqrt(2)
            assert math.isclose(result, expected, rel_tol=1e-9), f"P_{n}: {result} != {expected}"

    def test_star_formula(self, mg):
        """K_{1,k}: SO = k√(k²+1) for k=1..6."""
        for k in range(1, 7):
            g = MemoryGraph()
            build_star(g, k)
            result = g.sombor_index()
            expected = k * math.sqrt(k * k + 1)
            assert math.isclose(result, expected, rel_tol=1e-9), f"K_{{1,{k}}}: {result} != {expected}"


# ─── Sombor index: properties ─────────────────────────────────────────────────

class TestSomborProperties:
    def test_edge_addition_increases(self, mg):
        """Adding an edge should not decrease the Sombor index."""
        nodes = build_path(mg, 5)
        before = mg.sombor_index()
        # Add edge to make a cycle
        mg.link(nodes[0].id, nodes[-1].id, "r")
        after = mg.sombor_index()
        assert after > before

    def test_complete_ge_path(self, mg):
        """K_n should have higher SO than P_n for same n (more edges)."""
        n = 5
        g_k = MemoryGraph()
        build_complete(g_k, n)
        g_p = MemoryGraph()
        build_path(g_p, n)
        assert g_k.sombor_index() > g_p.sombor_index()

    def test_disconnected_components(self, mg):
        """SO should work with disconnected components (sums all edges)."""
        build_complete(mg, 3)  # K₃ component
        build_complete(mg, 3)  # Another K₃ component
        result = mg.sombor_index()
        expected = 2 * 6 * math.sqrt(2)  # Two K₃ copies
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_sombor_gt_sum_connectivity(self, mg):
        """SO >= sum_connectivity for any graph (each term >= 1/(d_u+d_v))."""
        build_complete(mg, 4)
        so = mg.sombor_index()
        sc = mg.sum_connectivity_index()
        assert so > sc

    def test_sombor_lt_zagreb_m2(self, mg):
        """SO <= M₂ for any graph: √(d_u²+d_v²) <= d_u·d_v when both >= 1."""
        build_complete(mg, 5)
        so = mg.sombor_index()
        zagreb = mg.zagreb_indices()
        assert so < zagreb["second"]


# ─── Reduced Sombor: edge cases ───────────────────────────────────────────────

class TestReducedSomborEdgeCases:
    def test_empty_graph(self, mg):
        assert mg.reduced_sombor_index() is None

    def test_single_node(self, mg):
        mg.add("a")
        assert mg.reduced_sombor_index() is None

    def test_two_nodes_no_edge(self, mg):
        mg.add("a")
        mg.add("b")
        assert mg.reduced_sombor_index() is None

    def test_non_mutating(self, mg):
        build_complete(mg, 4)
        before = mg.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        mg.reduced_sombor_index()
        after = mg.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        assert before == after


# ─── Reduced Sombor: basic graphs ─────────────────────────────────────────────

class TestReducedSomborBasic:
    def test_k2(self, mg):
        """K₂: RS = √(0+0) = 0."""
        build_complete(mg, 2)
        result = mg.reduced_sombor_index()
        assert result is not None
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_k3(self, mg):
        """K₃: RS = 3·√(1+1) = 3√2."""
        build_complete(mg, 3)
        result = mg.reduced_sombor_index()
        expected = 3 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_k4(self, mg):
        """K₄: RS = 6·√(4+4) = 6·2√2 = 12√2."""
        build_complete(mg, 4)
        result = mg.reduced_sombor_index()
        expected = 12 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_c4(self, mg):
        """C₄: RS = 4·√(1+1) = 4√2."""
        build_cycle(mg, 4)
        result = mg.reduced_sombor_index()
        expected = 4 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_p3(self, mg):
        """P₃: RS = 2·√(0+1) = 2."""
        build_path(mg, 3)
        result = mg.reduced_sombor_index()
        assert math.isclose(result, 2.0, rel_tol=1e-9)

    def test_p4(self, mg):
        """P₄: RS = 2·1 + √(1+1) = 2 + √2."""
        build_path(mg, 4)
        result = mg.reduced_sombor_index()
        expected = 2.0 + math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_star_k3(self, mg):
        """K_{1,3}: RS = 3·√(4+0) = 3·2 = 6."""
        build_star(mg, 3)
        result = mg.reduced_sombor_index()
        assert math.isclose(result, 6.0, rel_tol=1e-9)

    def test_star_k4(self, mg):
        """K_{1,4}: RS = 4·√(9+0) = 4·3 = 12."""
        build_star(mg, 4)
        result = mg.reduced_sombor_index()
        assert math.isclose(result, 12.0, rel_tol=1e-9)


# ─── Reduced Sombor: parametric verification ──────────────────────────────────

class TestReducedSomborParametric:
    def test_kn_formula(self, mg):
        """K_n: RS = n(n-1)(n-2)√2 / 2 for n=3..7."""
        for n in range(3, 8):
            g = MemoryGraph()
            build_complete(g, n)
            result = g.reduced_sombor_index()
            expected = n * (n - 1) * (n - 2) * math.sqrt(2) / 2
            assert math.isclose(result, expected, rel_tol=1e-9), f"K_{n}: {result} != {expected}"

    def test_cn_formula(self, mg):
        """C_n: RS = n√2 for n=3..8."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            result = g.reduced_sombor_index()
            expected = n * math.sqrt(2)
            assert math.isclose(result, expected, rel_tol=1e-9), f"C_{n}: {result} != {expected}"

    def test_pn_formula(self, mg):
        """P_n: RS = 2 + (n-3)√2 for n≥3."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_path(g, n)
            result = g.reduced_sombor_index()
            expected = 2.0 + (n - 3) * math.sqrt(2)
            assert math.isclose(result, expected, rel_tol=1e-9), f"P_{n}: {result} != {expected}"

    def test_star_formula(self, mg):
        """K_{1,k}: RS = k(k-1) for k=2..6."""
        for k in range(2, 7):
            g = MemoryGraph()
            build_star(g, k)
            result = g.reduced_sombor_index()
            expected = float(k * (k - 1))
            assert math.isclose(result, expected, rel_tol=1e-9), f"K_{{1,{k}}}: {result} != {expected}"


# ─── Reduced Sombor: properties ───────────────────────────────────────────────

class TestReducedSomborProperties:
    def test_rs_le_sombor(self, mg):
        """RS <= SO always (subtracting 1 reduces or keeps each term)."""
        for builder, args in [(build_complete, 5), (build_path, 6), (build_cycle, 5), (build_star, 4)]:
            g = MemoryGraph()
            builder(g, args) if builder != build_star else build_star(g, args)
            rs = g.reduced_sombor_index()
            so = g.sombor_index()
            assert rs <= so, f"RS {rs} > SO {so} for {builder.__name__}"

    def test_edge_addition_increases(self, mg):
        nodes = build_path(mg, 5)
        before = mg.reduced_sombor_index()
        mg.link(nodes[0].id, nodes[-1].id, "r")
        after = mg.reduced_sombor_index()
        assert after > before

    def test_k2_zero(self, mg):
        """RS(K₂) = 0 — the unique property that distinguishes it from SO."""
        build_complete(mg, 2)
        assert mg.reduced_sombor_index() == 0.0

    def test_disconnected_components(self, mg):
        build_complete(mg, 3)
        build_complete(mg, 3)
        result = mg.reduced_sombor_index()
        expected = 2 * 3 * math.sqrt(2)
        assert math.isclose(result, expected, rel_tol=1e-9)
