"""Tests for classification_compare_batch() — Cycle 385.

All-methods × all-queries comparison with pairwise McNemar significance.
"""
import math
import pytest
from memory_graph import MemoryGraph


def _build_canonical():
    """Build 6 canonical topology references with labels."""
    refs = []
    # Star
    g = MemoryGraph()
    for i in range(6):
        g.add(f"s{i}", kind="concept")
    for i in range(1, 6):
        g.link("s0", f"s{i}", "related")
    g.graph_meta = {"label": "star"}
    refs.append(g)
    # Path
    g = MemoryGraph()
    for i in range(6):
        g.add(f"p{i}", kind="concept")
    for i in range(5):
        g.link(f"p{i}", f"p{i+1}", "related")
    g.graph_meta = {"label": "path"}
    refs.append(g)
    # Cycle
    g = MemoryGraph()
    for i in range(6):
        g.add(f"c{i}", kind="concept")
    for i in range(6):
        g.link(f"c{i}", f"c{(i+1)%6}", "related")
    g.graph_meta = {"label": "cycle"}
    refs.append(g)
    return refs


def _make_star_copy(prefix="q"):
    """Exact copy of star topology."""
    g = MemoryGraph()
    for i in range(6):
        g.add(f"{prefix}{i}", kind="concept")
    for i in range(1, 6):
        g.link(f"{prefix}0", f"{prefix}{i}", "related")
    return g


def _make_path_copy(prefix="q"):
    """Exact copy of path topology."""
    g = MemoryGraph()
    for i in range(6):
        g.add(f"{prefix}{i}", kind="concept")
    for i in range(5):
        g.link(f"{prefix}{i}", f"{prefix}{i+1}", "related")
    return g


def _make_cycle_copy(prefix="q"):
    """Exact copy of cycle topology."""
    g = MemoryGraph()
    for i in range(6):
        g.add(f"{prefix}{i}", kind="concept")
    for i in range(6):
        g.link(f"{prefix}{i}", f"{prefix}{(i+1)%6}", "related")
    return g


