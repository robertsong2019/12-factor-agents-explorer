"""Tests for renyi_entropy() — generalized Rényi entropy of degree-based edge contributions.

H_α = 1/(1−α) · ln(Σ p_e^α), where α is the entropic order.
α → 1 recovers Shannon entropy. α = 2 gives collision entropy.
Supports all 7 degree-based contribution types.

Cycle 288.
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


# ─── Degenerate cases ──────────────────────────────────────────────────

class TestRenyiDegenerate:
    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.renyi_entropy(alpha=2.0) is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("a")
        assert g.renyi_entropy(alpha=2.0) is None

    def test_no_edges(self):
        g = MemoryGraph()
        g.add("a")
        g.add("b")
        assert g.renyi_entropy(alpha=2.0) is None

    def test_alpha_1_raises(self):
        g = MemoryGraph()
        build_complete(g, 3)
        with pytest.raises(ValueError):
            g.renyi_entropy(alpha=1.0)

    def test_negative_alpha(self):
        """Alpha < 1 is valid (superextensive)."""
        g = MemoryGraph()
        build_complete(g, 3)
        result = g.renyi_entropy(alpha=0.5)
        assert result is not None
        assert result > 0

    def test_alpha_0_hartley(self):
        """Alpha=0 gives Hartley entropy = ln(m) before normalization."""
        g = MemoryGraph()
        build_complete(g, 4)  # 6 edges
        raw = g.renyi_entropy(alpha=0.001, normalized=False)
        # H_0 → ln(m) as α→0
        assert raw is not None
        assert abs(raw - math.log(6)) < 0.01

    def test_large_alpha(self):
        """Alpha → ∞ gives min-entropy."""
        g = MemoryGraph()
        build_path(g, 4)  # irregular
        result = g.renyi_entropy(alpha=100.0)
        assert result is not None
        assert result >= 0

    def test_two_nodes_one_edge(self):
        """K₂: single edge, one p=1.0, H_α = 0."""
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        g.link(a.id, b.id, "r")
        result = g.renyi_entropy(alpha=2.0)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-12)


# ─── Regular graphs (normalized = 1.0) ─────────────────────────────────

class TestRenyiRegular:
    def test_k3_normalized_1(self):
        g = MemoryGraph()
        build_complete(g, 3)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)

    def test_k4_normalized_1(self):
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)

    def test_k5_normalized_1(self):
        g = MemoryGraph()
        build_complete(g, 5)
        assert g.renyi_entropy(alpha=3.0, normalized=True) == pytest.approx(1.0)

    def test_c4_normalized_1(self):
        g = MemoryGraph()
        build_cycle(g, 4)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)

    def test_c5_normalized_1(self):
        g = MemoryGraph()
        build_cycle(g, 5)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)

    def test_c6_normalized_1(self):
        g = MemoryGraph()
        build_cycle(g, 6)
        assert g.renyi_entropy(alpha=5.0, normalized=True) == pytest.approx(1.0)

    def test_star_k3_normalized_1(self):
        g = MemoryGraph()
        build_star(g, 3)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)

    def test_star_k5_normalized_1(self):
        g = MemoryGraph()
        build_star(g, 5)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)

    def test_p3_normalized_1(self):
        """P₃: two edges with identical (1,2) degree pair → 1.0."""
        g = MemoryGraph()
        build_path(g, 3)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)


# ─── Irregular graphs (normalized < 1.0) ───────────────────────────────

class TestRenyiIrregular:
    def test_p4_normalized_lt_1(self):
        g = MemoryGraph()
        build_path(g, 4)
        assert g.renyi_entropy(alpha=2.0, normalized=True) < 1.0

    def test_p5_normalized_lt_1(self):
        g = MemoryGraph()
        build_path(g, 5)
        assert g.renyi_entropy(alpha=2.0, normalized=True) < 1.0

    def test_p6_normalized_lt_1(self):
        g = MemoryGraph()
        build_path(g, 6)
        assert g.renyi_entropy(alpha=2.0, normalized=True) < 1.0

    def test_paw_normalized_lt_1(self):
        g = MemoryGraph()
        build_paw(g)
        assert g.renyi_entropy(alpha=2.0, normalized=True) < 1.0


# ─── Raw entropy values ────────────────────────────────────────────────

class TestRenyiRaw:
    def test_k3_raw_ln3(self):
        """K₃: 3 identical contributions → H_α = ln(3) for any α."""
        g = MemoryGraph()
        build_complete(g, 3)
        raw = g.renyi_entropy(alpha=2.0, normalized=False)
        assert raw == pytest.approx(math.log(3), abs=1e-10)

    def test_c4_raw_ln4(self):
        """C₄: 4 identical contributions → H_α = ln(4)."""
        g = MemoryGraph()
        build_cycle(g, 4)
        raw = g.renyi_entropy(alpha=2.0, normalized=False)
        assert raw == pytest.approx(math.log(4), abs=1e-10)

    def test_k4_raw_ln6(self):
        """K₄: 6 identical contributions → H_α = ln(6)."""
        g = MemoryGraph()
        build_complete(g, 4)
        raw = g.renyi_entropy(alpha=3.0, normalized=False)
        assert raw == pytest.approx(math.log(6), abs=1e-10)

    def test_star_k4_raw_ln4(self):
        """K_{1,4}: 4 identical contributions → H_α = ln(4)."""
        g = MemoryGraph()
        build_star(g, 4)
        raw = g.renyi_entropy(alpha=2.0, normalized=False)
        assert raw == pytest.approx(math.log(4), abs=1e-10)

    def test_regular_raw_independent_of_alpha(self):
        """Regular graph: raw Rényi = ln(m) for all α."""
        g = MemoryGraph()
        build_complete(g, 4)  # 6 edges
        for alpha in [0.5, 2.0, 5.0, 10.0]:
            raw = g.renyi_entropy(alpha=alpha, normalized=False)
            assert raw == pytest.approx(math.log(6), abs=1e-10), f"Failed for alpha={alpha}"


# ─── Alpha parameter behavior ──────────────────────────────────────────

class TestRenyiAlphaBehavior:
    def test_higher_alpha_lower_entropy(self):
        """For irregular graph: H_α decreases as α increases."""
        g = MemoryGraph()
        build_path(g, 5)
        h05 = g.renyi_entropy(alpha=0.5, normalized=False)
        h2 = g.renyi_entropy(alpha=2.0, normalized=False)
        h5 = g.renyi_entropy(alpha=5.0, normalized=False)
        assert h05 > h2 > h5

    def test_alpha_2_collision_entropy(self):
        """α=2: H_2 = −ln(Σp²) (collision entropy)."""
        g = MemoryGraph()
        build_path(g, 4)
        # Compute manually
        edges = [(1, 2), (2, 2), (2, 1)]  # degree-based contributions
        # P₄ degrees: 1,2,2,1
        # Sombor: √(1+4)=√5, √(4+4)=√8, √(4+1)=√5
        so = math.sqrt(5) + math.sqrt(8) + math.sqrt(5)
        p1 = math.sqrt(5) / so
        p2 = math.sqrt(8) / so
        p3 = math.sqrt(5) / so
        sum_p2 = p1**2 + p2**2 + p3**2
        expected = -math.log(sum_p2)
        result = g.renyi_entropy(alpha=2.0, normalized=False)
        assert result == pytest.approx(expected, abs=1e-10)

    def test_alpha_to_1_approaches_shannon(self):
        """As α→1, Rényi entropy → Shannon entropy."""
        g = MemoryGraph()
        build_path(g, 5)
        shannon = g.sombor_entropy(normalized=False)
        renyi_near1 = g.renyi_entropy(alpha=1.001, normalized=False)
        assert renyi_near1 == pytest.approx(shannon, abs=0.01)

    def test_alpha_0_equals_ln_m(self):
        """α→0: H_0 = ln(m) (Hartley/max entropy)."""
        g = MemoryGraph()
        build_path(g, 5)  # 4 edges
        hartley = g.renyi_entropy(alpha=0.0001, normalized=False)
        assert hartley == pytest.approx(math.log(4), abs=0.001)


# ─── All index types ───────────────────────────────────────────────────

class TestRenyiIndexTypes:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1",
        "ga", "augmented_zagreb",
    ])
    def test_all_indices_return_float(self, index):
        g = MemoryGraph()
        build_complete(g, 4)
        result = g.renyi_entropy(alpha=2.0, index=index)
        assert result is not None
        assert isinstance(result, float)
        assert 0 <= result <= 1.0

    def test_abc_index_k3(self):
        """ABC index: K₃ edges all have d_u+d_v-2=2, du·dv=4 → valid."""
        g = MemoryGraph()
        build_complete(g, 3)
        result = g.renyi_entropy(alpha=2.0, index="abc")
        assert result is not None

    def test_abc_index_k2_skipped(self):
        """ABC index: K₂ edges (d_u+d_v-2=0) are skipped."""
        g = MemoryGraph()
        g.add("a"), g.add("b")
        g.link("a", "b", "r")
        result = g.renyi_entropy(alpha=2.0, index="abc")
        assert result is None

    def test_augmented_zagreb_k2_skipped(self):
        """AZI: K₂ edges (d_u+d_v-2=0) are skipped."""
        g = MemoryGraph()
        g.add("a"), g.add("b")
        g.link("a", "b", "r")
        result = g.renyi_entropy(alpha=2.0, index="augmented_zagreb")
        assert result is None

    def test_unknown_index_raises(self):
        g = MemoryGraph()
        build_complete(g, 3)
        with pytest.raises(ValueError):
            g.renyi_entropy(alpha=2.0, index="bogus")


# ─── Normalization ─────────────────────────────────────────────────────

class TestRenyiNormalization:
    def test_normalized_bounded_0_1(self):
        """Normalized Rényi entropy must be in [0, 1]."""
        for builder, args in [
            (build_complete, [3, 4, 5]),
            (build_cycle, [4, 5, 6]),
            (build_path, [4, 5, 6, 7]),
        ]:
            for n in args:
                g = MemoryGraph()
                builder(g, n)
                result = g.renyi_entropy(alpha=2.0, normalized=True)
                assert result is not None
                assert 0 <= result <= 1.0, f"Failed for {builder.__name__}({n}): {result}"

    def test_raw_positive(self):
        """Raw Rényi entropy must be non-negative."""
        for builder, args in [
            (build_complete, [3, 4]),
            (build_cycle, [4, 5]),
            (build_path, [4, 5, 6]),
        ]:
            for n in args:
                g = MemoryGraph()
                builder(g, n)
                result = g.renyi_entropy(alpha=2.0, normalized=False)
                assert result is not None
                assert result >= 0


# ─── Non-mutating ──────────────────────────────────────────────────────

class TestRenyiNonMutating:
    def test_nodes_unchanged(self):
        g = MemoryGraph()
        build_path(g, 5)
        before = set(r["id"] for r in g.conn.execute("SELECT id FROM nodes"))
        g.renyi_entropy(alpha=2.0)
        after = set(r["id"] for r in g.conn.execute("SELECT id FROM nodes"))
        assert before == after

    def test_edges_unchanged(self):
        g = MemoryGraph()
        build_path(g, 5)
        before = list(g.conn.execute("SELECT source, target FROM edges"))
        g.renyi_entropy(alpha=2.0)
        after = list(g.conn.execute("SELECT source, target FROM edges"))
        assert before == after


# ─── Cross-check with Tsallis ──────────────────────────────────────────

class TestRenyiTsallisRelation:
    def test_renyi_tsallis_relationship(self):
        """H_α^Rényi = ln(1 + (1−α)·S_q^Tsallis) / (1−α)."""
        g = MemoryGraph()
        build_path(g, 5)
        alpha = 2.0
        renyi = g.renyi_entropy(alpha=alpha, normalized=False)
        tsallis = g.tsallis_entropy(q=alpha, normalized=False)
        # Relationship: H_R = ln(1 + (1-α)·S_T) / (1-α)
        expected = math.log(1 + (1 - alpha) * tsallis) / (1 - alpha)
        assert renyi == pytest.approx(expected, abs=1e-8)

    def test_regular_both_max(self):
        """For regular graphs: both Rényi and Tsallis normalized → max."""
        g = MemoryGraph()
        build_complete(g, 4)
        assert g.renyi_entropy(alpha=2.0, normalized=True) == pytest.approx(1.0)
        assert g.tsallis_entropy(q=2.0, normalized=True) == pytest.approx(1.0)
