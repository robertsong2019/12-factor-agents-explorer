"""Tests for Szeged index and Gutman index — Cycle 225 (key-dev-2 Loop B)."""

import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


class TestSzegedIndex:
    """Szeged index: Sz = Σ_{(u,v)∈E} n_u · n_v
    where n_u = |{w : d(w,u) < d(w,v)}| (including endpoints u, v themselves)."""

    def test_empty(self, mg):
        assert mg.szeged_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.szeged_index() is None

    def test_two_isolated(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.szeged_index() is None  # no edges

    def test_single_edge_k2(self, mg):
        """K₂: one edge. n_u = {u} = 1, n_v = {v} = 1. Sz = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.szeged_index() == 1

    def test_triangle_k3(self, mg):
        """K₃: each edge, the 3rd node is equidistant. n_u={u}=1, n_v={v}=1. Sz=3·1=3."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        assert mg.szeged_index() == 3

    def test_path_p3(self, mg):
        """P₃: a-b-c. Sz = W = 4 for trees (Gutman 1994 theorem).
        edge(a,b): n_u={a}=1, n_v={b,c}=2, product=2.
        edge(b,c): n_u={a,b}=2, n_v={c}=1, product=2. Sz=4.
        """
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.szeged_index() == 4

    def test_path_p4(self, mg):
        """P₄: a-b-c-d. For trees Sz = W = 10."""
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.szeged_index() == 10

    def test_star_k13(self, mg):
        """Star K_{1,3}: center + 3 leaves. Sz = W = 9."""
        center = mg.add("C")
        leaves = [mg.add(f"L{i}") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.szeged_index() == 9

    def test_star_k14(self, mg):
        """Star K_{1,4}: center + 4 leaves. Sz = W = 16."""
        center = mg.add("C")
        leaves = [mg.add(f"L{i}") for i in range(4)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.szeged_index() == 16

    def test_cycle_c4(self, mg):
        """C₄: a-b-c-d-a. Each edge: n_u=2, n_v=2. Sz=4·4=16."""
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        mg.link(d.id, a.id, "r")
        assert mg.szeged_index() == 16

    def test_disconnected(self, mg):
        """Two disconnected edges: a-b and c-d.
        edge(a,b): c,d unreachable, n_u={a}=1, n_v={b}=1. product=1.
        edge(c,d): similarly product=1. Sz=2.
        """
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert mg.szeged_index() == 2

    def test_edge_addition(self, mg):
        """Adding edges can increase Sz."""
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        sz_before = mg.szeged_index()
        mg.link(c.id, d.id, "r")  # extend to P₄
        sz_after = mg.szeged_index()
        assert sz_after >= sz_before

    def test_equals_wiener_for_paths(self, mg):
        """For paths P_n (n=3..7), verify Sz = W (Gutman's theorem)."""
        for n in range(3, 8):
            g = MemoryGraph()
            nodes = [g.add(f"N{i}") for i in range(n)]
            for i in range(n - 1):
                g.link(nodes[i].id, nodes[i+1].id, "r")
            assert g.szeged_index() == g.wiener_index(), \
                f"Sz != W for P_{n}: Sz={g.szeged_index()}, W={g.wiener_index()}"

    def test_non_mutating(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        nodes_before = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        edges_before = set((r["source"], r["target"]) for r in mg.conn.execute("SELECT source, target FROM edges"))
        _ = mg.szeged_index()
        nodes_after = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        edges_after = set((r["source"], r["target"]) for r in mg.conn.execute("SELECT source, target FROM edges"))
        assert nodes_before == nodes_after
        assert edges_before == edges_after


class TestGutmanIndex:
    """Gutman index: Gut = Σ_{u<v} d_u · d_v · d(u,v)."""

    def test_empty(self, mg):
        assert mg.gutman_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.gutman_index() is None

    def test_two_isolated(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.gutman_index() is None

    def test_single_edge_k2(self, mg):
        """K₂: d_a=1, d_b=1, d(a,b)=1. Gut = 1·1·1 = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.gutman_index() == 1

    def test_triangle_k3(self, mg):
        """K₃: all degrees 2, all distances 1. Gut = 3·(2·2·1) = 12."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(a.id, c.id, "r")
        assert mg.gutman_index() == 12

    def test_complete_k4(self, mg):
        """K₄: all degrees 3, all distances 1. Gut = C(4,2)·3·3·1 = 54."""
        nodes = [mg.add(chr(65+i)) for i in range(4)]
        for i in range(4):
            for j in range(i+1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert mg.gutman_index() == 54

    def test_path_p3(self, mg):
        """P₃: a-b-c. d_a=1, d_b=2, d_c=1.
        (a,b): 1·2·1=2, (a,c): 1·1·2=2, (b,c): 2·1·1=2. Gut=6."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert mg.gutman_index() == 6

    def test_path_p4(self, mg):
        """P₄: a-b-c-d. d_a=1, d_b=2, d_c=2, d_d=1. Gut=19."""
        nodes = [mg.add(chr(65+i)) for i in range(4)]
        for i in range(3):
            mg.link(nodes[i].id, nodes[i+1].id, "r")
        assert mg.gutman_index() == 19

    def test_star_k13(self, mg):
        """Star K_{1,3}: center deg 3, leaves deg 1. Gut=15."""
        center = mg.add("C")
        leaves = [mg.add(f"L{i}") for i in range(3)]
        for leaf in leaves:
            mg.link(center.id, leaf.id, "r")
        assert mg.gutman_index() == 15

    def test_cycle_c4(self, mg):
        """C₄: all degrees 2. Gut = k²·W = 4·8 = 32."""
        nodes = [mg.add(chr(65+i)) for i in range(4)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i+1) % 4].id, "r")
        assert mg.gutman_index() == 32

    def test_regular_graph_relationship(self, mg):
        """For 2-regular graph C₄: Gut = k² · W = 4 · 8 = 32."""
        nodes = [mg.add(chr(65+i)) for i in range(4)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i+1) % 4].id, "r")
        k_sq = 2 ** 2
        w = mg.wiener_index()
        assert mg.gutman_index() == k_sq * w

    def test_complete_kn_parametric(self, mg):
        """K_n: Gut = n(n-1)³/2."""
        for n in range(2, 7):
            g = MemoryGraph()
            nodes = [g.add(f"N{i}") for i in range(n)]
            for i in range(n):
                for j in range(i+1, n):
                    g.link(nodes[i].id, nodes[j].id, "r")
            expected = n * (n - 1) ** 3 // 2
            assert g.gutman_index() == expected, \
                f"Gut(K_{n}) = {g.gutman_index()}, expected {expected}"

    def test_disconnected_pairs_excluded(self, mg):
        """Unreachable pairs contribute 0."""
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        # Only (a,b): 1·1·1=1 and (c,d): 1·1·1=1. Cross pairs unreachable.
        assert mg.gutman_index() == 2

    def test_edge_addition_increases(self, mg):
        """Adding an edge increases Gutman index."""
        nodes = [mg.add(chr(65+i)) for i in range(4)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        before = mg.gutman_index()
        mg.link(nodes[2].id, nodes[3].id, "r")
        after = mg.gutman_index()
        assert after > before

    def test_gutman_ge_wiener_min_degree_2(self, mg):
        """For min degree ≥ 2: Gut ≥ W (each pair weighted by d_u·d_v ≥ 4)."""
        nodes = [mg.add(chr(65+i)) for i in range(4)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i+1) % 4].id, "r")
        assert mg.gutman_index() >= mg.wiener_index()

    def test_star_k1k_parametric(self, mg):
        """Star K_{1,k}: Gut = 2k² - k."""
        for k in range(1, 6):
            g = MemoryGraph()
            center = g.add("C")
            leaves = [g.add(f"L{i}") for i in range(k)]
            for leaf in leaves:
                g.link(center.id, leaf.id, "r")
            expected = 2 * k * k - k
            assert g.gutman_index() == expected, \
                f"Gut(K_{{1,{k}}}) = {g.gutman_index()}, expected {expected}"

    def test_non_mutating(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        nodes_before = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        edges_before = set((r["source"], r["target"]) for r in mg.conn.execute("SELECT source, target FROM edges"))
        _ = mg.gutman_index()
        nodes_after = set(r["id"] for r in mg.conn.execute("SELECT id FROM nodes"))
        edges_after = set((r["source"], r["target"]) for r in mg.conn.execute("SELECT source, target FROM edges"))
        assert nodes_before == nodes_after
        assert edges_before == edges_after
