"""Tests for eigenvector_centrality_entropy() — Shannon entropy of eigenvector centrality.

Second centrality-based entropy (after edge_betweenness_entropy).
Measures how evenly "influence" is distributed across nodes.

Cycle 283.
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
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return a, b, c, d


def build_binary_tree(g, depth=3):
    """Complete binary tree of given depth (2^depth - 1 nodes)."""
    n_nodes = 2**depth - 1
    nodes = [g.add(str(i)) for i in range(n_nodes)]
    for i in range(n_nodes):
        left = 2 * i + 1
        right = 2 * i + 2
        if left < n_nodes:
            g.link(nodes[i].id, nodes[left].id, "r")
        if right < n_nodes:
            g.link(nodes[i].id, nodes[right].id, "r")
    return nodes


# ─── Empty / degenerate cases ──────────────────────────────────────────

class TestEigenvectorEntropyDegenerate:
    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.eigenvector_centrality_entropy() is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("a")
        assert g.eigenvector_centrality_entropy() is None


# ─── Regular graphs: entropy = 1.0 ────────────────────────────────────

class TestEigenvectorEntropyRegular:
    def test_k3_normalized_one(self):
        """K₃: all centralities equal → entropy = 1.0."""
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)

    def test_k4_normalized_one(self):
        """K₄: symmetric → all equal → entropy = 1.0."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)

    def test_k5_normalized_one(self):
        g = MemoryGraph()
        build_complete(g, 5)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)

    def test_c3_normalized_one(self):
        """C₃ = K₃: symmetric → entropy = 1.0."""
        g = MemoryGraph()
        build_cycle(g, 3)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)

    def test_c4_normalized_one(self):
        """C₄: all nodes equivalent → entropy = 1.0."""
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)

    def test_c5_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 5)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)

    def test_c6_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 6)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)


# ─── Irregular graphs: entropy < 1.0 ──────────────────────────────────

class TestEigenvectorEntropyIrregular:
    def test_paw_less_than_one(self):
        """Paw graph: nodes have different centralities → entropy < 1.0."""
        g = MemoryGraph()
        build_paw(g)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_paw_positive(self):
        g = MemoryGraph()
        build_paw(g)
        assert g.eigenvector_centrality_entropy() > 0

    def test_star_less_than_one(self):
        """Star K_{1,3}: centre dominates → entropy < 1.0."""
        g = MemoryGraph()
        build_star(g, 3)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_star_k5_less_than_one(self):
        g = MemoryGraph()
        build_star(g, 5)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_binary_tree_less_than_one(self):
        """Binary tree: root has higher centrality → entropy < 1.0."""
        g = MemoryGraph()
        build_binary_tree(g, depth=3)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_binary_tree_positive(self):
        g = MemoryGraph()
        build_binary_tree(g, depth=3)
        assert g.eigenvector_centrality_entropy() > 0


# ─── Path graphs ──────────────────────────────────────────────────────

class TestEigenvectorEntropyPath:
    def test_p4_less_than_one(self):
        """P₄: endpoints have lower centrality → entropy < 1.0."""
        g = MemoryGraph()
        build_path(g, 4)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_p5_less_than_one(self):
        g = MemoryGraph()
        build_path(g, 5)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_p6_less_than_one(self):
        g = MemoryGraph()
        build_path(g, 6)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert val < 1.0

    def test_path_entropy_decreases_with_length(self):
        """Longer paths have more uneven centrality → lower entropy."""
        vals = []
        for n in [4, 5, 6, 7, 8]:
            g = MemoryGraph()
            build_path(g, n)
            v = g.eigenvector_centrality_entropy()
            assert v is not None
            vals.append(v)
        # Entropy should generally decrease
        for i in range(len(vals) - 1):
            assert vals[i] >= vals[i + 1] - 0.1  # allow small fluctuation


# ─── Raw entropy ──────────────────────────────────────────────────────

class TestEigenvectorEntropyRaw:
    def test_k3_raw_ln3(self):
        """K₃: 3 equal values → raw = ln(3)."""
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.eigenvector_centrality_entropy(normalized=False) == pytest.approx(math.log(3), abs=1e-4)

    def test_k4_raw_ln4(self):
        """K₄: 4 equal values → raw = ln(4)."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.eigenvector_centrality_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-4)

    def test_c4_raw_ln4(self):
        """C₄: 4 equal values → raw = ln(4)."""
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.eigenvector_centrality_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-4)


# ─── Bounded [0, 1] ──────────────────────────────────────────────────

class TestEigenvectorEntropyBounded:
    @pytest.mark.parametrize("builder,n", [
        (build_complete, 3),
        (build_complete, 4),
        (build_complete, 5),
        (build_cycle, 3),
        (build_cycle, 4),
        (build_cycle, 5),
        (build_cycle, 6),
    ])
    def test_bounded_regular(self, builder, n):
        g = MemoryGraph()
        builder(g, n)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-6

    @pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
    def test_bounded_path(self, n):
        g = MemoryGraph()
        build_path(g, n)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-6

    @pytest.mark.parametrize("k", [3, 4, 5])
    def test_bounded_star(self, k):
        g = MemoryGraph()
        build_star(g, k)
        val = g.eigenvector_centrality_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-6


# ─── Non-mutating ─────────────────────────────────────────────────────

class TestEigenvectorEntropyNonMutating:
    def test_does_not_add_nodes(self):
        g = MemoryGraph()
        build_complete(g, 3)
        before = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        g.eigenvector_centrality_entropy()
        after = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        assert before == after

    def test_does_not_add_edges(self):
        g = MemoryGraph()
        build_path(g, 4)
        before = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        g.eigenvector_centrality_entropy()
        after = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        assert before == after


# ─── Cross-checks ────────────────────────────────────────────────────

class TestEigenvectorEntropyCrossCheck:
    def test_regular_all_one(self):
        """On regular graphs, all entropies converge to 1.0."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.eigenvector_centrality_entropy() == pytest.approx(1.0, abs=1e-6)
        assert g.sombor_entropy() == pytest.approx(1.0, abs=1e-10)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_star_eb_vs_ec(self):
        """On star graphs, eigenvector centrality should be very uneven
        (centre dominates), while edge betweenness is perfectly even."""
        g = MemoryGraph()
        build_star(g, 4)
        ec = g.eigenvector_centrality_entropy()
        eb = g.edge_betweenness_entropy()
        assert ec is not None
        assert eb is not None
        # EB should be 1.0 (all edges equal), EC should be < 1.0
        assert eb == pytest.approx(1.0, abs=1e-10)
        assert ec < 1.0