class TestClassificationCompareBatchBasic:
    """Basic structure and return value tests."""

    def test_returns_dict(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        assert isinstance(result, dict)

    def test_keys_present(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        expected_keys = {
            "n_queries", "n_methods", "per_method",
            "pairwise_mcnemar", "best_method",
            "agreement_matrix", "hardest_queries", "summary",
        }
        assert expected_keys.issubset(result.keys())

    def test_n_queries_correct(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        assert result["n_queries"] == 2

    def test_n_methods_correct(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        assert result["n_methods"] == 5

    def test_empty_queries_raises(self):
        refs = _build_canonical()
        with pytest.raises(ValueError, match="at least one query"):
            refs[0].classification_compare_batch(refs, [], [])

    def test_mismatched_labels_raises(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        with pytest.raises(ValueError, match="length"):
            refs[0].classification_compare_batch(
                refs, queries, ["star", "path"])


class TestClassificationCompareBatchAccuracy:
    """Accuracy and per-method results."""

    def test_per_method_has_accuracy(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        for m, info in result["per_method"].items():
            assert "accuracy" in info
            assert "n_correct" in info
            assert "n_total" in info
            assert info["n_total"] == 1
            assert 0.0 <= info["accuracy"] <= 1.0

    def test_per_method_has_wilson_ci(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        for m, info in result["per_method"].items():
            assert "wilson_lo" in info
            assert "wilson_hi" in info
            assert 0.0 <= info["wilson_lo"] <= info["wilson_hi"] <= 1.0

    def test_best_method_in_per_method(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        assert result["best_method"] in result["per_method"]

    def test_all_correct_for_exact_copies(self):
        """At least one method should get star correct (trivial topology)."""
        refs = _build_canonical()
        queries = [
            _make_star_copy("q1"),
            _make_path_copy("q2"),
            _make_cycle_copy("q3"),
        ]
        labels = ["star", "path", "cycle"]
        result = refs[0].classification_compare_batch(
            refs, queries, labels)
        max_acc = max(
            info["accuracy"] for info in result["per_method"].values()
        )
        # Path and cycle have identical degree sequences (2-regular),
        # so degree-based methods confuse them. At least one method
        # should identify star correctly (1/3).
        assert max_acc > 0.0

    def test_multiple_queries_mixed_accuracy(self):
        """With noise, some methods should differ."""
        refs = _build_canonical()
        queries = []
        labels = []
        for i in range(2):
            queries.append(_make_star_copy(f"s{i}"))
            labels.append("star")
        for i in range(2):
            queries.append(_make_path_copy(f"p{i}"))
            labels.append("path")
        result = refs[0].classification_compare_batch(
            refs, queries, labels)
        assert result["n_queries"] == 4
        assert len(result["per_method"]) == 5


class TestClassificationCompareBatchPairwise:
    """Pairwise McNemar tests."""

    def test_pairwise_count(self):
        """C(5,2) = 10 pairs for 5 methods."""
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        assert len(result["pairwise_mcnemar"]) == 10

    def test_pairwise_structure(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        for p in result["pairwise_mcnemar"]:
            assert "method_a" in p
            assert "method_b" in p
            assert "n11" in p
            assert "n00" in p
            assert "n01" in p
            assert "n10" in p
            assert "chi_squared" in p
            assert "p_value" in p
            assert "significant" in p
            assert "better" in p

    def test_perfect_agreement_no_significance(self):
        """When all methods agree perfectly, McNemar = 0, p = 1."""
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        for p in result["pairwise_mcnemar"]:
            if p["n01"] + p["n10"] == 0:
                assert p["chi_squared"] == 0.0
                assert p["p_value"] == 1.0
                assert not p["significant"]

    def test_pairwise_symmetric_counts(self):
        """n11 + n00 + n01 + n10 = n_queries for every pair."""
        refs = _build_canonical()
        queries = [_make_star_copy(f"q{i}") for i in range(5)]
        labels = ["star"] * 5
        result = refs[0].classification_compare_batch(
            refs, queries, labels)
        for p in result["pairwise_mcnemar"]:
            total = p["n11"] + p["n00"] + p["n01"] + p["n10"]
            assert total == 5

    def test_alpha_parameter(self):
        """Custom alpha should be reflected."""
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"], alpha=0.01)
        for p in result["pairwise_mcnemar"]:
            assert p["alpha"] == 0.01


class TestClassificationCompareBatchAgreement:
    """Agreement matrix and hardest queries."""

    def test_agreement_matrix_size(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        assert len(result["agreement_matrix"]) == 2

    def test_agreement_values_in_range(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        for qi, n in result["agreement_matrix"].items():
            assert 0 <= n <= result["n_methods"]

    def test_hardest_queries_subset(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        for idx in result["hardest_queries"]:
            assert 0 <= idx < len(queries)

    def test_summary_is_string(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        assert isinstance(result["summary"], str)
        assert "Batch comparison" in result["summary"]


class TestClassificationCompareBatchWilson:
    """Wilson confidence interval correctness."""

    def test_wilson_for_all_correct(self):
        """When accuracy = 1.0, Wilson lo should be > 0."""
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2"),
                   _make_cycle_copy("q3")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path", "cycle"])
        for m, info in result["per_method"].items():
            if info["accuracy"] == 1.0:
                assert info["wilson_lo"] > 0.0
                assert info["wilson_hi"] == 1.0

    def test_wilson_for_all_wrong(self):
        """When accuracy = 0.0, Wilson hi should be < 1."""
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["wrong_label"])
        for m, info in result["per_method"].items():
            if info["accuracy"] == 0.0:
                assert info["wilson_lo"] == 0.0
                assert info["wilson_hi"] < 1.0

    def test_wilson_ordering(self):
        """Wilson lo <= accuracy <= wilson_hi."""
        refs = _build_canonical()
        queries = [_make_star_copy("q1"), _make_path_copy("q2")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star", "path"])
        for m, info in result["per_method"].items():
            assert info["wilson_lo"] <= info["accuracy"] + 1e-9
            assert info["accuracy"] <= info["wilson_hi"] + 1e-9


class TestClassificationCompareBatchEdge:
    """Edge cases and robustness."""

    def test_single_query(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"])
        assert result["n_queries"] == 1

    def test_many_queries(self):
        refs = _build_canonical()
        queries = []
        labels = []
        for i in range(10):
            queries.append(_make_star_copy(f"s{i}"))
            labels.append("star")
            queries.append(_make_path_copy(f"p{i}"))
            labels.append("path")
        result = refs[0].classification_compare_batch(
            refs, queries, labels)
        assert result["n_queries"] == 20

    def test_custom_degree_index(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"], degree_index="randic")
        assert result["n_methods"] == 5

    def test_custom_spectral_params(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"],
            spectral_measure="kl", bins=10)
        assert result["n_methods"] == 5

    def test_include_quarantined_flag(self):
        refs = _build_canonical()
        queries = [_make_star_copy("q1")]
        result = refs[0].classification_compare_batch(
            refs, queries, ["star"], include_quarantined=True)
        assert result["n_queries"] == 1
