"""Tests for entropy_fingerprint() and fingerprint_distance() — Cycle 314.

Compact entropy feature vector for graph classification and similarity.
Combines degree-based, spectral, and ego-local entropy into a single vector.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ── Graph builders (shared pattern) ──

def build_complete(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return g


def build_path(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        g.link(nodes[i].id, nodes[i + 1].id, "r")
    return g


def build_cycle(n):
    g = MemoryGraph()
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return g


def build_star(leaves):
    g = MemoryGraph()
    hub = g.add("hub")
    for i in range(leaves):
        leaf = g.add(f"leaf{i}")
        g.link(hub.id, leaf.id, "r")
    return g


def build_empty():
    return MemoryGraph()


def build_single():
    g = MemoryGraph()
    g.add("solo")
    return g


# ── Edge cases ──

class TestFingerprintEdgeCases:
    def test_empty_graph_returns_none(self):
        assert build_empty().entropy_fingerprint() is None

    def test_single_node_returns_none(self):
        assert build_single().entropy_fingerprint() is None

    def test_two_nodes_returns_result(self):
        g = MemoryGraph()
        a = g.add("A")
        b = g.add("B")
        g.link(a.id, b.id, "r")
        result = g.entropy_fingerprint()
        assert result is not None


# ── Basic structure ──

class TestFingerprintStructure:
    def test_returns_dict_with_required_keys(self):
        g = build_complete(4)
        result = g.entropy_fingerprint()
        assert "vector" in result
        assert "labels" in result
        assert "dimension" in result
        assert "indices" in result

    def test_vector_length_matches_labels(self):
        g = build_star(5)
        result = g.entropy_fingerprint()
        assert len(result["vector"]) == len(result["labels"])

    def test_dimension_matches_vector_length(self):
        g = build_path(5)
        result = g.entropy_fingerprint()
        assert result["dimension"] == len(result["vector"])

    def test_default_indices(self):
        g = build_complete(3)
        result = g.entropy_fingerprint()
        assert result["indices"] == ["sombor", "randic", "zagreb_m1", "abc"]

    def test_custom_indices(self):
        g = build_complete(3)
        result = g.entropy_fingerprint(indices=["sombor", "randic"])
        assert result["indices"] == ["sombor", "randic"]
        # Vector has 2 degree + 5 spectral (vne + 4 profile) = 7 dims
        assert result["dimension"] == 7

    def test_all_values_are_floats(self):
        g = build_complete(4)
        result = g.entropy_fingerprint()
        for v in result["vector"]:
            assert isinstance(v, (int, float))


# ── Spectral inclusion ──

class TestFingerprintSpectral:
    def test_include_spectral_adds_dimensions(self):
        g = build_complete(4)
        without_spec = g.entropy_fingerprint(include_spectral=False)
        with_spec = g.entropy_fingerprint(include_spectral=True)
        assert with_spec["dimension"] > without_spec["dimension"]

    def test_spectral_labels_present(self):
        g = build_complete(4)
        result = g.entropy_fingerprint(include_spectral=True)
        assert "von_neumann" in result["labels"]
        assert "algebraic_connectivity" in result["labels"]

    def test_spectral_excluded(self):
        g = build_complete(4)
        result = g.entropy_fingerprint(include_spectral=False)
        assert "von_neumann" not in result["labels"]


# ── Ego inclusion ──

class TestFingerprintEgo:
    def test_include_ego_adds_dimensions(self):
        g = build_complete(4)
        without_ego = g.entropy_fingerprint(include_ego=False)
        with_ego = g.entropy_fingerprint(include_ego=True)
        assert with_ego["dimension"] > without_ego["dimension"]

    def test_ego_labels_present(self):
        g = build_complete(4)
        result = g.entropy_fingerprint(include_ego=True)
        assert "ego_mean" in result["labels"]
        assert "ego_std" in result["labels"]
        assert "ego_uniformity" in result["labels"]
        assert "ego_frac_isolated" in result["labels"]

    def test_ego_excluded_by_default(self):
        g = build_complete(4)
        result = g.entropy_fingerprint()
        assert "ego_mean" not in result["labels"]


# ── Fingerprint distance ──

class TestFingerprintDistance:
    def test_identical_graphs_zero_distance(self):
        g1 = build_complete(5)
        g2 = build_complete(5)
        dist = g1.fingerprint_distance(g2)
        assert dist is not None
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_different_graphs_positive_distance(self):
        g1 = build_complete(5)
        g2 = build_path(5)
        dist = g1.fingerprint_distance(g2)
        assert dist is not None
        assert dist > 0.0

    def test_star_vs_path_positive_distance(self):
        g1 = build_star(5)
        g2 = build_path(5)
        dist = g1.fingerprint_distance(g2)
        assert dist is not None
        assert dist > 0.0

    def test_same_graph_type_closer_than_different(self):
        """Two complete graphs should be closer than complete vs star."""
        k5_1 = build_complete(5)
        k5_2 = build_complete(5)
        star = build_star(5)
        same_dist = k5_1.fingerprint_distance(k5_2)
        diff_dist = k5_1.fingerprint_distance(star)
        assert same_dist < diff_dist

    def test_distance_symmetric(self):
        """fingerprint_distance(a, b) == fingerprint_distance(b, a)."""
        g1 = build_complete(5)
        g2 = build_star(5)
        d12 = g1.fingerprint_distance(g2)
        d21 = g2.fingerprint_distance(g1)
        assert d12 == pytest.approx(d21, abs=1e-6)

    def test_distance_non_negative(self):
        g1 = build_complete(4)
        g2 = build_path(4)
        dist = g1.fingerprint_distance(g2)
        assert dist >= 0.0

    def test_distance_none_for_small_graph(self):
        g1 = build_complete(1)
        g2 = build_complete(2)
        dist = g1.fingerprint_distance(g2)
        assert dist is None

    def test_distance_with_ego(self):
        g1 = build_complete(5)
        g2 = build_path(5)
        dist = g1.fingerprint_distance(g2, include_ego=True)
        assert dist is not None
        assert dist > 0.0


# ── Fingerprint properties ──

class TestFingerprintProperties:
    def test_complete_graphs_same_fingerprint(self):
        """Same-size complete graphs should have identical fingerprints."""
        g1 = build_complete(5)
        g2 = build_complete(5)
        fp1 = g1.entropy_fingerprint()
        fp2 = g2.entropy_fingerprint()
        assert fp1["vector"] == pytest.approx(fp2["vector"], abs=1e-6)

    def test_different_size_different_fingerprint(self):
        """K4 and K6 should have different fingerprints."""
        g1 = build_complete(4)
        g2 = build_complete(6)
        fp1 = g1.entropy_fingerprint()
        fp2 = g2.entropy_fingerprint()
        # At least one dimension should differ
        diffs = [abs(a - b) for a, b in zip(fp1["vector"], fp2["vector"])]
        assert max(diffs) > 0.01

    def test_path_vs_star_different(self):
        g1 = build_path(5)
        g2 = build_star(5)
        fp1 = g1.entropy_fingerprint()
        fp2 = g2.entropy_fingerprint()
        diffs = [abs(a - b) for a, b in zip(fp1["vector"], fp2["vector"])]
        assert max(diffs) > 0.01

    def test_repeated_call_same_result(self):
        g = build_complete(4)
        fp1 = g.entropy_fingerprint()
        fp2 = g.entropy_fingerprint()
        assert fp1["vector"] == fp2["vector"]


# ── Custom index selection ──

class TestFingerprintCustomIndices:
    def test_single_index(self):
        g = build_complete(3)
        result = g.entropy_fingerprint(indices=["sombor"])
        assert result["dimension"] > 0

    def test_all_indices(self):
        g = build_complete(4)
        result = g.entropy_fingerprint(indices=[
            "sombor", "reduced_sombor", "randic", "zagreb_m1",
            "abc", "ga", "augmented_zagreb"
        ])
        # 7 degree entropies + 5 spectral = 12
        assert result["dimension"] == 12

    def test_unknown_index_yields_zero(self):
        g = build_complete(3)
        result = g.entropy_fingerprint(indices=["sombor", "unknown_idx"])
        # unknown_idx should contribute 0.0
        idx = result["labels"].index("shannon_unknown_idx")
        assert result["vector"][idx] == 0.0


# ── Large graph ──

class TestFingerprintLargeGraph:
    def test_100_nodes_efficient(self):
        import random
        random.seed(42)
        g = MemoryGraph()
        nodes = [g.add(str(i)) for i in range(100)]
        for i in range(1, 100):
            j = random.randint(0, i - 1)
            g.link(nodes[i].id, nodes[j].id, "r")
        result = g.entropy_fingerprint()
        assert result is not None
        assert result["dimension"] > 0

    def test_fingerprint_distance_large_graphs(self):
        import random
        random.seed(42)
        g1 = MemoryGraph()
        nodes = [g1.add(str(i)) for i in range(50)]
        for i in range(1, 50):
            j = random.randint(0, i - 1)
            g1.link(nodes[i].id, nodes[j].id, "r")

        g2 = MemoryGraph()
        nodes2 = [g2.add(str(i)) for i in range(50)]
        for i in range(1, 50):
            j = random.randint(100, i + 99)  # different topology
            if j < 50:
                g2.link(nodes2[i].id, nodes2[j].id, "r")

        dist = g1.fingerprint_distance(g2)
        assert dist is not None
        assert dist >= 0.0
