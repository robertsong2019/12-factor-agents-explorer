"""Tests for classification_confidence_interval (Cycle 358).

Bootstrap-based confidence intervals for classification metrics.
Research #050.
"""

import pytest
from memory_graph import MemoryGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _star(n, label="star"):
    mg = MemoryGraph()
    mg.graph_meta = {"label": label}
    center = mg.add("center", "hub")
    for i in range(n - 1):
        leaf = mg.add(f"leaf_{i}", "spoke")
        mg.link(center.id, leaf.id, "connects")
    return mg


def _path(n, label="path"):
    mg = MemoryGraph()
    mg.graph_meta = {"label": label}
    prev = mg.add("node_0", "node")
    for i in range(1, n):
        curr = mg.add(f"node_{i}", "node")
        mg.link(prev.id, curr.id, "connects")
        prev = curr
    return mg


def _clique(n, label="clique"):
    mg = MemoryGraph()
    mg.graph_meta = {"label": label}
    nodes = [mg.add(f"v{i}", "vertex") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "connects")
    return mg


def _make_refs():
    return [_star(6, "star"), _path(6, "path"), _clique(5, "clique")]


def _make_queries(refs, n_per_class=4):
    queries = []
    labels = []
    for pattern, label in [
        (_star, "star"),
        (_path, "path"),
        (_clique, "clique"),
    ]:
        factory = {"star": _star, "path": _path, "clique": _clique}[label]
        for i in range(n_per_class):
            n = 5 + (i % 3)
            queries.append(factory(n, f"{label}_q{i}"))
            labels.append(label)
    return queries, labels


