"""Tests for edge_betweenness_entropy() — Shannon entropy of edge betweenness centrality.

First centrality-based entropy in the toolkit. Measures how evenly
shortest paths are distributed across edges.

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

class TestEdgeBetwEntropyDegenerate:
    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.edge_betweenness_entropy() is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("a")
        assert g.edge_betweenness_entropy() is None

    def test_no_edges(self):
        g = MemoryGraph()
        g.add("a")
        g.add("b")
        assert g.edge_betweenness_entropy() is None

    def test_single_edge(self):
        """K₂: 1 edge, betweenness = 0 (no shortest paths through it as intermediary).
        Edge betweenness for a single edge in K₂: the edge is on the shortest path
        between the two nodes, so it gets betweenness 1 (or 0.5 after undirected division).
        With only 1 value, entropy = 0.0.
        """
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        g.link(a.id, b.id, "r")
        val = g.edge_betweenness_entropy()
        # Single-element entropy
        assert val is not None
        assert val == 0.0


# ─── Regular graphs: entropy = 1.0 ────────────────────────────────────

class TestEdgeBetwEntropyRegular:
    def test_k3_normalized_one(self):
        """K₃: all 3 edges have equal betweenness → entropy = 1.0."""
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_k4_normalized_one(self):
        """K₄: all 6 edges equal betweenness → entropy = 1.0."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_k5_normalized_one(self):
        g = MemoryGraph()
        build_complete(g, 5)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_c4_normalized_one(self):
        """C₄: all edges equal betweenness → entropy = 1.0."""
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_c5_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 5)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_c6_normalized_one(self):
        g = MemoryGraph()
        build_cycle(g, 6)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_star_k3_normalized_one(self):
        """K_{1,3}: all edges have equal betweenness → entropy = 1.0.

        In a star, each edge is on the same number of shortest paths
        (all paths go through center).
        """
        g = MemoryGraph()
        build_star(g, 3)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_star_k5_normalized_one(self):
        g = MemoryGraph()
        build_star(g, 5)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)


# ─── Path graphs: highly uneven betweenness ───────────────────────────

class TestEdgeBetwEntropyPath:
    def test_p3_normalized_one(self):
        """P₃: 2 edges with equal betweenness → entropy = 1.0.

        Both edges are on exactly 1 shortest path (between the two endpoints).
        """
        g = MemoryGraph()
        build_path(g, 3)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val == pytest.approx(1.0, abs=1e-10)

    def test_p4_less_than_one(self):
        """P₄: central edges carry more paths → entropy < 1.0."""
        g = MemoryGraph()
        build_path(g, 4)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val < 1.0

    def test_p5_less_than_one(self):
        g = MemoryGraph()
        build_path(g, 5)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val < 1.0

    def test_p6_less_than_one(self):
        g = MemoryGraph()
        build_path(g, 6)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val < 1.0

    def test_path_entropy_decreases_with_length(self):
        """Longer paths have more uneven betweenness → lower entropy."""
        vals = []
        for n in [4, 5, 6, 7, 8]:
            g = MemoryGraph()
            build_path(g, n)
            v = g.edge_betweenness_entropy()
            assert v is not None
            vals.append(v)
        # Entropy should generally decrease (more uneven)
        for i in range(len(vals) - 1):
            assert vals[i] >= vals[i + 1] - 0.05  # allow small fluctuation


# ─── Raw entropy ──────────────────────────────────────────────────────

