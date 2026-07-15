"""Tests for cycle 251: lorenz_coefficient, redefined_randic_indices, redefined_zagreb_index."""
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
    """Star graph K_{1,k}. Returns center node."""
    center = g.add("C")
    for i in range(k):
        leaf = g.add(f"L{i}")
        g.link(center.id, leaf.id, "r")
    return center


# ─── LorenzCoefficient / Gini ─────────────────────────────────────────────────

class TestLorenzCoefficient:

    def test_empty_graph(self, mg):
        assert mg.lorenz_coefficient() is None

    def test_single_node(self, mg):
        mg.add("A")
        result = mg.lorenz_coefficient()
        assert result is not None
        assert result["gini"] == 0.0
        assert result["degree_sequence"] == [0]

    def test_two_isolated_nodes(self, mg):
        mg.add("A")
        mg.add("B")
        result = mg.lorenz_coefficient()
        assert result["gini"] == 0.0
        assert result["mean_degree"] == 0.0

    def test_regular_graph_gini_zero(self, mg):
        """Regular graphs have Gini = 0 (all degrees equal)."""
        build_cycle(mg, 4)
        result = mg.lorenz_coefficient()
        assert abs(result["gini"]) < 1e-9
        assert result["mean_degree"] == 2.0

    def test_complete_graph_gini_zero(self, mg):
        """K_n is regular → Gini = 0."""
        build_complete(mg, 5)
        result = mg.lorenz_coefficient()
        assert abs(result["gini"]) < 1e-9

    def test_star_graph_moderate_gini(self, mg):
        """Star K_{1,5}: Gini = (k-1)/(2(k+1)) = 4/12 = 1/3."""
        build_star(mg, 5)
        result = mg.lorenz_coefficient()
        # Star K_{1,5}: Gini = (5-1)/(2*(5+1)) = 4/12 = 1/3
        assert result["gini"] > 0.25  # moderate inequality
        assert result["gini"] < 0.5

    def test_star_gini_exact(self, mg):
        """Star K_{1,k}: exact Gini = (k-1)/(2(k+1))."""
        k = 4  # K_{1,4}, n=5
        build_star(mg, k)
        result = mg.lorenz_coefficient()
        expected_gini = (k - 1) / (2.0 * (k + 1))  # 3/10 = 0.3
        assert abs(result["gini"] - expected_gini) < 1e-6

    def test_path_graph_low_gini(self, mg):
        """Path P_n has moderate Gini (degree 1 at ends, 2 in middle)."""
        build_path(mg, 6)
        result = mg.lorenz_coefficient()
        assert 0.0 < result["gini"] < 0.3

    def test_lorenz_curve_endpoints(self, mg):
        """Lorenz curve starts at (0,0) and ends at (1,1)."""
        build_path(mg, 3)
        result = mg.lorenz_coefficient()
        curve = result["lorenz_curve"]
        assert curve[0] == (0.0, 0.0)
        assert abs(curve[-1][0] - 1.0) < 1e-9
        assert abs(curve[-1][1] - 1.0) < 1e-9

    def test_lorenz_curve_monotonic(self, mg):
        """Lorenz curve x-coords strictly increasing, y non-decreasing."""
        build_cycle(mg, 5)
        g2 = mg
        g2.add("X")
        g2.add("Y")
        result = g2.lorenz_coefficient()
        curve = result["lorenz_curve"]
        for i in range(1, len(curve)):
            assert curve[i][0] > curve[i - 1][0]  # x strictly increasing
            assert curve[i][1] >= curve[i - 1][1]  # y non-decreasing

    def test_degree_sequence_returned(self, mg):
        build_cycle(mg, 3)
        result = mg.lorenz_coefficient()
        assert result["degree_sequence"] == [2, 2, 2]

    def test_mean_degree(self, mg):
        """3 edges, 4 nodes → mean = 6/4 = 1.5."""
        build_path(mg, 4)
        result = mg.lorenz_coefficient()
        assert abs(result["mean_degree"] - 1.5) < 1e-9

    def test_gini_in_range(self, mg):
        """Gini always in [0, 1]."""
        for builder, arg in [(build_star, 5), (build_path, 6), (build_cycle, 5), (build_complete, 4)]:
            g2 = MemoryGraph()
            builder(g2, arg)
            result = g2.lorenz_coefficient()
            assert 0.0 <= result["gini"] <= 1.0

    def test_disconnected_components(self, mg):
        """Gini works across disconnected components."""
        # Two triangles: all degree 2 → Gini = 0
        build_cycle(mg, 3)
        g2 = MemoryGraph()
        build_cycle(g2, 3)
        # Merge into one graph by building both in mg
        # Actually just test in single graph with two C3 components
        mg2 = MemoryGraph()
        n1 = [mg2.add(f"a{i}") for i in range(3)]
        for i in range(3):
            mg2.link(n1[i].id, n1[(i + 1) % 3].id, "r")
        n2 = [mg2.add(f"b{i}") for i in range(3)]
        for i in range(3):
            mg2.link(n2[i].id, n2[(i + 1) % 3].id, "r")
        result = mg2.lorenz_coefficient()
        assert abs(result["gini"]) < 1e-9

    def test_non_mutating(self, mg):
        build_path(mg, 3)
        before = mg.edge_count()
        mg.lorenz_coefficient()
        assert mg.edge_count() == before

    def test_all_isolated_nodes(self, mg):
        """All isolated → Gini 0 (all equal at 0)."""
        mg.add("X")
        mg.add("Y")
        mg.add("Z")
        result = mg.lorenz_coefficient()
        assert result["gini"] == 0.0
        assert result["mean_degree"] == 0.0

    def test_lorenz_curve_length(self, mg):
        """Lorenz curve has n+1 points."""
        build_cycle(mg, 5)
        result = mg.lorenz_coefficient()
        assert len(result["lorenz_curve"]) == 6  # 5 nodes + origin