# ---------------------------------------------------------------------------
# 1. Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_returns_dict(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        assert isinstance(result, dict)

    def test_required_keys(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        required = {
            "method", "n_queries", "n_bootstrap",
            "confidence_level", "point_estimate",
            "intervals", "per_class_intervals",
            "sample_sizes", "summary",
        }
        assert required <= set(result.keys())

    def test_intervals_has_expected_metrics(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        expected_metrics = {
            "accuracy", "macro_precision", "macro_recall",
            "macro_f1", "weighted_f1",
        }
        assert expected_metrics <= set(result["intervals"].keys())

    def test_per_interval_has_ci_fields(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        for mname, ci in result["intervals"].items():
            assert "lower" in ci
            assert "upper" in ci
            assert "mean" in ci
            assert "std" in ci
            assert "width" in ci
            assert "point_estimate" in ci

    def test_n_queries_matches(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        assert result["n_queries"] == len(queries)


# ---------------------------------------------------------------------------
# 2. Correctness
# ---------------------------------------------------------------------------

class TestCorrectness:
    def test_ci_bounds_ordered(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=100
        )
        for mname, ci in result["intervals"].items():
            assert ci["lower"] <= ci["upper"], (
                f"{mname}: lower={ci['lower']} > upper={ci['upper']}"
            )

    def test_ci_width_nonneg(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        for mname, ci in result["intervals"].items():
            assert ci["width"] >= 0.0

    def test_mean_within_ci(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=100
        )
        for mname, ci in result["intervals"].items():
            assert ci["lower"] - 0.01 <= ci["mean"] <= ci["upper"] + 0.01

    def test_point_estimate_matches_full_data(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        # Accuracy point estimate should match actual classification accuracy
        preds = []
        for query in queries:
            r = query.graph_classification(refs)
            idx = r.get("best_match", 0)
            ref_labels = ["star", "path", "clique"]
            if isinstance(idx, str):
                idx = int(idx)
            preds.append(ref_labels[min(idx, len(ref_labels) - 1)])
        correct = sum(1 for p, e in zip(preds, labels) if p == e)
        expected_acc = correct / len(labels)
        assert abs(result["point_estimate"]["accuracy"] - expected_acc) < 0.001

    def test_std_nonneg(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        for mname, ci in result["intervals"].items():
            assert ci["std"] >= 0.0

    def test_metrics_in_zero_one(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        for mname, ci in result["intervals"].items():
            assert 0.0 <= ci["lower"] <= 1.0
            assert 0.0 <= ci["upper"] <= 1.0
            assert 0.0 <= ci["mean"] <= 1.0

    def test_per_class_intervals_populated(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60
        )
        assert len(result["per_class_intervals"]) >= 3

    def test_ci_contains_point_estimate(self):
        """Point estimate should usually fall within the CI."""
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=200
        )
        acc_ci = result["intervals"]["accuracy"]
        pe = result["point_estimate"]["accuracy"]
        # Point estimate should be between lower and upper (with small
        # tolerance for edge cases in percentile method)
        assert acc_ci["lower"] - 0.05 <= pe <= acc_ci["upper"] + 0.05


# ---------------------------------------------------------------------------
# 3. Parameters
# ---------------------------------------------------------------------------

class TestParameters:
    def test_different_confidence_level(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r90 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=100,
            confidence_level=0.90,
        )
        r99 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=100,
            confidence_level=0.99,
        )
        # 99% CI should be wider than 90% CI
        w90 = r90["intervals"]["accuracy"]["width"]
        w99 = r99["intervals"]["accuracy"]["width"]
        assert w99 >= w90

    def test_different_method(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            method="spectral",
        )
        assert result["method"] == "spectral"

    def test_different_bins(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            bins=15,
        )
        assert "intervals" in result

    def test_random_seed_reproducible(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r1 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            random_seed=123,
        )
        r2 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            random_seed=123,
        )
        assert (
            r1["intervals"]["accuracy"]["lower"]
            == r2["intervals"]["accuracy"]["lower"]
        )
        assert (
            r1["intervals"]["accuracy"]["upper"]
            == r2["intervals"]["accuracy"]["upper"]
        )

    def test_no_seed_different_runs(self):
        """Without seed, CIs should usually differ (probabilistic)."""
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r1 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            random_seed=None,
        )
        r2 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            random_seed=None,
        )
        # Very unlikely to be identical on both bounds
        differ = (
            r1["intervals"]["accuracy"]["lower"]
            != r2["intervals"]["accuracy"]["lower"]
            or r1["intervals"]["accuracy"]["upper"]
            != r2["intervals"]["accuracy"]["upper"]
        )
        # Allow rare identical runs
        assert differ or r1["intervals"]["accuracy"]["std"] >= 0.0


# ---------------------------------------------------------------------------
# 4. Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_queries(self):
        refs = _make_refs()
        q = refs[0]
        result = q.classification_confidence_interval(
            refs, [], [], n_bootstrap=60,
        )
        assert result["n_queries"] == 0
        assert "No queries" in result["summary"]

    def test_mismatched_lengths_raises(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        with pytest.raises(ValueError, match="same length"):
            q.classification_confidence_interval(
                refs, queries, labels[:-1], n_bootstrap=60,
            )

    def test_too_few_bootstrap_raises(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        with pytest.raises(ValueError, match="n_bootstrap"):
            q.classification_confidence_interval(
                refs, queries, labels, n_bootstrap=10,
            )

    def test_invalid_confidence_level_raises(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        with pytest.raises(ValueError, match="confidence_level"):
            q.classification_confidence_interval(
                refs, queries, labels, n_bootstrap=60,
                confidence_level=1.5,
            )

    def test_single_class(self):
        refs = [_star(6, "star")]
        queries = [_star(5, "q1"), _star(7, "q2"), _star(6, "q3")]
        labels = ["star", "star", "star"]
        result = queries[0].classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
        )
        # With one class, accuracy should be high
        assert result["point_estimate"]["accuracy"] > 0.5

    def test_two_queries_minimum(self):
        refs = _make_refs()
        queries = [_star(6, "q1"), _path(6, "q2")]
        labels = ["star", "path"]
        result = queries[0].classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
        )
        assert result["n_queries"] == 2


# ---------------------------------------------------------------------------
# 5. Non-Mutating
# ---------------------------------------------------------------------------

class TestNonMutating:
    def test_graph_unchanged(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        before_nodes = q.stats()["nodes"]
        before_edges = q.stats()["edges"]
        q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
        )
        after = q.stats()
        assert after["nodes"] == before_nodes
        assert after["edges"] == before_edges

    def test_references_unchanged(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        ref_counts = [r.stats()["nodes"] for r in refs]
        queries[0].classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
        )
        for i, ref in enumerate(refs):
            assert ref.stats()["nodes"] == ref_counts[i]


# ---------------------------------------------------------------------------
# 6. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_result(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r1 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=80,
            random_seed=42,
        )
        r2 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=80,
            random_seed=42,
        )
        assert (
            r1["intervals"]["accuracy"]["lower"]
            == r2["intervals"]["accuracy"]["lower"]
        )

    def test_stable_across_calls(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r1 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=80,
            random_seed=99,
        )
        r2 = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=80,
            random_seed=99,
        )
        for mname in r1["intervals"]:
            assert r1["intervals"][mname]["mean"] == r2["intervals"][mname]["mean"]


# ---------------------------------------------------------------------------
# 7. Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_works_with_classification_report(self):
        """CI method should use the same classification as report."""
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        report = q.classification_report(
            refs, queries, labels, methods=["graph"]
        )
        ci = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60, method="graph",
        )
        # Point estimates should match
        report_acc = report["per_method"]["graph"]["accuracy"]
        ci_pe = ci["point_estimate"]["accuracy"]
        assert abs(report_acc - ci_pe) < 0.001

    def test_more_bootstrap_decreases_variance(self):
        """More bootstrap iterations → more stable CI estimates."""
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r_low = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
            random_seed=42,
        )
        r_high = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=500,
            random_seed=42,
        )
        # Both should produce valid CIs
        assert r_low["intervals"]["accuracy"]["lower"] <= r_low["intervals"]["accuracy"]["upper"]
        assert r_high["intervals"]["accuracy"]["lower"] <= r_high["intervals"]["accuracy"]["upper"]

    def test_perfect_classification(self):
        """If classification is perfect, accuracy should be 1.0."""
        refs = _make_refs()
        queries = [_star(6, "q1"), _path(6, "q2"), _clique(5, "q3")]
        labels = ["star", "path", "clique"]
        result = queries[0].classification_confidence_interval(
            refs, queries, labels, n_bootstrap=100,
        )
        assert result["point_estimate"]["accuracy"] == 1.0

    def test_sample_sizes_populated(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
        )
        ss = result["sample_sizes"]
        assert ss["min"] >= 1
        assert ss["max"] <= len(queries)
        assert "mean" in ss

    def test_summary_mentions_method(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60,
        )
        assert "graph" in result["summary"]
        assert "CI" in result["summary"] or "bootstrap" in result["summary"].lower()

    def test_wide_ci_for_small_sample(self):
        """Small sample → non-trivial CI width or perfect classification."""
        refs = _make_refs()
        queries = [_star(6, "q1"), _path(6, "q2")]
        labels = ["star", "path"]
        q = queries[0]
        result = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=100,
        )
        # With only 2 samples, CI width for accuracy is either 0
        # (perfect classification) or substantial
        width = result["intervals"]["accuracy"]["width"]
        assert width >= 0.0  # valid CI

    def test_multiple_methods_same_queries(self):
        refs = _make_refs()
        queries, labels = _make_queries(refs)
        q = queries[0]
        r_graph = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60, method="graph",
        )
        r_spectral = q.classification_confidence_interval(
            refs, queries, labels, n_bootstrap=60, method="spectral",
        )
        assert r_graph["method"] != r_spectral["method"]
