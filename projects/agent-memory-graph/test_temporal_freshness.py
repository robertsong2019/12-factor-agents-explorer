"""Tests for temporal_freshness_map() — Cycle 389.

Age distribution, freshness categories, freshness entropy,
temporal clustering, stale cluster detection.
"""
import time
import math
from memory_graph import MemoryGraph


def _add_at(mg, label, kind="fact", created=None):
    """Add node and override its created timestamp."""
    n = mg.add(label, kind)
    if created is not None:
        mg.conn.execute("UPDATE nodes SET created = ? WHERE id = ?",
                         (created, n.id))
        mg.conn.commit()
    return n


class TestTemporalFreshnessEmpty:
    def test_empty_graph(self):
        mg = MemoryGraph()
        result = mg.temporal_freshness_map()
        assert result["categories"] == {}
        assert result["freshness_entropy"] == 0.0
        assert result["summary"]["total"] == 0

    def test_empty_graph_no_crash(self):
        mg = MemoryGraph()
        result = mg.temporal_freshness_map(now=1000000)
        assert "distribution" in result
        assert result["distribution"] == []


class TestTemporalFreshnessCategories:
    def test_fresh_node(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "fresh event", "event", created=now - 100)  # ~1.5 min ago
        result = mg.temporal_freshness_map(now=now)
        assert result["categories"]["fresh"] == 1
        assert result["categories"]["recent"] == 0

    def test_recent_node(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "recent event", "event", created=now - 7200)  # 2h ago
        result = mg.temporal_freshness_map(now=now)
        assert result["categories"]["recent"] == 1
        assert result["categories"]["fresh"] == 0

    def test_mature_node(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "mature event", "event", created=now - 200000)  # ~2.3 days
        result = mg.temporal_freshness_map(now=now)
        assert result["categories"]["mature"] == 1

    def test_aging_node(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "aging event", "event", created=now - 1500000)  # ~17 days
        result = mg.temporal_freshness_map(now=now)
        assert result["categories"]["aging"] == 1

    def test_stale_node(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "stale event", "event", created=now - 50000000)  # ~578 days
        result = mg.temporal_freshness_map(now=now)
        assert result["categories"]["stale"] == 1

    def test_mixed_categories(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)       # fresh
        _add_at(mg, "b", "fact", created=now - 5000)     # recent
        _add_at(mg, "c", "fact", created=now - 300000)   # mature
        _add_at(mg, "d", "fact", created=now - 2000000)  # aging
        _add_at(mg, "e", "fact", created=now - 40000000) # stale
        result = mg.temporal_freshness_map(now=now)
        assert result["categories"]["fresh"] == 1
        assert result["categories"]["recent"] == 1
        assert result["categories"]["mature"] == 1
        assert result["categories"]["aging"] == 1
        assert result["categories"]["stale"] == 1

    def test_category_fractions(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)
        _add_at(mg, "b", "fact", created=now - 5000)
        result = mg.temporal_freshness_map(now=now)
        assert result["category_fractions"]["fresh"] == 0.5
        assert result["category_fractions"]["recent"] == 0.5


class TestTemporalFreshnessEntropy:
    def test_single_category_low_entropy(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"node{i}", "fact", created=now - 60)
        result = mg.temporal_freshness_map(now=now)
        assert result["freshness_entropy"] == 0.0  # All in one category

    def test_balanced_categories_high_entropy(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)        # fresh
        _add_at(mg, "b", "fact", created=now - 5000)      # recent
        _add_at(mg, "c", "fact", created=now - 300000)    # mature
        _add_at(mg, "d", "fact", created=now - 2000000)   # aging
        _add_at(mg, "e", "fact", created=now - 40000000)  # stale
        result = mg.temporal_freshness_map(now=now)
        # 5 categories, each 1/5 → entropy = log2(5) ≈ 2.32
        assert result["freshness_entropy"] > 0.99  # normalised → 1.0

    def test_two_categories_partial_entropy(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)
        _add_at(mg, "b", "fact", created=now - 60)
        _add_at(mg, "c", "fact", created=now - 5000)
        _add_at(mg, "d", "fact", created=now - 5000)
        result = mg.temporal_freshness_map(now=now)
        # 2 categories, 50/50 → entropy = 1.0, normalised = 1.0/(log2(min(4,5)))
        assert 0.3 < result["freshness_entropy"] < 1.0

    def test_raw_entropy_value(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)
        _add_at(mg, "b", "fact", created=now - 5000)
        result = mg.temporal_freshness_map(now=now)
        # 2 categories, 50/50 → entropy = 1.0
        assert abs(result["raw_entropy"] - 1.0) < 0.01


