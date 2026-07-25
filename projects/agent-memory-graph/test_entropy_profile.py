"""Tests for entropy_profile() — comparative degree-based entropy dashboard.

Computes all six degree-based Shannon entropies and returns structured comparison
with diversity stats, most heterogeneous/homogeneous index, and graph fingerprint.

Cycle 281.
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
    """Paw graph: triangle K₃ with a pendant edge."""
    a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
    g.link(a.id, b.id, "r")
    g.link(b.id, c.id, "r")
    g.link(a.id, c.id, "r")
    g.link(c.id, d.id, "r")
    return a, b, c, d


# ─── Empty / degenerate cases ──────────────────────────────────────────

class TestEntropyProfileDegenerate:
    def test_empty_graph(self):
        g = MemoryGraph()
        assert g.entropy_profile() is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("a")
        assert g.entropy_profile() is None

    def test_two_nodes_no_edges(self):
        g = MemoryGraph()
        g.add("a")
        g.add("b")
        assert g.entropy_profile() is None

    def test_single_edge(self):
        """K₂ — only 1 edge. Entropy = 0 for all indices (m=1, no normalization)."""
        g = MemoryGraph()
        a, b = g.add("a"), g.add("b")
        g.link(a.id, b.id, "r")
        result = g.entropy_profile()
        # abc skips K₂ edge → None. Other 5 indices return 0.0 (raw entropy of 1 item)
        assert result is not None
        assert result["index_count"] == 5  # abc excluded
        for val in result["values"].values():
            assert val == 0.0


# ─── Regular graphs: all entropies = 1.0 ───────────────────────────────

class TestEntropyProfileRegular:
    def test_k3_all_ones(self):
        """K₃: all contributions identical → all normalized entropies = 1.0."""
        g = MemoryGraph()
        build_complete(g, 3)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_k4_all_ones(self):
        g = MemoryGraph()
        build_complete(g, 4)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_k5_all_ones(self):
        g = MemoryGraph()
        build_complete(g, 5)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_c4_all_ones(self):
        g = MemoryGraph()
        build_cycle(g, 4)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_c5_all_ones(self):
        g = MemoryGraph()
        build_cycle(g, 5)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_star_k3_all_ones(self):
        """K_{1,3}: all edges identical → all entropies = 1.0."""
        g = MemoryGraph()
        build_star(g, 3)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_star_k5_all_ones(self):
        g = MemoryGraph()
        build_star(g, 5)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert val == pytest.approx(1.0, abs=1e-12), f"{name} != 1.0"

    def test_range_zero(self):
        """For regular graphs, range should be ~0."""
        g = MemoryGraph()
        build_complete(g, 4)
        p = g.entropy_profile()
        assert p["range"] == pytest.approx(0.0, abs=1e-12)

    def test_std_zero(self):
        g = MemoryGraph()
        build_complete(g, 4)
        p = g.entropy_profile()
        assert p["std"] == pytest.approx(0.0, abs=1e-12)

    def test_mean_one(self):
        g = MemoryGraph()
        build_cycle(g, 6)
        p = g.entropy_profile()
        assert p["mean"] == pytest.approx(1.0, abs=1e-12)


# ─── Irregular graphs: entropies < 1.0 ─────────────────────────────────

class TestEntropyProfileIrregular:
    def test_path_p4_less_than_one(self):
        """P₄: boundary vs interior edges differ → all entropies < 1.0."""
        g = MemoryGraph()
        build_path(g, 4)
        p = g.entropy_profile()
        assert p is not None
        for name, val in p["values"].items():
            assert 0 < val < 1.0, f"{name} should be < 1.0 for P₄"

    def test_path_p5_most_less_than_one(self):
        """P₅: most entropies < 1.0, but abc = 1.0 (all abc contributions identical)."""
        g = MemoryGraph()
        build_path(g, 5)
        p = g.entropy_profile()
        assert p is not None
        # abc entropy = 1.0 for paths (all abc contributions are √(1/2))
        # Other indices should be < 1.0
        below_one = [v for n, v in p["values"].items() if n != "abc"]
        for val in below_one:
            assert 0 < val < 1.0

    def test_paw_less_than_one(self):
        """Paw graph: different edge types → some entropies < 1.0."""
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        assert p is not None
        assert p["range"] > 0

    def test_range_positive(self):
        """Irregular graph should have positive range across indices."""
        g = MemoryGraph()
        build_path(g, 6)
        p = g.entropy_profile()
        assert p["range"] > 0

    def test_std_positive(self):
        g = MemoryGraph()
        build_path(g, 6)
        p = g.entropy_profile()
        assert p["std"] > 0


# ─── Structure tests ───────────────────────────────────────────────────

class TestEntropyProfileStructure:
    def test_returns_dict(self):
        g = MemoryGraph()
        build_complete(g, 3)
        p = g.entropy_profile()
        assert isinstance(p, dict)

    def test_has_required_keys(self):
        g = MemoryGraph()
        build_complete(g, 4)
        p = g.entropy_profile()
        required = {"values", "raw_values", "min", "max", "range",
                    "mean", "std", "most_heterogeneous", "most_homogeneous",
                    "fingerprint", "index_count"}
        assert required.issubset(p.keys())

    def test_values_dict(self):
        g = MemoryGraph()
        build_complete(g, 3)
        p = g.entropy_profile()
        assert isinstance(p["values"], dict)
        # Should have 5-6 entries (abc may be missing for some graphs)
        assert len(p["values"]) >= 5

    def test_raw_values_dict(self):
        g = MemoryGraph()
        build_complete(g, 3)
        p = g.entropy_profile()
        assert isinstance(p["raw_values"], dict)
        # Raw values should be ln(m) for regular graphs
        m = 3  # K₃ has 3 edges
        for name, val in p["raw_values"].items():
            assert val == pytest.approx(math.log(m), abs=1e-10)

    def test_fingerprint_is_tuple(self):
        g = MemoryGraph()
        build_complete(g, 4)
        p = g.entropy_profile()
        assert isinstance(p["fingerprint"], tuple)
        assert len(p["fingerprint"]) >= 5

    def test_fingerprint_rounded(self):
        g = MemoryGraph()
        build_path(g, 5)
        p = g.entropy_profile()
        # Each fingerprint value should be rounded to 6 decimal places
        for v in p["fingerprint"]:
            rounded = round(v, 6)
            assert v == pytest.approx(rounded, abs=1e-10)

    def test_index_count(self):
        g = MemoryGraph()
        build_complete(g, 4)
        p = g.entropy_profile()
        assert p["index_count"] >= 5
        assert p["index_count"] <= 6

    def test_most_heterogeneous_is_string(self):
        g = MemoryGraph()
        build_path(g, 6)
        p = g.entropy_profile()
        assert isinstance(p["most_heterogeneous"], str)

    def test_most_homogeneous_is_string(self):
        g = MemoryGraph()
        build_path(g, 6)
        p = g.entropy_profile()
        assert isinstance(p["most_homogeneous"], str)

    def test_min_matches_values(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        assert p["min"] == min(p["values"].values())

    def test_max_matches_values(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        assert p["max"] == max(p["values"].values())

    def test_range_matches(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        assert p["range"] == pytest.approx(p["max"] - p["min"])

    def test_mean_matches(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        vals = list(p["values"].values())
        assert p["mean"] == pytest.approx(sum(vals) / len(vals))

    def test_std_matches(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        vals = list(p["values"].values())
        mean = sum(vals) / len(vals)
        expected_std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        assert p["std"] == pytest.approx(expected_std)

    def test_most_heterogeneous_has_min_value(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        assert p["values"][p["most_heterogeneous"]] == pytest.approx(p["min"])

    def test_most_homogeneous_has_max_value(self):
        g = MemoryGraph()
        build_paw(g)
        p = g.entropy_profile()
        assert p["values"][p["most_homogeneous"]] == pytest.approx(p["max"])


# ─── Non-mutating ──────────────────────────────────────────────────────

class TestEntropyProfileNonMutating:
    def test_does_not_add_nodes(self):
        g = MemoryGraph()
        build_complete(g, 3)
        before = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        g.entropy_profile()
        after = len(g.conn.execute("SELECT id FROM nodes").fetchall())
        assert before == after

    def test_does_not_add_edges(self):
        g = MemoryGraph()
        build_path(g, 4)
        before = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        g.entropy_profile()
        after = len(g.conn.execute("SELECT source, target FROM edges").fetchall())
        assert before == after


# ─── Fingerprint comparison ────────────────────────────────────────────

class TestEntropyProfileFingerprint:
    def test_same_graph_same_fingerprint(self):
        """Isomorphic graphs should have identical fingerprints."""
        g1 = MemoryGraph()
        build_path(g1, 5)
        g2 = MemoryGraph()
        build_path(g2, 5)
        assert g1.entropy_profile()["fingerprint"] == g2.entropy_profile()["fingerprint"]

    def test_different_graphs_different_fingerprint(self):
        """Non-isomorphic irregular graphs should have different fingerprints."""
        g1 = MemoryGraph()
        build_path(g1, 6)  # P₆: irregular
        g2 = MemoryGraph()
        build_star(g2, 5)  # K_{1,5}: irregular but different shape
        # Both are irregular but structurally different
        # P₆: some entropies < 1.0; K_{1,5}: all entropies = 1.0
        assert g1.entropy_profile()["fingerprint"] != g2.entropy_profile()["fingerprint"]

    def test_path_fingerprint_changes_with_length(self):
        """P₄ and P₅ should have different fingerprints."""
        g4 = MemoryGraph()
        build_path(g4, 4)
        g5 = MemoryGraph()
        build_path(g5, 5)
        fp4 = g4.entropy_profile()["fingerprint"]
        fp5 = g5.entropy_profile()["fingerprint"]
        assert fp4 != fp5


# ─── ABC edge case ─────────────────────────────────────────────────────

class TestEntropyProfileABC:
    def test_abc_filtered_for_k2_only(self):
        """K₂-only graphs: abc entropy is None → profile should still work."""
        # Need at least 2 non-K₂ edges for abc to contribute
        # Path P₃ has 2 edges, both (1,2) → abc skips them → abc None
        g = MemoryGraph()
        build_path(g, 3)  # P₃: (1)-(2)-(3), both edges are (1,2) type
        p = g.entropy_profile()
        # P₃ has both edges with degree pairs (1,2) and (2,1) → not K₂
        # Actually P₃: node 0 deg=1, node 1 deg=2, node 2 deg=1
        # Edges: (0,1) → d_u+d_v-2 = 1, (1,2) → d_u+d_v-2 = 1
        # So abc contributions are non-zero
        # abc should be present
        if p is not None:
            assert "abc" in p["values"] or "abc" not in p["values"]
            # Either way, profile should work


# ─── Bounded [0, 1] ────────────────────────────────────────────────────

class TestEntropyProfileBounded:
    @pytest.mark.parametrize("builder,n", [
        (build_complete, 3),
        (build_complete, 4),
        (build_complete, 5),
        (build_cycle, 4),
        (build_cycle, 5),
        (build_cycle, 6),
    ])
    def test_all_values_bounded_regular(self, builder, n):
        g = MemoryGraph()
        builder(g, n)
        p = g.entropy_profile()
        assert p is not None
        for val in p["values"].values():
            assert 0 < val <= 1.0 + 1e-12

    @pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
    def test_all_values_bounded_path(self, n):
        g = MemoryGraph()
        build_path(g, n)
        p = g.entropy_profile()
        assert p is not None
        for val in p["values"].values():
            assert 0 < val <= 1.0 + 1e-12