class TestRedefinedRandicIndices:

    def test_empty_graph(self, mg):
        assert mg.redefined_randic_indices() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.redefined_randic_indices() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.redefined_randic_indices() is None

    def test_k2_exact(self, mg):
        """K₂: d_u=d_v=1, ratio = 1·1/(1+1) = 0.5."""
        build_complete(mg, 2)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 0.5) < 1e-9
        assert abs(result["rd2"] - 0.25) < 1e-9
        assert abs(result["rd3"] - 0.125) < 1e-9

    def test_c4_exact(self, mg):
        """C₄: d_u=d_v=2, ratio = 4/4 = 1. RD₁=RD₂=RD₃=4."""
        build_cycle(mg, 4)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 4.0) < 1e-9
        assert abs(result["rd2"] - 4.0) < 1e-9
        assert abs(result["rd3"] - 4.0) < 1e-9

    def test_c5_exact(self, mg):
        """C₅: all degree 2 → RD₁=RD₂=RD₃=5."""
        build_cycle(mg, 5)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 5.0) < 1e-9

    def test_star_k1_3_exact(self, mg):
        """Star K_{1,3}: center degree 3, leaves degree 1.
        ratio = 3·1/(3+1) = 0.75 per edge."""
        build_star(mg, 3)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 2.25) < 1e-9
        assert abs(result["rd2"] - 1.6875) < 1e-9
        assert abs(result["rd3"] - 1.265625) < 1e-9

    def test_star_k1_5_exact(self, mg):
        """Star K_{1,5}: ratio = 5/6 per edge."""
        k = 5
        build_star(mg, k)
        result = mg.redefined_randic_indices()
        ratio = k / (k + 1)
        assert abs(result["rd1"] - k * ratio) < 1e-9
        assert abs(result["rd2"] - k * ratio ** 2) < 1e-9
        assert abs(result["rd3"] - k * ratio ** 3) < 1e-9

    def test_path_p3_exact(self, mg):
        """P₃: edges (1,2) and (2,1). Each ratio = 2/3."""
        build_path(mg, 3)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 4.0 / 3.0) < 1e-9
        assert abs(result["rd2"] - 8.0 / 9.0) < 1e-9
        assert abs(result["rd3"] - 16.0 / 27.0) < 1e-9

    def test_path_p4_exact(self, mg):
        """P₄: edges (1,2), (2,2), (2,1).
        (1,2): ratio=2/3, (2,2): ratio=4/4=1
        RD₁ = 2·(2/3) + 1 = 7/3
        """
        build_path(mg, 4)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 7.0 / 3.0) < 1e-9
        assert abs(result["rd2"] - 17.0 / 9.0) < 1e-9
        assert abs(result["rd3"] - 43.0 / 27.0) < 1e-9

    def test_complete_k3(self, mg):
        """K₃: d_u=d_v=2, ratio = 4/4 = 1. RD₁=RD₂=RD₃=3."""
        build_complete(mg, 3)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 3.0) < 1e-9

    def test_complete_k4(self, mg):
        """K₄: d_u=d_v=3, ratio = 9/6 = 1.5. RD₁=6·1.5=9."""
        build_complete(mg, 4)
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 9.0) < 1e-9
        assert abs(result["rd2"] - 6 * 2.25) < 1e-9  # 13.5
        assert abs(result["rd3"] - 6 * 3.375) < 1e-9  # 20.25

    def test_rd_ordering_star(self, mg):
        """For star graph ratio < 1 → RD₁ > RD₂ > RD₃."""
        build_star(mg, 5)
        result = mg.redefined_randic_indices()
        assert result["rd1"] > result["rd2"] > result["rd3"]

    def test_rd_ordering_complete(self, mg):
        """For K_n (n≥3) ratio > 1 → RD₃ > RD₂ > RD₁."""
        build_complete(mg, 5)
        result = mg.redefined_randic_indices()
        assert result["rd3"] > result["rd2"] > result["rd1"]

    def test_all_positive(self, mg):
        build_cycle(mg, 4)
        mg.add("E")
        # connect E to make irregular
        nodes = [n.id for n in []]
        result = mg.redefined_randic_indices()
        assert result["rd1"] > 0
        assert result["rd2"] > 0
        assert result["rd3"] > 0

    def test_disconnected(self, mg):
        """Two K₂ edges: ratio = 0.5 each."""
        a1 = mg.add("A"); a2 = mg.add("B")
        b1 = mg.add("C"); b2 = mg.add("D")
        mg.link(a1.id, a2.id, "r")
        mg.link(b1.id, b2.id, "r")
        result = mg.redefined_randic_indices()
        assert abs(result["rd1"] - 1.0) < 1e-9
        assert abs(result["rd2"] - 0.5) < 1e-9

    def test_non_mutating(self, mg):
        build_path(mg, 3)
        before = mg.edge_count()
        mg.redefined_randic_indices()
        assert mg.edge_count() == before

    def test_parametric_c_n(self, mg):
        """C_n: RD₁=RD₂=RD₃=n."""
        for n in range(3, 9):
            g2 = MemoryGraph()
            build_cycle(g2, n)
            result = g2.redefined_randic_indices()
            assert abs(result["rd1"] - n) < 1e-9, f"C_{n} rd1"

    def test_parametric_k_n(self, mg):
        """K_n: ratio = (n-1)/2."""
        for n in range(2, 7):
            g2 = MemoryGraph()
            build_complete(g2, n)
            result = g2.redefined_randic_indices()
            m = n * (n - 1) // 2
            ratio = (n - 1) / 2.0
            assert abs(result["rd1"] - m * ratio) < 1e-9, f"K_{n} rd1"

    def test_parametric_star(self, mg):
        """Star K_{1,k} for various k."""
        for k in range(1, 7):
            g2 = MemoryGraph()
            build_star(g2, k)
            result = g2.redefined_randic_indices()
            ratio = k / (k + 1.0)
            assert abs(result["rd1"] - k * ratio) < 1e-9, f"K_1,{k} rd1"


