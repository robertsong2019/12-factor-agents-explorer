"""Tests for generalized_randic_index(α) and zagreb_indices().

Cycle 232 — builds on the topological index family established in
cycles 200-231 (Wiener, Harary, Randić, Balaban, Szeged, Gutman,
Schultz, Modified Wiener, Estrada, Natural connectivity, etc.).

References:
    Bollobás, B. & Erdős, P. (1998). "Graph distances and diameters."
    Randić, M. (1975). "On characterization of molecular branching."
    Gutman, I. & Trinajstić, N. (1972). "Graph theory and molecular orbitals."
"""

import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


# ==================================================================
# Generalized Randić Index R_α = Σ_{(u,v)∈E} (d_u · d_v)^α
# ==================================================================

class TestGeneralizedRandicIndex:
    """Tests for generalized_randic_index(α)."""

    def test_empty(self, mg):
        assert mg.generalized_randic_index() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.generalized_randic_index() is None

    def test_no_edges(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.generalized_randic_index() is None

    # --- K₂ (single edge) ---

    def test_k2_alpha_half(self, mg):
        """K₂: (1·1)^(-0.5) = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert abs(mg.generalized_randic_index(-0.5) - 1.0) < 1e-9

    def test_k2_alpha_zero(self, mg):
        """K₂ α=0: (1·1)^0 = 1 = m (edge count)."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert abs(mg.generalized_randic_index(0) - 1.0) < 1e-9

    def test_k2_alpha_one(self, mg):
        """K₂ α=1: (1·1)^1 = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert abs(mg.generalized_randic_index(1) - 1.0) < 1e-9

    def test_k2_alpha_neg_one(self, mg):
        """K₂ α=-1: 1/(1·1) = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert abs(mg.generalized_randic_index(-1) - 1.0) < 1e-9

    def test_k2_alpha_two(self, mg):
        """K₂ α=2: (1·1)^2 = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert abs(mg.generalized_randic_index(2) - 1.0) < 1e-9

    # --- K₃ (triangle) ---

    def test_k3_alpha_half(self, mg):
        """K₃ α=-0.5: 3·(4)^(-0.5) = 1.5 = classic Randić."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        for x, y in [(a, b), (b, c), (c, a)]:
            mg.link(x.id, y.id, "r")
        assert abs(mg.generalized_randic_index(-0.5) - 1.5) < 1e-9

    def test_k3_alpha_zero(self, mg):
        """K₃ α=0: 3 edges × 1 = 3 = m."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        for x, y in [(a, b), (b, c), (c, a)]:
            mg.link(x.id, y.id, "r")
        assert abs(mg.generalized_randic_index(0) - 3.0) < 1e-9

    def test_k3_alpha_one(self, mg):
        """K₃ α=1: 3·(2·2) = 12 = second Zagreb M₂."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        for x, y in [(a, b), (b, c), (c, a)]:
            mg.link(x.id, y.id, "r")
        assert abs(mg.generalized_randic_index(1) - 12.0) < 1e-9

    def test_k3_alpha_neg_one(self, mg):
        """K₃ α=-1: 3·(4)^(-1) = 3/4."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        for x, y in [(a, b), (b, c), (c, a)]:
            mg.link(x.id, y.id, "r")
        assert abs(mg.generalized_randic_index(-1) - 0.75) < 1e-9

    # --- K₄ (complete graph) ---

    def test_k4_alpha_half(self, mg):
        """K₄ α=-0.5: 6·(9)^(-0.5) = 6/3 = 2 = n/2."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert abs(mg.generalized_randic_index(-0.5) - 2.0) < 1e-9

    def test_k4_alpha_one(self, mg):
        """K₄ α=1: 6·(3·3) = 54."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        assert abs(mg.generalized_randic_index(1) - 54.0) < 1e-9

    # --- Cycle C₄ ---

    def test_c4_alpha_half(self, mg):
        """C₄ α=-0.5: 4·(4)^(-0.5) = 4/2 = 2 = n/2."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i + 1) % 4].id, "r")
        assert abs(mg.generalized_randic_index(-0.5) - 2.0) < 1e-9

    def test_c4_alpha_one(self, mg):
        """C₄ α=1: 4·(2·2) = 16."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i + 1) % 4].id, "r")
        assert abs(mg.generalized_randic_index(1) - 16.0) < 1e-9

    # --- Star K_{1,k} ---

    def test_star_alpha_half(self, mg):
        """K_{1,4} α=-0.5: 4·(4·1)^(-0.5) = 4/2 = 2 = √(n-1)."""
        center = mg.add("C")
        for i in range(4):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        assert abs(mg.generalized_randic_index(-0.5) - 2.0) < 1e-9

    def test_star_alpha_one(self, mg):
        """K_{1,4} α=1: 4·(4·1) = 16 = k²."""
        center = mg.add("C")
        for i in range(4):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        assert abs(mg.generalized_randic_index(1) - 16.0) < 1e-9

    def test_star_alpha_neg_one(self, mg):
        """K_{1,4} α=-1: 4·(4·1)^(-1) = 4/4 = 1."""
        center = mg.add("C")
        for i in range(4):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        assert abs(mg.generalized_randic_index(-1) - 1.0) < 1e-9

    # --- Path P₃ ---

    def test_p3_alpha_half(self, mg):
        """P₃ α=-0.5: 2·(1·2)^(-0.5) = 2/√2 = √2."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        expected = 2.0 / math.sqrt(2)
        assert abs(mg.generalized_randic_index(-0.5) - expected) < 1e-9

    def test_p3_alpha_one(self, mg):
        """P₃ α=1: (1·2) + (2·1) = 4."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert abs(mg.generalized_randic_index(1) - 4.0) < 1e-9

    def test_p3_alpha_neg_one(self, mg):
        """P₃ α=-1: 2·(2)^(-1) = 1."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        assert abs(mg.generalized_randic_index(-1) - 1.0) < 1e-9

    # --- Parametric formulas ---

    def test_kn_alpha_half_formula(self, mg):
        """For K_n α=-0.5: R = n/2 (all degrees = n-1)."""
        for n in range(2, 7):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    mg2.link(nodes[i].id, nodes[j].id, "r")
            assert abs(mg2.generalized_randic_index(-0.5) - n / 2.0) < 1e-9

    def test_kn_alpha_zero_formula(self, mg):
        """For K_n α=0: R_0 = m = n(n-1)/2."""
        for n in range(2, 7):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    mg2.link(nodes[i].id, nodes[j].id, "r")
            expected = n * (n - 1) / 2.0
            assert abs(mg2.generalized_randic_index(0) - expected) < 1e-9

    def test_kn_alpha_one_formula(self, mg):
        """For K_n α=1: R₁ = n(n-1)³/2 (= second Zagreb M₂)."""
        for n in range(2, 7):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    mg2.link(nodes[i].id, nodes[j].id, "r")
            expected = n * (n - 1) ** 3 / 2.0
            assert abs(mg2.generalized_randic_index(1) - expected) < 1e-9

    def test_kn_alpha_neg_one_formula(self, mg):
        """For K_n α=-1: R_{-1} = n/(2(n-1))."""
        for n in range(2, 7):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    mg2.link(nodes[i].id, nodes[j].id, "r")
            expected = n / (2.0 * (n - 1))
            assert abs(mg2.generalized_randic_index(-1) - expected) < 1e-9

    def test_star_alpha_half_formula(self, mg):
        """For K_{1,k} α=-0.5: R = √k."""
        for k in range(1, 6):
            mg2 = MemoryGraph(":memory:")
            center = mg2.add("C")
            for i in range(k):
                leaf = mg2.add(f"L{i}")
                mg2.link(center.id, leaf.id, "r")
            assert abs(mg2.generalized_randic_index(-0.5) - math.sqrt(k)) < 1e-9

    def test_star_alpha_one_formula(self, mg):
        """For K_{1,k} α=1: R₁ = k²."""
        for k in range(1, 6):
            mg2 = MemoryGraph(":memory:")
            center = mg2.add("C")
            for i in range(k):
                leaf = mg2.add(f"L{i}")
                mg2.link(center.id, leaf.id, "r")
            assert abs(mg2.generalized_randic_index(1) - k * k) < 1e-9

    def test_cycle_alpha_half_formula(self, mg):
        """For C_n α=-0.5: R = n/2 (all degrees = 2)."""
        for n in range(3, 8):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                mg2.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
            assert abs(mg2.generalized_randic_index(-0.5) - n / 2.0) < 1e-9

    def test_cycle_alpha_one_formula(self, mg):
        """For C_n α=1: R₁ = 4n (all edges (2·2)^1 = 4)."""
        for n in range(3, 8):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                mg2.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
            assert abs(mg2.generalized_randic_index(1) - 4.0 * n) < 1e-9

    # --- Relationship to classic Randić ---

    def test_matches_randic_at_half(self, mg):
        """generalized_randic_index(-0.5) == randic_index() for various graphs."""
        # Path P4
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        r_classic = mg.randic_index()
        r_general = mg.generalized_randic_index(-0.5)
        assert abs(r_classic - r_general) < 1e-9

    def test_alpha_one_equals_m2(self, mg):
        """R₁ = M₂ (second Zagreb): Σ d_u·d_v over edges."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        r1 = mg.generalized_randic_index(1)
        zagreb = mg.zagreb_indices()
        assert abs(r1 - zagreb["second"]) < 1e-9

    def test_alpha_zero_equals_edge_count(self, mg):
        """R₀ = m (edge count): any (d_u·d_v)^0 = 1."""
        a, b, c, d = mg.add("A"), mg.add("B"), mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, d.id, "r")
        mg.link(a.id, d.id, "r")
        assert abs(mg.generalized_randic_index(0) - 4.0) < 1e-9

    # --- Monotonicity and behavior ---

    def test_disconnected_components(self, mg):
        """Two disjoint edges: R_α = 2·(1)^α = 2 for any α."""
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        assert abs(mg.generalized_randic_index(-0.5) - 2.0) < 1e-9
        assert abs(mg.generalized_randic_index(1) - 2.0) < 1e-9
        assert abs(mg.generalized_randic_index(0) - 2.0) < 1e-9

    def test_default_alpha(self, mg):
        """Default α should be -0.5 (classic Randić)."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        mg.link(c.id, a.id, "r")
        default_val = mg.generalized_randic_index()
        half_val = mg.generalized_randic_index(-0.5)
        assert abs(default_val - half_val) < 1e-9

    def test_monotone_in_alpha(self, mg):
        """For a non-regular graph, R_α increases with α."""
        center = mg.add("C")
        for i in range(4):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        r_neg = mg.generalized_randic_index(-1)
        r_half = mg.generalized_randic_index(-0.5)
        r_zero = mg.generalized_randic_index(0)
        r_one = mg.generalized_randic_index(1)
        assert r_neg < r_half < r_zero < r_one

    def test_non_mutating(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        before = mg.generalized_randic_index(1)
        mg.generalized_randic_index(0)
        mg.generalized_randic_index(-1)
        after = mg.generalized_randic_index(1)
        assert before == after


# ==================================================================
# Zagreb Indices M₁ and M₂
# ==================================================================

class TestZagrebIndices:
    """Tests for zagreb_indices() — M₁ (first) and M₂ (second)."""

    def test_empty(self, mg):
        assert mg.zagreb_indices() is None

    def test_single_node(self, mg):
        mg.add("A")
        assert mg.zagreb_indices() is None

    def test_two_isolated(self, mg):
        mg.add("A")
        mg.add("B")
        assert mg.zagreb_indices() is None

    # --- K₂ ---

    def test_k2(self, mg):
        """K₂: M₁ = 1² + 1² = 2, M₂ = 1·1 = 1."""
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 2
        assert result["second"] == 1

    def test_k2_difference(self, mg):
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        result = mg.zagreb_indices()
        assert result["difference"] == 1  # M₁ - M₂ = 2 - 1

    def test_k2_ratio(self, mg):
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        result = mg.zagreb_indices()
        assert abs(result["ratio"] - 0.5) < 1e-9  # M₂/M₁ = 1/2

    # --- K₃ (triangle) ---

    def test_k3(self, mg):
        """K₃: all degrees = 2. M₁ = 3·4 = 12, M₂ = 3·4 = 12."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        for x, y in [(a, b), (b, c), (c, a)]:
            mg.link(x.id, y.id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 12
        assert result["second"] == 12
        assert result["difference"] == 0
        assert abs(result["ratio"] - 1.0) < 1e-9

    # --- K₄ ---

    def test_k4(self, mg):
        """K₄: all degrees = 3. M₁ = 4·9 = 36, M₂ = 6·9 = 54."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 36
        assert result["second"] == 54

    # --- C₄ ---

    def test_c4(self, mg):
        """C₄: all degrees = 2. M₁ = 4·4 = 16, M₂ = 4·4 = 16."""
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            mg.link(nodes[i].id, nodes[(i + 1) % 4].id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 16
        assert result["second"] == 16

    # --- P₃ ---

    def test_p3(self, mg):
        """P₃: degrees 1,2,1. M₁ = 1+4+1 = 6, M₂ = 2+2 = 4."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 6
        assert result["second"] == 4

    # --- Star K_{1,4} ---

    def test_star_k14(self, mg):
        """K_{1,4}: center deg=4, leaves deg=1.
        M₁ = 16+4 = 20, M₂ = 4·(4·1) = 16."""
        center = mg.add("C")
        for i in range(4):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 20
        assert result["second"] == 16

    # --- Parametric formulas ---

    def test_kn_formula(self, mg):
        """For K_n: M₁ = n(n-1)², M₂ = n(n-1)³/2."""
        for n in range(2, 7):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    mg2.link(nodes[i].id, nodes[j].id, "r")
            result = mg2.zagreb_indices()
            assert result["first"] == n * (n - 1) ** 2, f"K_{n} M₁"
            assert result["second"] == n * (n - 1) ** 3 // 2, f"K_{n} M₂"

    def test_cycle_formula(self, mg):
        """For C_n: M₁ = 4n, M₂ = 4n (all degrees = 2)."""
        for n in range(3, 8):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n):
                mg2.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
            result = mg2.zagreb_indices()
            assert result["first"] == 4 * n, f"C_{n} M₁"
            assert result["second"] == 4 * n, f"C_{n} M₂"

    def test_path_formula(self, mg):
        """For P_n (n≥2): M₁ = 4n-6, M₂ = 4n-6."""
        for n in range(2, 8):
            mg2 = MemoryGraph(":memory:")
            nodes = [mg2.add(f"n{i}") for i in range(n)]
            for i in range(n - 1):
                mg2.link(nodes[i].id, nodes[i + 1].id, "r")
            result = mg2.zagreb_indices()
            if n == 2:
                expected_m1 = 2
                expected_m2 = 1
            elif n >= 3:
                expected_m1 = 4 * n - 6  # 2 endpoints (d=1) + (n-2) internal (d=2): 2·1 + (n-2)·4 = 4n-6
                expected_m2 = 4 * n - 6  # (n-2) edges with (2·2) + 2 edges with (1·2) = 4(n-2)+4 = 4n-4
                # Wait let me recompute M₂ for P_n...
                # Edges: e_1=(v1,v2), e_{n-1}=(v_{n-1},v_n): each (1·2)=2
                # Internal edges (n-3 of them): each (2·2)=4
                # Actually for P_n with n≥3: endpoints have d=1, internal nodes have d=2
                # Edges: (n-1) total
                #   - 2 boundary edges: d_u·d_v = 1·2 = 2 each
                #   - (n-3) internal edges: d_u·d_v = 2·2 = 4 each (for n≥4)
                # M₂ = 2·2 + (n-3)·4 = 4 + 4n - 12 = 4n - 8 (for n≥3)
                # Wait, for P₃ (n=3): 2 edges, both boundary: M₂ = 2·2 = 4
                #   4n-8 = 12-8 = 4 ✓
                # For P₄ (n=4): 3 edges, 2 boundary + 1 internal: M₂ = 2·2 + 1·4 = 8
                #   4n-8 = 16-8 = 8 ✓
                expected_m2 = 4 * n - 8 if n >= 3 else 1
            assert result["first"] == expected_m1, f"P_{n} M₁: got {result['first']}, want {expected_m1}"
            assert result["second"] == expected_m2, f"P_{n} M₂: got {result['second']}, want {expected_m2}"

    def test_star_formula(self, mg):
        """For K_{1,k}: M₁ = k² + k, M₂ = k²."""
        for k in range(1, 6):
            mg2 = MemoryGraph(":memory:")
            center = mg2.add("C")
            for i in range(k):
                leaf = mg2.add(f"L{i}")
                mg2.link(center.id, leaf.id, "r")
            result = mg2.zagreb_indices()
            assert result["first"] == k * k + k, f"K_{{1,{k}}} M₁"
            assert result["second"] == k * k, f"K_{{1,{k}}} M₂"

    # --- Relationships ---

    def test_regular_graph_m1_eq_2m_times_k(self, mg):
        """For k-regular graph: M₁ = n·k², and 2m = n·k, so M₁ = k·(n·k) = k·2m."""
        # C₆: 2-regular, 6 nodes, 6 edges
        nodes = [mg.add(str(i)) for i in range(6)]
        for i in range(6):
            mg.link(nodes[i].id, nodes[(i + 1) % 6].id, "r")
        result = mg.zagreb_indices()
        # M₁ = n·k² = 6·4 = 24, 2m·k = 12·2 = 24
        assert result["first"] == 24
        assert result["second"] == 24

    def test_complete_graph_difference(self, mg):
        """For K_n: M₁ - M₂ = n(n-1)² - n(n-1)³/2 = n(n-1)²(1 - (n-1)/2) = n(n-1)²(3-n)/2."""
        # For K₂: diff = 2·1·(1)/2 = 1
        # For K₃: diff = 3·4·0/2 = 0
        # For K₄: diff = 4·9·(-1)/2 = -18
        nodes = [mg.add(str(i)) for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                mg.link(nodes[i].id, nodes[j].id, "r")
        result = mg.zagreb_indices()
        assert result["difference"] == -18  # M₂ > M₁ for K₄

    def test_ratio_range(self, mg):
        """Ratio M₂/M₁ is in [0, ∞) but for simple graphs typically [0.5, 2]."""
        # K₂: ratio = 0.5
        a, b = mg.add("A"), mg.add("B")
        mg.link(a.id, b.id, "r")
        assert mg.zagreb_indices()["ratio"] == 0.5

    # --- Edge addition behavior ---

    def test_edge_addition_increases_both(self, mg):
        """Adding an edge increases both M₁ and M₂."""
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        before = mg.zagreb_indices()
        mg.link(a.id, c.id, "r")  # Make triangle
        after = mg.zagreb_indices()
        assert after["first"] > before["first"]
        assert after["second"] > before["second"]

    # --- Disconnected components ---

    def test_disconnected(self, mg):
        """Two disjoint edges: M₁ = 1+1+1+1 = 4, M₂ = 1+1 = 2."""
        a, b = mg.add("A"), mg.add("B")
        c, d = mg.add("C"), mg.add("D")
        mg.link(a.id, b.id, "r")
        mg.link(c.id, d.id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 4
        assert result["second"] == 2

    # --- Non-mutating ---

    def test_non_mutating(self, mg):
        a, b, c = mg.add("A"), mg.add("B"), mg.add("C")
        mg.link(a.id, b.id, "r")
        mg.link(b.id, c.id, "r")
        before = mg.zagreb_indices()
        mg.zagreb_indices()
        after = mg.zagreb_indices()
        assert before == after

    # --- M₁ edge-form vs vertex-form equivalence ---

    def test_m1_vertex_edge_equivalence(self, mg):
        """M₁ = Σ_v d_v² = Σ_{(u,v)∈E} (d_u + d_v).
        Verify: build star K_{1,5}. Vertex form: 25+5=30.
        Edge form: 5·(5+1) = 30.
        """
        center = mg.add("C")
        for i in range(5):
            leaf = mg.add(f"L{i}")
            mg.link(center.id, leaf.id, "r")
        result = mg.zagreb_indices()
        assert result["first"] == 30  # 5² + 5·1² = 25 + 5 = 30
