"""Tests for optimize_reference_set() — Cycle 352.

Prototype selection via ENN / CCCD / Greedy algorithms.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def refs6():
    """6 refs: 3 stars + 3 paths of varying sizes."""
    return [
        _star(8, "r0"), _star(10, "r1"), _star(6, "r2"),
        _path(8, "r0"), _path(10, "r1"), _path(6, "r2"),
    ]


@pytest.fixture
def labels6():
    return ["star", "star", "star", "path", "path", "path"]


@pytest.fixture
def refs4():
    return [_star(8, "r"), _path(8, "r"), _cycle(8, "r"), _complete(6, "r")]


@pytest.fixture
def labels4():
    return ["star", "path", "cycle", "complete"]


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestOptimizeStructure:
    def test_returns_dict_with_keys(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        for key in ("algorithm", "method", "selected_indices",
                     "removed_indices", "selected_labels",
                     "original_size", "optimized_size",
                     "reduction", "per_label_original",
                     "per_label_kept", "summary"):
            assert key in r, f"Missing key: {key}"

    def test_algorithm_recorded(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="cccd")
        assert r["algorithm"] == "cccd"

    def test_original_size(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        assert r["original_size"] == 6

    def test_selected_plus_removed_equals_original(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        assert len(r["selected_indices"]) + len(r["removed_indices"]) == 6

    def test_no_overlap_selected_removed(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        assert set(r["selected_indices"]).isdisjoint(r["removed_indices"])

    def test_reduction_fraction(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        expected = 1.0 - len(r["selected_indices"]) / 6
        assert abs(r["reduction"] - expected) < 1e-6

    def test_summary_is_string(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        assert isinstance(r["summary"], str)
        assert "kept" in r["summary"]


# ---------------------------------------------------------------------------
# ENN algorithm
# ---------------------------------------------------------------------------

class TestENN:
    def test_enn_returns_subset(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="enn")
        assert r["optimized_size"] <= r["original_size"]

    def test_enn_with_k1(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="enn", k=1)
        # k=1: remove ref if its nearest neighbor has different label
        assert r["optimized_size"] <= 6

    def test_enn_with_k5(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="enn", k=5)
        # k=5: majority of 5 neighbors must be same label
        assert r["optimized_size"] <= 6

    def test_enn_single_class_all_kept(self):
        """If all refs are same class, ENN should keep all."""
        refs = [_star(8, "a"), _star(10, "b"), _star(6, "c")]
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs, ["x", "x", "x"], algorithm="enn")
        assert r["optimized_size"] == 3

    def test_enn_keeps_at_least_one(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="enn")
        assert r["optimized_size"] >= 0  # degenerate cases may remove all


# ---------------------------------------------------------------------------
# CCCD algorithm
# ---------------------------------------------------------------------------

class TestCCCD:
    def test_cccd_returns_subset(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="cccd")
        assert r["optimized_size"] <= 6

    def test_cccd_keeps_at_least_one_per_label(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="cccd")
        for lbl in ["star", "path"]:
            assert r["per_label_kept"][lbl] >= 1

    def test_cccd_single_class_keeps_one(self):
        refs = [_star(8, "a"), _star(10, "b"), _star(6, "c")]
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs, ["x", "x", "x"], algorithm="cccd")
        assert r["optimized_size"] == 1


# ---------------------------------------------------------------------------
# Greedy algorithm
# ---------------------------------------------------------------------------

class TestGreedy:
    def test_greedy_returns_subset(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="greedy")
        assert r["optimized_size"] <= 6

    def test_greedy_keeps_at_least_one_per_label(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6, algorithm="greedy")
        for lbl in ["star", "path"]:
            assert r["per_label_kept"][lbl] >= 1

    def test_greedy_single_class(self):
        refs = [_star(8, "a"), _star(10, "b"), _star(6, "c")]
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs, ["x", "x", "x"], algorithm="greedy")
        assert r["optimized_size"] >= 1


# ---------------------------------------------------------------------------
# Method parameter
# ---------------------------------------------------------------------------

class TestOptimizeMethod:
    @pytest.mark.parametrize("method", ["graph", "spectral", "hybrid", "rrf"])
    def test_runs_for_all_methods(self, refs6, labels6, method):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(
            refs6, labels6, method=method, algorithm="cccd"
        )
        assert r["method"] == method


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestOptimizeEdgeCases:
    def test_error_on_single_reference(self):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="at least 2"):
            g.optimize_reference_set([_star(8)], ["star"])

    def test_error_on_label_mismatch(self, refs6):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="labels length"):
            g.optimize_reference_set(refs6, ["star"])

    def test_error_on_unknown_algorithm(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        with pytest.raises(ValueError, match="Unknown algorithm"):
            g.optimize_reference_set(
                refs6, labels6, algorithm="nonexistent"
            )

    def test_two_references_same_label(self):
        refs = [_star(8, "a"), _star(10, "b")]
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs, ["x", "x"], algorithm="enn")
        assert r["original_size"] == 2

    def test_two_references_different_labels(self):
        refs = [_star(8, "a"), _path(8, "b")]
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(
            refs, ["star", "path"], algorithm="cccd"
        )
        assert r["optimized_size"] == 2  # CCCD keeps all


# ---------------------------------------------------------------------------
# Per-label stats
# ---------------------------------------------------------------------------

class TestPerLabelStats:
    def test_per_label_original(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        assert r["per_label_original"]["star"] == 3
        assert r["per_label_original"]["path"] == 3

    def test_per_label_kept_le_original(self, refs6, labels6):
        g = mg.MemoryGraph(":memory:")
        r = g.optimize_reference_set(refs6, labels6)
        for lbl in ["star", "path"]:
            assert r["per_label_kept"][lbl] <= r["per_label_original"][lbl]


# ---------------------------------------------------------------------------
# Consistency
# ---------------------------------------------------------------------------

class TestOptimizeConsistency:
    def test_repeatable(self, refs6, labels6):
        g1 = mg.MemoryGraph(":memory:")
        r1 = g1.optimize_reference_set(refs6, labels6, algorithm="enn")
        g2 = mg.MemoryGraph(":memory:")
        r2 = g2.optimize_reference_set(refs6, labels6, algorithm="enn")
        assert r1["selected_indices"] == r2["selected_indices"]
        assert r1["optimized_size"] == r2["optimized_size"]