class TestRedefinedZagrebIndex:

    def test_empty_graph(self, mg):
        assert mg.redefined_zagreb_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.redefined_zagreb_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.redefined_zagreb_index() is None

    def test_k2_exact(self, mg):
        """K₂: (1+1)·(1·1) = 2."""
        build_complete(mg, 2)
        assert abs(mg.redefined_zagreb_index() - 2.0) < 1e-9

    def test_k3_exact(self, mg):
        """K₃: 3 edges, each (2+2)·(2·2) = 16. Total = 48."""
        build_complete(mg, 3)
        assert abs(mg.redefined_zagreb_index() - 48.0) < 1e-9

    def test_c4_exact(self, mg):
        """C₄: 4 edges, each (2+2)·(4) = 16. Total = 64."""
        build_cycle(mg, 4)
        assert abs(mg.redefined_zagreb_index() - 64.0) < 1e-9

    def test_c_n_formula(self, mg):
        """C_n: ReZM₃ = 16n."""
        for n in range(3, 9):
            g2 = MemoryGraph()
            build_cycle(g2, n)
            assert abs(g2.redefined_zagreb_index() - 16 * n) < 1e-9, f"C_{n}"

    def test_star_k1_3_exact(self, mg):
        """Star K_{1,3}: 3 edges, each (3+1)·(3·1) = 12. Total = 36."""
        build_star(mg, 3)
        assert abs(mg.redefined_zagreb_index() - 36.0) < 1e-9

    def test_star_formula(self, mg):
        """Star K_{1,k}: Total = k²(k+1)."""
        for k in range(1, 7):
            g2 = MemoryGraph()
            build_star(g2, k)
            expected = k * k * (k + 1)
            assert abs(g2.redefined_zagreb_index() - expected) < 1e-9, f"K_1,{k}"

    def test_path_p3_exact(self, mg):
        """P₃: 2 edges, each (1+2)·(1·2) = 6. Total = 12."""
        build_path(mg, 3)
        assert abs(mg.redefined_zagreb_index() - 12.0) < 1e-9

    def test_path_p4_exact(self, mg):
        """P₄: edges (1,2), (2,2), (2,1).
        (1,2): 3·2=6, (2,2): 4·4=16, (2,1): 3·2=6. Total = 28."""
        build_path(mg, 4)
        assert abs(mg.redefined_zagreb_index() - 28.0) < 1e-9

    def test_complete_k4(self, mg):
        """K₄: 6 edges, each (3+3)·(9) = 54. Total = 324."""
        build_complete(mg, 4)
        assert abs(mg.redefined_zagreb_index() - 324.0) < 1e-9

    def test_complete_k_n_formula(self, mg):
        """K_n: m·2(n-1)³."""
        for n in range(2, 7):
            g2 = MemoryGraph()
            build_complete(g2, n)
            m = n * (n - 1) // 2
            expected = m * 2 * (n - 1) ** 3
            assert abs(g2.redefined_zagreb_index() - expected) < 1e-9, f"K_{n}"

    def test_positive_for_edges(self, mg):
        build_cycle(mg, 4)
        assert mg.redefined_zagreb_index() > 0

    def test_disconnected(self, mg):
        """Two K₂ edges: each (1+1)·1 = 2. Total = 4."""
        a1 = mg.add("A"); a2 = mg.add("B")
        b1 = mg.add("C"); b2 = mg.add("D")
        mg.link(a1.id, a2.id, "r")
        mg.link(b1.id, b2.id, "r")
        assert abs(mg.redefined_zagreb_index() - 4.0) < 1e-9

    def test_non_mutating(self, mg):
        build_path(mg, 3)
        before = mg.edge_count()
        mg.redefined_zagreb_index()
        assert mg.edge_count() == before

    def test_edge_addition_increases(self, mg):
        nodes = build_complete(mg, 2)
        v1 = mg.redefined_zagreb_index()
        c = mg.add("C")
        mg.link(nodes[0].id, c.id, "r")
        v2 = mg.redefined_zagreb_index()
        assert v2 > v1


