"""Tests for sombor_entropy() and reduced_sombor_entropy().

Shannon entropy of normalized Sombor / Reduced Sombor edge contributions.
Cycle 278.
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


# ─── Sombor Entropy — Basic ────────────────────────────────────────────

class TestSomborEntropyBasics:
    def test_empty_graph_none(self, mg):
        assert mg.sombor_entropy() is None

    def test_single_node_none(self, mg):
        mg.add("a")
        assert mg.sombor_entropy() is None

    def test_no_edges_none(self, mg):
        mg.add("a")
        mg.add("b")
        assert mg.sombor_entropy() is None

    def test_non_mutating(self, mg):
        build_path(mg, 5)
        snap = mg.snapshot()
        mg.sombor_entropy()
        assert mg.snapshot() == snap


# ─── Sombor Entropy — Regular Graphs (entropy = 1.0 normalized) ────────

class TestSomborEntropyRegular:
    def test_k2_normalized(self, mg):
        """K₂: single edge, p=1.0, entropy=0 (only one term)."""
        a = mg.add("a")
        b = mg.add("b")
        mg.link(a.id, b.id, "r")
        result = mg.sombor_entropy(normalized=True)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-12)

    def test_k3_normalized_one(self, mg):
        """K₃: 3 edges all (√(4+4)=2√2), uniform → H = ln(3)/ln(3) = 1."""
        build_complete(mg, 3)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_k4_normalized_one(self, mg):
        build_complete(mg, 4)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_k5_normalized_one(self, mg):
        build_complete(mg, 5)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_c3_normalized_one(self, mg):
        build_cycle(mg, 3)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_c5_normalized_one(self, mg):
        build_cycle(mg, 5)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_c6_normalized_one(self, mg):
        build_cycle(mg, 6)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_star_k3_normalized_one(self, mg):
        """K_{1,3}: 3 edges all (1,3) → uniform → normalized = 1."""
        build_star(mg, 3)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_star_k5_normalized_one(self, mg):
        build_star(mg, 5)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)


# ─── Sombor Entropy — Raw (unnormalized) values ────────────────────────

class TestSomborEntropyRaw:
    def test_k3_raw_ln3(self, mg):
        build_complete(mg, 3)
        assert mg.sombor_entropy(normalized=False) == pytest.approx(math.log(3), abs=1e-12)

    def test_c4_raw_ln4(self, mg):
        build_cycle(mg, 4)
        assert mg.sombor_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-12)

    def test_k4_raw_ln6(self, mg):
        build_complete(mg, 4)
        assert mg.sombor_entropy(normalized=False) == pytest.approx(math.log(6), abs=1e-12)

    def test_star_k4_raw_ln4(self, mg):
        build_star(mg, 4)
        assert mg.sombor_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-12)


# ─── Sombor Entropy — Non-regular graphs ───────────────────────────────

class TestSomborEntropyNonRegular:
    def test_p3_normalized_one(self, mg):
        """P₃: 2 edges both degree pair (1,2) → equal contributions → 1."""
        build_path(mg, 3)
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_p4_less_than_one(self, mg):
        """P₄: 3 edges — √5, 2√2, √5 → middle different → < 1."""
        build_path(mg, 4)
        result = mg.sombor_entropy(normalized=True)
        assert result is not None
        assert 0 < result < 1.0

    def test_p5_less_than_one(self, mg):
        build_path(mg, 5)
        result = mg.sombor_entropy(normalized=True)
        assert result is not None
        assert 0 < result < 1.0

    def test_p6_less_than_one(self, mg):
        build_path(mg, 6)
        result = mg.sombor_entropy(normalized=True)
        assert result is not None
        assert 0 < result < 1.0

    def test_path_raw_increases_with_n(self, mg):
        """Longer paths → more edges → higher raw entropy."""
        entropies = []
        for n in [4, 6, 8, 10]:
            g = MemoryGraph()
            build_path(g, n)
            entropies.append(g.sombor_entropy(normalized=False))
        assert entropies[0] < entropies[-1]

    def test_disconnected_regular_components(self, mg):
        """Two separate K₃ triangles: all edges (2,2) → normalized = 1."""
        nodes = [mg.add(f"n{i}") for i in range(6)]
        # Triangle 1
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[0].id, nodes[2].id, "r")
        # Triangle 2
        mg.link(nodes[3].id, nodes[4].id, "r")
        mg.link(nodes[4].id, nodes[5].id, "r")
        mg.link(nodes[3].id, nodes[5].id, "r")
        assert mg.sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)


# ─── Sombor Entropy — Edge addition effect ─────────────────────────────

class TestSomborEntropyEdgeAddition:
    def test_adding_edge_changes_entropy(self, mg):
        nodes = build_path(mg, 4)
        before = mg.sombor_entropy(normalized=False)
        extra = mg.add("extra")
        mg.link(extra.id, nodes[0].id, "r")
        after = mg.sombor_entropy(normalized=False)
        assert before != after

    def test_entropy_bounded(self, mg):
        """Normalized entropy always in [0, 1]."""
        for n in [4, 6, 8]:
            g = MemoryGraph()
            build_path(g, n)
            e = g.sombor_entropy(normalized=True)
            assert e is not None and 0 <= e <= 1.0 + 1e-12
        for k in [3, 4, 5]:
            g = MemoryGraph()
            build_star(g, k)
            e = g.sombor_entropy(normalized=True)
            assert e is not None and 0 <= e <= 1.0 + 1e-12
        for n in [3, 4, 5]:
            g = MemoryGraph()
            build_complete(g, n)
            e = g.sombor_entropy(normalized=True)
            assert e is not None and 0 <= e <= 1.0 + 1e-12
        for n in [4, 5, 6]:
            g = MemoryGraph()
            build_cycle(g, n)
            e = g.sombor_entropy(normalized=True)
            assert e is not None and 0 <= e <= 1.0 + 1e-12


# ─── Reduced Sombor Entropy — Basic ───────────────────────────────────

class TestReducedSomborEntropyBasics:
    def test_empty_graph_none(self, mg):
        assert mg.reduced_sombor_entropy() is None

    def test_single_node_none(self, mg):
        mg.add("a")
        assert mg.reduced_sombor_entropy() is None

    def test_no_edges_none(self, mg):
        mg.add("a")
        mg.add("b")
        assert mg.reduced_sombor_entropy() is None

    def test_non_mutating(self, mg):
        build_path(mg, 5)
        snap = mg.snapshot()
        mg.reduced_sombor_entropy()
        assert mg.snapshot() == snap


# ─── Reduced Sombor Entropy — Special cases ───────────────────────────

class TestReducedSomborEntropySpecial:
    def test_k2_zero(self, mg):
        """K₂: RS = 0, entropy defined as 0.0 by convention."""
        a = mg.add("a")
        b = mg.add("b")
        mg.link(a.id, b.id, "r")
        assert mg.reduced_sombor_entropy() == 0.0

    def test_two_k2_edges_zero(self, mg):
        """Two disconnected K₂ edges: each contributes 0 → RS = 0 → entropy 0."""
        nodes = [mg.add(f"n{i}") for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[2].id, nodes[3].id, "r")
        assert mg.reduced_sombor_entropy() == 0.0


# ─── Reduced Sombor Entropy — Regular graphs ──────────────────────────

class TestReducedSomborEntropyRegular:
    def test_k3_normalized_one(self, mg):
        build_complete(mg, 3)
        assert mg.reduced_sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_k4_normalized_one(self, mg):
        build_complete(mg, 4)
        assert mg.reduced_sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_c4_normalized_one(self, mg):
        build_cycle(mg, 4)
        assert mg.reduced_sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_c5_normalized_one(self, mg):
        build_cycle(mg, 5)
        assert mg.reduced_sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_star_k4_normalized_one(self, mg):
        build_star(mg, 4)
        assert mg.reduced_sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)

    def test_k3_raw_ln3(self, mg):
        build_complete(mg, 3)
        assert mg.reduced_sombor_entropy(normalized=False) == pytest.approx(math.log(3), abs=1e-12)

    def test_c4_raw_ln4(self, mg):
        build_cycle(mg, 4)
        assert mg.reduced_sombor_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-12)


# ─── Reduced Sombor Entropy — Non-regular ─────────────────────────────

class TestReducedSomborEntropyNonRegular:
    def test_p4_less_than_one(self, mg):
        """P₄: rs contributions differ → < 1."""
        build_path(mg, 4)
        result = mg.reduced_sombor_entropy(normalized=True)
        assert result is not None
        assert 0 < result < 1.0

    def test_p5_less_than_one(self, mg):
        build_path(mg, 5)
        result = mg.reduced_sombor_entropy(normalized=True)
        assert result is not None
        assert 0 < result < 1.0

    def test_disconnected_regular_components(self, mg):
        """Two K₃ triangles: all rs_e equal → normalized = 1."""
        nodes = [mg.add(f"n{i}") for i in range(6)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[0].id, nodes[2].id, "r")
        mg.link(nodes[3].id, nodes[4].id, "r")
        mg.link(nodes[4].id, nodes[5].id, "r")
        mg.link(nodes[3].id, nodes[5].id, "r")
        assert mg.reduced_sombor_entropy(normalized=True) == pytest.approx(1.0, abs=1e-12)


# ─── Cross-relationship: Sombor vs Reduced Sombor entropy ─────────────

class TestSomborEntropyRelationships:
    def test_both_entropies_bounded(self, mg):
        """Both entropies in [0, 1] for various graphs."""
        builders = [
            (lambda g: build_complete(g, 3),),
            (lambda g: build_complete(g, 4),),
            (lambda g: build_complete(g, 5),),
            (lambda g: build_cycle(g, 4),),
            (lambda g: build_cycle(g, 5),),
            (lambda g: build_cycle(g, 6),),
            (lambda g: build_path(g, 4),),
            (lambda g: build_path(g, 5),),
            (lambda g: build_path(g, 6),),
            (lambda g: build_star(g, 3),),
            (lambda g: build_star(g, 4),),
            (lambda g: build_star(g, 5),),
        ]
        for (builder,) in builders:
            g = MemoryGraph()
            builder(g)
            se = g.sombor_entropy(normalized=True)
            rse = g.reduced_sombor_entropy(normalized=True)
            assert se is not None and 0 <= se <= 1.0 + 1e-12
            assert rse is not None and 0 <= rse <= 1.0 + 1e-12

    def test_regular_entropy_equal_raw(self, mg):
        """For regular graphs, raw entropy = ln(m) for both."""
        build_complete(mg, 4)  # m=6
        expected = math.log(6)
        assert mg.sombor_entropy(normalized=False) == pytest.approx(expected, abs=1e-12)
        assert mg.reduced_sombor_entropy(normalized=False) == pytest.approx(expected, abs=1e-12)

    def test_path_p4_raw_both_below_ln3(self, mg):
        """P₄: both entropies < ln(3) since not uniform."""
        build_path(mg, 4)
        assert mg.sombor_entropy(normalized=False) < math.log(3)
        assert mg.reduced_sombor_entropy(normalized=False) < math.log(3)

    def test_adding_edge_changes_entropy(self, mg):
        nodes = build_path(mg, 3)
        before = mg.sombor_entropy(normalized=False)
        extra = mg.add("x")
        mg.link(extra.id, nodes[1].id, "r")
        after = mg.sombor_entropy(normalized=False)
        assert before != after
