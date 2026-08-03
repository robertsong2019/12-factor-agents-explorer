"""Tests for classification_report() — Cycle 349.

Evaluates the detailed classification report API with confusion matrix,
per-class metrics, error analysis, and cross-method comparison.
"""

import math
import pytest
import memory_graph as mg


# ---------------------------------------------------------------------------
# Topology builders
# ---------------------------------------------------------------------------

def _star(n, label=""):
    g = mg.MemoryGraph(":memory:")
    c = g.add(f"c_{label}", "n")
    for i in range(n - 1):
        leaf = g.add(f"l{i}_{label}", "n")
        g.link(c.id, leaf.id, "e")
    g.graph_meta = {"label": "star"}
    return g


def _path(n, label=""):
    g = mg.MemoryGraph(":memory:")
    prev = g.add(f"p0_{label}", "n")
    for i in range(1, n):
        curr = g.add(f"p{i}_{label}", "n")
        g.link(prev.id, curr.id, "e")
        prev = curr
    g.graph_meta = {"label": "path"}
    return g


def _cycle(n, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"c{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "e")
    g.graph_meta = {"label": "cycle"}
    return g


def _complete(n, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"k{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "e")
    g.graph_meta = {"label": "complete"}
    return g


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def refs3():
    """Three reference topologies: star, path, cycle."""
    return [_star(8, "r"), _path(8, "r"), _cycle(8, "r")]


@pytest.fixture
def queries3():
    """Three matching queries."""
    return [_star(8, "q"), _path(8, "q"), _cycle(8, "q")]


@pytest.fixture
def labels3():
    return ["star", "path", "cycle"]


@pytest.fixture
def empty_report():
    """Report with no queries."""
    g = mg.MemoryGraph(":memory:")
    return g.classification_report([], [], [])


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_returns_dict(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(refs3, queries3, labels3)
        assert isinstance(r, dict)

    def test_result_keys(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(refs3, queries3, labels3)
        expected = {
            "labels", "methods_evaluated", "num_queries",
            "num_references", "per_method", "best_method_overall",
            "best_method_per_class", "hardest_queries", "summary",
        }
        assert expected <= set(r)

    def test_labels_returned(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(refs3, queries3, labels3)
        assert isinstance(r["labels"], list)
        assert set(r["labels"]) >= {"star", "path", "cycle"}

    def test_num_queries(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(refs3, queries3, labels3)
        assert r["num_queries"] == 3

    def test_num_references(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(refs3, queries3, labels3)
        assert r["num_references"] == 3

    def test_methods_evaluated(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        assert r["methods_evaluated"] == ["graph", "spectral"]

    def test_default_methods(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(refs3, queries3, labels3)
        assert "graph" in r["methods_evaluated"]


# ---------------------------------------------------------------------------
# Per-method results
# ---------------------------------------------------------------------------

class TestPerMethod:
    def test_per_method_keys(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert "graph" in r["per_method"]

    def test_method_result_keys(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        data = r["per_method"]["graph"]
        expected = {
            "accuracy", "macro_precision", "macro_recall", "macro_f1",
            "weighted_precision", "weighted_recall", "weighted_f1",
            "error_count", "confusion_matrix", "normalised_matrix",
            "per_class", "errors", "most_confused_pairs",
        }
        assert expected <= set(data)

    def test_accuracy_value(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        acc = r["per_method"]["graph"]["accuracy"]
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

    def test_perfect_accuracy(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert r["per_method"]["graph"]["accuracy"] == 1.0

    def test_error_count_zero_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert r["per_method"]["graph"]["error_count"] == 0

    def test_macro_f1_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        f1 = r["per_method"]["graph"]["macro_f1"]
        assert 0.0 <= f1 <= 1.0


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------

class TestConfusionMatrix:
    def test_matrix_is_dict(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        cm = r["per_method"]["graph"]["confusion_matrix"]
        assert isinstance(cm, dict)

    def test_matrix_diagonal(self, refs3, queries3, labels3):
        """Diagonal should be non-zero for correct predictions."""
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        cm = r["per_method"]["graph"]["confusion_matrix"]
        for label in ["star", "path", "cycle"]:
            assert cm[label][label] >= 1

    def test_matrix_off_diagonal_zero_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        cm = r["per_method"]["graph"]["confusion_matrix"]
        for actual in cm:
            for pred in cm[actual]:
                if actual != pred:
                    assert cm[actual][pred] == 0

    def test_normalised_matrix_rows_sum_to_one(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        nm = r["per_method"]["graph"]["normalised_matrix"]
        for actual, row in nm.items():
            total = sum(row.values())
            if total > 0:
                assert abs(total - 1.0) < 0.01

    def test_normalised_matrix_values_in_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        nm = r["per_method"]["graph"]["normalised_matrix"]
        for row in nm.values():
            for v in row.values():
                assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# Per-class metrics
# ---------------------------------------------------------------------------

class TestPerClass:
    def test_per_class_keys(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        pc = r["per_method"]["graph"]["per_class"]
        for label in ["star", "path", "cycle"]:
            assert label in pc

    def test_per_class_fields(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        pc = r["per_method"]["graph"]["per_class"]["star"]
        expected = {
            "precision", "recall", "f1", "support",
            "tp", "fp", "fn",
            "most_confused_with", "confusion_rate",
        }
        assert expected <= set(pc)

    def test_precision_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        for label, cls in r["per_method"]["graph"]["per_class"].items():
            assert 0.0 <= cls["precision"] <= 1.0

    def test_recall_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        for label, cls in r["per_method"]["graph"]["per_class"].items():
            assert 0.0 <= cls["recall"] <= 1.0

    def test_f1_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        for label, cls in r["per_method"]["graph"]["per_class"].items():
            assert 0.0 <= cls["f1"] <= 1.0

    def test_perfect_classification_metrics(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        for label, cls in r["per_method"]["graph"]["per_class"].items():
            if cls["support"] > 0:
                assert cls["precision"] == 1.0
                assert cls["recall"] == 1.0
                assert cls["f1"] == 1.0

    def test_support_values(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        pc = r["per_method"]["graph"]["per_class"]
        assert pc["star"]["support"] == 1
        assert pc["path"]["support"] == 1
        assert pc["cycle"]["support"] == 1

    def test_most_confused_with_none_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        for label, cls in r["per_method"]["graph"]["per_class"].items():
            if cls["support"] > 0:
                assert cls["most_confused_with"] is None

    def test_confusion_rate_zero_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        for label, cls in r["per_method"]["graph"]["per_class"].items():
            if cls["support"] > 0:
                assert cls["confusion_rate"] == 0.0


# ---------------------------------------------------------------------------
# Errors and confused pairs
# ---------------------------------------------------------------------------

class TestErrors:
    def test_errors_is_list(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert isinstance(r["per_method"]["graph"]["errors"], list)

    def test_errors_empty_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert r["per_method"]["graph"]["errors"] == []

    def test_confused_pairs_is_list(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert isinstance(
            r["per_method"]["graph"]["most_confused_pairs"], list
        )

    def test_confused_pairs_empty_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert r["per_method"]["graph"]["most_confused_pairs"] == []


# ---------------------------------------------------------------------------
# Best method / overall
# ---------------------------------------------------------------------------

class TestBestMethod:
    def test_best_overall_is_string(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        assert isinstance(r["best_method_overall"], str)

    def test_best_overall_in_methods(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral", "hybrid"]
        )
        assert r["best_method_overall"] in ["graph", "spectral", "hybrid"]

    def test_best_per_class_keys(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        for label in ["star", "path", "cycle"]:
            assert label in r["best_method_per_class"]

    def test_best_per_class_has_method_and_f1(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        for label, info in r["best_method_per_class"].items():
            assert "method" in info
            assert "f1" in info
            assert info["method"] in ["graph", "spectral"]

    def test_best_overall_highest_accuracy(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        best = r["best_method_overall"]
        for m in ["graph", "spectral"]:
            assert r["per_method"][best]["accuracy"] >= r["per_method"][m]["accuracy"]


# ---------------------------------------------------------------------------
# Hardest queries
# ---------------------------------------------------------------------------

class TestHardestQueries:
    def test_hardest_is_list(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        assert isinstance(r["hardest_queries"], list)

    def test_hardest_empty_when_all_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        # All methods get 100% → no hard queries
        assert r["hardest_queries"] == []

    def test_hardest_sorted_by_correct_count(self, refs3, queries3, labels3):
        """When some methods fail, hardest queries are sorted ascending."""
        # Use wrong labels to create errors
        wrong_labels = ["path", "star", "cycle"]
        r = queries3[0].classification_report(
            refs3, queries3, wrong_labels, methods=["graph", "spectral", "hybrid"]
        )
        if r["hardest_queries"]:
            correct_counts = [q["methods_correct"] for q in r["hardest_queries"]]
            assert correct_counts == sorted(correct_counts)

    def test_hardest_query_fields(self, refs3, queries3, labels3):
        wrong_labels = ["path", "star", "cycle"]
        r = queries3[0].classification_report(
            refs3, queries3, wrong_labels, methods=["graph", "spectral"]
        )
        if r["hardest_queries"]:
            q = r["hardest_queries"][0]
            assert "query_idx" in q
            assert "actual" in q
            assert "methods_correct" in q
            assert "methods_total" in q

    def test_hardest_max_10(self, refs3):
        """Hardest queries list capped at 10."""
        queries = [_star(8, f"q{i}") for i in range(20)]
        labels = ["star"] * 20
        r = queries[0].classification_report(
            refs3, queries, labels, methods=["graph"]
        )
        assert len(r["hardest_queries"]) <= 10


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_is_string(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert isinstance(r["summary"], str)

    def test_summary_non_empty(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert len(r["summary"]) > 0

    def test_summary_mentions_best_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert "graph" in r["summary"]

    def test_summary_mentions_query_count(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert "3" in r["summary"]  # 3 queries


# ---------------------------------------------------------------------------
# Multiple methods
# ---------------------------------------------------------------------------

class TestMultipleMethods:
    def test_two_methods(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        assert len(r["per_method"]) == 2

    def test_three_methods(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral", "hybrid"]
        )
        assert len(r["per_method"]) == 3

    def test_all_methods(self, refs3, queries3, labels3):
        methods = [
            "graph", "spectral", "hybrid", "rrf",
            "bayesian", "knn", "weighted_average", "compare",
        ]
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=methods
        )
        assert len(r["per_method"]) == len(methods)

    def test_method_accuracy_consistent_with_benchmark(self, refs3, queries3, labels3):
        """classification_report should produce same accuracy as direct calls."""
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        # Direct call
        direct = queries3[0].graph_classification(refs3)
        direct_label = refs3[direct["best_match"]].graph_meta["label"]
        report_pred = r["per_method"]["graph"]["errors"] == []
        assert report_pred == (direct_label == labels3[0])


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_queries(self, refs3):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_report(refs3, [], [])
        assert r["num_queries"] == 0
        assert r["per_method"] == {}
        assert r["best_method_overall"] is None

    def test_empty_references(self, queries3, labels3):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_report([], queries3, labels3, methods=["graph"])
        # Should handle gracefully — all predictions None
        assert r["num_references"] == 0

    def test_single_query(self, refs3):
        q = _star(8, "single")
        r = q.classification_report(refs3, [q], ["star"], methods=["graph"])
        assert r["num_queries"] == 1
        assert r["per_method"]["graph"]["accuracy"] == 1.0

    def test_single_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert len(r["methods_evaluated"]) == 1

    def test_mismatched_lengths_raises(self, refs3, queries3):
        with pytest.raises(ValueError, match="same length"):
            queries3[0].classification_report(
                refs3, queries3, ["star", "path"],  # 2 labels, 3 queries
                methods=["graph"],
            )

    def test_unknown_method_skipped(self, refs3, queries3, labels3):
        """Unknown methods should produce None predictions."""
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["nonexistent"]
        )
        assert "nonexistent" in r["per_method"]
        assert r["per_method"]["nonexistent"]["accuracy"] == 0.0

    def test_all_same_label(self, refs3):
        """All queries same topology."""
        queries = [_star(8, f"q{i}") for i in range(3)]
        labels = ["star"] * 3
        r = queries[0].classification_report(
            refs3, queries, labels, methods=["graph"]
        )
        assert r["per_method"]["graph"]["accuracy"] == 1.0


# ---------------------------------------------------------------------------
# Normalised matrix
# ---------------------------------------------------------------------------

class TestNormalisedMatrix:
    def test_normalised_is_dict(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert isinstance(r["per_method"]["graph"]["normalised_matrix"], dict)

    def test_normalised_diagonal_one_when_perfect(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        nm = r["per_method"]["graph"]["normalised_matrix"]
        for label in ["star", "path", "cycle"]:
            if label in nm:
                assert nm[label][label] == 1.0

    def test_normalised_sums_to_one(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        nm = r["per_method"]["graph"]["normalised_matrix"]
        for actual, row in nm.items():
            assert abs(sum(row.values()) - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Weighted averages
# ---------------------------------------------------------------------------

class TestWeightedAverages:
    def test_weighted_precision_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        wp = r["per_method"]["graph"]["weighted_precision"]
        assert 0.0 <= wp <= 1.0

    def test_weighted_recall_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        wr = r["per_method"]["graph"]["weighted_recall"]
        assert 0.0 <= wr <= 1.0

    def test_weighted_f1_range(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        wf = r["per_method"]["graph"]["weighted_f1"]
        assert 0.0 <= wf <= 1.0

    def test_weighted_equals_macro_when_balanced(self, refs3, queries3, labels3):
        """When each class has equal support, weighted == macro."""
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        data = r["per_method"]["graph"]
        assert abs(data["weighted_f1"] - data["macro_f1"]) < 0.01


# ---------------------------------------------------------------------------
# Error scenario (intentional misclassification)
# ---------------------------------------------------------------------------

class TestErrorScenario:
    def test_wrong_labels_produce_errors(self, refs3, queries3):
        """Swapping labels should produce errors."""
        wrong = ["path", "star", "cycle"]  # star→path, path→star swapped
        r = queries3[0].classification_report(
            refs3, queries3, wrong, methods=["graph"]
        )
        assert r["per_method"]["graph"]["error_count"] >= 1

    def test_errors_have_three_elements(self, refs3, queries3):
        wrong = ["path", "star", "cycle"]
        r = queries3[0].classification_report(
            refs3, queries3, wrong, methods=["graph"]
        )
        for err in r["per_method"]["graph"]["errors"]:
            assert len(err) == 3  # (idx, actual, predicted)

    def test_confused_pairs_populated_on_errors(self, refs3, queries3):
        wrong = ["path", "star", "cycle"]
        r = queries3[0].classification_report(
            refs3, queries3, wrong, methods=["graph"]
        )
        pairs = r["per_method"]["graph"]["most_confused_pairs"]
        assert len(pairs) >= 1

    def test_most_confused_pair_sorted_desc(self, refs3):
        """Most confused pairs sorted by count descending."""
        # Create queries that will be systematically wrong
        queries = [_star(8, f"q{i}") for i in range(5)]
        wrong_labels = ["path"] * 5  # All stars misclassified as paths
        r = queries[0].classification_report(
            refs3, queries, wrong_labels, methods=["graph"]
        )
        pairs = r["per_method"]["graph"]["most_confused_pairs"]
        if pairs:
            counts = [p[2] for p in pairs]
            assert counts == sorted(counts, reverse=True)

    def test_per_class_confusion_rate_on_errors(self, refs3):
        queries = [_star(8, f"q{i}") for i in range(3)]
        wrong_labels = ["path"] * 3
        r = queries[0].classification_report(
            refs3, queries, wrong_labels, methods=["graph"]
        )
        pc = r["per_method"]["graph"]["per_class"]
        # star has support 3 (all queries are actually star)
        # but predicted as path → star recall = 0
        assert pc["star"]["recall"] == 0.0

    def test_hardest_queries_populated_on_errors(self, refs3):
        queries = [_star(8, f"q{i}") for i in range(3)]
        wrong_labels = ["path"] * 3
        r = queries[0].classification_report(
            refs3, queries, wrong_labels, methods=["graph", "spectral"]
        )
        assert len(r["hardest_queries"]) >= 1


# ---------------------------------------------------------------------------
# Non-mutating
# ---------------------------------------------------------------------------

class TestNonMutating:
    def test_query_unchanged(self, refs3, queries3, labels3):
        q = queries3[0]
        node_count_before = q.stats()["nodes"]
        q.classification_report(refs3, queries3, labels3, methods=["graph"])
        assert q.stats()["nodes"] == node_count_before

    def test_references_unchanged(self, refs3, queries3, labels3):
        ref_counts = [r.stats()["nodes"] for r in refs3]
        queries3[0].classification_report(refs3, queries3, labels3, methods=["graph"])
        for ref, count_before in zip(refs3, ref_counts):
            assert ref.stats()["nodes"] == count_before

    def test_no_new_edges(self, refs3, queries3, labels3):
        edge_counts = [q.count_edges() for q in queries3]
        queries3[0].classification_report(refs3, queries3, labels3, methods=["graph"])
        for q, count_before in zip(queries3, edge_counts):
            assert q.count_edges() == count_before


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_result_twice(self, refs3, queries3, labels3):
        r1 = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        r2 = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph", "spectral"]
        )
        assert r1["per_method"]["graph"]["accuracy"] == r2["per_method"]["graph"]["accuracy"]
        assert r1["per_method"]["spectral"]["accuracy"] == r2["per_method"]["spectral"]["accuracy"]

    def test_confusion_matrix_deterministic(self, refs3, queries3, labels3):
        r1 = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        r2 = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["graph"]
        )
        assert (
            r1["per_method"]["graph"]["confusion_matrix"]
            == r2["per_method"]["graph"]["confusion_matrix"]
        )


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_with_complete_topology(self):
        refs = [
            _star(8, "r"),
            _path(8, "r"),
            _complete(8, "r"),
        ]
        for i, r in enumerate(refs):
            r.graph_meta = {"label": ["star", "path", "complete"][i]}

        queries = [_star(8, "q"), _path(8, "q"), _complete(8, "q")]
        labels = ["star", "path", "complete"]

        r = queries[0].classification_report(
            refs, queries, labels, methods=["graph"]
        )
        assert r["per_method"]["graph"]["accuracy"] == 1.0

    def test_many_queries(self, refs3):
        queries = []
        labels = []
        for i in range(10):
            queries.append(_star(8, f"s{i}"))
            labels.append("star")
            queries.append(_path(8, f"p{i}"))
            labels.append("path")
            queries.append(_cycle(8, f"c{i}"))
            labels.append("cycle")

        r = queries[0].classification_report(
            refs3, queries, labels, methods=["graph"]
        )
        assert r["num_queries"] == 30
        assert r["per_method"]["graph"]["accuracy"] == 1.0

    def test_rrf_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["rrf"]
        )
        assert "rrf" in r["per_method"]

    def test_bayesian_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["bayesian"]
        )
        assert "bayesian" in r["per_method"]

    def test_knn_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["knn"]
        )
        assert "knn" in r["per_method"]

    def test_compare_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["compare"]
        )
        assert "compare" in r["per_method"]

    def test_weighted_average_method(self, refs3, queries3, labels3):
        r = queries3[0].classification_report(
            refs3, queries3, labels3, methods=["weighted_average"]
        )
        assert "weighted_average" in r["per_method"]

    def test_report_after_consolidation(self):
        """Report should work on graphs that have been modified."""
        g = mg.MemoryGraph(":memory:")
        a = g.add("alpha", "node")
        b = g.add("beta", "node")
        g.link(a.id, b.id, "edge")
        g2 = _star(6, "ref")
        g2.graph_meta = {"label": "star"}
        r = g.classification_report([g2], [g], ["unknown"], methods=["graph"])
        assert r["num_queries"] == 1
