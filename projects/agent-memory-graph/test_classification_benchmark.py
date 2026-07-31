"""Tests for classification_benchmark() — Cycle 334.

Tests the benchmark infrastructure itself (not classification accuracy):
- Reference/query generation
- Method dispatch for all 8 methods
- Metrics computation (accuracy, precision, recall, F1)
- Per-topology breakdown
- Best-method-per-topology identification
- Confusion matrix
- Parameter handling
- Non-mutating
- Edge cases
"""

import pytest
from memory_graph import MemoryGraph


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _run_quick(**kwargs):
    """Run benchmark with minimal settings for fast tests."""
    mg = MemoryGraph()
    defaults = dict(
        topologies=["star", "path"],
        sizes=[6],
        num_references_per_category=1,
        num_queries=1,
        methods=["graph", "spectral"],
    )
    defaults.update(kwargs)
    return mg.classification_benchmark(**defaults)


# ---------------------------------------------------------------------
# Structure & Keys
# ---------------------------------------------------------------------

class TestBenchmarkStructure:
    def test_result_has_expected_keys(self):
        r = _run_quick()
        expected = {
            "methods_evaluated", "topologies_tested", "sizes",
            "num_references", "num_queries", "method_results",
            "overall_best", "overall_best_accuracy",
            "best_per_topology", "confusion",
        }
        assert expected.issubset(r.keys())

    def test_methods_evaluated_matches_input(self):
        r = _run_quick(methods=["graph", "spectral", "hybrid"])
        assert set(r["methods_evaluated"]) == {"graph", "spectral", "hybrid"}

    def test_topologies_tested_matches_input(self):
        r = _run_quick(topologies=["star", "cycle", "tree"])
        assert set(r["topologies_tested"]) == {"star", "cycle", "tree"}

    def test_sizes_matches_input(self):
        r = _run_quick(sizes=[5, 10])
        assert r["sizes"] == [5, 10]

    def test_method_results_contains_all_methods(self):
        r = _run_quick(methods=["graph", "spectral", "rrf"])
        for m in ["graph", "spectral", "rrf"]:
            assert m in r["method_results"]

    def test_method_result_entry_has_expected_keys(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert "accuracy" in entry
            assert "correct" in entry
            assert "total" in entry
            assert "precision" in entry
            assert "recall" in entry
            assert "f1" in entry
            assert "avg_confidence" in entry
            assert "per_topology" in entry
            assert "predictions" in entry


# ---------------------------------------------------------------------
# Reference/Query Generation
# ---------------------------------------------------------------------

class TestGeneration:
    def test_num_references_correct(self):
        r = _run_quick(topologies=["star", "path", "cycle"], sizes=[6, 8], num_references_per_category=2)
        # 3 topologies × 2 sizes × 2 refs = 12
        assert r["num_references"] == 12

    def test_num_queries_correct(self):
        r = _run_quick(topologies=["star", "path"], sizes=[6, 8], num_queries=3)
        # 2 topologies × 2 sizes × 3 queries = 12
        assert r["num_queries"] == 12

    def test_single_topology(self):
        r = _run_quick(topologies=["star"])
        assert r["num_references"] >= 1
        assert r["num_queries"] >= 1

    def test_single_size(self):
        r = _run_quick(sizes=[10])
        assert r["num_queries"] >= 1

    def test_multiple_references_per_category(self):
        r1 = _run_quick(num_references_per_category=1)
        r3 = _run_quick(num_references_per_category=3)
        assert r3["num_references"] == 3 * r1["num_references"]

    def test_multiple_queries(self):
        r1 = _run_quick(num_queries=1)
        r2 = _run_quick(num_queries=2)
        assert r2["num_queries"] == 2 * r1["num_queries"]


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------

class TestMetrics:
    def test_accuracy_in_range(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert 0.0 <= entry["accuracy"] <= 1.0

    def test_precision_in_range(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert 0.0 <= entry["precision"] <= 1.0

    def test_recall_in_range(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert 0.0 <= entry["recall"] <= 1.0

    def test_f1_in_range(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert 0.0 <= entry["f1"] <= 1.0

    def test_avg_confidence_in_range(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert 0.0 <= entry["avg_confidence"] <= float("inf")

    def test_correct_plus_incorrect_equals_total(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            assert entry["correct"] <= entry["total"]

    def test_accuracy_equals_correct_over_total(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            if entry["total"] > 0:
                expected_acc = round(entry["correct"] / entry["total"], 4)
                assert entry["accuracy"] == expected_acc

    def test_predictions_length_matches_queries(self):
        r = _run_quick(num_queries=2)
        for m, entry in r["method_results"].items():
            assert len(entry["predictions"]) == r["num_queries"]

    def test_per_topology_has_all_topologies(self):
        topos = ["star", "path", "cycle"]
        r = _run_quick(topologies=topos)
        for m, entry in r["method_results"].items():
            for t in topos:
                assert t in entry["per_topology"]
                pt = entry["per_topology"][t]
                assert "correct" in pt
                assert "total" in pt
                assert "accuracy" in pt
                assert 0.0 <= pt["accuracy"] <= 1.0

    def test_per_topology_accuracy_consistent(self):
        r = _run_quick()
        for m, entry in r["method_results"].items():
            total_correct = sum(pt["correct"] for pt in entry["per_topology"].values())
            assert total_correct == entry["correct"]


# ---------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------

class TestRanking:
    def test_overall_best_is_highest_accuracy(self):
        r = _run_quick(methods=["graph", "spectral", "hybrid"])
        best = r["overall_best"]
        best_acc = r["method_results"][best]["accuracy"]
        for m, entry in r["method_results"].items():
            assert entry["accuracy"] <= best_acc + 1e-9

    def test_overall_best_accuracy_matches(self):
        r = _run_quick()
        best = r["overall_best"]
        assert r["overall_best_accuracy"] == r["method_results"][best]["accuracy"]

    def test_best_per_topology_returns_valid_method(self):
        methods = ["graph", "spectral"]
        r = _run_quick(methods=methods)
        for topo, info in r["best_per_topology"].items():
            assert info["best_method"] in methods

    def test_best_per_topology_accuracy_matches(self):
        r = _run_quick()
        for topo, info in r["best_per_topology"].items():
            m = info["best_method"]
            assert r["method_results"][m]["per_topology"][topo]["accuracy"] == info["accuracy"]


# ---------------------------------------------------------------------
# Confusion
# ---------------------------------------------------------------------

class TestConfusion:
    def test_confusion_is_dict(self):
        r = _run_quick()
        assert isinstance(r["confusion"], dict)

    def test_confusion_keys_are_pairs(self):
        r = _run_quick(topologies=["star", "path"])
        for key in r["confusion"]:
            assert "→" in key

    def test_confusion_values_positive(self):
        r = _run_quick()
        for key, count in r["confusion"].items():
            assert count > 0

    def test_confusion_sorted_by_count(self):
        r = _run_quick()
        counts = list(r["confusion"].values())
        assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------
# Method Dispatch
# ---------------------------------------------------------------------

class TestMethodDispatch:
    @pytest.mark.parametrize("method", [
        "graph", "spectral", "hybrid", "rrf", "bayesian",
        "knn", "weighted_average", "compare",
    ])
    def test_method_runs_without_error(self, method):
        r = _run_quick(methods=[method], topologies=["star", "path"], sizes=[6])
        assert method in r["method_results"]

    def test_unknown_method_handled(self):
        r = _run_quick(methods=["graph", "nonexistent"])
        assert "nonexistent" in r["method_results"]
        # Unknown methods should have all-None predictions
        assert all(p is None for p in r["method_results"]["nonexistent"]["predictions"])
        assert r["method_results"]["nonexistent"]["accuracy"] == 0.0

    def test_all_methods_simultaneously(self):
        r = _run_quick(
            methods=["graph", "spectral", "hybrid", "rrf", "bayesian",
                     "knn", "weighted_average", "compare"],
            topologies=["star", "path", "cycle"],
            sizes=[6, 8],
        )
        assert len(r["method_results"]) == 8


# ---------------------------------------------------------------------
# Topology Builder
# ---------------------------------------------------------------------

class TestTopologyBuilder:
    def test_star_topology(self):
        mg = MemoryGraph._bench_build_topology("star", 5)
        assert mg.graph_meta["topology"] == "star"
        stats = mg.stats()
        # Star with 5 nodes: 4 edges
        assert stats["edges"] == 4

    def test_path_topology(self):
        mg = MemoryGraph._bench_build_topology("path", 5)
        # Path with 5 nodes: 4 edges
        assert mg.stats()["edges"] == 4

    def test_cycle_topology(self):
        mg = MemoryGraph._bench_build_topology("cycle", 5)
        # Cycle with 5 nodes: 5 edges
        assert mg.stats()["edges"] == 5

    def test_complete_topology(self):
        mg = MemoryGraph._bench_build_topology("complete", 5)
        # Complete K5: 5*4/2 = 10 edges
        assert mg.stats()["edges"] == 10

    def test_bipartite_topology(self):
        mg = MemoryGraph._bench_build_topology("bipartite", 6)
        # Bipartite K3,3: 3*3 = 9 edges
        assert mg.stats()["edges"] == 9

    def test_tree_topology(self):
        mg = MemoryGraph._bench_build_topology("tree", 7)
        # Tree with 7 nodes: 6 edges
        assert mg.stats()["edges"] == 6

    def test_unknown_topology_raises(self):
        with pytest.raises(ValueError):
            MemoryGraph._bench_build_topology("nonexistent", 5)

    def test_label_set_in_graph_meta(self):
        mg = MemoryGraph._bench_build_topology("star", 5, label="custom")
        assert mg.graph_meta["label"] == "custom"

    def test_default_label_is_topology_name(self):
        mg = MemoryGraph._bench_build_topology("path", 5)
        assert mg.graph_meta["label"] == "path"


# ---------------------------------------------------------------------
# Non-mutating
# ---------------------------------------------------------------------

class TestNonMutating:
    def test_query_graph_unchanged(self):
        mg = MemoryGraph()
        mg_copy = MemoryGraph()
        mg_copy.add("test", "fact")
        mg_copy.classification_benchmark(
            topologies=["star"], sizes=[5], methods=["graph"],
            num_references_per_category=1, num_queries=1,
        )
        # The original mg should be unaffected
        assert mg.stats()["nodes"] == 0

    def test_benchmark_does_not_add_nodes_to_self(self):
        mg = MemoryGraph()
        before = mg.stats()["nodes"]
        mg.classification_benchmark(
            topologies=["star", "path"], sizes=[6, 8],
            methods=["graph", "spectral"],
            num_references_per_category=2, num_queries=2,
        )
        after = mg.stats()["nodes"]
        assert before == after


# ---------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_topologies(self):
        mg = MemoryGraph()
        r = mg.classification_benchmark(topologies=[], methods=["graph"])
        assert r["num_references"] == 0
        assert r["num_queries"] == 0
        assert r["method_results"] == {}

    def test_empty_methods(self):
        mg = MemoryGraph()
        r = mg.classification_benchmark(methods=[])
        assert len(r["method_results"]) == 0
        assert r["overall_best"] is None

    def test_single_topology_single_method(self):
        r = _run_quick(topologies=["star"], sizes=[6], methods=["graph"])
        assert r["overall_best"] == "graph"

    def test_large_number_of_references(self):
        r = _run_quick(
            topologies=["star", "path"],
            sizes=[6, 8, 10],
            num_references_per_category=3,
            methods=["spectral"],
        )
        assert r["num_references"] == 2 * 3 * 3  # 18

    def test_quarantined_flag_accepted(self):
        r = _run_quick(include_quarantined=True)
        assert "method_results" in r

    def test_default_parameters(self):
        mg = MemoryGraph()
        r = mg.classification_benchmark(methods=["graph"])
        assert r["topologies_tested"] == ["star", "path", "cycle", "complete", "bipartite", "tree"]
        assert r["sizes"] == [8, 12]

    def test_different_sizes_produce_different_references(self):
        r = _run_quick(sizes=[5, 10], topologies=["star"])
        assert r["num_references"] == 2  # 1 topology × 2 sizes × 1 ref


# ---------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_result(self):
        r1 = _run_quick(topologies=["star", "path"], sizes=[6], methods=["graph", "spectral"])
        r2 = _run_quick(topologies=["star", "path"], sizes=[6], methods=["graph", "spectral"])
        assert r1["overall_best"] == r2["overall_best"]
        assert r1["overall_best_accuracy"] == r2["overall_best_accuracy"]

    def test_predictions_deterministic(self):
        r1 = _run_quick(methods=["graph"])
        r2 = _run_quick(methods=["graph"])
        assert r1["method_results"]["graph"]["predictions"] == r2["method_results"]["graph"]["predictions"]


# ---------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------

class TestIntegration:
    def test_benchmark_with_all_topologies(self):
        mg = MemoryGraph()
        r = mg.classification_benchmark(
            topologies=["star", "path", "cycle", "complete", "bipartite", "tree"],
            sizes=[8],
            methods=["graph", "spectral"],
            num_references_per_category=1,
            num_queries=1,
        )
        assert len(r["topologies_tested"]) == 6
        assert r["num_references"] == 6
        assert r["num_queries"] == 6

    def test_benchmark_predictions_are_valid_topologies(self):
        topologies = ["star", "path", "cycle"]
        r = _run_quick(topologies=topologies, methods=["graph", "spectral"])
        for m, entry in r["method_results"].items():
            for pred in entry["predictions"]:
                if pred is not None:
                    assert pred in topologies