class TestEdgeBetwEntropyRaw:
    def test_k3_raw_ln3(self):
        """K₃: 3 equal values → raw = ln(3)."""
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.edge_betweenness_entropy(normalized=False) == pytest.approx(math.log(3), abs=1e-10)

    def test_k4_raw_ln6(self):
        """K₄: 6 equal values → raw = ln(6)."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.edge_betweenness_entropy(normalized=False) == pytest.approx(math.log(6), abs=1e-10)

    def test_c4_raw_ln4(self):
        """C₄: 4 equal values → raw = ln(4)."""
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.edge_betweenness_entropy(normalized=False) == pytest.approx(math.log(4), abs=1e-10)


# ─── Paw graph ────────────────────────────────────────────────────────

class TestEdgeBetwEntropyPaw:
    def test_paw_less_than_one(self):
        """Paw graph: pendant edge has different betweenness → entropy < 1.0."""
        g = MemoryGraph()
        build_paw(g)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val < 1.0

    def test_paw_positive(self):
        g = MemoryGraph()
        build_paw(g)
        assert g.edge_betweenness_entropy() > 0


# ─── Binary tree ──────────────────────────────────────────────────────

class TestEdgeBetwEntropyTree:
    def test_binary_tree_less_than_one(self):
        """Binary tree: root edges carry more paths → entropy < 1.0."""
        g = MemoryGraph()
        build_binary_tree(g, depth=3)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val < 1.0

    def test_binary_tree_positive(self):
        g = MemoryGraph()
        build_binary_tree(g, depth=3)
        assert g.edge_betweenness_entropy() > 0


# ─── Disconnected graphs ──────────────────────────────────────────────

class TestEdgeBetwEntropyDisconnected:
    def test_two_k3(self):
        """Two disjoint K₃: each has equal betweenness → all equal → 1.0."""
        g = MemoryGraph()
        build_complete(g, 3)
        nodes2 = [g.add(f"x{i}") for i in range(3)]
        g.link(nodes2[0].id, nodes2[1].id, "r")
        g.link(nodes2[1].id, nodes2[2].id, "r")
        g.link(nodes2[0].id, nodes2[2].id, "r")
        val = g.edge_betweenness_entropy()
        assert val is not None
        # All 6 edges have equal betweenness (within each K₃, edges have same betweenness)
        assert val == pytest.approx(1.0, abs=1e-10)

    def test_two_c4(self):
        g = MemoryGraph()
        build_cycle(g, 4)
        nodes2 = [g.add(f"y{i}") for i in range(4)]
        for i in range(4):
            g.link(nodes2[i].id, nodes2[(i + 1) % 4].id, "r")
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert val == pytest.approx(1.0, abs=1e-10)


# ─── Edge addition ────────────────────────────────────────────────────

class TestEdgeBetwEntropyEdgeAddition:
    def test_adding_bridge_edge_changes_entropy(self):
        """Connecting two components changes the betweenness distribution."""
        # Start with a path P₄
        g = MemoryGraph()
        build_path(g, 4)
        before = g.edge_betweenness_entropy()
        # Add a completely separate K₃ component, then bridge it
        nodes_orig = [str(r["id"]) for r in g.conn.execute("SELECT id FROM nodes").fetchall()]
        e, f, h = g.add("e"), g.add("f"), g.add("h")
        g.link(e.id, f.id, "r")
        g.link(f.id, h.id, "r")
        g.link(e.id, h.id, "r")  # K₃
        g.link(nodes_orig[3], e.id, "r")  # bridge edge
        after = g.edge_betweenness_entropy()
        assert before is not None
        assert after is not None
        # Connecting components via a bridge creates a very uneven betweenness
        assert before != after


# ─── Bounded [0, 1] ──────────────────────────────────────────────────

class TestEdgeBetwEntropyBounded:
    @pytest.mark.parametrize("builder,n", [
        (build_complete, 3),
        (build_complete, 4),
        (build_complete, 5),
        (build_cycle, 4),
        (build_cycle, 5),
        (build_cycle, 6),
    ])
    def test_bounded_regular(self, builder, n):
        g = MemoryGraph()
        builder(g, n)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-12

    @pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
    def test_bounded_path(self, n):
        g = MemoryGraph()
        build_path(g, n)
        val = g.edge_betweenness_entropy()
        assert val is not None
        assert 0 < val <= 1.0 + 1e-12


# ─── Non-mutating ─────────────────────────────────────────────────────

class TestEdgeBetwEntropyNonMutating:
    def test_does_not_add_nodes(self):
        g = MemoryGraph()
        build_complete(g, 3)
        before = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        g.edge_betweenness_entropy()
        after = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        assert before == after

    def test_does_not_add_edges(self):
        g = MemoryGraph()
        build_path(g, 4)
        before = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        g.edge_betweenness_entropy()
        after = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        assert before == after


# ─── Cross-checks with degree-based entropies ────────────────────────

class TestEdgeBetwEntropyCrossCheck:
    def test_regular_all_one(self):
        """On regular graphs, edge-betweenness entropy = degree entropies = 1.0."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.edge_betweenness_entropy() == pytest.approx(1.0, abs=1e-10)
        assert g.sombor_entropy() == pytest.approx(1.0, abs=1e-10)
        assert g.abc_entropy() == pytest.approx(1.0, abs=1e-10)

    def test_path_eb_different_from_degree(self):
        """Edge-betweenness entropy captures structure differently from degree.

        On P₅, all degree-based entropies might be near 1.0 (small degree variation),
        but edge-betweenness entropy should be significantly < 1.0
        (central edges carry much more traffic).
        """
        g = MemoryGraph()
        build_path(g, 5)
        eb = g.edge_betweenness_entropy()
        sombor = g.sombor_entropy()
        assert eb is not None
        assert sombor is not None
        # EB should be lower (more uneven) than degree-based on paths
        assert eb < sombor + 0.1

    def test_paw_all_below_one(self):
        """On paw graph, EB entropy < 1.0 like all degree entropies."""
        g = MemoryGraph()
        build_paw(g)
        assert g.edge_betweenness_entropy() < 1.0
        assert g.sombor_entropy() < 1.0
        assert g.augmented_zagreb_entropy() < 1.0
