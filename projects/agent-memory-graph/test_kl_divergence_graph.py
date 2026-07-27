"""Tests for kl_divergence_graph() — Cycle 299.

KL(P‖Q) = Σ_{e: p_e > 0} p_e · ln(p_e / q_e)

Information-theoretic trilogy completion:
  - entropy_distance (JSD, symmetric, cycle 288)
  - cross_entropy_graph (H(P,Q), asymmetric, cycle 298)
  - kl_divergence_graph (KL(P‖Q), asymmetric, cycle 299)
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──────────────────────────────────────────────────────────────

def build_complete(n):
    """Complete graph K_n — all nodes connected to each other."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_path(n):
    """Path graph P_n — linear chain."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_cycle(n):
    """Cycle graph C_n — circular path."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(leaves):
    """Star graph K_{1,leaves} — one hub connected to all leaves."""
    g = MemoryGraph()
    hub = g.add("hub")
    leaf_nodes = [g.add(f"leaf{i}") for i in range(leaves)]
    for ln in leaf_nodes:
        g.link(hub.id, ln.id, "r")
    return g


def build_paw():
    """Paw graph: triangle (a,b,c) + pendant edge (c,d)."""
    g = MemoryGraph()
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return g


def build_k2():
    """Single edge K₂."""
    g = MemoryGraph()
    a, b = g.add("a"), g.add("b")
    g.link(a.id, b.id, "r")
    return g


# Convenience instances
_k3 = lambda: build_complete(3)
_c4 = lambda: build_cycle(4)
_c5 = lambda: build_cycle(5)
_p4 = lambda: build_path(4)
_p6 = lambda: build_path(6)
_star5 = lambda: build_star(4)
_paw = lambda: build_paw()
_k2 = lambda: build_k2()


# ── Degenerate cases ──────────────────────────────────────────────

class TestKLDegenerate:
    def test_both_empty(self):
        g1 = MemoryGraph()
        g2 = MemoryGraph()
        assert g1.kl_divergence_graph(g2) is None

    def test_self_empty(self):
        g1 = MemoryGraph()
        g2 = _k3()
        assert g1.kl_divergence_graph(g2) is None

    def test_other_empty(self):
        g1 = _k3()
        g2 = MemoryGraph()
        assert g1.kl_divergence_graph(g2) is None

    def test_no_edges(self):
        g1 = MemoryGraph()
        g1.add("a")
        g1.add("b")
        g2 = _k3()
        assert g1.kl_divergence_graph(g2) is None

    def test_single_edge_self(self):
        g1 = _k2()
        g2 = _k2()
        result = g1.kl_divergence_graph(g2)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-9)


# ── Self-divergence ───────────────────────────────────────────────

class TestKLSelfDivergence:
    def test_self_divergence_zero_k3(self):
        g = _k3()
        assert g.kl_divergence_graph(g) == pytest.approx(0.0, abs=1e-9)

    def test_self_divergence_zero_c4(self):
        g = _c4()
        assert g.kl_divergence_graph(g) == pytest.approx(0.0, abs=1e-9)

    def test_self_divergence_zero_p4(self):
        g = _p4()
        assert g.kl_divergence_graph(g) == pytest.approx(0.0, abs=1e-9)

    def test_self_divergence_zero_star(self):
        g = _star5()
        assert g.kl_divergence_graph(g) == pytest.approx(0.0, abs=1e-9)

    def test_self_divergence_zero_paw(self):
        g = _paw()
        assert g.kl_divergence_graph(g) == pytest.approx(0.0, abs=1e-9)

    def test_identical_graphs_zero(self):
        g1 = _k3()
        g2 = _k3()
        assert g1.kl_divergence_graph(g2) == pytest.approx(0.0, abs=1e-9)


# ── Non-negativity (Gibbs' inequality) ────────────────────────────

class TestKLNonNegative:
    def test_all_pairs_non_negative(self):
        graphs = [_k3(), _c4(), _p4(), _star5(), _paw()]
        for i, ga in enumerate(graphs):
            for j, gb in enumerate(graphs):
                kl = ga.kl_divergence_graph(gb)
                assert kl is not None, f"None for pair ({i}, {j})"
                assert kl >= 0.0, f"Negative KL for pair ({i}, {j}): {kl}"

    def test_both_directions_non_negative(self):
        g1 = _p4()
        g2 = _paw()
        kl_12 = g1.kl_divergence_graph(g2)
        kl_21 = g2.kl_divergence_graph(g1)
        assert kl_12 >= 0.0
        assert kl_21 >= 0.0


# ── Asymmetry ─────────────────────────────────────────────────────

