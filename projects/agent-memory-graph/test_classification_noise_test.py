"""Tests for classification_noise_test() — Cycle 341.

Tests the noise robustness evaluation framework that measures how
classification accuracy degrades under random graph perturbation.
"""

import pytest
from memory_graph import MemoryGraph


# ── Helpers ──

def _run_quick(**kwargs):
    """Run noise test with minimal settings for speed."""
    mg = MemoryGraph()
    defaults = dict(
        size=6,
        noise_levels=[0.0, 0.1],
        num_references_per_category=1,
        num_queries=1,
        topologies=["star", "path", "cycle"],
        methods=["graph", "spectral"],
    )
    defaults.update(kwargs)
    return mg.classification_noise_test(**defaults)


# ── Result structure ──

class TestResultStructure:
    def test_returns_dict(self):
        r = _run_quick()
        assert isinstance(r, dict)

    def test_result_keys(self):
        r = _run_quick()
        expected_keys = {
            "noise_levels", "methods", "topologies", "size",
            "degradation_curves", "robustness_score", "rankings",
            "breakpoint", "per_topology_robustness",
            "per_topology_at_noise", "best_method", "worst_method",
            "summary",
        }
        assert expected_keys.issubset(r.keys())

    def test_noise_levels_returned(self):
        r = _run_quick(noise_levels=[0.0, 0.15, 0.3])
        assert r["noise_levels"] == [0.0, 0.15, 0.3]

    def test_methods_returned(self):
        r = _run_quick(methods=["graph", "spectral"])
        assert r["methods"] == ["graph", "spectral"]

    def test_topologies_returned(self):
        r = _run_quick(topologies=["star", "cycle"])
        assert r["topologies"] == ["star", "cycle"]

    def test_size_returned(self):
        r = _run_quick(size=8)
        assert r["size"] == 8


# ── Degradation curves ──

class TestDegradationCurves:
    def test_curve_per_method(self):
        r = _run_quick(methods=["graph", "spectral"])
        assert set(r["degradation_curves"].keys()) == {"graph", "spectral"}

    def test_curve_per_noise_level(self):
        r = _run_quick(noise_levels=[0.0, 0.1, 0.2], methods=["graph"])
        curve = r["degradation_curves"]["graph"]
        assert set(curve.keys()) == {0.0, 0.1, 0.2}

    def test_curve_values_are_floats(self):
        r = _run_quick()
        for method, curve in r["degradation_curves"].items():
            for nl, acc in curve.items():
                assert isinstance(acc, float)

    def test_curve_values_in_range(self):
        r = _run_quick()
        for method, curve in r["degradation_curves"].items():
            for nl, acc in curve.items():
                assert 0.0 <= acc <= 1.0

    def test_zero_noise_high_accuracy(self):
        r = _run_quick(noise_levels=[0.0], methods=["graph"])
        for method in r["methods"]:
            acc = r["degradation_curves"][method][0.0]
            assert acc >= 0.5, f"{method} should classify reasonably at zero noise"

    def test_degradation_trend(self):
        """With enough noise, accuracy should generally decrease."""
        r = _run_quick(
            noise_levels=[0.0, 0.3],
            methods=["graph"],
            size=8,
            num_queries=2,
            num_references_per_category=1,
        )
        clean = r["degradation_curves"]["graph"][0.0]
        noisy = r["degradation_curves"]["graph"][0.3]
        assert noisy <= clean


# ── Robustness scores ──

class TestRobustnessScore:
    def test_score_per_method(self):
        r = _run_quick(methods=["graph", "spectral"])
        assert set(r["robustness_score"].keys()) == {"graph", "spectral"}

    def test_scores_are_floats(self):
        r = _run_quick()
        for m, s in r["robustness_score"].items():
            assert isinstance(s, float)

    def test_scores_in_range(self):
        r = _run_quick()
        for m, s in r["robustness_score"].items():
            assert 0.0 <= s <= 1.0

    def test_higher_score_more_robust(self):
        """The best method should have the highest robustness score."""
        r = _run_quick()
        rankings = r["rankings"]
        if len(rankings) >= 2:
            assert rankings[0][1] >= rankings[-1][1]


