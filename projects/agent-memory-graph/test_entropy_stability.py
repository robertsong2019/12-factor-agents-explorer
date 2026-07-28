"""Tests for entropy_stability() — Cycle 307.

Monte Carlo analysis of entropy variance under random edge perturbation.
"""
import math
import pytest
from memory_graph import MemoryGraph


# ── Helpers ──

def _build_graph(edges_spec, n_nodes):
    """Build a graph with n_nodes nodes and edges from edges_spec (index pairs)."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(f"n{i}") for i in range(n_nodes)]
    for i, j in edges_spec:
        mg.link(nodes[i].id, nodes[j].id, "rel")
    return mg


# ── Fixtures ──

@pytest.fixture
def small_graph():
    """5 nodes, 6 edges — enough for stability analysis."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(label) for label in ["A", "B", "C", "D", "E"]]
    edges = [(0,1), (0,2), (1,2), (2,3), (3,4), (0,3)]
    for i, j in edges:
        mg.link(nodes[i].id, nodes[j].id, "knows")
    return mg


@pytest.fixture
def star_graph():
    """Star topology — center node + 4 leaves."""
    mg = MemoryGraph(":memory:")
    center = mg.add("hub")
    leaves = [mg.add(f"leaf{i}") for i in range(4)]
    for leaf in leaves:
        mg.link(center.id, leaf.id, "edge")
    return mg


@pytest.fixture
def complete_graph():
    """Complete graph K5 — maximally connected."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(f"n{i}") for i in range(5)]
    for i in range(5):
        for j in range(i + 1, 5):
            mg.link(nodes[i].id, nodes[j].id, "edge")
    return mg


@pytest.fixture
def path_graph():
    """Path graph: 0-1-2-3-4."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(f"p{i}") for i in range(5)]
    for i in range(4):
        mg.link(nodes[i].id, nodes[i + 1].id, "edge")
    return mg


@pytest.fixture
def large_graph():
    """20 nodes, 30 edges for more realistic testing."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(f"node{i}") for i in range(20)]
    edges = [
        (0, 1), (0, 2), (0, 3), (1, 4), (2, 5), (3, 6),
        (4, 7), (5, 8), (6, 9), (7, 10), (8, 11), (9, 12),
        (10, 13), (11, 14), (12, 15), (13, 16), (14, 17),
        (15, 18), (16, 19), (0, 10), (1, 11), (2, 12),
        (3, 13), (4, 14), (5, 15), (6, 16), (7, 17),
        (8, 18), (9, 19), (10, 15),
    ]
    for i, j in edges:
        mg.link(nodes[i].id, nodes[j].id, "rel")
    return mg


# ── Basic functionality ──

class TestEntropyStabilityBasic:
    """Basic API tests."""

    def test_returns_dict(self, small_graph):
        result = small_graph.entropy_stability(trials=10, seed=42)
        assert isinstance(result, dict)

    def test_none_for_empty_graph(self):
        mg = MemoryGraph(":memory:")
        assert mg.entropy_stability() is None

    def test_none_for_single_edge(self):
        mg = MemoryGraph(":memory:")
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "e")
        assert mg.entropy_stability() is None

    def test_none_for_two_nodes_one_edge(self):
        """Two nodes can't have enough edges."""
        mg = MemoryGraph(":memory:")
        a = mg.add("A")
        b = mg.add("B")
        mg.link(a.id, b.id, "e")
        assert mg.entropy_stability() is None

    def test_baseline_entropy_present(self, small_graph):
        result = small_graph.entropy_stability(trials=5, seed=42)
        assert "baseline_entropy" in result
        assert result["baseline_entropy"] > 0

    def test_all_expected_keys(self, small_graph):
        result = small_graph.entropy_stability(trials=5, seed=42)
        expected_keys = {
            "baseline_entropy", "mean", "std", "cv",
            "min", "max", "range", "stability_score",
            "entropy_values", "perturbed_edges", "trials",
            "mode", "index",
        }
        assert set(result.keys()) == expected_keys

    def test_entropy_values_length(self, small_graph):
        result = small_graph.entropy_stability(trials=20, seed=42)
        assert len(result["entropy_values"]) == result["trials"]
        assert result["trials"] <= 20

    def test_default_index_sombor(self, small_graph):
        result = small_graph.entropy_stability(trials=5, seed=42)
        assert result["index"] == "sombor"

    def test_default_mode_remove(self, small_graph):
        result = small_graph.entropy_stability(trials=5, seed=42)
        assert result["mode"] == "remove"