class TestCrossRelationships:
    """Cross-verify relationships between new and existing indices."""

    def test_lorenz_zero_for_regular(self, mg):
        """All regular graphs have Gini = 0."""
        build_cycle(mg, 6)
        result = mg.lorenz_coefficient()
        assert abs(result["gini"]) < 1e-9

    def test_rd_positive_when_sc_positive(self, mg):
        """RD₁ and sum-connectivity both positive for same graph."""
        build_path(mg, 4)
        rd = mg.redefined_randic_indices()
        sc = mg.sum_connectivity_index()
        assert rd["rd1"] > 0
        assert sc > 0

    def test_redefined_zagreb_gt_zagreb_second(self, mg):
        """ReZM₃ = Σ(d_u+d_v)·(d_u·d_v) ≥ M₂ = Σ(d_u·d_v) since (d_u+d_v) ≥ 1."""
        build_complete(mg, 3)
        rezm3 = mg.redefined_zagreb_index()
        zagreb = mg.zagreb_indices()
        assert rezm3 >= zagreb["second"]

    def test_all_three_new_distinct(self, mg):
        """All three new APIs produce valid output for asymmetric graph."""
        hub = mg.add("hub")
        a = mg.add("a")
        b = mg.add("b")
        c = mg.add("c")
        mg.link(hub.id, a.id, "r")
        mg.link(hub.id, b.id, "r")
        mg.link(hub.id, c.id, "r")
        mg.link(a.id, b.id, "r")

        lorenz = mg.lorenz_coefficient()
        rd = mg.redefined_randic_indices()
        rezm3 = mg.redefined_zagreb_index()

        assert lorenz is not None
        assert rd is not None
        assert rezm3 is not None
        assert lorenz["gini"] >= 0
        assert rd["rd1"] > 0
        assert rezm3 > 0
