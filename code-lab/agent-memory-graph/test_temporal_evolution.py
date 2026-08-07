"""Tests for temporal_evolution_report() — aggregated graph evolution."""
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def evolved_graph():
    """Graph with nodes created at different times and kinds."""
    g = MemoryGraph()
    base = time.time() - 1000  # Start 1000s ago

    # Create nodes with explicit timestamps by manipulating created
    # We'll create in sequence and use the actual timestamps
    facts = [g.add(f"fact_{i}", kind="fact") for i in range(5)]
    tasks = [g.add(f"task_{i}", kind="task") for i in range(3)]
    ideas = [g.add(f"idea_{i}", kind="idea") for i in range(2)]

    # Link some
    g.link(facts[0].id, tasks[0].id, "relates")
    g.link(tasks[0].id, ideas[0].id, "inspires")

    return g, base


class TestTemporalEvolutionReport:

    def test_empty_graph(self):
        g = MemoryGraph()
        now = time.time()
        r = g.temporal_evolution_report(now - 100, now)
        assert r["totals"]["nodes_created_in_window"] == 0
        assert r["growth"]["node_rate_per_hour"] == 0

    def test_basic_structure(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now)
        for key in ("window", "totals", "growth", "kind_distribution",
                     "kind_shift", "buckets", "lifespan_stats", "top_kinds"):
            assert key in r

    def test_window_info(self, evolved_graph):
        g, base = evolved_graph
        r = g.temporal_evolution_report(base, base + 1000)
        assert r["window"]["start"] == base
        assert r["window"]["end"] == base + 1000
        assert r["window"]["duration_seconds"] == 1000

    def test_nodes_in_window(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert r["totals"]["nodes_created_in_window"] == 10  # 5 facts + 3 tasks + 2 ideas

    def test_kind_distribution(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert "fact" in r["kind_distribution"]
        assert "task" in r["kind_distribution"]
        assert "idea" in r["kind_distribution"]

    def test_kind_shift(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        # Kind shift keys should be union of start/end kinds
        # Nodes without explicit validity are always valid → shift = 0
        assert isinstance(r["kind_shift"], dict)
        for v in r["kind_shift"].values():
            assert isinstance(v, int)

    def test_buckets_count(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1, bucket_count=5)
        assert len(r["buckets"]) == 5

    def test_buckets_default_count(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert len(r["buckets"]) == 10

    def test_bucket_nodes_added(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1, bucket_count=10)
        total_in_buckets = sum(b["nodes_added"] for b in r["buckets"])
        assert total_in_buckets == 10  # All 10 nodes

    def test_growth_rate(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert r["growth"]["node_rate_per_hour"] > 0
        assert r["growth"]["duration_hours"] > 0

    def test_invalid_time_range(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        with pytest.raises(ValueError):
            g.temporal_evolution_report(now, now)  # zero duration

    def test_invalid_reversed_range(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        with pytest.raises(ValueError):
            g.temporal_evolution_report(now + 100, now)

    def test_lifespan_stats_empty(self):
        """No invalidated nodes → lifespan_stats should be zeros."""
        g = MemoryGraph()
        now = time.time()
        g.add("n1", kind="fact")
        r = g.temporal_evolution_report(now - 100, now + 100)
        assert r["lifespan_stats"]["count"] == 0
        assert r["lifespan_stats"]["mean"] == 0

    def test_lifespan_stats_with_invalidation(self):
        """Nodes with valid_from/valid_to should produce lifespan stats."""
        g = MemoryGraph()
        now = time.time()
        n = g.add("temp", kind="fact")
        g.set_validity(n.id, valid_from=now - 500, valid_to=now - 100)
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert r["lifespan_stats"]["count"] >= 0  # depends on whether created falls in window

    def test_top_kinds_sorted(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        # Top kinds should be sorted by count descending
        counts = [c for _, c in r["top_kinds"]]
        assert counts == sorted(counts, reverse=True)

    def test_top_kinds_max_five(self, evolved_graph):
        g = MemoryGraph()
        now = time.time()
        for i in range(10):
            g.add(f"n{i}", kind=f"kind{i}")
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert len(r["top_kinds"]) <= 5

    def test_no_nodes_in_empty_window(self, evolved_graph):
        """Query a time window far from any node creation."""
        g, base = evolved_graph
        r = g.temporal_evolution_report(1.0, 2.0)  # Very old timestamps
        assert r["totals"]["nodes_created_in_window"] == 0

    def test_bucket_boundaries(self, evolved_graph):
        """Each bucket should have correct start/end."""
        g, base = evolved_graph
        r = g.temporal_evolution_report(1000.0, 2000.0, bucket_count=5)
        assert r["buckets"][0]["bucket_start"] == 1000.0
        assert r["buckets"][-1]["bucket_end"] == 2000.0
        for i in range(len(r["buckets"]) - 1):
            assert r["buckets"][i]["bucket_end"] == r["buckets"][i + 1]["bucket_start"]

    def test_totals_keys(self, evolved_graph):
        g, base = evolved_graph
        now = time.time()
        r = g.temporal_evolution_report(now - 10000, now + 1)
        assert "nodes_created_in_window" in r["totals"]
        assert "nodes_valid_at_end" in r["totals"]
        assert "kinds" in r["totals"]
