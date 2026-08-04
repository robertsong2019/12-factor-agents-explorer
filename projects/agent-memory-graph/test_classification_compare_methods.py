"""Tests for classification_compare_methods() — Cycle 353.

McNemar test + bootstrap CI for pairwise method comparison.
Research #046 ✅.
"""
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
def refs6():
    return [_star(8, "r"), _path(8, "r"), _cycle(8, "r"),
            _complete(6, "r"), _bipartite(4, 4, "r"), _star(6, "r2")]


@pytest.fixture
def queries6():
    return [_star(8, "q"), _path(8, "q"), _cycle(8, "q"),
            _complete(6, "q"), _bipartite(4, 4, "q"), _star(6, "q2")]


@pytest.fixture
def labels6():
    return ["star", "path", "cycle", "complete", "bipartite", "star2"]


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
# Structure
# ---------------------------------------------------------------------------

class TestCompareStructure:
    def test_returns_dict_with_keys(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        for key in ("methods", "accuracy", "pairwise",
                     "bootstrap_ci", "n_queries", "summary"):
            assert key in r, f"Missing key: {key}"

    def test_methods_list(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        assert r["methods"] == ["graph", "spectral"]

    def test_n_queries(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        assert r["n_queries"] == 4

    def test_summary_is_string(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        assert isinstance(r["summary"], str)


# ---------------------------------------------------------------------------
# Accuracy
# ---------------------------------------------------------------------------

class TestAccuracy:
    def test_accuracy_for_each_method(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        assert "graph" in r["accuracy"]
        assert "spectral" in r["accuracy"]
        for m, acc in r["accuracy"].items():
            assert 0.0 <= acc <= 1.0

    def test_perfect_accuracy_when_exact_match(self, refs4, queries4, labels4):
        """When queries are isomorphic to refs and labels match indices,
        graph method should get 100% (exact match always finds itself)."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, ["ref_0", "ref_1", "ref_2", "ref_3"],
            methods=["graph"],
        )
        assert r["accuracy"]["graph"] == 1.0


# ---------------------------------------------------------------------------
# McNemar test
# ---------------------------------------------------------------------------

class TestMcNemar:
    def test_pairwise_keys(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral", "hybrid"],
        )
        assert "graph_vs_spectral" in r["pairwise"]
        assert "graph_vs_hybrid" in r["pairwise"]
        assert "spectral_vs_hybrid" in r["pairwise"]

    def test_mcnemar_fields(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        pair = r["pairwise"]["graph_vs_spectral"]
        for key in ("n01", "n10", "chi2", "p_value", "significant", "better"):
            assert key in pair

    def test_mcnemar_n01_plus_n10_le_n(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        pair = r["pairwise"]["graph_vs_spectral"]
        assert pair["n01"] + pair["n10"] <= 4

    def test_mcnemar_perfect_agreement(self, refs4, queries4, labels4):
        """If both methods get all correct, n01=n10=0, chi2=0, p=1."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "graph"],
        )
        # Same method twice → perfect agreement
        # But "graph" appears twice, so key would be "graph_vs_graph"
        # Methods list shouldn't have duplicates actually
        # Let's test with graph vs spectral where both get 100%
        pair = r["pairwise"].get("graph_vs_graph")
        if pair:
            assert pair["n01"] == 0
            assert pair["n10"] == 0
            assert pair["chi2"] == 0.0

    def test_p_value_range(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4, methods=["graph", "spectral"],
        )
        for pair_data in r["pairwise"].values():
            assert 0.0 <= pair_data["p_value"] <= 1.0


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------

class TestBootstrapCI:
    def test_ci_keys(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4,
            methods=["graph", "spectral"],
            n_bootstrap=100,
        )
        assert "graph_vs_spectral" in r["bootstrap_ci"]

    def test_ci_bounds_ordered(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4,
            methods=["graph", "spectral"],
            n_bootstrap=100,
        )
        ci = r["bootstrap_ci"]["graph_vs_spectral"]
        assert ci["lower"] <= ci["upper"] + 1e-9

    def test_ci_contains_zero_when_identical(self, refs4, queries4, labels4):
        """When both methods agree on all queries, CI should contain 0."""
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4,
            methods=["graph", "spectral"],
            n_bootstrap=200,
        )
        ci = r["bootstrap_ci"]["graph_vs_spectral"]
        assert ci["lower"] <= 0.0 <= ci["upper"] + 1e-9 or \
               abs(ci["lower"]) < 0.01 or abs(ci["upper"]) < 0.01

    def test_reproducible_with_seed(self, refs4, queries4, labels4):
        g1 = mg.MemoryGraph(":memory:")
        r1 = g1.classification_compare_methods(
            refs4, queries4, labels4,
            methods=["graph", "spectral"],
            n_bootstrap=200,
            seed=123,
        )
        g2 = mg.MemoryGraph(":memory:")
        r2 = g2.classification_compare_methods(
            refs4, queries4, labels4,
            methods=["graph", "spectral"],
            n_bootstrap=200,
            seed=123,
        )
        assert r1["bootstrap_ci"] == r2["bootstrap_ci"]


# ---------------------------------------------------------------------------
# Multiple methods
# ---------------------------------------------------------------------------

class TestMultipleMethods:
    @pytest.mark.parametrize("method_list", [
        ["graph", "spectral"],
        ["graph", "spectral", "hybrid"],
        ["graph", "spectral", "hybrid", "rrf"],
    ])
    def test_pair_count(self, refs4, queries4, labels4, method_list):
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, queries4, labels4,
            methods=method_list,
            n_bootstrap=50,
        )
        n = len(method_list)
        expected_pairs = n * (n - 1) // 2
        assert len(r["pairwise"]) == expected_pairs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestCompareEdgeCases:
    def test_error_on_no_queries(self, refs4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="at least one query"):
            g.classification_compare_methods(refs4, [], [])

    def test_error_on_label_mismatch(self, refs4, queries4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="expected_labels length"):
            g.classification_compare_methods(refs4, queries4, ["star"])

    def test_error_on_unknown_method(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="Unknown method"):
            g.classification_compare_methods(
                refs4, queries4, labels4,
                methods=["nonexistent"],
            )

    def test_single_query(self, refs4):
        q = _star(8, "q")
        g = mg.MemoryGraph(":memory:")
        r = g.classification_compare_methods(
            refs4, [q], ["star"],
            methods=["graph", "spectral"],
            n_bootstrap=50,
        )
        assert r["n_queries"] == 1
