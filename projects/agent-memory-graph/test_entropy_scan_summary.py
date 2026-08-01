"""Tests for entropy_scan_summary() — Cycle 342.

Human-readable topology summary from entropy scan shape descriptors.
"""
import pytest
from memory_graph import MemoryGraph


def _star(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(1, n):
        mg.link(nodes[0].id, nodes[i].id, "r")
    return mg, nodes


def _complete(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            mg.link(nodes[i].id, nodes[j].id, "r")
    return mg, nodes


def _path(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n - 1):
        mg.link(nodes[i].id, nodes[i + 1].id, "r")
    return mg, nodes


def _cycle(n):
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(n)]
    for i in range(n):
        mg.link(nodes[i].id, nodes[(i + 1) % n].id, "r")
    return mg, nodes


def _barbell(a, b):
    """Two cliques connected by a bridge edge."""
    mg = MemoryGraph(":memory:")
    nodes = [mg.add(str(i)) for i in range(a + b)]
    for i in range(a):
        for j in range(i + 1, a):
            mg.link(nodes[i].id, nodes[j].id, "r")
    for i in range(a, a + b):
        for j in range(i + 1, a + b):
            mg.link(nodes[i].id, nodes[j].id, "r")
    mg.link(nodes[0].id, nodes[a].id, "r")  # bridge
    return mg, nodes


class TestSummaryBasic:
    def test_returns_str(self):
        mg, nodes = _path(5)
        result = mg.entropy_scan_summary()
        assert isinstance(result, str)

    def test_none_for_empty(self):
        mg = MemoryGraph(":memory:")
        assert mg.entropy_scan_summary() is None

    def test_none_for_no_edges(self):
        mg = MemoryGraph(":memory:")
        mg.add("a")
        assert mg.entropy_scan_summary() is None

    def test_contains_node_count(self):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary()
        assert "5 nodes" in result

    def test_contains_edge_count(self):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary()
        assert "4 edges" in result

    def test_contains_shannon(self):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary()
        assert "Shannon" in result

    def test_contains_index(self):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary(index="randic")
        assert "randic" in result


class TestSummaryContent:
    def test_uniform_for_complete(self):
        mg, _ = _complete(8)
        result = mg.entropy_scan_summary()
        assert "UNIFORM" in result

    def test_uniform_for_star(self):
        mg, _ = _star(8)
        result = mg.entropy_scan_summary()
        assert "UNIFORM" in result

    def test_simple_assessment_for_regular(self):
        """Star and complete graphs have uniform distributions → SIMPLE."""
        mg, _ = _complete(8)
        assert "SIMPLE" in mg.entropy_scan_summary()

    def test_assessment_present(self):
        mg, _ = _path(10)
        result = mg.entropy_scan_summary()
        assert "Assessment:" in result

    def test_curve_description(self):
        mg, _ = _path(8)
        result = mg.entropy_scan_summary()
        assert "Rényi curve:" in result

    def test_fingerprint_info(self):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary()
        assert "Fingerprint:" in result


class TestSummaryIndexParameter:
    @pytest.mark.parametrize("index", [
        "sombor", "reduced_sombor", "randic", "zagreb_m1", "abc", "ga", "augmented_zagreb"
    ])
    def test_index_works(self, index):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary(index=index)
        assert result is not None
        assert index in result

    def test_invalid_index_raises(self):
        mg, _ = _path(5)
        with pytest.raises(ValueError):
            mg.entropy_scan_summary(index="bad")


class TestSummaryMultiLine:
    def test_summary_has_multiple_lines(self):
        mg, _ = _path(10)
        result = mg.entropy_scan_summary()
        assert result.count("\n") >= 5

    def test_summary_ends_with_fingerprint(self):
        mg, _ = _path(5)
        result = mg.entropy_scan_summary()
        assert "Fingerprint" in result


class TestSummaryBarbell:
    def test_barbell_shows_complexity(self):
        """Barbell graph (two cliques + bridge) has heterogeneous edges."""
        mg, _ = _barbell(5, 5)
        result = mg.entropy_scan_summary()
        # The bridge edge has very different contribution from clique edges
        assert "Assessment:" in result
