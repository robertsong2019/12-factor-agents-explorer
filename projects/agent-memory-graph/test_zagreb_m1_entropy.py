"""Tests for zagreb_m1_entropy() — Shannon entropy of Zagreb M₁ edge contributions.

For each edge e=(u,v), Zagreb M₁ contribution = d_u + d_v.
H_M1 = -Σ p_e · ln(p_e) where p_e = z_e / M₁_edges.

Cycle 279.
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


@pytest.fixture
def mg():
    return MemoryGraph()


# ─── Edge Cases ────────────────────────────────────────────────────────

class TestZagrebM1EntropyBasics:
    def test_empty_graph_none(self, mg):
        assert mg.zagreb_m1_entropy() is None

    def test_single_node_none(self, mg):
        mg.add("a")
        assert mg.zagreb_m1_entropy() is None

    def test_no_edges_none(self, mg):
        mg.add("a"); mg.add("b")
        assert mg.zagreb_m1_entropy() is None

    def test_non_mutating(self, mg):
        build_path(mg, 3)
        before = mg.edge_count()
        mg.zagreb_m1_entropy()
        assert mg.edge_count() == before


# ─── Regular Graphs → normalized = 1.0 ─────────────────────────────────

class TestZagrebM1EntropyRegular:
    def test_k3_normalized_one(self, mg):
        build_complete(mg, 3)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_k4_normalized_one(self, mg):
        build_complete(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_k5_normalized_one(self, mg):
        build_complete(mg, 5)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_c5_normalized_one(self, mg):
        build_cycle(mg, 5)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_c6_normalized_one(self, mg):
        build_cycle(mg, 6)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)


# ─── Star Graphs → normalized = 1.0 ────────────────────────────────────

class TestZagrebM1EntropyStar:
    def test_k13_normalized_one(self, mg):
        build_star(mg, 3)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_k15_normalized_one(self, mg):
        build_star(mg, 5)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)


# ─── Path Graphs → normalized < 1.0 ────────────────────────────────────

class TestZagrebM1EntropyPath:
    def test_p3_normalized_one(self, mg):
        """P₃: edges (1,2),(2,1) → sums 3,3 → equal → 1.0."""
        build_path(mg, 3)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_p4_normalized_below_one(self, mg):
        build_path(mg, 4)
        val = mg.zagreb_m1_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_p5_normalized_below_one(self, mg):
        build_path(mg, 5)
        val = mg.zagreb_m1_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_p6_normalized_below_one(self, mg):
        build_path(mg, 6)
        val = mg.zagreb_m1_entropy(normalized=True)
        assert val is not None and val < 1.0

    def test_path_entropy_increases_with_n(self, mg):
        from memory_graph import MemoryGraph as MG
        g3 = MG(); build_path(g3, 3)
        g5 = MG(); build_path(g5, 5)
        e3 = g3.zagreb_m1_entropy(normalized=False)
        e5 = g5.zagreb_m1_entropy(normalized=False)
        assert e5 > e3


# ─── Raw Entropy Values ────────────────────────────────────────────────

class TestZagrebM1EntropyRaw:
    def test_k3_raw_ln3(self, mg):
        build_complete(mg, 3)
        assert mg.zagreb_m1_entropy(normalized=False) == pytest.approx(math.log(3))

    def test_c4_raw_ln4(self, mg):
        build_cycle(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=False) == pytest.approx(math.log(4))

    def test_k4_raw_ln6(self, mg):
        build_complete(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=False) == pytest.approx(math.log(6))

    def test_k14_raw_ln4(self, mg):
        build_star(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=False) == pytest.approx(math.log(4))


# ─── Disconnected Components ───────────────────────────────────────────

class TestZagrebM1EntropyDisconnected:
    def test_two_triangles_normalized_one(self, mg):
        build_complete(mg, 3)
        build_complete(mg, 3)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)

    def test_two_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        build_cycle(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)


# ─── Dynamics ──────────────────────────────────────────────────────────

class TestZagrebM1EntropyDynamics:
    def test_edge_addition_changes_entropy(self, mg):
        nodes = build_path(mg, 4)
        before = mg.zagreb_m1_entropy(normalized=True)
        mg.link(nodes[0].id, nodes[3].id, "r")
        after = mg.zagreb_m1_entropy(normalized=True)
        assert before != after

    def test_bounded_0_1(self, mg):
        build_complete(mg, 3)
        assert 0.0 < mg.zagreb_m1_entropy(normalized=True) <= 1.0 + 1e-12

        mg2 = MemoryGraph(); build_cycle(mg2, 4)
        assert 0.0 < mg2.zagreb_m1_entropy(normalized=True) <= 1.0 + 1e-12

        mg3 = MemoryGraph(); build_path(mg3, 5)
        assert 0.0 < mg3.zagreb_m1_entropy(normalized=True) <= 1.0 + 1e-12

        mg4 = MemoryGraph(); build_star(mg4, 5)
        assert 0.0 < mg4.zagreb_m1_entropy(normalized=True) <= 1.0 + 1e-12

        mg5 = MemoryGraph(); build_complete(mg5, 5)
        assert 0.0 < mg5.zagreb_m1_entropy(normalized=True) <= 1.0 + 1e-12


# ─── Cross-check with other entropies ──────────────────────────────────

class TestZagrebM1EntropyCrossCheck:
    def test_regular_all_three_one(self, mg):
        """All degree-based entropies = 1.0 for regular graphs."""
        build_complete(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.randic_entropy(normalized=True) == pytest.approx(1.0)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0)

    def test_path_all_below_one(self, mg):
        build_path(mg, 4)
        assert mg.zagreb_m1_entropy(normalized=True) < 1.0
        assert mg.randic_entropy(normalized=True) < 1.0
        assert mg.sombor_entropy(normalized=True) < 1.0

    def test_m1_sombor_different_raw_paw(self, mg):
        nodes = build_complete(mg, 3)
        p = mg.add("p")
        mg.link(nodes[0].id, p.id, "r")
        m1 = mg.zagreb_m1_entropy(normalized=False)
        so = mg.sombor_entropy(normalized=False)
        assert m1 != pytest.approx(so, abs=0.001)

    def test_m1_randic_different_raw_paw(self, mg):
        nodes = build_complete(mg, 3)
        p = mg.add("p")
        mg.link(nodes[0].id, p.id, "r")
        m1 = mg.zagreb_m1_entropy(normalized=False)
        r = mg.randic_entropy(normalized=False)
        assert m1 != pytest.approx(r, abs=0.001)
