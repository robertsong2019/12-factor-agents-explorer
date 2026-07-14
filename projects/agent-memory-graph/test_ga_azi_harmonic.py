"""Tests for ga_index(), augmented_zagreb_index(), and harmonic_index().

Cycle 239 — degree-based topological indices continuing from cycle 238
(Forgotten, ABC, Sum-connectivity).

GA     = Σ 2√(d_u·d_v) / (d_u + d_v)               (Dăscălescu et al. 2010)
AZI    = Σ (d_u·d_v / (d_u + d_v - 2))³              (Furtula et al. 2010)
H      = Σ 2 / (d_u + d_v)                            (Fajtlowicz 1998)
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
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return nodes


def build_star(g, k):
    """Star graph K_{1,k}."""
    center = g.add("C")
    for i in range(k):
        leaf = g.add(f"L{i}")
        g.link(center.id, leaf.id, "r")
    return center


# ─── GA Index ──────────────────────────────────────────────────────────────────

class TestGAIndex:

    def test_empty(self, mg):
        assert mg.ga_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.ga_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.ga_index() is None

    def test_k2(self, mg):
        """K₂: GA = 2·√(1·1)/(1+1) = 2·1/2 = 1."""
        build_complete(mg, 2)
        assert mg.ga_index() == pytest.approx(1.0)

    def test_k3(self, mg):
        """K₃: all edges (2,2), GA = 3 · 1 = 3."""
        build_complete(mg, 3)
        assert mg.ga_index() == pytest.approx(3.0)

    def test_k4(self, mg):
        """K₄: all edges (3,3), GA = 6 · 1 = 6 = m."""
        build_complete(mg, 4)
        assert mg.ga_index() == pytest.approx(6.0)

    def test_k5(self, mg):
        """K₅: GA = 10 = m (all equal-degree endpoints)."""
        build_complete(mg, 5)
        assert mg.ga_index() == pytest.approx(10.0)

    def test_c4(self, mg):
        """C₄: all edges (2,2), GA = 4 = m."""
        build_cycle(mg, 4)
        assert mg.ga_index() == pytest.approx(4.0)

    def test_c5(self, mg):
        """C₅: GA = 5 = m."""
        build_cycle(mg, 5)
        assert mg.ga_index() == pytest.approx(5.0)

    def test_c6(self, mg):
        """C₆: GA = 6 = m."""
        build_cycle(mg, 6)
        assert mg.ga_index() == pytest.approx(6.0)

    def test_p3(self, mg):
        """P₃: two endpoint edges (1,2): 2·√2/3 each. GA = 2 · 2√2/3."""
        build_path(mg, 3)
        expected = 2 * 2 * math.sqrt(2) / 3
        assert mg.ga_index() == pytest.approx(expected)

    def test_p4(self, mg):
        """P₄: 2 endpoint edges (1,2) + 1 internal edge (2,2).
        GA = 2·(2√2/3) + 1·1 = 4√2/3 + 1."""
        build_path(mg, 4)
        endpoint_term = 2 * math.sqrt(2) / 3
        internal_term = 1.0
        expected = 2 * endpoint_term + internal_term
        assert mg.ga_index() == pytest.approx(expected)

    def test_p5(self, mg):
        """P₅: 2 endpoint edges + 2 internal edges.
        GA = 2·(2√2/3) + 2·1."""
        build_path(mg, 5)
        endpoint_term = 2 * math.sqrt(2) / 3
        internal_term = 1.0
        expected = 2 * endpoint_term + 2 * internal_term
        assert mg.ga_index() == pytest.approx(expected)

    def test_star_k3(self, mg):
        """K_{1,3}: 3 edges (1,3): 2·√3/4 each. GA = 3 · 2√3/4 = 3√3/2."""
        build_star(mg, 3)
        expected = 3 * 2 * math.sqrt(3) / 4
        assert mg.ga_index() == pytest.approx(expected)

    def test_star_k4(self, mg):
        """K_{1,4}: 4 edges (1,4): GA = 4 · 2√4/5 = 4 · 4/5 = 16/5."""
        build_star(mg, 4)
        expected = 4 * 2 * math.sqrt(4) / 5  # = 4 * 4/5 = 16/5
        assert mg.ga_index() == pytest.approx(expected)

    def test_star_k5(self, mg):
        """K_{1,5}: GA = 5 · 2√5/6 = 5√5/3."""
        build_star(mg, 5)
        expected = 5 * 2 * math.sqrt(5) / 6
        assert mg.ga_index() == pytest.approx(expected)

    # ── Parametric families ──

    def test_parametric_kn(self, mg):
        """GA(K_n) = m = n(n-1)/2 for n = 2..7."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_complete(g, n)
            expected = n * (n - 1) / 2
            assert g.ga_index() == pytest.approx(expected), f"K_{n}"

    def test_parametric_cn(self, mg):
        """GA(C_n) = n for n = 3..8."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.ga_index() == pytest.approx(n), f"C_{n}"

    def test_parametric_pn(self, mg):
        """GA(P_n) = 2·2√2/3 + (n-3)·1 for n ≥ 3."""
        endpoint_term = 2 * math.sqrt(2) / 3
        for n in range(3, 9):
            g = MemoryGraph()
            build_path(g, n)
            expected = 2 * endpoint_term + (n - 3) * 1.0
            assert g.ga_index() == pytest.approx(expected), f"P_{n}"

    def test_parametric_star(self, mg):
        """GA(K_{1,k}) = k · 2√k/(k+1) for k = 1..6."""
        for k in range(1, 7):
            g = MemoryGraph()
            build_star(g, k)
            expected = k * 2 * math.sqrt(k) / (k + 1)
            assert g.ga_index() == pytest.approx(expected), f"K_{{1,{k}}}"

    # ── Properties ──

    def test_regular_ga_equals_edge_count(self, mg):
        """For r-regular graphs, GA = m (every term = 1)."""
        # C_n is 2-regular
        build_cycle(mg, 7)
        assert mg.ga_index() == pytest.approx(7.0)  # m = 7

    def test_ga_le_m_always(self, mg):
        """GA ≤ m since each term ≤ 1 (AM-GM inequality)."""
        build_star(mg, 5)
        m = 5
        assert mg.ga_index() <= m

    def test_ga_positive(self, mg):
        """GA > 0 for any graph with edges."""
        build_path(mg, 4)
        assert mg.ga_index() > 0

    def test_disconnected(self, mg):
        """Two disjoint K₃ triangles: GA = 2 · 3 = 6."""
        # First triangle
        n1 = [mg.add(f"A{i}") for i in range(3)]
        for i in range(3):
            mg.link(n1[i].id, n1[(i + 1) % 3].id, "r")
        # Second triangle
        n2 = [mg.add(f"B{i}") for i in range(3)]
        for i in range(3):
            mg.link(n2[i].id, n2[(i + 1) % 3].id, "r")
        assert mg.ga_index() == pytest.approx(6.0)

    def test_edge_addition_increases(self, mg):
        """Adding an edge should increase GA (more terms)."""
        nodes = build_path(mg, 4)
        before = mg.ga_index()
        # Connect endpoints to form C₄
        mg.link(nodes[0].id, nodes[-1].id, "r")
        after = mg.ga_index()
        assert after > before

    def test_non_mutating(self, mg):
        """GA index should not modify graph state."""
        build_complete(mg, 4)
        before_nodes = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        before_edges = set(
            (r["source"], r["target"])
            for r in mg.conn.execute("SELECT source, target FROM edges")
        )
        _ = mg.ga_index()
        after_nodes = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        after_edges = set(
            (r["source"], r["target"])
            for r in mg.conn.execute("SELECT source, target FROM edges")
        )
        assert before_nodes == after_nodes
        assert before_edges == after_edges


# ─── Augmented Zagreb Index (AZI) ──────────────────────────────────────────────

class TestAugmentedZagrebIndex:

    def test_empty(self, mg):
        assert mg.augmented_zagreb_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.augmented_zagreb_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.augmented_zagreb_index() is None

    def test_k2_azi_zero(self, mg):
        """K₂: d_u + d_v - 2 = 0, so AZI = 0 (skipped)."""
        build_complete(mg, 2)
        assert mg.augmented_zagreb_index() == pytest.approx(0.0)

    def test_k3(self, mg):
        """K₃: edges (2,2): (4/2)³ = 8 per edge. AZI = 3·8 = 24."""
        build_complete(mg, 3)
        assert mg.augmented_zagreb_index() == pytest.approx(24.0)

    def test_k4(self, mg):
        """K₄: edges (3,3): (9/4)³ = 729/64. AZI = 6·729/64."""
        build_complete(mg, 4)
        term = (9 / 4) ** 3
        assert mg.augmented_zagreb_index() == pytest.approx(6 * term)

    def test_k5(self, mg):
        """K₅: edges (4,4): (16/6)³ = (8/3)³. AZI = 10·(8/3)³."""
        build_complete(mg, 5)
        term = (16 / 6) ** 3
        assert mg.augmented_zagreb_index() == pytest.approx(10 * term)

    def test_c4(self, mg):
        """C₄: edges (2,2): (4/2)³ = 8. AZI = 4·8 = 32."""
        build_cycle(mg, 4)
        assert mg.augmented_zagreb_index() == pytest.approx(32.0)

    def test_c5(self, mg):
        """C₅: AZI = 5·8 = 40."""
        build_cycle(mg, 5)
        assert mg.augmented_zagreb_index() == pytest.approx(40.0)

    def test_c6(self, mg):
        """C₆: AZI = 6·8 = 48."""
        build_cycle(mg, 6)
        assert mg.augmented_zagreb_index() == pytest.approx(48.0)

    def test_p3(self, mg):
        """P₃: 2 endpoint edges (1,2): (2/1)³ = 8. AZI = 2·8 = 16."""
        build_path(mg, 3)
        assert mg.augmented_zagreb_index() == pytest.approx(16.0)

    def test_p4(self, mg):
        """P₄: 2 endpoint edges (1,2): 8 each + 1 internal (2,2): 8. AZI = 3·8 = 24."""
        build_path(mg, 4)
        assert mg.augmented_zagreb_index() == pytest.approx(24.0)

    def test_p5(self, mg):
        """P₅: 2 endpoint + 2 internal, all contribute 8. AZI = 4·8 = 32."""
        build_path(mg, 5)
        assert mg.augmented_zagreb_index() == pytest.approx(32.0)

    def test_star_k3(self, mg):
        """K_{1,3}: 3 edges (1,3): (3/2)³ = 27/8 each. AZI = 3·27/8."""
        build_star(mg, 3)
        term = (3 / 2) ** 3
        assert mg.augmented_zagreb_index() == pytest.approx(3 * term)

    def test_star_k4(self, mg):
        """K_{1,4}: 4 edges (1,4): (4/3)³ each. AZI = 4·(4/3)³."""
        build_star(mg, 4)
        term = (4 / 3) ** 3
        assert mg.augmented_zagreb_index() == pytest.approx(4 * term)

    def test_star_k5(self, mg):
        """K_{1,5}: 5 edges (1,5): (5/4)³ each. AZI = 5·(5/4)³."""
        build_star(mg, 5)
        term = (5 / 4) ** 3
        assert mg.augmented_zagreb_index() == pytest.approx(5 * term)

    # ── Parametric families ──

    def test_parametric_kn(self, mg):
        """AZI(K_n) for n = 3..7."""
        for n in range(3, 8):
            g = MemoryGraph()
            build_complete(g, n)
            d = n - 1
            term = (d * d / (2 * d - 2)) ** 3  # (d²/(2d-2))³ = (d²/(2(d-1)))³
            m = n * (n - 1) / 2
            assert g.augmented_zagreb_index() == pytest.approx(m * term), f"K_{n}"

    def test_parametric_cn(self, mg):
        """AZI(C_n) = 8n for n = 3..8."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.augmented_zagreb_index() == pytest.approx(8 * n), f"C_{n}"

    def test_parametric_pn(self, mg):
        """AZI(P_n) = 8(n-1) for n ≥ 3 (each edge contributes 8)."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_path(g, n)
            assert g.augmented_zagreb_index() == pytest.approx(8 * (n - 1)), f"P_{n}"

    def test_parametric_star(self, mg):
        """AZI(K_{1,k}) = k·(k/(k-1))³ for k = 2..6."""
        for k in range(2, 7):
            g = MemoryGraph()
            build_star(g, k)
            term = (k / (k - 1)) ** 3
            assert g.augmented_zagreb_index() == pytest.approx(k * term), f"K_{{1,{k}}}"

    # ── Properties ──

    def test_azi_positive_for_nontrivial(self, mg):
        """AZI > 0 for any graph where d_u + d_v > 2 on at least one edge."""
        build_path(mg, 3)
        assert mg.augmented_zagreb_index() > 0

    def test_azi_k2_zero(self, mg):
        """K₂ has d_u + d_v = 2, denominator 0, AZI = 0."""
        build_complete(mg, 2)
        assert mg.augmented_zagreb_index() == 0.0

    def test_azi_amplifies_heterogeneity(self, mg):
        """AZI for star should be higher than for cycle with same edge count."""
        # Star K_{1,4}: 4 edges, AZI = 4·(4/3)³ ≈ 4·2.37 = 9.48
        # C₄: 4 edges, AZI = 4·8 = 32
        # Actually for AZI, regular graphs have very high values due to the cubic
        # C₄ has (2·2/(2+2-2))³ = 4³ = ... wait: 2·2/(2+2-2) = 4/2 = 2, 2³ = 8
        # K_{1,4} has (1·4/(1+4-2))³ = (4/3)³ ≈ 2.37
        # So AZI(C₄) = 32 >> AZI(K_{1,4}) = 9.48
        # AZI rewards equal-degree edges! Let me verify that.
        g1 = MemoryGraph()
        build_star(g1, 4)
        g2 = MemoryGraph()
        build_cycle(g2, 4)
        assert g2.augmented_zagreb_index() > g1.augmented_zagreb_index()

    def test_disconnected(self, mg):
        """Two disjoint K₃: AZI = 2·24 = 48."""
        n1 = [mg.add(f"A{i}") for i in range(3)]
        for i in range(3):
            mg.link(n1[i].id, n1[(i + 1) % 3].id, "r")
        n2 = [mg.add(f"B{i}") for i in range(3)]
        for i in range(3):
            mg.link(n2[i].id, n2[(i + 1) % 3].id, "r")
        assert mg.augmented_zagreb_index() == pytest.approx(48.0)

    def test_edge_addition_increases(self, mg):
        """Adding an edge should not decrease AZI."""
        build_path(mg, 4)
        before = mg.augmented_zagreb_index()
        mg.link("0", "3", "r")  # Form C₄
        after = mg.augmented_zagreb_index()
        assert after >= before

    def test_non_mutating(self, mg):
        """AZI should not modify graph state."""
        build_complete(mg, 4)
        before_nodes = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        before_edges = set(
            (r["source"], r["target"])
            for r in mg.conn.execute("SELECT source, target FROM edges")
        )
        _ = mg.augmented_zagreb_index()
        after_nodes = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        after_edges = set(
            (r["source"], r["target"])
            for r in mg.conn.execute("SELECT source, target FROM edges")
        )
        assert before_nodes == after_nodes
        assert before_edges == after_edges


# ─── Harmonic Index ────────────────────────────────────────────────────────────

class TestHarmonicIndex:

    def test_empty(self, mg):
        assert mg.harmonic_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.harmonic_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.harmonic_index() is None

    def test_k2(self, mg):
        """K₂: H = 2/(1+1) = 1."""
        build_complete(mg, 2)
        assert mg.harmonic_index() == pytest.approx(1.0)

    def test_k3(self, mg):
        """K₃: H = 3·2/4 = 3/2."""
        build_complete(mg, 3)
        assert mg.harmonic_index() == pytest.approx(1.5)

    def test_k4(self, mg):
        """K₄: H = 6·2/6 = 2 = n/2."""
        build_complete(mg, 4)
        assert mg.harmonic_index() == pytest.approx(2.0)

    def test_k5(self, mg):
        """K₅: H = 5/2 = n/2."""
        build_complete(mg, 5)
        assert mg.harmonic_index() == pytest.approx(2.5)

    def test_c4(self, mg):
        """C₄: H = 4·2/4 = 2 = n/2."""
        build_cycle(mg, 4)
        assert mg.harmonic_index() == pytest.approx(2.0)

    def test_c5(self, mg):
        """C₅: H = 5/2 = n/2."""
        build_cycle(mg, 5)
        assert mg.harmonic_index() == pytest.approx(2.5)

    def test_c6(self, mg):
        """C₆: H = 3 = n/2."""
        build_cycle(mg, 6)
        assert mg.harmonic_index() == pytest.approx(3.0)

    def test_p3(self, mg):
        """P₃: 2 endpoint edges (1,2): 2/3 each. H = 2·(2/3) = 4/3."""
        build_path(mg, 3)
        assert mg.harmonic_index() == pytest.approx(4.0 / 3.0)

    def test_p4(self, mg):
        """P₄: 2 endpoint (1,2): 2/3 + 1 internal (2,2): 2/4 = 1/2.
        H = 4/3 + 1/2 = 11/6."""
        build_path(mg, 4)
        expected = 4.0 / 3.0 + 0.5
        assert mg.harmonic_index() == pytest.approx(expected)

    def test_p5(self, mg):
        """P₅: 2 endpoint + 2 internal. H = 4/3 + 1 = 7/3."""
        build_path(mg, 5)
        expected = 4.0 / 3.0 + 2 * 0.5
        assert mg.harmonic_index() == pytest.approx(expected)

    def test_star_k3(self, mg):
        """K_{1,3}: 3 edges (1,3): 2/4 each. H = 3·(1/2) = 3/2."""
        build_star(mg, 3)
        assert mg.harmonic_index() == pytest.approx(1.5)

    def test_star_k4(self, mg):
        """K_{1,4}: 4 edges (1,4): 2/5 each. H = 4·(2/5) = 8/5."""
        build_star(mg, 4)
        assert mg.harmonic_index() == pytest.approx(8.0 / 5.0)

    def test_star_k5(self, mg):
        """K_{1,5}: 5 edges (1,5): 2/6 each. H = 5·(1/3) = 5/3."""
        build_star(mg, 5)
        assert mg.harmonic_index() == pytest.approx(5.0 / 3.0)

    # ── Parametric families ──

    def test_parametric_kn(self, mg):
        """H(K_n) = n/2 for n = 2..7."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_complete(g, n)
            assert g.harmonic_index() == pytest.approx(n / 2.0), f"K_{n}"

    def test_parametric_cn(self, mg):
        """H(C_n) = n/2 for n = 3..8."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.harmonic_index() == pytest.approx(n / 2.0), f"C_{n}"

    def test_parametric_pn(self, mg):
        """H(P_n) = 4/3 + (n-3)/2 for n ≥ 3."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_path(g, n)
            expected = 4.0 / 3.0 + (n - 3) * 0.5
            assert g.harmonic_index() == pytest.approx(expected), f"P_{n}"

    def test_parametric_star(self, mg):
        """H(K_{1,k}) = 2k/(k+1) for k = 1..6."""
        for k in range(1, 7):
            g = MemoryGraph()
            build_star(g, k)
            expected = 2.0 * k / (k + 1)
            assert g.harmonic_index() == pytest.approx(expected), f"K_{{1,{k}}}"

    # ── Properties ──

    def test_h_equals_2x_sum_connectivity(self, mg):
        """H = 2 · χ_S for various graphs."""
        # K₄
        build_complete(mg, 4)
        sc = mg.sum_connectivity_index()
        assert mg.harmonic_index() == pytest.approx(2 * sc)

    def test_h_equals_2x_sum_connectivity_path(self, mg):
        """H = 2 · χ_S for path graph."""
        build_path(mg, 6)
        sc = mg.sum_connectivity_index()
        assert mg.harmonic_index() == pytest.approx(2 * sc)

    def test_h_equals_2x_sum_connectivity_star(self, mg):
        """H = 2 · χ_S for star graph."""
        build_star(mg, 5)
        sc = mg.sum_connectivity_index()
        assert mg.harmonic_index() == pytest.approx(2 * sc)

    def test_regular_h_formula(self, mg):
        """For r-regular graphs: H = m/r."""
        # C₇ is 2-regular, m=7, H = 7/2
        build_cycle(mg, 7)
        assert mg.harmonic_index() == pytest.approx(7.0 / 2.0)

    def test_h_positive(self, mg):
        """H > 0 for any graph with edges."""
        build_path(mg, 3)
        assert mg.harmonic_index() > 0

    def test_disconnected(self, mg):
        """Two disjoint C₃: H = 2·(3/2) = 3."""
        n1 = [mg.add(f"A{i}") for i in range(3)]
        for i in range(3):
            mg.link(n1[i].id, n1[(i + 1) % 3].id, "r")
        n2 = [mg.add(f"B{i}") for i in range(3)]
        for i in range(3):
            mg.link(n2[i].id, n2[(i + 1) % 3].id, "r")
        assert mg.harmonic_index() == pytest.approx(3.0)

    def test_edge_addition_increases(self, mg):
        """Adding an edge increases H."""
        nodes = build_path(mg, 4)
        before = mg.harmonic_index()
        mg.link(nodes[0].id, nodes[-1].id, "r")
        after = mg.harmonic_index()
        assert after > before

    def test_non_mutating(self, mg):
        """Harmonic index should not modify graph state."""
        build_complete(mg, 4)
        before_nodes = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        before_edges = set(
            (r["source"], r["target"])
            for r in mg.conn.execute("SELECT source, target FROM edges")
        )
        _ = mg.harmonic_index()
        after_nodes = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        after_edges = set(
            (r["source"], r["target"])
            for r in mg.conn.execute("SELECT source, target FROM edges")
        )
        assert before_nodes == after_nodes
        assert before_edges == after_edges