class TestKLAsymmetry:
    def test_regular_graphs_same_size_symmetric(self):
        """Two identical K₃ graphs → symmetric KL = 0.

        K₃ vs C₄ have different total contributions (3 vs 4 edges),
        so their binned distributions use different keys and KL is
        naturally large — this is correct information-theoretic behavior.
        """
        g1 = _k3()
        g2 = _k3()
        kl_12 = g1.kl_divergence_graph(g2)
        kl_21 = g2.kl_divergence_graph(g1)
        assert kl_12 == pytest.approx(0.0, abs=1e-6)
        assert kl_21 == pytest.approx(0.0, abs=1e-6)

    def test_irregular_both_directions(self):
        """P₄ vs paw: both directions should be valid non-negative."""
        g1 = _p4()
        g2 = _paw()
        kl_12 = g1.kl_divergence_graph(g2)
        kl_21 = g2.kl_divergence_graph(g1)
        assert kl_12 >= 0.0
        assert kl_21 >= 0.0

    def test_star_vs_paw_both_directions(self):
        g1 = _star5()
        g2 = _paw()
        kl_12 = g1.kl_divergence_graph(g2)
        kl_21 = g2.kl_divergence_graph(g1)
        assert kl_12 >= 0.0
        assert kl_21 >= 0.0


# ── Index support ─────────────────────────────────────────────────

class TestKLIndexSupport:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1",
        "abc", "ga", "augmented_zagreb",
    ])
    def test_all_indices_return_float(self, index):
        g1 = _p4()
        g2 = _paw()
        result = g1.kl_divergence_graph(g2, index=index)
        if result is not None:
            assert isinstance(result, float)
            assert math.isfinite(result)
            assert result >= 0.0

    def test_unknown_index_raises(self):
        g1 = _k3()
        g2 = _k3()
        with pytest.raises(ValueError, match="unknown index"):
            g1.kl_divergence_graph(g2, index="nonexistent")


# ── ABC / AZI K₂ filtering ────────────────────────────────────────

class TestKLKEdgeCases:
    def test_abc_k2_only(self):
        """ABC index filters K₂ edges. Graph with only K₂ → None."""
        g1 = _k2()
        g2 = _k2()
        result = g1.kl_divergence_graph(g2, index="abc")
        assert result is None

    def test_augmented_zagreb_k2_only(self):
        """AZI filters K₂ edges. Graph with only K₂ → None."""
        g1 = _k2()
        g2 = _k2()
        result = g1.kl_divergence_graph(g2, index="augmented_zagreb")
        assert result is None

    def test_abc_valid_for_higher_degree(self):
        """ABC should work for graphs with edges where d_u + d_v > 2."""
        g1 = _k3()
        g2 = _paw()
        result = g1.kl_divergence_graph(g2, index="abc")
        if result is not None:
            assert result >= 0.0


# ── Relationship to cross-entropy and JSD ─────────────────────────

class TestKLRelationships:
    def test_kl_le_cross_entropy(self):
        """KL(P‖Q) = H(P,Q) − H(P) ≤ H(P,Q) since H(P) ≥ 0."""
        g1 = _p4()
        g2 = _paw()
        ce = g1.cross_entropy_graph(g2)
        kl = g1.kl_divergence_graph(g2)
        if ce is not None and kl is not None:
            assert kl <= ce + 1e-9

    def test_kl_zero_when_identical(self):
        """KL(P,P) = 0, and JSD(P,P) = 0."""
        g = _p4()
        kl = g.kl_divergence_graph(g)
        jsd = g.entropy_distance(g)
        assert kl == pytest.approx(0.0, abs=1e-9)
        assert jsd == pytest.approx(0.0, abs=1e-9)

    def test_jsd_bounded_by_max_kl(self):
        """JSD ≤ max(KL(P‖Q), KL(Q‖P))."""
        g1 = _p4()
        g2 = _star5()
        jsd = g1.entropy_distance(g2)
        kl_12 = g1.kl_divergence_graph(g2)
        kl_21 = g2.kl_divergence_graph(g1)
        if jsd is not None and kl_12 is not None and kl_21 is not None:
            max_kl = max(kl_12, kl_21)
            assert jsd <= max_kl + 1e-6 or jsd == pytest.approx(0.0, abs=1e-6)


# ── Mathematical verification ─────────────────────────────────────