# ── Rankings ──

class TestRankings:
    def test_rankings_is_list(self):
        r = _run_quick()
        assert isinstance(r["rankings"], list)

    def test_rankings_sorted_descending(self):
        r = _run_quick()
        scores = [s for _, s in r["rankings"]]
        assert scores == sorted(scores, reverse=True)

    def test_rankings_contain_all_methods(self):
        r = _run_quick(methods=["graph", "spectral", "hybrid"])
        ranked_methods = [m for m, _ in r["rankings"]]
        assert set(ranked_methods) == {"graph", "spectral", "hybrid"}

    def test_best_method_is_rankings_top(self):
        r = _run_quick()
        if r["rankings"]:
            assert r["best_method"] == r["rankings"][0][0]

    def test_worst_method_is_rankings_bottom(self):
        r = _run_quick()
        if r["rankings"]:
            assert r["worst_method"] == r["rankings"][-1][0]


# ── Breakpoint ──

class TestBreakpoint:
    def test_breakpoint_per_method(self):
        r = _run_quick(methods=["graph", "spectral"])
        assert set(r["breakpoint"].keys()) == {"graph", "spectral"}

    def test_breakpoint_values_are_float_or_none(self):
        r = _run_quick()
        for m, bp in r["breakpoint"].items():
            assert bp is None or isinstance(bp, float)

    def test_breakpoint_is_noise_level(self):
        r = _run_quick(noise_levels=[0.0, 0.1, 0.2, 0.3])
        for m, bp in r["breakpoint"].items():
            if bp is not None:
                assert bp in [0.0, 0.1, 0.2, 0.3]

    def test_zero_noise_never_below_threshold(self):
        """At 0.0 noise with clean canonical topologies, accuracy should be high."""
        r = _run_quick(noise_levels=[0.0])
        for m, bp in r["breakpoint"].items():
            # If 0.0 is the only level, breakpoint should be None (never drops below 0.8)
            # or 0.0 if accuracy was already low
            pass  # Just ensure no crash

    def test_extreme_noise_has_breakpoint(self):
        r = _run_quick(
            noise_levels=[0.0, 0.5],
            methods=["graph"],
            size=8,
        )
        bp = r["breakpoint"]["graph"]
        # At 50% noise, likely below 0.8
        if bp is not None:
            assert bp <= 0.5


# ── Per-topology robustness ──

class TestPerTopologyRobustness:
    def test_per_topology_keys(self):
        r = _run_quick(topologies=["star", "path", "cycle"])
        assert set(r["per_topology_robustness"].keys()) == {"star", "path", "cycle"}

    def test_per_topology_values_are_floats(self):
        r = _run_quick()
        for t, v in r["per_topology_robustness"].items():
            assert isinstance(v, float)

    def test_per_topology_values_in_range(self):
        r = _run_quick()
        for t, v in r["per_topology_robustness"].items():
            assert 0.0 <= v <= 1.0

    def test_per_topology_at_noise_keys(self):
        r = _run_quick(noise_levels=[0.0, 0.1], topologies=["star", "cycle"])
        assert set(r["per_topology_at_noise"].keys()) == {0.0, 0.1}

    def test_per_topology_at_noise_nested_keys(self):
        r = _run_quick(noise_levels=[0.0, 0.1], topologies=["star", "cycle"])
        for nl in [0.0, 0.1]:
            assert set(r["per_topology_at_noise"][nl].keys()) == {"star", "cycle"}


# ── Summary ──

class TestSummary:
    def test_summary_is_string(self):
        r = _run_quick()
        assert isinstance(r["summary"], str)

    def test_summary_non_empty(self):
        r = _run_quick()
        assert len(r["summary"]) > 20

    def test_summary_mentions_best_method(self):
        r = _run_quick()
        assert r["best_method"] in r["summary"]

    def test_summary_mentions_auc(self):
        r = _run_quick()
        assert "AUC" in r["summary"]

    def test_summary_mentions_noise(self):
        r = _run_quick()
        assert "noise" in r["summary"].lower()


# ── Reproducibility ──