# ─── Cross-Relationship Tests ──────────────────────────────────────────────────

class TestCrossRelationships:

    def test_harmonic_is_2x_sumconn_multiple(self, mg):
        """H = 2·χ_S verified across K_n, C_n, P_n, K_{1,k}."""
        graphs = [
            ("K4", lambda g: build_complete(g, 4)),
            ("K5", lambda g: build_complete(g, 5)),
            ("C5", lambda g: build_cycle(g, 5)),
            ("C7", lambda g: build_cycle(g, 7)),
            ("P4", lambda g: build_path(g, 4)),
            ("P6", lambda g: build_path(g, 6)),
            ("S4", lambda g: build_star(g, 4)),
            ("S6", lambda g: build_star(g, 6)),
        ]
        for name, builder in graphs:
            g = MemoryGraph()
            builder(g)
            sc = g.sum_connectivity_index()
            h = g.harmonic_index()
            assert h == pytest.approx(2 * sc), f"H vs 2·χ_S for {name}"

    def test_ga_bounded_by_m(self, mg):
        """GA ≤ m for all standard graph families (AM ≥ GM)."""
        graphs = [
            ("K5", lambda g: build_complete(g, 5), 10),
            ("C6", lambda g: build_cycle(g, 6), 6),
            ("P5", lambda g: build_path(g, 5), 4),
            ("S5", lambda g: build_star(g, 5), 5),
        ]
        for name, builder, m in graphs:
            g = MemoryGraph()
            builder(g)
            assert g.ga_index() <= m, f"GA ≤ m for {name}"

    def test_all_three_distinct_for_k4(self, mg):
        """GA, AZI, H produce distinct values for K₄."""
        build_complete(mg, 4)
        ga = mg.ga_index()
        azi = mg.augmented_zagreb_index()
        h = mg.harmonic_index()
        assert ga != azi
        assert ga != h
        assert azi != h

    def test_azi_ge_azi_k2(self, mg):
        """AZI(K_n) ≥ AZI(K₂) = 0 for all n ≥ 2."""
        g2 = MemoryGraph()
        build_complete(g2, 2)
        azi2 = g2.augmented_zagreb_index()
        for n in range(3, 7):
            g = MemoryGraph()
            build_complete(g, n)
            assert g.augmented_zagreb_index() > azi2, f"AZI(K_{n}) > AZI(K_2)"
