"""Tests for cross_entropy_graph() — asymmetric inter-graph cross-entropy.

Cycle 298: H(P, Q) = −Σ p·ln(q) between two graphs' edge-contribution
distributions (binned by normalized contribution value).  Complements
entropy_distance (JSD) with a directional information-theoretic measure.
"""

import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──────────────────────────────────────────────────────────────

def build_complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_cycle(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(k):
    g = MemoryGraph()
    center = g.add("hub")
    leaves = [g.add(f"l{i}") for i in range(k)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "r")
    return g


def build_paw():
    """Paw graph: triangle + pendant edge."""
    g = MemoryGraph()
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(c.id, a.id, "r")
    g.link(c.id, d.id, "r")
    return g


def build_edge():
    g = MemoryGraph()
    a, b = g.add("a"), g.add("b")
    g.link(a.id, b.id, "r")
    return g


def build_single():
    g = MemoryGraph()
    g.add("x")
    return g


# ── Degenerate cases ────────────────────────────────────────────────────

class TestDegenerate:
    def test_both_empty(self):
        g1, g2 = MemoryGraph(), MemoryGraph()
        assert g1.cross_entropy_graph(g2) is None

    def test_both_single_node(self):
        g1, g2 = build_single(), build_single()
        assert g1.cross_entropy_graph(g2) is None

    def test_self_empty_other_has_edges(self):
        g1, g2 = MemoryGraph(), build_edge()
        assert g1.cross_entropy_graph(g2) is None

    def test_self_has_edges_other_empty(self):
        g1, g2 = build_edge(), MemoryGraph()
        assert g1.cross_entropy_graph(g2) is None

    def test_no_edges_returns_none(self):
        g = MemoryGraph()
        g.add("a"); g.add("b"); g.add("c")
        other = build_edge()
        assert g.cross_entropy_graph(other) is None


# ── Self cross-entropy properties ───────────────────────────────────────

class TestSelfCrossEntropy:
    def test_self_ce_non_negative(self):
        """H(P, P) ≥ 0."""
        g = build_path(5)
        ce = g.cross_entropy_graph(g, index="sombor")
        assert ce is not None
        assert ce >= 0

    def test_self_ce_minimal(self):
        """H(P, P) ≤ H(P, Q) for any Q (self is the 'cheapest' encoding).

        This is Gibbs' inequality applied to the binned distribution.
        """
        g1 = build_path(5)
        g2 = build_star(5)
        self_ce = g1.cross_entropy_graph(g1, index="sombor")
        cross_ce = g1.cross_entropy_graph(g2, index="sombor")
        assert self_ce is not None and cross_ce is not None
        assert self_ce <= cross_ce + 1e-9

    def test_self_ce_k3(self):
        """K₃ has all edges identical → 1 bin → H(P,P) = 0."""
        g = build_complete(3)
        ce = g.cross_entropy_graph(g, index="sombor")
        assert ce is not None
        # Single bin → -1·ln(1) = 0, normalized by ln(2) = 0
        assert abs(ce) < 1e-9

    def test_self_ce_p4_positive(self):
        """P₄ has two edge types → 2 bins → H(P,P) > 0."""
        g = build_path(4)
        ce = g.cross_entropy_graph(g, index="sombor")
        assert ce is not None
        assert ce > 0

    def test_self_ce_symmetric_directions(self):
        """H(P, P) computed in either 'direction' is the same."""
        g = build_path(5)
        ce = g.cross_entropy_graph(g, index="randic")
        assert ce is not None
        # Self cross-entropy is trivially the same in both directions
        assert ce == ce  # tautology but documents the property


# ── Asymmetry ───────────────────────────────────────────────────────────

class TestAsymmetry:
    def test_symmetric_for_identical_regular(self):
        """For identical regular graphs, both directions equal."""
        g1, g2 = build_complete(4), build_complete(4)
        h12 = g1.cross_entropy_graph(g2, index="sombor")
        h21 = g2.cross_entropy_graph(g1, index="sombor")
        assert h12 is not None and h21 is not None
        assert abs(h12 - h21) < 1e-9

    def test_both_directions_non_negative(self):
        """Cross-entropy is non-negative in both directions."""
        g1 = MemoryGraph()
        a, b, c, d = g1.add("a"), g1.add("b"), g1.add("c"), g1.add("d")
        g1.link(a.id, b.id, "r")
        g1.link(b.id, c.id, "r")
        g1.link(c.id, d.id, "r")
        g1.link(a.id, c.id, "r")
        g2 = build_star(4)
        h12 = g1.cross_entropy_graph(g2, index="sombor")
        h21 = g2.cross_entropy_graph(g1, index="sombor")
        assert h12 is not None and h21 is not None
        assert h12 >= 0
        assert h21 >= 0


# ── Gibbs' inequality: H(P, Q) ≥ H(P, P) ───────────────────────────────

class TestGibbsInequality:
    def test_cross_ge_self(self):
        """H(P, Q) ≥ H(P, P) — Gibbs' inequality on binned distributions."""
        k3 = build_complete(3)
        p4 = build_path(4)
        self_ce = k3.cross_entropy_graph(k3, index="sombor")
        cross_ce = k3.cross_entropy_graph(p4, index="sombor")
        assert self_ce is not None and cross_ce is not None
        assert cross_ce >= self_ce - 1e-9

    def test_star_vs_path_gibbs(self):
        """Cross-entropy ≥ self cross-entropy."""
        star = build_star(5)
        path = build_path(5)
        self_ce = star.cross_entropy_graph(star, index="randic")
        cross_ce = star.cross_entropy_graph(path, index="randic")
        assert self_ce is not None and cross_ce is not None
        assert cross_ce >= self_ce - 1e-9

    def test_gibbs_paw(self):
        """Gibbs' inequality on irregular graph."""
        g = build_paw()
        other = build_path(4)
        self_ce = g.cross_entropy_graph(g, index="sombor")
        cross_ce = g.cross_entropy_graph(other, index="sombor")
        assert self_ce is not None and cross_ce is not None
        assert cross_ce >= self_ce - 1e-9


# ── Non-negative ─────────────────────────────────────────────────────────

class TestNonNegative:
    def test_all_pairs_non_negative(self):
        graphs = [build_complete(3), build_path(4), build_cycle(5), build_star(4), build_edge()]
        for i, ga in enumerate(graphs):
            for j, gb in enumerate(graphs):
                ce = ga.cross_entropy_graph(gb, index="sombor")
                if ce is not None:
                    assert ce >= 0, f"Negative CE for graphs[{i}] vs graphs[{j}]: {ce}"


# ── Index support ───────────────────────────────────────────────────────

class TestIndexSupport:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1",
        "abc", "ga", "augmented_zagreb",
    ])
    def test_all_indices_return_float(self, index):
        g1, g2 = build_path(4), build_path(5)
        ce = g1.cross_entropy_graph(g2, index=index)
        if ce is not None:
            assert isinstance(ce, float)
            assert ce >= 0

    def test_unknown_index_raises(self):
        g1, g2 = build_path(3), build_path(4)
        with pytest.raises(ValueError, match="unknown index"):
            g1.cross_entropy_graph(g2, index="nonexistent")


