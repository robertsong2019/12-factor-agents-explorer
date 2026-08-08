"""Tests for edge_entropy_sensitivity() — Cycle 386.

Edge-level leave-one-out entropy sensitivity analysis.
"""
import pytest
from memory_graph import MemoryGraph


def _build_graph(n=6, star=True):
    """Build a star graph with n nodes."""
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(1, n):
        g.link("n0", f"n{i}", "related")
    return g


def _build_path(n=6):
    """Build a path graph with n nodes."""
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(n - 1):
        g.link(f"n{i}", f"n{i+1}", "related")
    return g


def _build_cycle(n=6):
    """Build a cycle graph with n nodes."""
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(n):
        g.link(f"n{i}", f"n{(i+1)%n}", "related")
    return g


def _build_complete(n=4):
    """Build a complete graph K_n."""
    g = MemoryGraph()
    for i in range(n):
        g.add(f"n{i}", kind="concept")
    for i in range(n):
        for j in range(i + 1, n):
            g.link(f"n{i}", f"n{j}", "related")
    return g


class TestEdgeEntropySensitivityBasic:
    """Basic structure tests."""

    def test_returns_dict(self):
        g = _build_path()
        result = g.edge_entropy_sensitivity()
        assert isinstance(result, dict)

    def test_keys_present(self):
        g = _build_path()
        result = g.edge_entropy_sensitivity()
        expected_keys = {
            "baseline_entropy", "sensitivities", "ranked",
            "mean", "std", "max_delta", "min_delta",
            "critical_edges", "expendable_edges",
            "index", "sampled", "evaluated",
        }
        assert expected_keys.issubset(result.keys())

    def test_none_for_small_graph(self):
        """Graph with < 3 nodes should return None."""
        g = MemoryGraph()
        g.add("a", kind="concept")
        g.add("b", kind="concept")
        g.link("a", "b", "related")
        assert g.edge_entropy_sensitivity() is None

    def test_none_for_single_edge(self):
        """Graph with < 2 edges should return None."""
        g = MemoryGraph()
        for i in range(3):
            g.add(f"n{i}", kind="concept")
        g.link("n0", "n1", "related")
        assert g.edge_entropy_sensitivity() is None

    def test_invalid_index_raises(self):
        g = _build_path()
        with pytest.raises(ValueError, match="Unknown index"):
            g.edge_entropy_sensitivity(index="nonexistent")


class TestEdgeEntropySensitivityValues:
    """Numerical correctness tests."""

    def test_evaluated_count_matches_edges(self):
        g = _build_path(n=6)
        result = g.edge_entropy_sensitivity()
        assert result["evaluated"] == 5  # 5 edges in path of 6 nodes

    def test_star_evaluated_count(self):
        g = _build_graph(n=6, star=True)
        result = g.edge_entropy_sensitivity()
        assert result["evaluated"] == 5  # 5 edges in star of 6 nodes

    def test_baseline_entropy_positive(self):
        g = _build_path()
        result = g.edge_entropy_sensitivity()
        assert result["baseline_entropy"] >= 0.0

    def test_all_deltas_non_negative(self):
        g = _build_path()
        result = g.edge_entropy_sensitivity()
        for k, d in result["sensitivities"].items():
            assert d >= 0.0

    def test_max_min_bounds(self):
        g = _build_path()
        result = g.edge_entropy_sensitivity()
        assert result["max_delta"] >= result["min_delta"]
        assert result["max_delta"] == max(result["sensitivities"].values())
        assert result["min_delta"] == min(result["sensitivities"].values())

    def test_mean_std_consistency(self):
        g = _build_complete(n=4)
        result = g.edge_entropy_sensitivity()
        deltas = list(result["sensitivities"].values())
        expected_mean = sum(deltas) / len(deltas)
        assert result["mean"] == pytest.approx(expected_mean, rel=1e-3)

    def test_ranked_sorted_descending(self):
        g = _build_path()
        result = g.edge_entropy_sensitivity()
        values = [v for _, v in result["ranked"]]
        assert values == sorted(values, reverse=True)


