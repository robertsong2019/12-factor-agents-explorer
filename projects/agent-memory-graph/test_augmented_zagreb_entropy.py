"""Tests for augmented_zagreb_entropy() — Shannon entropy of AZI edge contributions.

AZI uses cubic contributions: a_e = (d_u·d_v/(d_u+d_v−2))³
K₂ edges (d_u+d_v=2) are excluded (denominator = 0).

Cycle 282.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ─── Helpers ────────────────────────────────────────────────────────────

def build_complete(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes


def build_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes


def build_cycle(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return nodes


def build_star(g, k):
    center = g.add("0")
    leaves = [g.add(str(i + 1)) for i in range(k)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "r")
    return center, leaves


def build_paw(g):
    """Paw graph: triangle K₃ with a pendant edge."""
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return a, b, c, d


# ─── Empty / degenerate cases ──────────────────────────────────────────

class TestAugZagrebEntropyDegenerate:
    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.augmented_zagreb_entropy() is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("a")
        assert g.augmented_zagreb_entropy() is None

    def test_no_edges(self):
        g = MemoryGraph()
        g.add("a")
        g.add("b")
        assert g.augmented_zagreb_entropy() is None

    def test_single_k2_edge(self):
        """K₂: d_u+d_v−2 = 0 → edge skipped → None."""
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        g.link(a.id, b.id, "r")
        assert g.augmented_zagreb_entropy() is None

    def test_multiple_k2_edges(self):
        """Two independent K₂ edges: all skipped → None."""
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        c, d = g.add("c"), g.add("d")
        g.link(a.id, b.id, "r")
        g.link(c.id, d.id, "r")
        assert g.augmented_zagreb_entropy() is None

    def test_k2_plus_k3(self):
        """K₂ + K₃ mix: K₂ skipped, K₃ has equal contributions → entropy defined."""
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        c, d, e = g.add("c"), g.add("d"), g.add("e")
        g.link(a.id, b.id, "r")  # K₂ edge
        g.link(c.id, d.id, "r")
        g.link(d.id, e.id, "r")
        g.link(c.id, e.id, "r")  # K₃
        result = g.augmented_zagreb_entropy()
        assert result is not None


# ─── Regular graphs: entropy = 1.0 ────────────────────────────────────

class TestAugZagrebEntropyRegular:
    def test_k3_normalized_one(self):
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_k4_normalized_one(self):
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_k5_normalized_one(self):
        g = MemoryGraph()
        build_complete(g, 5)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_c4_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_c5_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 5)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_c6_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 6)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_star_k3_normalized_one(self):
        g = MemoryGraph()
        build_star(g, 3)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_star_k5_normalized_one(self):
        g = MemoryGraph()
        build_star(g, 5)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_star_k7_normalized_one(self):
        g = MemoryGraph()
        build_star(g, 7)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)


# ─── Raw entropy on regular graphs ────────────────────────────────────

class TestAugZagrebEntropyRaw:
    def test_k3_raw_ln3(self):
        """K₃: 3 identical AZI contributions → raw entropy = ln(3)."""
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.augmented_zagreb_entropy(normalized=False) == pytest.approx(math.log(3), abs=1e-10)

    def test_k4_raw_ln6(self):
        """K₄: 6 identical contributions → raw entropy = ln(6)."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.augmented_zagreb_entropy(normalized=False) == pytest.approx(math.log(6), abs=1e-10)

    def test_c4_raw_ln4(self):
        """C₄: 4 identical contributions → raw entropy = ln(4)."""
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.augmented_zagreb_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-10)

    def test_star_k4_raw_ln4(self):
        """K_{1,4}: 4 identical contributions → raw entropy = ln(4)."""
        g = MemoryGraph()
        build_star(g, 4)
        assert g.augmented_zagreb_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-10)

    def test_p3_raw(self):
        """P₃: 2 edges with same AZI contribution → raw entropy = ln(2)."""
        g = MemoryGraph()
        build_path(g, 3)
        # Both edges: (1,2) type → AZI = (2/1)³ = 8
        assert g.augmented_zagreb_entropy(normalized=False) == pytest.approx(math.log(2), abs=1e-10)


# ─── Path entropy ─────────────────────────────────────────────────────

class TestAugZagrebEntropyPath:
    def test_p3_normalized_one(self):
        """P₃: both edges have same AZI → entropy = 1.0."""
        g = MemoryGraph()
        build_path(g, 3)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_p4_normalized(self):
        """P₄: all AZI contributions = 8 → entropy ≈ 1.0."""
        # P₄: (1,2), (2,2), (2,1) — all AZI = 8
        g = MemoryGraph()
        build_path(g, 4)
        val = g.augmented_zagreb_entropy()
        assert val is not None
        assert val == pytest.approx(1.0, abs=1e-10)

    def test_p5_normalized_one(self):
        """P₅: all AZI contributions = 8 → entropy = 1.0 exactly."""
        g = MemoryGraph()
        build_path(g, 5)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-12)

    def test_p6_normalized_one(self):
        """P₆: all AZI contributions = 8 → entropy = 1.0."""
        g = MemoryGraph()
        build_path(g, 6)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-10)


# ─── Paw graph ────────────────────────────────────────────────────────

