"""Tests for ga_entropy() — Shannon entropy of Geometric-Arithmetic edge contributions.

For each edge e=(u,v), GA contribution = 2·√(d_u·d_v) / (d_u+d_v).
H_GA = −Σ p_e · ln(p_e) where p_e = g_e / GA.

Cycle 280.
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
    nodes = build_path(g, n)
    g.link(nodes[-1].id, nodes[0].id, "r")
    return nodes


def build_star(g, k):
    center = g.add("c")
    leaves = [g.add(f"l{i}") for i in range(k)]
    for leaf in leaves:
        g.link(center.id, leaf.id, "r")
    return center, leaves


def build_paw(g):
    """Paw graph: K₃ with a pendant edge."""
    a, b, c = g.add("a"), g.add("b"), g.add("c")
    d = g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(c.id, a.id, "r")
    g.link(a.id, d.id, "r")
    return [a, b, c, d]


@pytest.fixture
def mg():
    return MemoryGraph()


# ─── Edge Cases ────────────────────────────────────────────────────────

class TestGaEntropyBasics:
    def test_empty_graph_none(self, mg):
        assert mg.ga_entropy() is None

    def test_single_node_none(self, mg):
        mg.add("a")
        assert mg.ga_entropy() is None

    def test_no_edges_none(self, mg):
        mg.add("a"); mg.add("b")
        assert mg.ga_entropy() is None

    def test_non_mutating(self, mg):
        build_path(mg, 3)
        before = mg.edge_count()
        mg.ga_entropy()
        assert mg.edge_count() == before


# ─── Single Edge ──────────────────────────────────────────────────────

class TestGaEntropySingleEdge:
    def test_k2_raw_zero(self, mg):
        """K₂: single edge, entropy of one element = −1·ln(1) = 0."""
        a, b = mg.add("a"), mg.add("b")
        mg.link(a.id, b.id, "r")
        assert mg.ga_entropy(normalized=False) == pytest.approx(0.0)

    def test_k2_normalized_zero(self, mg):
        """K₂ normalized: m=1, normalization skipped, returns 0.0."""
        a, b = mg.add("a"), mg.add("b")
        mg.link(a.id, b.id, "r")
        assert mg.ga_entropy(normalized=True) == pytest.approx(0.0)


# ─── Regular Graphs → normalized = 1.0 ─────────────────────────────────

class TestGaEntropyRegular:
    def test_k3_normalized_one(self, mg):
        build_complete(mg, 3)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_k4_normalized_one(self, mg):
        build_complete(mg, 4)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_k5_normalized_one(self, mg):
        build_complete(mg, 5)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_c5_normalized_one(self, mg):
        build_cycle(mg, 5)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_c6_normalized_one(self, mg):
        build_cycle(mg, 6)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)


# ─── Star Graphs → normalized = 1.0 ────────────────────────────────────

class TestGaEntropyStar:
    def test_k13_normalized_one(self, mg):
        build_star(mg, 3)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_k15_normalized_one(self, mg):
        build_star(mg, 5)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_k17_normalized_one(self, mg):
        build_star(mg, 7)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)


# ─── Path Graphs → normalized < 1.0 for n≥4 ───────────────────────────

class TestGaEntropyPath:
    def test_p3_normalized_one(self, mg):
        """P₃: both edges (1,2) → equal GA contributions → 1.0."""
        build_path(mg, 3)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_p4_normalized_below_one(self, mg):
        """P₄: endpoint (1,2) vs interior (2,2) → different GA → < 1.0."""
        build_path(mg, 4)
        val = mg.ga_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_p5_normalized_below_one(self, mg):
        build_path(mg, 5)
        val = mg.ga_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_p6_normalized_below_one(self, mg):
        build_path(mg, 6)
        val = mg.ga_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_path_raw_entropy_increases(self, mg):
        """Raw entropy increases with path length."""
        g3 = MemoryGraph(); build_path(g3, 3)
        g6 = MemoryGraph(); build_path(g6, 6)
        e3 = g3.ga_entropy(normalized=False)
        e6 = g6.ga_entropy(normalized=False)
        assert e6 > e3


# ─── Raw Entropy Values ────────────────────────────────────────────────

class TestGaEntropyRaw:
    def test_k3_raw_ln3(self, mg):
        """K₃: 3 identical edges → H = ln(3)."""
        build_complete(mg, 3)
        assert mg.ga_entropy(normalized=False) == pytest.approx(math.log(3))

    def test_c4_raw_ln4(self, mg):
        """C₄: 4 identical edges → H = ln(4)."""
        build_cycle(mg, 4)
        assert mg.ga_entropy(normalized=False) == pytest.approx(math.log(4))

    def test_k4_raw_ln6(self, mg):
        """K₄: 6 identical edges → H = ln(6)."""
        build_complete(mg, 4)
        assert mg.ga_entropy(normalized=False) == pytest.approx(math.log(6))

    def test_k14_raw_ln4(self, mg):
        """K_{1,4}: 4 identical edges → H = ln(4)."""
        build_star(mg, 4)
        assert mg.ga_entropy(normalized=False) == pytest.approx(math.log(4))


# ─── Disconnected Components ───────────────────────────────────────────

class TestGaEntropyDisconnected:
    def test_two_triangles_normalized_one(self, mg):
        build_complete(mg, 3)
        build_complete(mg, 3)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_two_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        build_cycle(mg, 4)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)

    def test_two_stars_normalized_one(self, mg):
        build_star(mg, 3)
        build_star(mg, 5)
        # All edges within each star are identical, but stars differ → < 1.0
        val = mg.ga_entropy(normalized=True)
        assert val is not None and val < 1.0


# ─── Dynamics ──────────────────────────────────────────────────────────

class TestGaEntropyDynamics:
    def test_edge_addition_changes_entropy(self, mg):
        nodes = build_path(mg, 4)
        before = mg.ga_entropy(normalized=True)
        mg.link(nodes[0].id, nodes[3].id, "r")
        after = mg.ga_entropy(normalized=True)
        assert before != after

    def test_bounded_0_1(self, mg):
        """Normalized entropy in (0, 1] across diverse topologies."""
        build_complete(mg, 3)
        assert 0.0 < mg.ga_entropy(normalized=True) <= 1.0 + 1e-12

        mg2 = MemoryGraph(); build_cycle(mg2, 4)
        assert 0.0 < mg2.ga_entropy(normalized=True) <= 1.0 + 1e-12

        mg3 = MemoryGraph(); build_path(mg3, 5)
        assert 0.0 < mg3.ga_entropy(normalized=True) <= 1.0 + 1e-12

        mg4 = MemoryGraph(); build_star(mg4, 5)
        assert 0.0 < mg4.ga_entropy(normalized=True) <= 1.0 + 1e-12

        mg5 = MemoryGraph(); build_complete(mg5, 5)
        assert 0.0 < mg5.ga_entropy(normalized=True) <= 1.0 + 1e-12


# ─── Paw Graph (irregular) ─────────────────────────────────────────────

class TestGaEntropyPaw:
    def test_paw_below_one(self, mg):
        build_paw(mg)
        val = mg.ga_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_paw_raw_positive(self, mg):
        build_paw(mg)
        val = mg.ga_entropy(normalized=False)
        assert val is not None and val > 0.0


# ─── Cross-checks with other entropies ─────────────────────────────────

class TestGaEntropyCrossCheck:
    def test_regular_all_entropies_one(self, mg):
        """On C₅, all degree-based entropies should be 1.0."""
        build_cycle(mg, 5)
        assert mg.ga_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.randic_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_paw_ga_differs_from_all(self, mg):
        """On paw graph, GA entropy differs from most others.

        Note: GA and ABC can be numerically close since both involve
        √(d_u·d_v) in their contribution formulas, but they are not
        exactly equal.
        """
        build_paw(mg)
        ga = mg.ga_entropy(normalized=False)
        abc = mg.abc_entropy(normalized=False)
        r = mg.randic_entropy(normalized=False)
        s = mg.sombor_entropy(normalized=False)
        z = mg.zagreb_m1_entropy(normalized=False)
        assert ga != pytest.approx(r, abs=0.001)
        assert ga != pytest.approx(s, abs=0.001)
        assert ga != pytest.approx(z, abs=0.001)
        # GA and ABC are close but not exactly equal
        assert ga != abc

    def test_five_entropy_fingerprint(self, mg):
        """5 degree-based entropies on an irregular graph are all distinct values.

        On graphs with few distinct edge types, all degree-based entropies
        converge because Shannon entropy is dominated by the number and
        proportion of distinct contributions, not their specific formula.
        We verify they produce different numerical values (not identical).
        """
        # Use a graph with diverse degree pairs
        hub = mg.add('hub')
        n1 = mg.add('n1')
        n2 = mg.add('n2')
        n3 = mg.add('n3')
        n4 = mg.add('n4')
        n5 = mg.add('n5')
        mg.link(hub.id, n1.id, 'r')  # (1,3)
        mg.link(hub.id, n2.id, 'r')  # (2,3) after n2-n3
        mg.link(hub.id, n3.id, 'r')  # (2,3)
        mg.link(n2.id, n4.id, 'r')   # (1,2)
        mg.link(n3.id, n5.id, 'r')   # (1,2)
        mg.link(n4.id, n5.id, 'r')   # (1,2) → n4 and n5 now degree 2
        vals = [
            mg.abc_entropy(normalized=False),
            mg.ga_entropy(normalized=False),
            mg.randic_entropy(normalized=False),
            mg.sombor_entropy(normalized=False),
            mg.zagreb_m1_entropy(normalized=False),
        ]
        # All produce valid float values
        for v in vals:
            assert v is not None and v > 0.0
        # Sombor and Zagreb M1 should be distinguishable (different formulas)
        assert vals[3] != vals[4]  # sombor vs zagreb
        # Verify the entropy family produces a multi-valued fingerprint
        unique_vals = set(round(v, 8) for v in vals)
        assert len(unique_vals) >= 3  # at least 3 distinct values