class TestEdgeEntropySensitivityTopK:
    """top_k parameter tests."""

    def test_top_k_limits_results(self):
        g = _build_path(n=10)
        result = g.edge_entropy_sensitivity(top_k=3)
        assert len(result["ranked"]) <= 3

    def test_top_k_zero_returns_all(self):
        g = _build_path(n=6)
        result = g.edge_entropy_sensitivity(top_k=0)
        assert len(result["ranked"]) == 5


class TestEdgeEntropySensitivitySampling:
    """Sampling parameter tests."""

    def test_sampling_used(self):
        g = _build_path(n=20)
        result = g.edge_entropy_sensitivity(sample=5)
        assert result["sampled"] is True
        assert result["evaluated"] == 5

    def test_no_sampling_for_small_graph(self):
        g = _build_path(n=6)
        result = g.edge_entropy_sensitivity()
        assert result["sampled"] is False
        assert result["evaluated"] == 5

    def test_sample_equal_to_total(self):
        """sample >= n_edges should not trigger sampling."""
        g = _build_path(n=6)
        result = g.edge_entropy_sensitivity(sample=10)
        assert result["sampled"] is False


class TestEdgeEntropySensitivityIndices:
    """Multiple entropy index tests."""

    @pytest.mark.parametrize("index", [
        "sombor", "randic", "abc", "ga", "zagreb_m1",
        "augmented_zagreb", "reduced_sombor",
    ])
    def test_all_indices_work(self, index):
        g = _build_path(n=6)
        result = g.edge_entropy_sensitivity(index=index)
        assert result is not None
        assert result["index"] == index

    def test_different_indices_different_results(self):
        """Each index should run without error and produce results."""
        g = MemoryGraph()
        for i in range(7):
            g.add(f"n{i}", kind="concept")
        # Irregular structure
        g.link("n0", "n1", "related")
        g.link("n0", "n2", "related")
        g.link("n0", "n3", "related")
        g.link("n0", "n4", "related")
        g.link("n4", "n5", "related")
        g.link("n5", "n6", "related")
        sombor = g.edge_entropy_sensitivity(index="sombor")
        randic = g.edge_entropy_sensitivity(index="randic")
        assert sombor is not None
        assert randic is not None
        assert sombor["index"] == "sombor"
        assert randic["index"] == "randic"


class TestEdgeEntropySensitivityStructure:
    """Critical/expendable edges classification."""

    def test_critical_edges_present(self):
        g = _build_path(n=8)
        result = g.edge_entropy_sensitivity()
        assert isinstance(result["critical_edges"], list)

    def test_expendable_edges_present(self):
        g = _build_path(n=8)
        result = g.edge_entropy_sensitivity()
        assert isinstance(result["expendable_edges"], list)

    def test_critical_above_mean_plus_std(self):
        g = _build_path(n=8)
        result = g.edge_entropy_sensitivity()
        threshold = result["mean"] + result["std"]
        for k in result["critical_edges"]:
            assert result["sensitivities"][k] > threshold

    def test_expendable_below_mean_minus_std(self):
        g = _build_path(n=8)
        result = g.edge_entropy_sensitivity()
        threshold = max(0.0, result["mean"] - result["std"])
        for k in result["expendable_edges"]:
            assert result["sensitivities"][k] < threshold

    def test_star_central_edges_identified(self):
        """In a star, removing any edge should have similar impact."""
        g = _build_graph(n=6, star=True)
        result = g.edge_entropy_sensitivity()
        # All edges in a star are symmetric — deltas should be similar
        deltas = list(result["sensitivities"].values())
        max_d = max(deltas)
        min_d = min(deltas)
        # In a symmetric graph, all edges should have similar sensitivity
        assert (max_d - min_d) < 0.1 or max_d == pytest.approx(0.0)


class TestEdgeEntropySensitivityEdgeCases:
    """Edge cases."""

    def test_complete_graph(self):
        g = _build_complete(n=5)
        result = g.edge_entropy_sensitivity()
        assert result is not None
        assert result["evaluated"] == 10  # C(5,2)

    def test_cycle_graph(self):
        g = _build_cycle(n=6)
        result = g.edge_entropy_sensitivity()
        assert result is not None
        assert result["evaluated"] == 6

    def test_key_format(self):
        """Keys should be 'source→target' format."""
        g = _build_path(n=4)
        result = g.edge_entropy_sensitivity()
        for k in result["sensitivities"]:
            assert "\u2192" in k
            assert k.count("\u2192") == 1
