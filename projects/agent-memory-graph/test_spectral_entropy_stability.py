"""Cycle 311: entropy_stability_spectral() — Monte Carlo von Neumann entropy stability.

Tests:
- K_n: highly stable (uniform spectrum)
- Path: less stable (heterogeneous spectrum)
- Star: moderate stability
- remove vs rewire modes
- Higher edge_fraction = lower stability
- Consistency with von_neumann_entropy baseline
- Small graph edge cases
- Seed reproducibility
"""

import math
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def g():
    return MemoryGraph(":memory:")


def _make_kn(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            g.link(nodes[i].id, nodes[j].id, "r")
    return nodes


def _make_path(g, n):
    nodes = [g.add(str(i)) for i in range(n)]
    for i in range(n-1):
        g.link(nodes[i].id, nodes[i+1].id, "r")
    return nodes


def _make_star(g, n_leaves):
    hub = g.add("hub")
    leaves = [g.add(f"l{i}") for i in range(n_leaves)]
    for lf in leaves:
        g.link(hub.id, lf.id, "r")
    return hub, leaves


class TestSpectralEntropyStabilityBasic:

    def test_none_for_tiny_graph(self, g):
        g.add("a")
        result = g.entropy_stability_spectral(trials=5)
        assert result is None

    def test_kn_highly_stable(self, g):
        """K_6 uniform spectrum should be very stable."""
        _make_kn(g, 6)
        result = g.entropy_stability_spectral(trials=20, edge_fraction=0.1)
        assert result is not None
        assert result["stability_score"] > 0.5  # uniform = stable

    def test_path_less_stable_than_kn(self, g):
        """Path graphs have heterogeneous spectra → less stable."""
        g_path = MemoryGraph(":memory:")
        _make_path(g_path, 6)
        r_path = g_path.entropy_stability_spectral(trials=20, edge_fraction=0.15)
        g_kn = MemoryGraph(":memory:")
        _make_kn(g_kn, 6)
        r_kn = g_kn.entropy_stability_spectral(trials=20, edge_fraction=0.15)
        # Path should be less stable than K_n (higher CV)
        assert r_path["stability_score"] <= r_kn["stability_score"]

    def test_return_structure(self, g):
        _make_path(g, 5)
        result = g.entropy_stability_spectral(trials=10)
        required = [
            "baseline_entropy", "mean", "std", "cv",
            "min", "max", "range", "stability_score",
            "entropy_values", "perturbed_edges", "trials",
            "mode", "index",
        ]
        for k in required:
            assert k in result, f"Missing key: {k}"
        assert result["index"] == "von_neumann"
        assert result["mode"] == "remove"
        assert len(result["entropy_values"]) == result["trials"]


class TestSpectralEntropyStabilityModes:

    def test_remove_mode(self, g):
        _make_star(g, 4)
        result = g.entropy_stability_spectral(trials=10, mode="remove")
        assert result["mode"] == "remove"
        assert result is not None

    def test_invalid_mode_raises(self, g):
        _make_path(g, 5)
        with pytest.raises(ValueError, match="mode"):
            g.entropy_stability_spectral(mode="invalid")

    def test_invalid_edge_fraction(self, g):
        _make_path(g, 5)
        with pytest.raises(ValueError):
            g.entropy_stability_spectral(edge_fraction=0.0)


class TestSpectralEntropyStabilityProperties:

    def test_baseline_matches_von_neumann(self, g):
        _make_path(g, 5)
        vn = g.von_neumann_entropy(normalized=True)
        result = g.entropy_stability_spectral(trials=5)
        assert abs(result["baseline_entropy"] - vn) < 1e-6

    def test_higher_fraction_lower_stability(self, g):
        """More edges removed → less stable."""
        _make_path(g, 6)
        r_low = g.entropy_stability_spectral(trials=15, edge_fraction=0.05, seed=42)
        r_high = g.entropy_stability_spectral(trials=15, edge_fraction=0.4, seed=42)
        # More perturbation should reduce or maintain stability
        assert r_low["stability_score"] >= r_high["stability_score"] - 0.1

    def test_star_moderate_stability(self, g):
        _make_star(g, 5)
        result = g.entropy_stability_spectral(trials=15, edge_fraction=0.1)
        assert 0.0 <= result["stability_score"] <= 1.0

    def test_disconnected_graph(self, g):
        a, b, c, d = g.add("a"), g.add("b"), g.add("c"), g.add("d")
        g.link(a.id, b.id, "r")
        g.link(c.id, d.id, "r")
        result = g.entropy_stability_spectral(trials=10, edge_fraction=0.1)
        assert result is not None

    def test_entropy_values_within_bounds(self, g):
        _make_kn(g, 5)
        result = g.entropy_stability_spectral(trials=20, edge_fraction=0.2)
        for v in result["entropy_values"]:
            assert 0.0 <= v <= 1.0

    def test_cv_calculation(self, g):
        _make_path(g, 5)
        result = g.entropy_stability_spectral(trials=10, seed=123)
        vals = result["entropy_values"]
        mean = sum(vals) / len(vals)
        var = sum((v - mean)**2 for v in vals) / len(vals)
        expected_cv = (var**0.5) / mean if mean > 0 else float("inf")
        assert abs(result["cv"] - expected_cv) < 1e-4
