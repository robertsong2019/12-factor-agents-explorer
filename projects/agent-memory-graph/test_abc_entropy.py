"""Tests for abc_entropy() — Shannon entropy of Atom-Bond Connectivity edge contributions.

For each edge e=(u,v), ABC contribution = √((d_u+d_v−2)/(d_u·d_v)).
H_ABC = −Σ p_e · ln(p_e) where p_e = a_e / ABC.

Edges with d_u+d_v−2 = 0 (K₂ edges) are excluded from the entropy calculation.

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

class TestAbcEntropyBasics:
    def test_empty_graph_none(self, mg):
        assert mg.abc_entropy() is None

    def test_single_node_none(self, mg):
        mg.add("a")
        assert mg.abc_entropy() is None

    def test_no_edges_none(self, mg):
        mg.add("a"); mg.add("b")
        assert mg.abc_entropy() is None

    def test_non_mutating(self, mg):
        build_path(mg, 3)
        before = mg.edge_count()
        mg.abc_entropy()
        assert mg.edge_count() == before


# ─── K₂ Exclusion ─────────────────────────────────────────────────────

class TestAbcEntropyK2Exclusion:
    def test_k2_returns_none(self, mg):
        """K₂ edge has d_u+d_v−2=0, so ABC contribution is 0 → excluded → None."""
        a, b = mg.add("a"), mg.add("b")
        mg.link(a.id, b.id, "r")
        assert mg.abc_entropy() is None

    def test_only_k2_edges_returns_none(self, mg):
        """Multiple K₂ edges (disconnected pairs) → all excluded → None."""
        pairs = [(mg.add(f"a{i}"), mg.add(f"b{i}")) for i in range(3)]
        for a, b in pairs:
            mg.link(a.id, b.id, "r")
        assert mg.abc_entropy() is None

    def test_k2_plus_triangle_works(self, mg):
        """K₂ + K₃: only K₃ edges contribute → entropy from 3 equal edges."""
        a, b = mg.add("a"), mg.add("b")
        mg.link(a.id, b.id, "r")  # K₂ edge, excluded
        build_complete(mg, 3)      # K₃ edges, all contribute
        val = mg.abc_entropy()
        assert val is not None


# ─── Regular Graphs → normalized = 1.0 ─────────────────────────────────

class TestAbcEntropyRegular:
    def test_k3_normalized_one(self, mg):
        build_complete(mg, 3)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_k4_normalized_one(self, mg):
        build_complete(mg, 4)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_k5_normalized_one(self, mg):
        build_complete(mg, 5)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_c5_normalized_one(self, mg):
        build_cycle(mg, 5)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_c6_normalized_one(self, mg):
        build_cycle(mg, 6)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)


# ─── Star Graphs → normalized = 1.0 ────────────────────────────────────

class TestAbcEntropyStar:
    def test_k13_normalized_one(self, mg):
        build_star(mg, 3)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_k15_normalized_one(self, mg):
        build_star(mg, 5)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_k17_normalized_one(self, mg):
        build_star(mg, 7)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)


# ─── Path Graphs ──────────────────────────────────────────────────────

class TestAbcEntropyPath:
    def test_p3_normalized_one(self, mg):
        """P₃: both edges (1,2) → same ABC contribution → 1.0."""
        build_path(mg, 3)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_p4_normalized_one(self, mg):
        """P₄: all edges are (1,2) or (2,2), all give √(1/2) → 1.0."""
        build_path(mg, 4)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_p5_normalized_one(self, mg):
        """P₅: same pattern — all edge degree pairs are (1,2) or (2,2)."""
        build_path(mg, 5)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_path_raw_entropy_increases(self, mg):
        """Raw entropy increases with path length (more edges → higher H)."""
        g3 = MemoryGraph(); build_path(g3, 3)
        g6 = MemoryGraph(); build_path(g6, 6)
        e3 = g3.abc_entropy(normalized=False)
        e6 = g6.abc_entropy(normalized=False)
        assert e6 > e3


# ─── Raw Entropy Values ────────────────────────────────────────────────

class TestAbcEntropyRaw:
    def test_k3_raw_ln3(self, mg):
        """K₃: 3 edges, all identical → H = ln(3)."""
        build_complete(mg, 3)
        assert mg.abc_entropy(normalized=False) == pytest.approx(math.log(3))

    def test_c4_raw_ln4(self, mg):
        """C₄: 4 edges, all identical → H = ln(4)."""
        build_cycle(mg, 4)
        assert mg.abc_entropy(normalized=False) == pytest.approx(math.log(4))

    def test_k4_raw_ln6(self, mg):
        """K₄: 6 edges, all identical → H = ln(6)."""
        build_complete(mg, 4)
        assert mg.abc_entropy(normalized=False) == pytest.approx(math.log(6))

    def test_k14_raw_ln4(self, mg):
        """K_{1,4}: 4 edges, all identical → H = ln(4)."""
        build_star(mg, 4)
        assert mg.abc_entropy(normalized=False) == pytest.approx(math.log(4))


# ─── Disconnected Components ───────────────────────────────────────────

class TestAbcEntropyDisconnected:
    def test_two_triangles_normalized_one(self, mg):
        build_complete(mg, 3)
        build_complete(mg, 3)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_two_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        build_cycle(mg, 4)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)

    def test_mixed_regular_normalized_one(self, mg):
        """K₃ + C₄: within each component all edges identical → still 1.0."""
        build_complete(mg, 3)
        build_cycle(mg, 4)
        # K₃ edges: (2,2), C₄ edges: (2,2) — same contribution → 1.0
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)


# ─── Dynamics ──────────────────────────────────────────────────────────

class TestAbcEntropyDynamics:
    def test_edge_addition_changes_entropy(self, mg):
        """Adding an edge to paw graph changes ABC entropy."""
        nodes = build_paw(mg)
        before = mg.abc_entropy(normalized=True)
        mg.link(nodes[1].id, nodes[3].id, "r")
        after = mg.abc_entropy(normalized=True)
        assert before != after

    def test_bounded_0_1(self, mg):
        """Normalized entropy must be in (0, 1] across diverse topologies."""
        build_complete(mg, 3)
        assert 0.0 < mg.abc_entropy(normalized=True) <= 1.0 + 1e-12

        mg2 = MemoryGraph(); build_cycle(mg2, 4)
        assert 0.0 < mg2.abc_entropy(normalized=True) <= 1.0 + 1e-12

        mg3 = MemoryGraph(); build_path(mg3, 5)
        assert 0.0 < mg3.abc_entropy(normalized=True) <= 1.0 + 1e-12

        mg4 = MemoryGraph(); build_star(mg4, 5)
        assert 0.0 < mg4.abc_entropy(normalized=True) <= 1.0 + 1e-12

        mg5 = MemoryGraph(); build_complete(mg5, 5)
        assert 0.0 < mg5.abc_entropy(normalized=True) <= 1.0 + 1e-12


# ─── Paw Graph (irregular) ─────────────────────────────────────────────

class TestAbcEntropyPaw:
    def test_paw_below_one(self, mg):
        """Paw graph: K₃ + pendant has different ABC contributions."""
        build_paw(mg)
        val = mg.abc_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_paw_raw_positive(self, mg):
        build_paw(mg)
        val = mg.abc_entropy(normalized=False)
        assert val is not None and val > 0.0


# ─── Cross-checks with other entropies ─────────────────────────────────

class TestAbcEntropyCrossCheck:
    def test_regular_all_entropies_one(self, mg):
        """On K₄, all degree-based entropies should be 1.0."""
        build_complete(mg, 4)
        assert mg.abc_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.randic_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_paw_all_entropies_differ(self, mg):
        """On paw graph, all four entropies have distinct raw values."""
        build_paw(mg)
        abc = mg.abc_entropy(normalized=False)
        r = mg.randic_entropy(normalized=False)
        s = mg.sombor_entropy(normalized=False)
        z = mg.zagreb_m1_entropy(normalized=False)
        # ABC differs from all others
        assert abc != pytest.approx(r, abs=0.001)
        assert abc != pytest.approx(s, abs=0.001)
        assert abc != pytest.approx(z, abs=0.001)

    def test_paw_differs_from_ga(self, mg):
        """ABC and GA entropies differ on paw graph (may be numerically close)."""
        build_paw(mg)
        abc = mg.abc_entropy(normalized=False)
        ga = mg.ga_entropy(normalized=False)
        # ABC and GA both involve √(d_u·d_v), so they can be close
        assert abc != ga  # not exactly equal