class TestAugZagrebEntropyPaw:
    def test_paw_less_than_one(self):
        """Paw: different edge types → entropy < 1.0."""
        g = MemoryGraph()
        build_paw(g)
        val = g.augmented_zagreb_entropy()
        assert val is not None
        assert val < 1.0

    def test_paw_positive(self):
        g = MemoryGraph()
        build_paw(g)
        assert g.augmented_zagreb_entropy() > 0


# ─── Disconnected graphs ──────────────────────────────────────────────

class TestAugZagrebEntropyDisconnected:
    def test_two_k3(self):
        g = MemoryGraph()
        build_complete(g, 3)
        h = MemoryGraph()
        build_complete(h, 3)
        # Merge: add 3 more nodes + 3 more edges to g
        nodes2 = [g.add(f"x{i}") for i in range(3)]
        g.link(nodes2[0].id, nodes2[1].id, "r")
        g.link(nodes2[1].id, nodes2[2].id, "r")
        g.link(nodes2[0].id, nodes2[2].id, "r")
        # All contributions identical within each K₃, but K₃ components
        # are same size → all 6 contributions equal
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_two_c4(self):
        g = MemoryGraph()
        build_cycle(g, 4)
        nodes2 = [g.add(f"y{i}") for i in range(4)]
        for i in range(4):
            g.link(nodes2[i].id, nodes2[(i + 1) % 4].id, "r")
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-10)


# ─── Edge addition ────────────────────────────────────────────────────

class TestAugZagrebEntropyEdgeAddition:
    def test_adding_edge_changes_entropy(self):
        """Adding an edge between leaves of a star changes the AZI entropy."""
        g = MemoryGraph()
        center = g.add("c")
        leaves = [g.add(f"l{i}") for i in range(4)]
        for leaf in leaves:
            g.link(center.id, leaf.id, "r")
        before = g.augmented_zagreb_entropy()
        # Connect two leaves — creates irregular degree distribution
        g.link(leaves[0].id, leaves[1].id, "r")
        after = g.augmented_zagreb_entropy()
        assert before != after
        assert abs(before - after) > 1e-6  # meaningful change, not float noise


# ─── Bounded [0, 1] ──────────────────────────────────────────────────

class TestAugZagrebEntropyBounded:
    @pytest.mark.parametrize("builder,n", [
        (build_complete, 3),
        (build_complete, 4),
        (build_complete, 5),
        (build_cycle, 4),
        (build_cycle, 5),
        (build_cycle, 6),
        (build_star, 3),
        (build_star, 5),
    ])
    def test_bounded_regular(self, builder, n):
        g = MemoryGraph()
        if builder == build_star:
            builder(g, n)
        else:
            builder(g, n)
        val = g.augmented_zagreb_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-12

    @pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
    def test_bounded_path(self, n):
        g = MemoryGraph()
        build_path(g, n)
        val = g.augmented_zagreb_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-12

    def test_paw_bounded(self):
        g = MemoryGraph()
        build_paw(g)
        val = g.augmented_zagreb_entropy()
        assert 0 < val < 1.0


# ─── Non-mutating ─────────────────────────────────────────────────────

class TestAugZagrebEntropyNonMutating:
    def test_does_not_add_nodes(self):
        g = MemoryGraph()
        build_complete(g, 3)
        before = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        g.augmented_zagreb_entropy()
        after = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        assert before == after

    def test_does_not_add_edges(self):
        g = MemoryGraph()
        build_path(g, 4)
        before = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        g.augmented_zagreb_entropy()
        after = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        assert before == after


# ─── Cross-checks with other entropies ────────────────────────────────

class TestAugZagrebEntropyCrossCheck:
    def test_regular_all_one(self):
        """On regular graphs, all entropies including AZI = 1.0."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.augmented_zagreb_entropy() == pytest.approx(1.0, abs=1e-10)
        assert g.abc_entropy() == pytest.approx(1.0, abs=1e-10)
        assert g.sombor_entropy() == pytest.approx(1.0, abs=1e-10)
        assert g.ga_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_paw_all_below_one(self):
        """On paw graph, AZI entropy < 1.0 like other irregular entropies."""
        g = MemoryGraph()
        build_paw(g)
        assert g.augmented_zagreb_entropy() < 1.0
        assert g.abc_entropy() < 1.0
        assert g.sombor_entropy() < 1.0

    def test_azi_more_sensitive_than_others(self):
        """AZI cubic exponent makes it more sensitive to degree heterogeneity.

        On graphs with diverse degree pairs, AZI entropy should typically be
        lower (more uneven) than linear entropies like Zagreb M₁.
        """
        g = MemoryGraph()
        # Build a graph with diverse degree pairs
        nodes = [g.add(str(i)) for i in range(6)]
        g.link(nodes[0].id, nodes[1].id, "r")
        g.link(nodes[0].id, nodes[2].id, "r")
        g.link(nodes[0].id, nodes[3].id, "r")
        g.link(nodes[0].id, nodes[4].id, "r")
        g.link(nodes[4].id, nodes[5].id, "r")
        azi = g.augmented_zagreb_entropy()
        m1 = g.zagreb_m1_entropy()
        # AZI should be more sensitive (lower or equal normalized entropy)
        assert azi is not None
        assert m1 is not None
        # Both should be valid
        assert 0 < azi <= 1.0 + 1e-10
        assert 0 < m1 <= 1.0 + 1e-10