class TestKLMathVerification:
    def test_regular_graphs_different_sizes(self):
        """K₃ vs C₄: both regular but different sizes → different bin keys.

        K₃ has 3 edges, each normalized to 1/3 ≈ 0.333.
        C₄ has 4 edges, each normalized to 1/4 = 0.25.
        Different bins → disjoint support → high KL (correct behavior).
        """
        g1 = _k3()
        g2 = _c4()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert kl > 0.0  # Different distributions
        assert math.isfinite(kl)  # Clamped, not infinite

    def test_k3_self_zero(self):
        g = _k3()
        kl = g.kl_divergence_graph(g)
        assert kl == pytest.approx(0.0, abs=1e-9)

    def test_p4_vs_paw_positive(self):
        """P₄ and paw have different structures → positive KL."""
        g1 = _p4()
        g2 = _paw()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert kl > 0.0

    def test_star_vs_path_positive(self):
        """Star and path have very different structures → positive KL."""
        g1 = _star5()
        g2 = _p4()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert kl > 0.0

    def test_at_least_one_direction_positive(self):
        """For different graphs, at least one direction has positive KL."""
        g1 = _p4()
        g2 = _star5()
        kl_12 = g1.kl_divergence_graph(g2)
        kl_21 = g2.kl_divergence_graph(g1)
        assert kl_12 > 0.0 or kl_21 > 0.0


# ── Disjoint support ──────────────────────────────────────────────

class TestKLDisjointSupport:
    def test_different_graphs_finite(self):
        """Different structures should produce finite KL (clamped)."""
        g1 = _k3()
        g2 = _paw()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert math.isfinite(kl)

    def test_star_vs_k3_finite(self):
        g1 = _star5()
        g2 = _k3()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert math.isfinite(kl)


# ── Non-mutating ──────────────────────────────────────────────────

class TestKLNonMutating:
    def test_self_unchanged(self):
        g1 = _p4()
        g2 = _paw()
        nodes_before = set(g1.conn.execute("SELECT id FROM nodes").fetchall())
        edges_before = set(g1.conn.execute("SELECT source, target FROM edges").fetchall())
        g1.kl_divergence_graph(g2)
        nodes_after = set(g1.conn.execute("SELECT id FROM nodes").fetchall())
        edges_after = set(g1.conn.execute("SELECT source, target FROM edges").fetchall())
        assert nodes_before == nodes_after
        assert edges_before == edges_after

    def test_other_unchanged(self):
        g1 = _p4()
        g2 = _paw()
        nodes_before = set(g2.conn.execute("SELECT id FROM nodes").fetchall())
        edges_before = set(g2.conn.execute("SELECT source, target FROM edges").fetchall())
        g1.kl_divergence_graph(g2)
        nodes_after = set(g2.conn.execute("SELECT id FROM nodes").fetchall())
        edges_after = set(g2.conn.execute("SELECT source, target FROM edges").fetchall())
        assert nodes_before == nodes_after
        assert edges_before == edges_after


# ── Bounded values ────────────────────────────────────────────────

class TestKLBounded:
    def test_all_values_reasonable(self):
        """All KL values should be reasonable (< 100 after normalization)."""
        graphs = [_k3(), _c4(), _p4(), _star5(), _paw()]
        for ga in graphs:
            for gb in graphs:
                kl = ga.kl_divergence_graph(gb)
                if kl is not None:
                    assert kl < 100.0, f"KL too large: {kl}"

    def test_kl_not_nan(self):
        g1 = _p4()
        g2 = _paw()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert not math.isnan(kl)

    def test_kl_not_inf(self):
        g1 = _star5()
        g2 = _k3()
        kl = g1.kl_divergence_graph(g2)
        assert kl is not None
        assert not math.isinf(kl)


# ── Multi-index consistency ───────────────────────────────────────

class TestKLMultiIndex:
    def test_different_indices_valid(self):
        """Different indices capture different structural aspects."""
        g1 = _p4()
        g2 = _paw()
        for idx in ["sombor", "reduced_sombor", "randic", "zagreb_m1",
                     "ga"]:
            kl = g1.kl_divergence_graph(g2, index=idx)
            if kl is not None:
                assert kl >= 0.0

    def test_all_indices_self_zero(self):
        """For any index, self-divergence should be 0."""
        g = _paw()
        for idx in ["sombor", "reduced_sombor", "randic", "zagreb_m1",
                     "abc", "ga", "augmented_zagreb"]:
            kl = g.kl_divergence_graph(g, index=idx)
            if kl is not None:
                assert kl == pytest.approx(0.0, abs=1e-9), f"Self-KL[{idx}] = {kl}"


# ── KL is NOT a metric (no triangle inequality) ──────────────────

class TestKLNotMetric:
    def test_kl_graceful_no_triangle_inequality(self):
        """KL divergence does NOT satisfy triangle inequality.

        We just verify all computations work without error.
        """
        ga = _p4()
        gb = _k3()
        gc = _star5()
        kl_ab = ga.kl_divergence_graph(gb)
        kl_bc = gb.kl_divergence_graph(gc)
        kl_ac = ga.kl_divergence_graph(gc)
        for kl in [kl_ab, kl_bc, kl_ac]:
            if kl is not None:
                assert kl >= 0.0
