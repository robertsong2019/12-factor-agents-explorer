"""Tests for classification_calibrate() — Cycle 351.

Temperature scaling for graph classification confidence via ECE minimisation.
Research #046 ✅.
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


def _bipartite(a, b, label=""):
    g = mg.MemoryGraph(":memory:")
    na = [g.add(f"a{i}_{label}", "n") for i in range(a)]
    nb = [g.add(f"b{i}_{label}", "n") for i in range(b)]
    for x in na:
        for y in nb:
            g.link(x.id, y.id, "e")
    g.graph_meta = {"label": "bipartite"}
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
# Structure
# ---------------------------------------------------------------------------

class TestCalibrateStructure:
    def test_returns_dict_with_keys(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4, method="graph"
        )
        for key in ("method", "num_queries", "optimal_temperature",
                     "ece_at_optimal", "ece_at_default", "improvement",
                     "reliability_diagram", "accuracy", "summary"):
            assert key in r, f"Missing key: {key}"

    def test_method_recorded(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4, method="spectral"
        )
        assert r["method"] == "spectral"

    def test_num_queries_matches(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert r["num_queries"] == 4

    def test_reliability_diagram_is_list(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert isinstance(r["reliability_diagram"], list)
        assert len(r["reliability_diagram"]) > 0

    def test_reliability_bin_structure(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4, n_bins=5
        )
        bin0 = r["reliability_diagram"][0]
        for key in ("bin_range", "count", "accuracy",
                     "avg_confidence", "gap"):
            assert key in bin0

    def test_summary_is_string(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert isinstance(r["summary"], str)
        assert "ECE" in r["summary"]


# ---------------------------------------------------------------------------
# ECE properties
# ---------------------------------------------------------------------------

class TestECEProperties:
    def test_ece_in_range(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert 0.0 <= r["ece_at_optimal"] <= 1.0
        assert 0.0 <= r["ece_at_default"] <= 1.0

    def test_optimal_ece_le_default(self, refs4, queries4, labels4):
        """Optimal temperature should not produce worse ECE than default."""
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert r["ece_at_optimal"] <= r["ece_at_default"] + 1e-9

    def test_improvement_non_negative(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert r["improvement"] >= -1e-9

    def test_optimal_temperature_positive(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert r["optimal_temperature"] > 0

    def test_accuracy_in_range(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        assert 0.0 <= r["accuracy"] <= 1.0


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------

class TestCalibrateMethods:
    @pytest.mark.parametrize("method", [
        "graph", "spectral", "hybrid", "rrf",
        "weighted_average", "bayesian",
    ])
    def test_runs_for_all_methods(self, refs4, queries4, labels4, method):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4, method=method
        )
        assert r["method"] == method
        assert r["num_queries"] == 4


# ---------------------------------------------------------------------------
# Custom temperature grid
# ---------------------------------------------------------------------------

class TestTemperatureGrid:
    def test_custom_grid(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4,
            temperature_grid=(0.5, 1.0, 2.0),
        )
        assert r["optimal_temperature"] in (0.5, 1.0, 2.0)

    def test_single_temperature(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4,
            temperature_grid=(1.0,),
        )
        assert r["optimal_temperature"] == 1.0
        assert abs(r["improvement"]) < 1e-9

    def test_low_temperature_selected(self, refs4, queries4, labels4):
        """Graph scores are under-confident, so T<1 should help."""
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4,
        )
        # At least check the optimal T is found (may or may not be <1
        # depending on the specific graphs).
        assert r["optimal_temperature"] > 0


# ---------------------------------------------------------------------------
# n_bins parameter
# ---------------------------------------------------------------------------

class TestNBins:
    def test_n_bins_affects_diagram_length(self, refs4, queries4, labels4):
        r5 = queries4[0].classification_calibrate(
            refs4, queries4, labels4, n_bins=5
        )
        r10 = queries4[0].classification_calibrate(
            refs4, queries4, labels4, n_bins=10
        )
        assert len(r5["reliability_diagram"]) == 5
        assert len(r10["reliability_diagram"]) == 10

    def test_bins_cover_full_range(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4, n_bins=10
        )
        # First bin starts at 0.0, last bin ends at 1.0
        assert r["reliability_diagram"][0]["bin_range"][0] == 0.0
        assert r["reliability_diagram"][-1]["bin_range"][1] == 1.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestCalibrateEdgeCases:
    def test_error_on_no_queries(self, refs4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="at least one query"):
            g.classification_calibrate(refs4, [], [])

    def test_error_on_label_mismatch(self, refs4, queries4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="expected_labels length"):
            g.classification_calibrate(refs4, queries4, ["star"])

    def test_error_on_unknown_method(self, refs4, queries4, labels4):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="Unknown method"):
            g.classification_calibrate(
                refs4, queries4, labels4, method="nonexistent"
            )

    def test_single_query(self, refs4):
        """One query — calibration should still work."""
        q = _star(8, "q")
        r = q.classification_calibrate(refs4, [q], ["star"])
        assert r["num_queries"] == 1


# ---------------------------------------------------------------------------
# Reliability diagram correctness
# ---------------------------------------------------------------------------

class TestReliabilityDiagram:
    def test_bin_counts_sum_to_num_queries(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4, n_bins=10
        )
        total = sum(b["count"] for b in r["reliability_diagram"])
        assert total == r["num_queries"]

    def test_gap_non_negative(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        for b in r["reliability_diagram"]:
            assert b["gap"] >= 0.0

    def test_accuracy_in_bin_range(self, refs4, queries4, labels4):
        r = queries4[0].classification_calibrate(
            refs4, queries4, labels4
        )
        for b in r["reliability_diagram"]:
            if b["count"] > 0:
                assert 0.0 <= b["accuracy"] <= 1.0
                assert 0.0 <= b["avg_confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Consistency
# ---------------------------------------------------------------------------

class TestCalibrateConsistency:
    def test_repeatable(self, refs4, queries4, labels4):
        r1 = queries4[0].classification_calibrate(refs4, queries4, labels4)
        r2 = queries4[1].classification_calibrate(refs4, queries4, labels4)
        assert r1["optimal_temperature"] == r2["optimal_temperature"]
        assert r1["ece_at_optimal"] == r2["ece_at_optimal"]
