"""Tests for forgotten_index(), abc_index(), and sum_connectivity_index().

Cycle 238 — degree-based topological indices continuing from cycle 232.

Forgotten F = Σ d_v³ = Σ_{(u,v)∈E} (d_u² + d_v²)   (Fajtlowicz 1998)
ABC = Σ √((d_u+d_v-2)/(d_u·d_v))                     (Estrada et al. 1998)
Sum-connectivity χ_S = Σ 1/(d_u+d_v)                  (Zhou & Trinajstić 2009)
"""

import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def build_complete(g, n):
    """Complete graph K_n."""
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes


def build_path(g, n):
    """Path graph P_n."""
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return nodes


def build_cycle(g, n):
    """Cycle graph C_n."""
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return nodes


def build_star(g, k):
    """Star graph K_{1,k}."""
    center = g.add("C")
    for i in range(k):
        leaf = g.add(f"L{i}")
        g.link(center.id, leaf.id, "r")
    return center


# ─── Forgotten Index F ─────────────────────────────────────────────────────────

class TestForgottenIndex:

    def test_empty(self, mg):
        assert mg.forgotten_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.forgotten_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.forgotten_index() is None

    def test_k2(self, mg):
        """K₂: F = 1³ + 1³ = 2."""
        build_complete(mg, 2)
        assert mg.forgotten_index() == 2

    def test_k3(self, mg):
        """K₃: all degree 2, F = 3·2³ = 24."""
        build_complete(mg, 3)
        assert mg.forgotten_index() == 24

    def test_k4(self, mg):
        """K₄: all degree 3, F = 4·3³ = 108."""
        build_complete(mg, 4)
        assert mg.forgotten_index() == 108

    def test_k5(self, mg):
        """K₅: all degree 4, F = 5·4³ = 320."""
        build_complete(mg, 5)
        assert mg.forgotten_index() == 320

    def test_c4(self, mg):
        """C₄: all degree 2, F = 4·2³ = 32."""
        build_cycle(mg, 4)
        assert mg.forgotten_index() == 32

    def test_c5(self, mg):
        """C₅: all degree 2, F = 5·2³ = 40."""
        build_cycle(mg, 5)
        assert mg.forgotten_index() == 40

    def test_c6(self, mg):
        """C₆: all degree 2, F = 6·2³ = 48."""
        build_cycle(mg, 6)
        assert mg.forgotten_index() == 48

    def test_p3(self, mg):
        """P₃: degrees 1,2,1; F = 1+8+1 = 10."""
        build_path(mg, 3)
        assert mg.forgotten_index() == 10

    def test_p4(self, mg):
        """P₄: degrees 1,2,2,1; F = 1+8+8+1 = 18."""
        build_path(mg, 4)
        assert mg.forgotten_index() == 18

    def test_p5(self, mg):
        """P₅: degrees 1,2,2,2,1; F = 1+8+8+8+1 = 26."""
        build_path(mg, 5)
        assert mg.forgotten_index() == 26

    def test_star_k3(self, mg):
        """K_{1,3}: center deg 3, leaves deg 1; F = 27+3 = 30."""
        build_star(mg, 3)
        assert mg.forgotten_index() == 30

    def test_star_k4(self, mg):
        """K_{1,4}: center deg 4, leaves deg 1; F = 64+4 = 68."""
        build_star(mg, 4)
        assert mg.forgotten_index() == 68

    def test_star_k5(self, mg):
        """K_{1,5}: center deg 5, leaves deg 1; F = 125+5 = 130."""
        build_star(mg, 5)
        assert mg.forgotten_index() == 130

    # Parametric formulas

    def test_parametric_kn(self, mg):
        """K_n: F = n(n-1)³."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_complete(g, n)
            expected = n * (n - 1) ** 3
            assert g.forgotten_index() == expected, f"K_{n}"

    def test_parametric_cn(self, mg):
        """C_n: F = 8n."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.forgotten_index() == 8 * n, f"C_{n}"

    def test_parametric_pn(self, mg):
        """P_n: F = 8n-14 for n≥3, F=2 for n=2."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_path(g, n)
            expected = 2 if n == 2 else 8 * n - 14
            assert g.forgotten_index() == expected, f"P_{n}"

    def test_parametric_star(self, mg):
        """K_{1,k}: F = k³ + k."""
        for k in range(1, 7):
            g = MemoryGraph()
            build_star(g, k)
            assert g.forgotten_index() == k ** 3 + k, f"K_{{1,{k}}}"

    # Properties

    def test_f_ge_m1(self, mg):
        """F ≥ M₁ for any graph (d³ ≥ d² for d ≥ 1)."""
        for builder in [lambda g: build_complete(g, 4),
                        lambda g: build_path(g, 5),
                        lambda g: build_cycle(g, 6),
                        lambda g: build_star(g, 4)]:
            g = MemoryGraph()
            builder(g)
            assert g.forgotten_index() >= g.zagreb_indices()["first"]

    def test_edge_form_equals_vertex_form(self, mg):
        """F_vertex = Σ d_v³ should equal F_edge = Σ(d_u² + d_v²)."""
        for builder in [lambda g: build_complete(g, 4),
                        lambda g: build_path(g, 5),
                        lambda g: build_cycle(g, 5),
                        lambda g: build_star(g, 4)]:
            g = MemoryGraph()
            builder(g)
            f_method = g.forgotten_index()
            # Compute edge form manually
            rows = g.conn.execute("SELECT id FROM nodes").fetchall()
            deg = {str(r["id"]): g.degree(str(r["id"])) for r in rows}
            edges = g.conn.execute("SELECT source, target FROM edges").fetchall()
            f_edge = sum(deg[str(r["source"])] ** 2 + deg[str(r["target"])] ** 2
                         for r in edges)
            assert f_method == f_edge, f"Vertex {f_method} != edge {f_edge}"

    def test_regular_graph(self, mg):
        """For r-regular: F = n·r³. C_n is 2-regular: F = 8n."""
        for n in range(3, 8):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.forgotten_index() == n * 8

    def test_disconnected(self, mg):
        """Two disjoint K₃: F = 2 × 24 = 48."""
        nodes = [mg.add(str(i)) for i in range(6)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[0].id, nodes[2].id, "r")
        mg.link(nodes[3].id, nodes[4].id, "r")
        mg.link(nodes[4].id, nodes[5].id, "r")
        mg.link(nodes[3].id, nodes[5].id, "r")
        assert mg.forgotten_index() == 48

    def test_edge_addition_increases(self, mg):
        """Adding an edge increases F."""
        nodes = build_path(mg, 4)
        f_before = mg.forgotten_index()
        mg.link(nodes[0].id, nodes[3].id, "r")
        f_after = mg.forgotten_index()
        assert f_after > f_before

    def test_non_mutating(self, mg):
        build_complete(mg, 4)
        edges_before = set(mg.conn.execute("SELECT source, target FROM edges").fetchall())
        _ = mg.forgotten_index()
        edges_after = set(mg.conn.execute("SELECT source, target FROM edges").fetchall())
        assert edges_before == edges_after


# ─── ABC Index ─────────────────────────────────────────────────────────────────

class TestABCIndex:

    def test_empty(self, mg):
        assert mg.abc_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.abc_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.abc_index() is None

    def test_k2(self, mg):
        """K₂: edge (1,1), ABC = √(0/1) = 0."""
        build_complete(mg, 2)
        assert mg.abc_index() == pytest.approx(0.0)

    def test_k3(self, mg):
        """K₃: 3 edges (2,2): √(2/4); ABC = 3/√2."""
        build_complete(mg, 3)
        assert mg.abc_index() == pytest.approx(3.0 / math.sqrt(2))

    def test_k4(self, mg):
        """K₄: 6 edges (3,3): √(4/9)=2/3; ABC = 4."""
        build_complete(mg, 4)
        assert mg.abc_index() == pytest.approx(4.0)

    def test_k5(self, mg):
        """K₅: 10 edges (4,4): √(6/16); ABC = 10·√(3/8)."""
        build_complete(mg, 5)
        expected = 10.0 * math.sqrt(3.0 / 8.0)
        assert mg.abc_index() == pytest.approx(expected)

    def test_c4(self, mg):
        """C₄: 4 edges (2,2): ABC = 4/√2 = 2√2."""
        build_cycle(mg, 4)
        assert mg.abc_index() == pytest.approx(4.0 / math.sqrt(2))

    def test_c5(self, mg):
        """C₅: ABC = 5/√2."""
        build_cycle(mg, 5)
        assert mg.abc_index() == pytest.approx(5.0 / math.sqrt(2))

    def test_c6(self, mg):
        """C₆: ABC = 6/√2 = 3√2."""
        build_cycle(mg, 6)
        assert mg.abc_index() == pytest.approx(6.0 / math.sqrt(2))

    def test_p3(self, mg):
        """P₃: 2 edges both √(1/2); ABC = √2."""
        build_path(mg, 3)
        assert mg.abc_index() == pytest.approx(math.sqrt(2))

    def test_p4(self, mg):
        """P₄: 3 edges all √(1/2); ABC = 3/√2."""
        build_path(mg, 4)
        assert mg.abc_index() == pytest.approx(3.0 / math.sqrt(2))

    def test_p5(self, mg):
        """P₅: 4 edges all √(1/2); ABC = 4/√2 = 2√2."""
        build_path(mg, 5)
        assert mg.abc_index() == pytest.approx(4.0 / math.sqrt(2))

    def test_star_k3(self, mg):
        """K_{1,3}: 3 edges (1,3): √(2/3); ABC = 3·√(2/3)."""
        build_star(mg, 3)
        assert mg.abc_index() == pytest.approx(3.0 * math.sqrt(2.0 / 3.0))

    def test_star_k4(self, mg):
        """K_{1,4}: 4 edges (1,4): √(3/4); ABC = 4·√(3/4)."""
        build_star(mg, 4)
        assert mg.abc_index() == pytest.approx(4.0 * math.sqrt(3.0 / 4.0))

    def test_star_k5(self, mg):
        """K_{1,5}: 5 edges (1,5): √(4/5); ABC = 5·√(4/5) = 2√5."""
        build_star(mg, 5)
        assert mg.abc_index() == pytest.approx(5.0 * math.sqrt(4.0 / 5.0))

    # Parametric

    def test_parametric_cn(self, mg):
        """C_n: ABC = n/√2."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.abc_index() == pytest.approx(n / math.sqrt(2)), f"C_{n}"

    def test_parametric_pn(self, mg):
        """P_n: ABC = (n-1)/√2 for n≥3; P₂=0 (lone edge deg(1,1))."""
        for n in range(2, 9):
            g = MemoryGraph()
            build_path(g, n)
            expected = 0.0 if n == 2 else (n - 1) / math.sqrt(2)
            assert g.abc_index() == pytest.approx(expected), f"P_{n}"

    def test_parametric_star(self, mg):
        """K_{1,k}: ABC = k·√((k-1)/k), K_{1,1}→0."""
        for k in range(1, 7):
            g = MemoryGraph()
            build_star(g, k)
            expected = 0.0 if k == 1 else k * math.sqrt((k - 1) / k)
            assert g.abc_index() == pytest.approx(expected), f"K_{{1,{k}}}"

    def test_parametric_kn(self, mg):
        """K_n: ABC = m·√(2(n-2)/(n-1)²)."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_complete(g, n)
            if n == 2:
                expected = 0.0
            else:
                m = n * (n - 1) / 2
                expected = m * math.sqrt(2 * (n - 2) / (n - 1) ** 2)
            assert g.abc_index() == pytest.approx(expected), f"K_{n}"

    # Properties

    def test_abc_zero_for_isolated_edges(self, mg):
        """Graph of only K₂ components: ABC = 0."""
        for i in range(4):
            a = mg.add(f"a{i}")
            b = mg.add(f"b{i}")
            mg.link(a.id, b.id, "r")
        assert mg.abc_index() == pytest.approx(0.0)

    def test_abc_differs_from_randic(self, mg):
        """ABC ≠ Randić in general."""
        build_star(mg, 4)
        assert mg.abc_index() != pytest.approx(mg.randic_index())

    def test_disconnected(self, mg):
        """Two disjoint C₄: ABC = 2 × 4/√2."""
        nodes_a = [mg.add(f"a{i}") for i in range(4)]
        for i in range(4):
            mg.link(nodes_a[i].id, nodes_a[(i + 1) % 4].id, "r")
        nodes_b = [mg.add(f"b{i}") for i in range(4)]
        for i in range(4):
            mg.link(nodes_b[i].id, nodes_b[(i + 1) % 4].id, "r")
        assert mg.abc_index() == pytest.approx(2 * 4.0 / math.sqrt(2))

    def test_non_mutating(self, mg):
        build_complete(mg, 4)
        edges_before = set(mg.conn.execute("SELECT source, target FROM edges").fetchall())
        _ = mg.abc_index()
        edges_after = set(mg.conn.execute("SELECT source, target FROM edges").fetchall())
        assert edges_before == edges_after


# ─── Sum-Connectivity Index ────────────────────────────────────────────────────

class TestSumConnectivityIndex:

    def test_empty(self, mg):
        assert mg.sum_connectivity_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.sum_connectivity_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.sum_connectivity_index() is None

    def test_k2(self, mg):
        """K₂: 1/(1+1) = 1/2."""
        build_complete(mg, 2)
        assert mg.sum_connectivity_index() == pytest.approx(0.5)

    def test_k3(self, mg):
        """K₃: 3·1/4 = 3/4."""
        build_complete(mg, 3)
        assert mg.sum_connectivity_index() == pytest.approx(0.75)

    def test_k4(self, mg):
        """K₄: 6·1/6 = 1."""
        build_complete(mg, 4)
        assert mg.sum_connectivity_index() == pytest.approx(1.0)

    def test_k5(self, mg):
        """K₅: 10·1/8 = 5/4."""
        build_complete(mg, 5)
        assert mg.sum_connectivity_index() == pytest.approx(10.0 / 8.0)

    def test_c4(self, mg):
        """C₄: 4·1/4 = 1."""
        build_cycle(mg, 4)
        assert mg.sum_connectivity_index() == pytest.approx(1.0)

    def test_c5(self, mg):
        """C₅: 5/4."""
        build_cycle(mg, 5)
        assert mg.sum_connectivity_index() == pytest.approx(5.0 / 4.0)

    def test_c6(self, mg):
        """C₆: 6/4 = 3/2."""
        build_cycle(mg, 6)
        assert mg.sum_connectivity_index() == pytest.approx(6.0 / 4.0)

    def test_p3(self, mg):
        """P₃: 2·1/3 = 2/3."""
        build_path(mg, 3)
        assert mg.sum_connectivity_index() == pytest.approx(2.0 / 3.0)

    def test_p4(self, mg):
        """P₄: 2·(1/3) + 1/4 = 11/12."""
        build_path(mg, 4)
        assert mg.sum_connectivity_index() == pytest.approx(11.0 / 12.0)

    def test_p5(self, mg):
        """P₅: 2·(1/3) + 2·(1/4) = 7/6."""
        build_path(mg, 5)
        assert mg.sum_connectivity_index() == pytest.approx(2.0/3.0 + 2.0/4.0)

    def test_star_k3(self, mg):
        """K_{1,3}: 3·1/4 = 3/4."""
        build_star(mg, 3)
        assert mg.sum_connectivity_index() == pytest.approx(3.0 / 4.0)

    def test_star_k4(self, mg):
        """K_{1,4}: 4·1/5 = 4/5."""
        build_star(mg, 4)
        assert mg.sum_connectivity_index() == pytest.approx(4.0 / 5.0)

    def test_star_k5(self, mg):
        """K_{1,5}: 5·1/6 = 5/6."""
        build_star(mg, 5)
        assert mg.sum_connectivity_index() == pytest.approx(5.0 / 6.0)

    # Parametric

    def test_parametric_kn(self, mg):
        """K_n: χ_S = n/4."""
        for n in range(2, 8):
            g = MemoryGraph()
            build_complete(g, n)
            assert g.sum_connectivity_index() == pytest.approx(n / 4.0), f"K_{n}"

    def test_parametric_cn(self, mg):
        """C_n: χ_S = n/4."""
        for n in range(3, 9):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.sum_connectivity_index() == pytest.approx(n / 4.0), f"C_{n}"

    def test_parametric_star(self, mg):
        """K_{1,k}: χ_S = k/(k+1)."""
        for k in range(1, 7):
            g = MemoryGraph()
            build_star(g, k)
            assert g.sum_connectivity_index() == pytest.approx(k / (k + 1.0)), f"K_{{1,{k}}}"

    def test_parametric_pn(self, mg):
        """P_n: χ_S = 2/3 + (n-3)/4 for n≥3; P₂=1/2."""
        for n in range(2, 9):
            g = MemoryGraph()
            build_path(g, n)
            expected = 0.5 if n == 2 else 2.0/3.0 + (n - 3) / 4.0
            assert g.sum_connectivity_index() == pytest.approx(expected), f"P_{n}"

    # Properties

    def test_regular_graph(self, mg):
        """For r-regular: χ_S = m/(2r). C_n: n/4."""
        for n in range(3, 8):
            g = MemoryGraph()
            build_cycle(g, n)
            assert g.sum_connectivity_index() == pytest.approx(n / 4.0)

    def test_sum_conn_vs_randic(self, mg):
        """χ_S ≠ Randić in general."""
        build_star(mg, 3)
        assert mg.sum_connectivity_index() != pytest.approx(mg.randic_index())

    def test_disconnected(self, mg):
        """Two disjoint K₃: χ_S = 2×3/4."""
        nodes = [mg.add(str(i)) for i in range(6)]
        mg.link(nodes[0].id, nodes[1].id, "r")
        mg.link(nodes[1].id, nodes[2].id, "r")
        mg.link(nodes[0].id, nodes[2].id, "r")
        mg.link(nodes[3].id, nodes[4].id, "r")
        mg.link(nodes[4].id, nodes[5].id, "r")
        mg.link(nodes[3].id, nodes[5].id, "r")
        assert mg.sum_connectivity_index() == pytest.approx(2 * 0.75)

    def test_edge_addition_changes(self, mg):
        """Adding an edge changes χ_S."""
        nodes = build_path(mg, 4)
        sc_before = mg.sum_connectivity_index()
        mg.link(nodes[0].id, nodes[3].id, "r")
        sc_after = mg.sum_connectivity_index()
        assert sc_after != sc_before

    def test_non_mutating(self, mg):
        build_complete(mg, 4)
        edges_before = set(mg.conn.execute("SELECT source, target FROM edges").fetchall())
        _ = mg.sum_connectivity_index()
        edges_after = set(mg.conn.execute("SELECT source, target FROM edges").fetchall())
        assert edges_before == edges_after


# ─── Cross-Relationships ───────────────────────────────────────────────────────

class TestCrossRelationships:

    def test_f_ge_m1_always(self, mg):
        """F ≥ M₁ since d³ ≥ d² for d ≥ 1."""
        for builder in [lambda g: build_complete(g, 5),
                        lambda g: build_path(g, 6),
                        lambda g: build_cycle(g, 7),
                        lambda g: build_star(g, 5)]:
            g = MemoryGraph()
            builder(g)
            assert g.forgotten_index() >= g.zagreb_indices()["first"]

    def test_abc_k2_zero_vs_sum_conn_nonzero(self, mg):
        """ABC(K₂) = 0 but χ_S(K₂) = 1/2."""
        build_complete(mg, 2)
        assert mg.abc_index() == pytest.approx(0.0)
        assert mg.sum_connectivity_index() == pytest.approx(0.5)

    def test_three_indices_distinct(self, mg):
        """All three produce different values for K₄."""
        build_complete(mg, 4)
        assert mg.forgotten_index() != mg.abc_index()
        assert mg.abc_index() != mg.sum_connectivity_index()
        assert mg.forgotten_index() != mg.sum_connectivity_index()

    def test_sum_conn_vs_gen_randic_neg1(self, mg):
        """χ_S = Σ1/(d_u+d_v) ≠ R_{-1} = Σ1/(d_u·d_v) in general."""
        build_complete(mg, 4)
        assert mg.sum_connectivity_index() != pytest.approx(
            mg.generalized_randic_index(alpha=-1))
