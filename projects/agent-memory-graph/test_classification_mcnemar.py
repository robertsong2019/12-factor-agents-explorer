"""Tests for classification_mcnemar() — McNemar significance test.

Standalone McNemar's χ² test comparing two classification methods
on the same set of queries.  Research #046 ✅, Insight #199 ✅.
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
    return g


def _path(n, label=""):
    g = mg.MemoryGraph(":memory:")
    prev = g.add(f"p0_{label}", "n")
    for i in range(1, n):
        curr = g.add(f"p{i}_{label}", "n")
        g.link(prev.id, curr.id, "e")
        prev = curr
    return g


def _cycle(n, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"c{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        g.link(nodes[i].id, nodes[(i + 1) % n].id, "e")
    return g


def _complete(n, label=""):
    g = mg.MemoryGraph(":memory:")
    nodes = [g.add(f"k{i}_{label}", "n") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g.link(nodes[i].id, nodes[j].id, "e")
    return g


def _bipartite(a, b, label=""):
    g = mg.MemoryGraph(":memory:")
    na = [g.add(f"a{i}_{label}", "n") for i in range(a)]
    nb = [g.add(f"b{i}_{label}", "n") for i in range(b)]
    for x in na:
        for y in nb:
            g.link(x.id, y.id, "e")
    return g


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def refs4():
    return [_star(8, "r"), _path(8, "r"), _cycle(8, "r"), _complete(6, "r")]


@pytest.fixture
def queries4():
    return [_star(8, "q"), _path(8, "q"), _cycle(8, "q"), _complete(6, "q")]


@pytest.fixture
def labels4():
    return ["star", "path", "cycle", "complete"]


# ---------------------------------------------------------------------------
# Structure & Return Shape
# ---------------------------------------------------------------------------

class TestMcNemarStructure:
    def test_returns_dict(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert isinstance(r, dict)

    def test_has_all_keys(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        expected_keys = {
            "method_a", "method_b", "n11", "n00", "n01", "n10",
            "n_agree", "chi_squared", "p_value", "significant",
            "accuracy_a", "accuracy_b", "better", "alpha",
            "n_queries", "summary",
        }
        assert expected_keys <= set(r.keys()), (
            f"Missing keys: {expected_keys - set(r.keys())}"
        )

    def test_method_names_preserved(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert r["method_a"] == "graph"
        assert r["method_b"] == "spectral"

    def test_n_queries(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert r["n_queries"] == 4

    def test_summary_is_string(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert isinstance(r["summary"], str)
        assert len(r["summary"]) > 0

    def test_alpha_default(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert r["alpha"] == 0.05


# ---------------------------------------------------------------------------
# Contingency Table Integrity
# ---------------------------------------------------------------------------

class TestContingencyTable:
    def test_table_sums_to_n(self, refs4, queries4, labels4):
        """n11 + n00 + n01 + n10 must equal n_queries."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        total = r["n11"] + r["n00"] + r["n01"] + r["n10"]
        assert total == r["n_queries"]

    def test_n_agree_equals_n11_plus_n00(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert r["n_agree"] == r["n11"] + r["n00"]

    def test_non_negative_counts(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        for key in ("n11", "n00", "n01", "n10"):
            assert r[key] >= 0

    def test_accuracy_in_range(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert 0.0 <= r["accuracy_a"] <= 1.0
        assert 0.0 <= r["accuracy_b"] <= 1.0


# ---------------------------------------------------------------------------
# McNemar χ² Calculation
# ---------------------------------------------------------------------------

class TestChiSquaredCalc:
    def test_chi_squared_non_negative(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert r["chi_squared"] >= 0.0

    def test_p_value_in_range(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert 0.0 <= r["p_value"] <= 1.0

    def test_no_discordant_pairs(self):
        """When n01 = n10 = 0, χ² = 0 and p = 1.0."""
        # Use same method against itself indirectly by using
        # identical queries that all methods classify the same way.
        # Build refs and queries that are trivially classifiable.
        g = mg.MemoryGraph(":memory:")
        ref = _star(8, "ref")
        q = _star(8, "q")
        # With a single reference, every method must pick it.
        r = g.classification_mcnemar(
            [ref], [q], ["ref"],
            method_a="graph", method_b="spectral",
        )
        assert r["n01"] == 0
        assert r["n10"] == 0
        assert r["chi_squared"] == 0.0
        assert r["p_value"] == 1.0
        assert r["significant"] is False

    def test_manual_chi_squared(self):
        """Verify χ² matches manual computation for known values."""
        # χ² = (|n01 - n10| - 1)² / (n01 + n10)
        # If n01=3, n10=7: χ² = (4-1)²/10 = 0.9
        # We can't easily control method output, but we can
        # verify the formula via the contingency table.
        g = mg.MemoryGraph(":memory:")
        refs = [_star(8, "r"), _path(8, "r"), _cycle(8, "r")]
        queries = [_star(8, "q"), _path(8, "q"), _cycle(8, "q")]
        labels = ["star", "path", "cycle"]
        r = g.classification_mcnemar(
            refs, queries, labels,
            method_a="graph", method_b="spectral",
        )
        n01, n10 = r["n01"], r["n10"]
        if n01 + n10 > 0:
            expected_chi2 = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
        else:
            expected_chi2 = 0.0
        assert abs(r["chi_squared"] - round(expected_chi2, 6)) < 1e-5

    def test_p_value_from_erfc(self):
        """p-value should match erfc(sqrt(chi2/2))."""
        g = mg.MemoryGraph(":memory:")
        refs = [_star(8, "r"), _path(8, "r"), _cycle(8, "r")]
        queries = [_star(8, "q"), _path(8, "q"), _cycle(8, "q")]
        labels = ["star", "path", "cycle"]
        r = g.classification_mcnemar(
            refs, queries, labels,
            method_a="graph", method_b="spectral",
        )
        chi2 = r["chi_squared"]
        if chi2 == 0.0:
            assert r["p_value"] == 1.0
        else:
            expected_p = math.erfc(math.sqrt(chi2 / 2))
            assert abs(r["p_value"] - round(expected_p, 6)) < 1e-5


# ---------------------------------------------------------------------------
# Identical Methods / Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_same_method_raises(self, refs4, queries4, labels4):
        """method_a == method_b should raise ValueError."""
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="must differ"):
            g.classification_mcnemar(
                refs4, queries4, labels4,
                method_a="graph", method_b="graph",
            )

    def test_empty_queries_raises(self, refs4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="at least one query"):
            g.classification_mcnemar(
                refs4, [], [],
                method_a="graph", method_b="spectral",
            )

    def test_label_mismatch_raises(self, refs4, queries4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="expected_labels length"):
            g.classification_mcnemar(
                refs4, queries4, ["star"],
                method_a="graph", method_b="spectral",
            )

    def test_single_query(self):
        """Works with a single query."""
        g = mg.MemoryGraph(":memory:")
        ref = _star(8, "r")
        q = _star(8, "q")
        r = g.classification_mcnemar(
            [ref], [q], ["ref"],
            method_a="graph", method_b="spectral",
        )
        assert r["n_queries"] == 1
        assert r["n11"] + r["n00"] + r["n01"] + r["n10"] == 1

    def test_unknown_method_raises(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="Unknown method"):
            g.classification_mcnemar(
                refs4, queries4, labels4,
                method_a="graph", method_b="nonexistent",
            )


# ---------------------------------------------------------------------------
# Better / Significant Logic
# ---------------------------------------------------------------------------

class TestBetterAndSignificant:
    def test_better_is_string(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert isinstance(r["better"], str)

    def test_significant_is_bool(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        assert isinstance(r["significant"], bool)

    def test_no_difference_better_is_tie(self):
        """When both methods agree perfectly, better = 'tie'."""
        g = mg.MemoryGraph(":memory:")
        ref = _star(8, "r")
        q = _star(8, "q")
        r = g.classification_mcnemar(
            [ref], [q], ["ref"],
            method_a="graph", method_b="spectral",
        )
        assert r["better"] == "tie"
        assert r["significant"] is False

    def test_custom_alpha(self, refs4, queries4, labels4):
        """Custom alpha is respected."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
            alpha=0.50,
        )
        assert r["alpha"] == 0.50


# ---------------------------------------------------------------------------
# Multiple Methods
# ---------------------------------------------------------------------------

class TestMultipleMethods:
    def test_hybrid_vs_rrf(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="hybrid", method_b="rrf",
        )
        assert r["method_a"] == "hybrid"
        assert r["method_b"] == "rrf"
        assert r["n_queries"] == 4

    def test_bayesian_vs_knn(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="bayesian", method_b="knn",
        )
        assert r["method_a"] == "bayesian"
        assert r["method_b"] == "knn"

    def test_weighted_vs_max_confidence(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="weighted_average", method_b="max_confidence",
        )
        assert r["method_a"] == "weighted_average"
        assert r["method_b"] == "max_confidence"


# ---------------------------------------------------------------------------
# Accuracy Consistency
# ---------------------------------------------------------------------------

class TestAccuracyConsistency:
    def test_accuracy_matches_n_correct(self, refs4, queries4, labels4):
        """accuracy_a should equal (n11 + n10) / n_queries."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        expected_a = (r["n11"] + r["n10"]) / r["n_queries"]
        assert abs(r["accuracy_a"] - round(expected_a, 6)) < 1e-5

    def test_accuracy_b_matches_n_correct(self, refs4, queries4, labels4):
        """accuracy_b should equal (n11 + n01) / n_queries."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_mcnemar(
            refs4, queries4, labels4,
            method_a="graph", method_b="spectral",
        )
        expected_b = (r["n11"] + r["n01"]) / r["n_queries"]
        assert abs(r["accuracy_b"] - round(expected_b, 6)) < 1e-5
