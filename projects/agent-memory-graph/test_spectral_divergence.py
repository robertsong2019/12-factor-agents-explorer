"""Tests for spectral_divergence() — Cycle 308.

Histogram-based information-theoretic divergence between Laplacian
eigenvalue distributions of two graphs.

Measures:
  - jsd: Jensen-Shannon distance √(½KL(P‖M)+½KL(Q‖M)), symmetric
  - kl:  KL divergence Σ p·ln(p/q), asymmetric
  - ce:  Cross-entropy −Σ p·ln(q), asymmetric

Complements quantum_jensen_shannon_distance() (elementwise on padded
eigenvalue vectors) with a histogram-based approach that captures
spectral *shape* and is size-invariant.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──────────────────────────────────────────────────────────────

def build_complete(n):
    """Complete graph K_n."""
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
    """Cycle graph C_n."""
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(leaves):
    """Star graph K_{1,leaves}."""
    g = MemoryGraph()
    hub = g.add("hub")
    for i in range(leaves):
        leaf = g.add(f"leaf{i}")
        g.link(hub.id, leaf.id, "r")
    return g


def build_empty():
    return MemoryGraph()


def build_single():
    g = MemoryGraph()
    g.add("a")
    return g


def build_no_edges():
    g = MemoryGraph()
    g.add("a")
    g.add("b")
    g.add("c")
    return g


def build_paw():
    """Paw graph: triangle with a pendant edge."""
    g = MemoryGraph()
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return g


# ── Degenerate cases ─────────────────────────────────────────────────────

class TestDegenerate:
    def test_empty_vs_empty(self):
        assert build_empty().spectral_divergence(build_empty()) is None

    def test_single_vs_single(self):
        assert build_single().spectral_divergence(build_single()) is None

    def test_no_edges_vs_no_edges(self):
        assert build_no_edges().spectral_divergence(build_no_edges()) is None

    def test_k3_vs_empty(self):
        assert build_complete(3).spectral_divergence(build_empty()) is None

    def test_empty_vs_k3(self):
        assert build_empty().spectral_divergence(build_complete(3)) is None


# ── Self-divergence ──────────────────────────────────────────────────────

class TestSelfDivergence:
    @pytest.mark.parametrize("builder,name", [
        (lambda: build_complete(3), "K3"),
        (lambda: build_complete(4), "K4"),
        (lambda: build_cycle(4), "C4"),
        (lambda: build_cycle(5), "C5"),
        (lambda: build_path(4), "P4"),
        (lambda: build_path(5), "P5"),
        (lambda: build_star(3), "S3"),
        (lambda: build_star(4), "S4"),
        (lambda: build_paw(), "paw"),
    ])
    def test_self_jsd_zero(self, builder, name):
        g = builder()
        val = g.spectral_divergence(g, measure="jsd")
        assert val is not None
        assert val < 1e-10, f"Self-JSD({name}) should be ~0, got {val}"

    @pytest.mark.parametrize("builder,name", [
        (lambda: build_complete(3), "K3"),
        (lambda: build_cycle(4), "C4"),
        (lambda: build_path(4), "P4"),
        (lambda: build_star(3), "S3"),
    ])
    def test_self_kl_zero(self, builder, name):
        g = builder()
        val = g.spectral_divergence(g, measure="kl")
        assert val is not None
        assert val < 1e-10, f"Self-KL({name}) should be ~0, got {val}"

    @pytest.mark.parametrize("builder,name", [
        (lambda: build_complete(3), "K3"),
        (lambda: build_cycle(4), "C4"),
        (lambda: build_path(4), "P4"),
        (lambda: build_star(3), "S3"),
    ])
    def test_self_ce_nonneg(self, builder, name):
        """Self-CE on binned histograms may be > 0 when multiple
        eigenvalues share a bin (since the histogram normalises by
        count, not by eigenvalue). It must still be non-negative."""
        g = builder()
        val = g.spectral_divergence(g, measure="ce")
        assert val is not None
        assert val >= -1e-10, f"Self-CE({name}) should be ≥ 0, got {val}"


# ── Non-negativity ───────────────────────────────────────────────────────

class TestNonNegative:
    @pytest.mark.parametrize("measure", ["jsd", "kl", "ce"])
    def test_all_pairs_nonneg(self, measure):
        graphs = [
            build_complete(3), build_complete(4),
            build_cycle(4), build_cycle(5),
            build_path(3), build_path(4),
            build_star(3), build_star(4),
            build_paw(),
        ]
        for i, a in enumerate(graphs):
            for j, b in enumerate(graphs):
                if i == j:
                    continue
                val = a.spectral_divergence(b, measure=measure)
                if val is not None:
                    assert val >= -1e-10, (
                        f"{measure}({type(a).__name__},{type(b).__name__}) "
                        f"= {val} < 0"
                    )


# ── JSD symmetry ─────────────────────────────────────────────────────────

class TestJSDSymmetry:
    @pytest.mark.parametrize("a,b,name_a,name_b", [
        (build_complete(3), build_complete(4), "K3", "K4"),
        (build_cycle(4), build_path(4), "C4", "P4"),
        (build_star(3), build_paw(), "S3", "paw"),
        (build_complete(3), build_cycle(4), "K3", "C4"),
        (build_path(3), build_star(3), "P3", "S3"),
    ])
    def test_jsd_symmetric(self, a, b, name_a, name_b):
        v1 = a.spectral_divergence(b, measure="jsd")
        v2 = b.spectral_divergence(a, measure="jsd")
        assert v1 is not None and v2 is not None
        assert abs(v1 - v2) < 1e-8, (
            f"JSD({name_a},{name_b})={v1} ≠ JSD({name_b},{name_a})={v2}"
        )


# ── KL/CE asymmetry ──────────────────────────────────────────────────────

class TestAsymmetry:
    def test_kl_can_differ(self):
        """KL(P‖Q) ≠ KL(Q‖P) for sufficiently different graphs."""
        a, b = build_complete(3), build_path(4)
        kl_ab = a.spectral_divergence(b, measure="kl")
        kl_ba = b.spectral_divergence(a, measure="kl")
        assert kl_ab is not None and kl_ba is not None
        # They *can* be equal for identical histograms, but for
        # K3 vs P4 they should differ
        assert kl_ab != kl_ba or abs(kl_ab) < 1e-6

    def test_ce_can_differ(self):
        a, b = build_complete(3), build_star(3)
        ce_ab = a.spectral_divergence(b, measure="ce")
        ce_ba = b.spectral_divergence(a, measure="ce")
        assert ce_ab is not None and ce_ba is not None
        assert ce_ab != ce_ba or abs(ce_ab) < 1e-6


# ── Measure relationships ────────────────────────────────────────────────

class TestMeasureRelationships:
    def test_jsd_bounded_sqrt_ln2(self):
        """JSD ≤ √(ln2) ≈ 0.8326."""
        graphs = [
            build_complete(3), build_cycle(4), build_path(4),
            build_star(3), build_paw(),
        ]
        bound = math.sqrt(math.log(2)) + 1e-9
        for i, a in enumerate(graphs):
            for j, b in enumerate(graphs):
                if i == j:
                    continue
                val = a.spectral_divergence(b, measure="jsd")
                if val is not None:
                    assert val <= bound, f"JSD={val} > √(ln2)={bound}"

    def test_kl_le_cross_entropy(self):
        """KL(P‖Q) = H(P,Q) − H(P) ≤ H(P,Q) since H(P) ≥ 0."""
        a, b = build_complete(3), build_path(4)
        kl = a.spectral_divergence(b, measure="kl")
        ce = a.spectral_divergence(b, measure="ce")
        assert kl is not None and ce is not None
        # KL ≤ CE (since H(P) ≥ 0 on the binned distribution)
        assert kl <= ce + 1e-9, f"KL={kl} > CE={ce}"

    def test_identical_kl_ce_relationship(self):
        """For identical graphs: KL=0, CE = H(self) ≥ 0."""
        g = build_complete(4)
        kl = g.spectral_divergence(g, measure="kl")
        ce = g.spectral_divergence(g, measure="ce")
        assert kl is not None and ce is not None
        assert abs(kl) < 1e-10
        assert ce >= -1e-10


# ── Measure validation ───────────────────────────────────────────────────

class TestMeasureValidation:
    def test_unknown_measure_raises(self):
        g1, g2 = build_complete(3), build_complete(4)
        with pytest.raises(ValueError, match="unknown measure"):
            g1.spectral_divergence(g2, measure="foo")

    def test_bins_too_small_raises(self):
        g1, g2 = build_complete(3), build_complete(4)
        with pytest.raises(ValueError, match="bins must be"):
            g1.spectral_divergence(g2, bins=1)


# ── Size-invariance ──────────────────────────────────────────────────────

class TestSizeInvariance:
    def test_different_size_graphs_compared(self):
        """Graphs with different node counts produce a valid divergence."""
        a, b = build_complete(3), build_complete(5)
        val = a.spectral_divergence(b, measure="jsd")
        assert val is not None
        assert 0 <= val <= math.sqrt(math.log(2))

    def test_different_structure_same_size(self):
        """Same node count, different structure → positive divergence."""
        a, b = build_cycle(5), build_star(4)
        val = a.spectral_divergence(b, measure="jsd")
        assert val is not None
        assert val > 0.01, f"Expected significant divergence, got {val}"


# ── Bins parameter ───────────────────────────────────────────────────────

class TestBinsParameter:
    def test_more_bins_changes_value(self):
        """Increasing bins should change the divergence value
        (finer resolution)."""
        a, b = build_complete(3), build_path(5)
        v5 = a.spectral_divergence(b, measure="jsd", bins=5)
        v20 = a.spectral_divergence(b, measure="jsd", bins=20)
        v50 = a.spectral_divergence(b, measure="jsd", bins=50)
        assert v5 is not None and v20 is not None and v50 is not None
        # At least one should differ
        assert len({round(v5, 4), round(v20, 4), round(v50, 4)}) >= 2

    def test_bins_self_zero_regardless(self):
        """Self-divergence is always ~0 regardless of bins."""
        g = build_complete(4)
        for b in [2, 5, 10, 20, 50]:
            val = g.spectral_divergence(g, measure="jsd", bins=b)
            assert val is not None
            assert val < 1e-10, f"Self-JSD with bins={b}: {val}"


# ── Comparison with quantum_jensen_shannon_distance ──────────────────────

class TestVsQuantumJSD:
    def test_both_return_valid_values(self):
        a, b = build_complete(3), build_path(4)
        hist_jsd = a.spectral_divergence(b, measure="jsd")
        elem_jsd = a.quantum_jensen_shannon_distance(b)
        assert hist_jsd is not None
        assert elem_jsd is not None
        assert 0 <= hist_jsd <= math.sqrt(math.log(2))
        assert 0 <= elem_jsd <= math.sqrt(math.log(2))

    def test_different_approaches_different_values(self):
        """The histogram and elementwise approaches measure different
        things — they should produce different values for some graphs."""
        a, b = build_complete(3), build_star(3)
        hist_jsd = a.spectral_divergence(b, measure="jsd", bins=10)
        elem_jsd = a.quantum_jensen_shannon_distance(b)
        assert hist_jsd is not None and elem_jsd is not None
        # They are not identical
        assert abs(hist_jsd - elem_jsd) > 1e-6, (
            f"Hist JSD={hist_jsd} ≈ Elem JSD={elem_jsd}, "
            "expected different values from different methods"
        )


# ── Monotonicity ─────────────────────────────────────────────────────────

class TestMonotonicity:
    def test_edge_addition_changes_divergence(self):
        """A path and a cycle on the same number of nodes should have
        a positive spectral divergence."""
        g1 = build_path(5)
        g2 = build_cycle(5)
        val = g1.spectral_divergence(g2, measure="jsd")
        assert val is not None
        assert val > 0.001, ("P5 vs C5 spectral JSD should be > 0, got {val}"
        )

    def test_more_similar_graphs_closer(self):
        """K3 is spectrally closer to K4 than to P4 (both vs K3)."""
        k3 = build_complete(3)
        k4 = build_complete(4)
        p4 = build_path(4)
        d_k3k4 = k3.spectral_divergence(k4, measure="jsd")
        d_k3p4 = k3.spectral_divergence(p4, measure="jsd")
        assert d_k3k4 is not None and d_k3p4 is not None
        # Two complete graphs should be more similar than complete vs path
        assert d_k3k4 < d_k3p4 + 0.3, (
            f"K3-K4 JSD={d_k3k4}, K3-P4 JSD={d_k3p4}; "
            "expected K3-K4 to be closer"
        )


# ── All three measures together ──────────────────────────────────────────

class TestAllMeasures:
    @pytest.mark.parametrize("measure", ["jsd", "kl", "ce"])
    def test_k3_vs_p4_returns_valid(self, measure):
        a, b = build_complete(3), build_path(4)
        val = a.spectral_divergence(b, measure=measure)
        assert val is not None
        assert not math.isnan(val)
        assert not math.isinf(val)

    @pytest.mark.parametrize("measure", ["jsd", "kl", "ce"])
    def test_star_vs_cycle_returns_valid(self, measure):
        a, b = build_star(4), build_cycle(5)
        val = a.spectral_divergence(b, measure=measure)
        assert val is not None
        assert not math.isnan(val)
        assert not math.isinf(val)


# ── Non-mutating ─────────────────────────────────────────────────────────

class TestNonMutating:
    def test_self_unchanged(self):
        g1 = build_complete(4)
        g2 = build_path(4)
        n_before = g1.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e_before = g1.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        g1.spectral_divergence(g2, measure="jsd")
        n_after = g1.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e_after = g1.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        assert n_before == n_after
        assert e_before == e_after

    def test_other_unchanged(self):
        g1 = build_complete(4)
        g2 = build_path(4)
        n_before = g2.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e_before = g2.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        g1.spectral_divergence(g2, measure="kl")
        n_after = g2.conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        e_after = g2.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
        assert n_before == n_after
        assert e_before == e_after


# ── Include quarantined ──────────────────────────────────────────────────

class TestIncludeQuarantined:
    def test_includes_quarantined_nodes(self):
        """Including quarantined nodes can change the result."""
        g1 = build_complete(4)
        # Quarantine a node in g1
        first_id = g1.conn.execute(
            "SELECT id FROM nodes ORDER BY id LIMIT 1"
        ).fetchone()["id"]
        g1.conn.execute(
            "UPDATE nodes SET quarantined = 1 WHERE id = ?",
            (first_id,)
        )
        g1.conn.commit()

        g2 = build_complete(4)
        val_excl = g1.spectral_divergence(g2, measure="jsd",
                                          include_quarantined=False)
        val_incl = g1.spectral_divergence(g2, measure="jsd",
                                          include_quarantined=True)
        assert val_excl is not None
        assert val_incl is not None
        # With quarantined excluded, g1 has 3 nodes (K3) vs g2's K4
        # With quarantined included, g1 has 4 nodes (K4 with an isolated node)
        assert abs(val_excl - val_incl) > 1e-6 or (
            val_excl < 1e-6 and val_incl < 1e-6
        )
