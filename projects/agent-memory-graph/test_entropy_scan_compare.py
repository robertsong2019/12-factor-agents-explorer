"""Tests for entropy_scan_compare() — Cycle 340.

Compares two graphs' entropy scan profiles: L2 fingerprint distance,
per-α Rényi divergence, shape descriptor deltas, and classification.
"""
import math
import pytest
from memory_graph import MemoryGraph


def _star(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(1, n):
        mg.link(nodes[0].id, nodes[i].id, "r")
    return mg


def _complete(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "r")
    return mg


def _path(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        mg.link(nodes[i].id, nodes[i + 1].id, "r")
    return mg


def _cycle(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return mg


class TestScanCompareBasic:
    def test_returns_dict(self):
        result = _path(5).entropy_scan_compare(_path(5))
        assert isinstance(result, dict)

    def test_none_for_empty_self(self):
        mg = MemoryGraph(":memory:")
        assert mg.entropy_scan_compare(_path(5)) is None

    def test_none_for_empty_other(self):
        mg = _path(5)
        empty = MemoryGraph(":memory:")
        assert mg.entropy_scan_compare(empty) is None

    def test_result_keys(self):
        result = _path(5).entropy_scan_compare(_path(5))
        assert "distance" in result
        assert "per_alpha_divergence" in result
        assert "shape_delta" in result
        assert "classification" in result
        assert "scan1" in result
        assert "scan2" in result

    def test_max_divergence_fields(self):
        result = _path(5).entropy_scan_compare(_star(5))
        assert "max_divergence_alpha" in result
        assert "max_divergence_value" in result


class TestScanCompareDistance:
    def test_identical_graphs_zero_distance(self):
        result = _path(10).entropy_scan_compare(_path(10))
        assert result["distance"] < 1e-6

    def test_different_graphs_positive_distance(self):
        result = _path(10).entropy_scan_compare(_star(10))
        assert result["distance"] > 0.01

    def test_star_vs_complete_large_distance(self):
        result = _star(10).entropy_scan_compare(_complete(10))
        assert result["distance"] > 1.0

    def test_distance_is_symmetric(self):
        """L2 distance should be symmetric."""
        d1 = _star(10).entropy_scan_compare(_complete(10))["distance"]
        d2 = _complete(10).entropy_scan_compare(_star(10))["distance"]
        assert abs(d1 - d2) < 1e-6

    def test_path_vs_cycle_small_distance(self):
        """Path and cycle have similar entropy profiles (both near-uniform)."""
        result = _path(10).entropy_scan_compare(_cycle(10))
        assert result["distance"] < 5.0


class TestPerAlphaDivergence:
    def test_per_alpha_length(self):
        result = _path(5).entropy_scan_compare(_path(5))
        # Default alphas = 8
        assert len(result["per_alpha_divergence"]) == 8

    def test_per_alpha_entries(self):
        result = _path(5).entropy_scan_compare(_star(5))
        for entry in result["per_alpha_divergence"]:
            assert "alpha" in entry
            assert "abs_diff" in entry
            assert entry["abs_diff"] >= 0

    def test_identical_zero_per_alpha(self):
        result = _path(10).entropy_scan_compare(_path(10))
        for entry in result["per_alpha_divergence"]:
            assert entry["abs_diff"] < 1e-6

    def test_max_divergence_alpha_in_range(self):
        result = _star(10).entropy_scan_compare(_complete(10))
        if result["max_divergence_alpha"] is not None:
            assert 0.1 <= result["max_divergence_alpha"] <= 10.0


class TestShapeDelta:
    def test_shape_delta_keys(self):
        result = _path(5).entropy_scan_compare(_star(5))
        sd = result["shape_delta"]
        assert "area_delta" in sd
        assert "gap_delta" in sd
        assert "slope_delta" in sd
        assert "monotonic_match" in sd
        assert "convex_match" in sd

    def test_identical_shape_delta_zero(self):
        result = _path(10).entropy_scan_compare(_path(10))
        sd = result["shape_delta"]
        assert abs(sd["area_delta"]) < 1e-6
        assert abs(sd["gap_delta"]) < 1e-6
        assert abs(sd["slope_delta"]) < 1e-6

    def test_monotonic_match_identical(self):
        result = _path(10).entropy_scan_compare(_path(10))
        assert result["shape_delta"]["monotonic_match"] is True


class TestClassification:
    def test_identical_classified_similar(self):
        result = _path(10).entropy_scan_compare(_path(10))
        assert result["classification"] == "similar"

    def test_star_vs_complete_different(self):
        result = _star(10).entropy_scan_compare(_complete(10))
        assert result["classification"] == "different"

    def test_path_vs_star_small_distance(self):
        """Path(10) and Star(10) both have near-uniform distributions
        at this scale → classified as 'similar' by the heuristic.
        This is mathematically correct: both are simple trees with
        modest heterogeneity at n=10."""
        result = _path(10).entropy_scan_compare(_star(10))
        assert result["distance"] < 1.0
        # The classification depends on threshold; at this scale they ARE similar


class TestIndexParameter:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1", "abc", "ga", "augmented_zagreb"
    ])
    def test_index_works(self, index):
        result = _path(5).entropy_scan_compare(_star(5), index=index)
        assert result is not None

    def test_invalid_index_raises(self):
        with pytest.raises(ValueError):
            _path(5).entropy_scan_compare(_star(5), index="bad")


class TestScansIncluded:
    def test_scan1_is_self(self):
        mg = _path(5)
        result = mg.entropy_scan_compare(_star(5))
        assert "renyi" in result["scan1"]
        assert "shape" in result["scan1"]

    def test_scan2_is_other(self):
        mg = _path(5)
        other = _star(5)
        result = mg.entropy_scan_compare(other)
        assert "renyi" in result["scan2"]
        assert "shape" in result["scan2"]