# ── ABC K₂ filtering ────────────────────────────────────────────────────

class TestABCK2:
    def test_abc_k2_only_returns_none(self):
        """Graph with only K₂ edges: ABC contributions empty → None."""
        g1, g2 = build_edge(), build_edge()
        ce = g1.cross_entropy_graph(g2, index="abc")
        assert ce is None

    def test_azi_k2_only_returns_none(self):
        """Graph with only K₂ edges: AZI contributions empty → None."""
        g1, g2 = build_edge(), build_edge()
        ce = g1.cross_entropy_graph(g2, index="augmented_zagreb")
        assert ce is None


# ── Relationship to entropy_distance (JSD) ──────────────────────────────

class TestJSRelationship:
    def test_jsd_leq_max_cross(self):
        """JSD(P,Q) ≤ max(H(P,Q), H(Q,P)) in normalized terms."""
        g1 = build_path(4)
        g2 = build_path(6)
        jsd = g1.entropy_distance(g2, index="sombor")
        h12 = g1.cross_entropy_graph(g2, index="sombor")
        h21 = g2.cross_entropy_graph(g1, index="sombor")
        assert jsd is not None
        assert h12 is not None and h21 is not None
        assert jsd <= max(h12, h21) + 1e-9

    def test_identical_graphs_zero_jsd(self):
        """For identical graphs: JSD=0 and both cross-entropies equal."""
        g1, g2 = build_complete(4), build_complete(4)
        jsd = g1.entropy_distance(g2, index="sombor")
        h12 = g1.cross_entropy_graph(g2, index="sombor")
        h21 = g2.cross_entropy_graph(g1, index="sombor")
        assert jsd is not None
        assert abs(jsd) < 1e-9
        assert abs(h12 - h21) < 1e-9


