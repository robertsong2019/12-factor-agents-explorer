"""Tests for memory_age_stats() — age distribution statistics."""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mixed_age_graph():
    """Graph with a few nodes."""
    g = MemoryGraph()
    g.add("recent1", kind="fact")
    g.add("recent2", kind="fact")
    g.add("task1", kind="task")
    g.add("idea1", kind="idea")
    g.add("old1", kind="fact")
    return g


class TestMemoryAgeStats:

    def test_empty_graph(self):
        g = MemoryGraph()
        r = g.memory_age_stats()
        assert r["count"] == 0
        assert r["mean_age_hours"] == 0
        assert r["by_kind"] == {}

    def test_basic_structure(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats()
        for key in ("count", "mean_age_hours", "median_age_hours",
                     "std_age_hours", "min_age_hours", "max_age_hours",
                     "p25_age_hours", "p50_age_hours", "p75_age_hours",
                     "p90_age_hours", "by_kind", "fresh_nodes", "stale_nodes"):
            assert key in r

    def test_count(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats()
        assert r["count"] == 5

    def test_kind_filter(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats(kind="fact")
        assert r["count"] == 3  # recent1, recent2, old1

    def test_kind_filter_no_match(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats(kind="nonexistent")
        assert r["count"] == 0

    def test_ages_positive(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats()
        assert r["min_age_hours"] >= 0
        assert r["mean_age_hours"] >= 0
        assert r["max_age_hours"] >= r["min_age_hours"]

    def test_fresh_nodes(self):
        """Nodes just created should be fresh (< 1 hour)."""
        g = MemoryGraph()
        g.add("n1")
        g.add("n2")
        r = g.memory_age_stats()
        assert r["fresh_nodes"] == 2

    def test_stale_nodes_zero(self):
        """Fresh nodes shouldn't be stale."""
        g = MemoryGraph()
        g.add("n1")
        r = g.memory_age_stats()
        assert r["stale_nodes"] == 0

    def test_by_kind_structure(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats()
        assert "fact" in r["by_kind"]
        assert "task" in r["by_kind"]
        assert "idea" in r["by_kind"]
        for k, v in r["by_kind"].items():
            assert "count" in v
            assert "mean_age_hours" in v
            assert "median_age_hours" in v

    def test_by_kind_counts(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats()
        assert r["by_kind"]["fact"]["count"] == 3
        assert r["by_kind"]["task"]["count"] == 1
        assert r["by_kind"]["idea"]["count"] == 1

    def test_percentile_ordering(self, mixed_age_graph):
        r = mixed_age_graph.memory_age_stats()
        assert r["p25_age_hours"] <= r["p50_age_hours"]
        assert r["p50_age_hours"] <= r["p75_age_hours"]
        assert r["p75_age_hours"] <= r["p90_age_hours"]

    def test_single_node(self):
        g = MemoryGraph()
        g.add("only", kind="fact")
        r = g.memory_age_stats()
        assert r["count"] == 1
        assert r["std_age_hours"] == 0  # std of single value
        assert r["min_age_hours"] == r["max_age_hours"]

    def test_std_zero_for_identical(self):
        """With one node, std should be 0."""
        g = MemoryGraph()
        g.add("n1")
        r = g.memory_age_stats()
        assert r["std_age_hours"] == 0

    def test_two_nodes(self):
        g = MemoryGraph()
        g.add("n1", kind="a")
        g.add("n2", kind="b")
        r = g.memory_age_stats()
        assert r["count"] == 2
        assert len(r["by_kind"]) == 2

    def test_all_fresh(self, mixed_age_graph):
        """Recently created nodes should all be fresh."""
        r = mixed_age_graph.memory_age_stats()
        assert r["fresh_nodes"] == 5

    def test_fresh_count_matches(self):
        g = MemoryGraph()
        for i in range(10):
            g.add(f"n{i}")
        r = g.memory_age_stats()
        assert r["fresh_nodes"] == 10