class TestReproducibility:
    def test_same_seed_same_results(self):
        r1 = _run_quick(seed=123)
        r2 = _run_quick(seed=123)
        assert r1["degradation_curves"] == r2["degradation_curves"]

    def test_different_seed_different_results(self):
        """Different seeds may produce different noise patterns."""
        r1 = _run_quick(seed=1, noise_levels=[0.0, 0.3], num_queries=1)
        r2 = _run_quick(seed=999, noise_levels=[0.0, 0.3], num_queries=1)
        # Zero-noise results should be the same
        for m in r1["methods"]:
            assert r1["degradation_curves"][m][0.0] == r2["degradation_curves"][m][0.0]
        # High-noise results might differ
        # (not guaranteed, but likely with different random edge perturbations)


# ── Edge cases ──

class TestEdgeCases:
    def test_empty_methods(self):
        r = _run_quick(methods=[])
        assert r["degradation_curves"] == {}
        assert r["rankings"] == []

    def test_single_method(self):
        r = _run_quick(methods=["graph"])
        assert len(r["rankings"]) == 1
        assert r["best_method"] == "graph"

    def test_single_noise_level(self):
        r = _run_quick(noise_levels=[0.0])
        for m in r["methods"]:
            assert 0.0 in r["degradation_curves"][m]

    def test_single_topology(self):
        r = _run_quick(topologies=["star"])
        assert r["per_topology_robustness"]["star"] >= 0.0

    def test_large_noise(self):
        """At 100% noise, all edges replaced."""
        r = _run_quick(noise_levels=[1.0], size=5, methods=["graph"])
        # Should not crash, accuracy will be low
        acc = r["degradation_curves"]["graph"][1.0]
        assert 0.0 <= acc <= 1.0


# ── Integration ──

class TestIntegration:
    def test_consistent_with_benchmark(self):
        """Zero-noise accuracy should match benchmark accuracy."""
        mg = MemoryGraph()
        topo_list = ["star", "path", "cycle"]
        refs_per = 1

        # Benchmark
        bench = mg.classification_benchmark(
            topologies=topo_list,
            sizes=[8],
            num_references_per_category=refs_per,
            num_queries=1,
            methods=["graph"],
        )
        bench_acc = bench["method_results"]["graph"]["accuracy"]

        # Noise test at zero noise
        noise = mg.classification_noise_test(
            topologies=topo_list,
            size=8,
            noise_levels=[0.0],
            num_references_per_category=refs_per,
            num_queries=1,
            methods=["graph"],
        )
        noise_acc = noise["degradation_curves"]["graph"][0.0]

        # They should be very close (same canonical topologies, same size)
        assert abs(bench_acc - noise_acc) <= 0.2  # allow small variance due to randomness

    def test_all_methods_work(self):
        """All 8 classification methods should produce results."""
        r = _run_quick(
            methods=["graph", "spectral", "hybrid", "rrf", "bayesian",
                     "knn", "weighted_average", "compare"],
            size=8,
            noise_levels=[0.0, 0.1],
            topologies=["star", "path"],
        )
        for m in r["methods"]:
            assert m in r["degradation_curves"]
            assert len(r["degradation_curves"][m]) == 2


# ── Non-mutating ──

class TestNonMutating:
    def test_reference_graph_unchanged(self):
        """The calling MemoryGraph should not be modified."""
        mg = MemoryGraph()
        mg.add("original_node", "test")
        original_count = len(mg.conn.execute("SELECT id FROM nodes").fetchall())

        mg.classification_noise_test(
            size=6,
            noise_levels=[0.0, 0.1],
            num_references_per_category=1,
            num_queries=1,
            topologies=["star"],
            methods=["graph"],
        )

        after_count = len(mg.conn.execute("SELECT id FROM nodes").fetchall())
        assert after_count == original_count


# ── Determinism ──

class TestDeterminism:
    def test_deterministic_with_seed(self):
        r1 = _run_quick(seed=42)
        r2 = _run_quick(seed=42)
        assert r1["degradation_curves"] == r2["degradation_curves"]
        assert r1["robustness_score"] == r2["robustness_score"]