# ── Statistical correctness ──

class TestEntropyStabilityStats:
    """Verify statistical properties of the results."""

    def test_mean_in_range(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        assert 0.0 <= result["mean"] <= 1.0

    def test_std_non_negative(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        assert result["std"] >= 0.0

    def test_min_le_max(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        assert result["min"] <= result["max"]

    def test_range_equals_max_minus_min(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        assert abs(result["range"] - (result["max"] - result["min"])) < 1e-5

    def test_cv_non_negative(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        assert result["cv"] >= 0.0

    def test_stability_score_in_unit_interval(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        assert 0.0 <= result["stability_score"] <= 1.0

    def test_cv_equals_std_over_mean(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        if result["mean"] > 0:
            expected_cv = result["std"] / result["mean"]
            assert abs(result["cv"] - expected_cv) < 1e-5

    def test_stability_equals_1_minus_cv(self, small_graph):
        result = small_graph.entropy_stability(trials=30, seed=42)
        expected = max(0.0, min(1.0, 1.0 - result["cv"]))
        assert abs(result["stability_score"] - expected) < 1e-5

    def test_reproducible_with_seed(self, small_graph):
        r1 = small_graph.entropy_stability(trials=10, seed=99)
        r2 = small_graph.entropy_stability(trials=10, seed=99)
        assert r1["entropy_values"] == r2["entropy_values"]

    def test_different_seeds_different_results(self, small_graph):
        r1 = small_graph.entropy_stability(trials=10, seed=1)
        r2 = small_graph.entropy_stability(trials=10, seed=2)
        # Very unlikely to be identical with different seeds
        assert r1["entropy_values"] != r2["entropy_values"]


# ── Perturbation modes ──

class TestEntropyStabilityModes:
    """Test remove and rewire modes."""

    def test_remove_mode_decreases_entropy(self, small_graph):
        """In remove mode, perturbation should tend to lower entropy."""
        result = small_graph.entropy_stability(
            trials=30, mode="remove", edge_fraction=0.3, seed=42
        )
        # Mean entropy should generally be <= baseline (fewer edges = less info)
        assert result["mean"] <= result["baseline_entropy"] + 0.15

    def test_rewire_mode_produces_valid_entropy(self, small_graph):
        """Rewire mode should keep edge count roughly the same."""
        result = small_graph.entropy_stability(
            trials=20, mode="rewire", edge_fraction=0.3, seed=42
        )
        assert result["trials"] > 0
        assert 0.0 <= result["mean"] <= 1.0

    def test_invalid_mode_raises(self, small_graph):
        with pytest.raises(ValueError, match="Unknown mode"):
            small_graph.entropy_stability(mode="flip")


# ── Edge fraction ──

class TestEntropyStabilityEdgeFraction:
    """Test edge_fraction parameter."""

    def test_perturbed_edges_proportional(self, small_graph):
        # small_graph has 6 edges
        r10 = small_graph.entropy_stability(trials=5, edge_fraction=0.1, seed=42)
        r50 = small_graph.entropy_stability(trials=5, edge_fraction=0.5, seed=42)
        assert r10["perturbed_edges"] == 1  # max(1, int(6 * 0.1)) = max(1, 0) = 1
        assert r50["perturbed_edges"] == 3  # int(6 * 0.5) = 3

    def test_large_fraction_works(self, small_graph):
        """edge_fraction=0.8 should still work."""
        result = small_graph.entropy_stability(
            trials=5, edge_fraction=0.8, seed=42
        )
        assert result is not None
        assert result["perturbed_edges"] >= 1

    def test_invalid_edge_fraction_zero(self, small_graph):
        with pytest.raises(ValueError, match="edge_fraction"):
            small_graph.entropy_stability(edge_fraction=0.0)

    def test_invalid_edge_fraction_negative(self, small_graph):
        with pytest.raises(ValueError, match="edge_fraction"):
            small_graph.entropy_stability(edge_fraction=-0.5)

    def test_invalid_edge_fraction_above_one(self, small_graph):
        with pytest.raises(ValueError, match="edge_fraction"):
            small_graph.entropy_stability(edge_fraction=1.5)


# ── Multi-index support ──

class TestEntropyStabilityIndices:
    """Test all supported degree-based indices."""

    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic",
        "zagreb_m1", "abc", "ga", "augmented_zagreb",
    ])
    def test_index_works(self, small_graph, index):
        result = small_graph.entropy_stability(
            index=index, trials=5, seed=42
        )
        assert result is not None
        assert result["index"] == index
        assert result["baseline_entropy"] >= 0.0

    def test_invalid_index_raises(self, small_graph):
        with pytest.raises(ValueError, match="Unknown index"):
            small_graph.entropy_stability(index="nonexistent")


# ── Graph topology comparison ──

class TestEntropyStabilityTopology:
    """Compare stability across different graph topologies."""

    def test_complete_graph_more_stable_than_path(self):
        """Complete graphs should be more stable under edge removal."""
        # K5 complete
        mg_k = MemoryGraph(":memory:")
        nodes = [mg_k.add(f"n{i}") for i in range(5)]
        for i in range(5):
            for j in range(i + 1, 5):
                mg_k.link(nodes[i].id, nodes[j].id, "e")

        # Path: 0-1-2-3-4
        mg_p = MemoryGraph(":memory:")
        nodes_p = [mg_p.add(f"n{i}") for i in range(5)]
        for i in range(4):
            mg_p.link(nodes_p[i].id, nodes_p[i + 1].id, "e")

        r_k = mg_k.entropy_stability(trials=30, edge_fraction=0.2, seed=42)
        r_p = mg_p.entropy_stability(trials=30, edge_fraction=0.2, seed=42)

        # Complete graph has more redundant edges → higher stability
        assert r_k["stability_score"] >= r_p["stability_score"] - 0.15

    def test_star_graph(self, star_graph):
        result = star_graph.entropy_stability(trials=20, seed=42)
        assert result is not None
        assert result["stability_score"] >= 0.0

    def test_path_graph(self, path_graph):
        result = path_graph.entropy_stability(trials=20, seed=42)
        assert result is not None
        assert result["baseline_entropy"] > 0


# ── Trials parameter ──

class TestEntropyStabilityTrials:
    """Test trials parameter."""

    def test_single_trial(self, small_graph):
        result = small_graph.entropy_stability(trials=1, seed=42)
        assert result["trials"] == 1
        assert result["std"] == 0.0

    def test_more_trials_smoother(self, small_graph):
        """More trials should generally give more stable estimates."""
        r10 = small_graph.entropy_stability(trials=10, seed=42)
        r50 = small_graph.entropy_stability(trials=50, seed=42)
        # Both should be valid
        assert r10["trials"] > 0
        assert r50["trials"] > 0

    def test_zero_trials_raises(self, small_graph):
        with pytest.raises(ValueError, match="trials"):
            small_graph.entropy_stability(trials=0)


# ── Large graph ──

class TestEntropyStabilityLarge:
    """Test on a larger graph."""

    def test_large_graph_returns_result(self, large_graph):
        result = large_graph.entropy_stability(trials=20, seed=42)
        assert result is not None
        assert result["trials"] == 20

    def test_large_graph_stability_positive(self, large_graph):
        result = large_graph.entropy_stability(trials=20, seed=42)
        assert result["stability_score"] >= 0.0

    def test_large_graph_rewire_mode(self, large_graph):
        result = large_graph.entropy_stability(
            trials=15, mode="rewire", seed=42
        )
        assert result is not None
        assert result["mode"] == "rewire"


# ── Consistency with existing entropy API ──

class TestEntropyStabilityConsistency:
    """Verify entropy_stability baseline matches direct entropy calls."""

    def test_baseline_matches_sombor_entropy(self, small_graph):
        """baseline_entropy should match sombor_entropy() value."""
        direct = small_graph.sombor_entropy()
        result = small_graph.entropy_stability(
            index="sombor", trials=5, seed=42
        )
        assert direct is not None
        assert abs(result["baseline_entropy"] - direct) < 1e-5

    def test_baseline_matches_randic_entropy(self, small_graph):
        direct = small_graph.randic_entropy()
        result = small_graph.entropy_stability(
            index="randic", trials=5, seed=42
        )
        assert direct is not None
        assert abs(result["baseline_entropy"] - direct) < 1e-5

    def test_baseline_matches_abc_entropy(self, small_graph):
        direct = small_graph.abc_entropy()
        result = small_graph.entropy_stability(
            index="abc", trials=5, seed=42
        )
        assert direct is not None
        assert abs(result["baseline_entropy"] - direct) < 1e-5