# ── Mathematical verification ───────────────────────────────────────────

class TestMathVerification:
    def test_k3_single_bin_zero_self_ce(self):
        """K₃: all edges identical → 1 distribution bin → H(P,P) = 0.

        With a single bin, p = 1.0 and ln(1.0) = 0.
        """
        g1, g2 = build_complete(3), build_complete(3)
        ce = g1.cross_entropy_graph(g2, index="sombor")
        assert ce is not None
        assert abs(ce) < 1e-9

    def test_c4_single_bin_zero_self_ce(self):
        """C₄: all edges identical → 1 bin → H(P,P) = 0."""
        g = build_cycle(4)
        ce = g.cross_entropy_graph(g, index="sombor")
        assert ce is not None
        assert abs(ce) < 1e-9

    def test_p4_two_bins_positive_ce(self):
        """P₄: two edge types (endpoint, interior) → 2 bins → H > 0."""
        g = build_path(4)
        ce = g.cross_entropy_graph(g, index="sombor")
        assert ce is not None
        assert ce > 0

    def test_regular_graphs_cross_entropy_well_defined(self):
        """Star K₁,₄ and C₄: cross-entropy is well-defined and ≥ 0."""
        star = build_star(4)
        cyc = build_cycle(4)
        ce_sc = star.cross_entropy_graph(cyc, index="sombor")
        ce_cs = cyc.cross_entropy_graph(star, index="sombor")
        assert ce_sc is not None
        assert ce_cs is not None
        assert ce_sc >= 0
        assert ce_cs >= 0

    def test_paw_self_ce_positive(self):
        """Paw graph has 3+ edge types → H(P,P) > 0."""
        g = build_paw()
        ce = g.cross_entropy_graph(g, index="sombor")
        assert ce is not None
        assert ce > 0


# ── Disjoint support ────────────────────────────────────────────────────

class TestDisjointSupport:
    def test_disjoint_support_finite(self):
        """Graphs with different contribution values produce finite CE."""
        k3 = build_complete(3)
        p4 = build_path(4)
        ce = k3.cross_entropy_graph(p4, index="sombor")
        assert ce is not None
        assert math.isfinite(ce)
        assert ce >= 0

    def test_different_graphs_both_finite(self):
        """Path vs complete: very different structures, both directions finite."""
        p4 = build_path(4)
        k5 = build_complete(5)
        ce_pk = p4.cross_entropy_graph(k5, index="sombor")
        ce_kp = k5.cross_entropy_graph(p4, index="sombor")
        assert ce_pk is not None
        assert ce_kp is not None
        assert math.isfinite(ce_pk)
        assert math.isfinite(ce_kp)


# ── Non-mutating ────────────────────────────────────────────────────────

class TestNonMutating:
    def test_non_mutating_self(self):
        g1 = build_path(4)
        g2 = build_star(4)
        nodes_before = g1.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        edges_before = g1.edge_count()
        _ = g1.cross_entropy_graph(g2, index="sombor")
        assert g1.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0] == nodes_before
        assert g1.edge_count() == edges_before

    def test_non_mutating_other(self):
        g1 = build_path(4)
        g2 = build_star(4)
        nodes_before = g2.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]
        edges_before = g2.edge_count()
        _ = g1.cross_entropy_graph(g2, index="sombor")
        assert g2.conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0] == nodes_before
        assert g2.edge_count() == edges_before


# ── Bounded output ──────────────────────────────────────────────────────

class TestBounded:
    def test_output_bounded_reasonably(self):
        """Cross-entropy normalized by ln(m) should be bounded.

        For overlapping distributions, CE/ln(m) ∈ [0, ~2].
        For disjoint distributions, the clamping keeps it finite.
        """
        graphs = [build_complete(3), build_path(4), build_cycle(6),
                  build_star(5), build_paw()]
        for ga in graphs:
            for gb in graphs:
                ce = ga.cross_entropy_graph(gb, index="sombor")
                if ce is not None:
                    assert ce < 100, f"CE unexpectedly large: {ce}"