class TestTemporalFreshnessDistribution:
    def test_histogram_bin_count(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(20):
            _add_at(mg, f"n{i}", "fact", created=now - i * 1000)
        result = mg.temporal_freshness_map(now=now, bins=5)
        assert len(result["distribution"]) == 5

    def test_histogram_sums_to_total(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(15):
            _add_at(mg, f"n{i}", "fact", created=now - i * 500)
        result = mg.temporal_freshness_map(now=now, bins=4)
        total_in_bins = sum(b["count"] for b in result["distribution"])
        assert total_in_bins == 15

    def test_histogram_fractions(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - i * 100)
        result = mg.temporal_freshness_map(now=now, bins=3)
        total_frac = sum(b["fraction"] for b in result["distribution"])
        assert abs(total_frac - 1.0) < 0.01

    def test_custom_bin_count(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - i * 1000)
        result = mg.temporal_freshness_map(now=now, bins=8)
        assert len(result["distribution"]) == 8


class TestTemporalClustering:
    def test_uniform_arrivals_low_clustering(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - (10 - i) * 1000)
        result = mg.temporal_freshness_map(now=now)
        # Uniform gaps → VMR ≈ 0
        assert result["temporal_clustering"] < 0.5

    def test_burst_arrivals_high_clustering(self):
        mg = MemoryGraph()
        now = time.time()
        # Burst: 5 nodes at same time, then gap, then 5 more
        for i in range(5):
            _add_at(mg, f"n{i}", "fact", created=now - 100000)
        for i in range(5):
            _add_at(mg, f"n{i+5}", "fact", created=now - 10)
        result = mg.temporal_freshness_map(now=now)
        assert result["temporal_clustering"] > 1.0

    def test_single_node_no_clustering(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "only", "fact", created=now - 100)
        result = mg.temporal_freshness_map(now=now)
        assert result["temporal_clustering"] == 0.0


class TestStaleClusters:
    def test_no_stale_clusters_small_graph(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)
        _add_at(mg, "b", "fact", created=now - 120)
        mg.link("a", "b", "related")
        result = mg.temporal_freshness_map(now=now)
        assert result["stale_clusters"] == []

    def test_stale_cluster_detection(self):
        mg = MemoryGraph()
        now = time.time()
        # Create 5 stale nodes with edges between them
        ids = []
        for i in range(5):
            n = _add_at(mg, f"stale{i}", "fact", created=now - 50000000)
            ids.append(n.id)
        # Link them in a chain
        for i in range(4):
            mg.link(ids[i], ids[i+1], "related")
        result = mg.temporal_freshness_map(now=now)
        assert len(result["stale_clusters"]) >= 1
        assert result["stale_clusters"][0]["size"] >= 3

    def test_stale_cluster_size_cap(self):
        mg = MemoryGraph()
        now = time.time()
        ids = []
        for i in range(10):
            n = _add_at(mg, f"old{i}", "fact", created=now - 50000000)
            ids.append(n.id)
        for i in range(9):
            mg.link(ids[i], ids[i+1], "related")
        result = mg.temporal_freshness_map(now=now)
        if result["stale_clusters"]:
            # node_ids capped at 10
            assert len(result["stale_clusters"][0]["node_ids"]) <= 10


class TestFreshnessSummary:
    def test_summary_fields(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)
        _add_at(mg, "b", "fact", created=now - 100000)
        result = mg.temporal_freshness_map(now=now)
        s = result["summary"]
        assert "total" in s
        assert "freshness_ratio" in s
        assert "stale_ratio" in s
        assert "median_age" in s
        assert "mean_age" in s
        assert "interpretation" in s

    def test_freshness_ratio(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "fresh1", "fact", created=now - 60)
        _add_at(mg, "fresh2", "fact", created=now - 120)
        _add_at(mg, "stale1", "fact", created=now - 50000000)
        result = mg.temporal_freshness_map(now=now)
        assert result["summary"]["freshness_ratio"] == round(2/3, 4)

    def test_interpretation_healthy(self):
        mg = MemoryGraph()
        now = time.time()
        # Spread across all 5 categories
        for cat_age in [60, 5000, 300000, 2000000, 40000000]:
            _add_at(mg, f"n", "fact", created=now - cat_age)
        result = mg.temporal_freshness_map(now=now)
        assert result["summary"]["interpretation"] == "healthy"

    def test_interpretation_concentrated(self):
        mg = MemoryGraph()
        now = time.time()
        for i in range(10):
            _add_at(mg, f"n{i}", "fact", created=now - 60)
        result = mg.temporal_freshness_map(now=now)
        assert result["summary"]["interpretation"] == "concentrated"


class TestFreshnessEdgeCases:
    def test_all_same_timestamp(self):
        mg = MemoryGraph()
        now = time.time()
        ts = now - 1000
        for i in range(5):
            _add_at(mg, f"n{i}", "fact", created=ts)
        result = mg.temporal_freshness_map(now=now)
        # 1000s ≈ 16.7min → fresh (< 1 hour)
        assert result["categories"]["fresh"] == 5
        assert result["freshness_entropy"] == 0.0

    def test_two_nodes_minimum(self):
        mg = MemoryGraph()
        now = time.time()
        _add_at(mg, "a", "fact", created=now - 60)
        _add_at(mg, "b", "fact", created=now - 200000)
        result = mg.temporal_freshness_map(now=now)
        assert result["summary"]["total"] == 2

    def test_explicit_now_parameter(self):
        mg = MemoryGraph()
        fixed_now = 2000000000  # well-defined timestamp
        _add_at(mg, "a", "fact", created=fixed_now - 3600)
        result = mg.temporal_freshness_map(now=fixed_now)
        # age = 3600 = exactly 1 hour → fresh (<=)
        assert result["categories"]["fresh"] == 1
