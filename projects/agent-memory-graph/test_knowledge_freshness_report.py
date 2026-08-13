"""Tests for knowledge_freshness_report() — graph-level freshness diagnostic.

Cycle 426. Research #051: FAMA penalizes stale memory by 15-43 points.
"""
import time
import pytest
import memory_graph as mg
from memory_graph import MemoryGraph


class TestKnowledgeFreshnessReportBasic:
    """Basic functionality tests."""

    def test_empty_graph_returns_none(self):
        g = MemoryGraph()
        assert g.knowledge_freshness_report() is None

    def test_single_node(self):
        g = MemoryGraph()
        g.add("fresh fact", kind="fact")
        report = g.knowledge_freshness_report()
        assert report is not None
        assert report["total_nodes"] == 1
        assert report["freshness_score"] > 0.9  # just created

    def test_returns_all_fields(self):
        g = MemoryGraph()
        g.add("fact 1", kind="fact")
        report = g.knowledge_freshness_report()
        for key in ("total_nodes", "freshness_score", "bucket_distribution",
                    "bucket_weight", "by_kind", "stalest_nodes",
                    "freshest_nodes", "stale_percentage", "recommendation"):
            assert key in report, f"Missing key: {key}"

    def test_bucket_distribution_has_all_buckets(self):
        g = MemoryGraph()
        g.add("test", kind="fact")
        report = g.knowledge_freshness_report()
        for bucket in ("fresh", "recent", "aging", "stale", "decayed"):
            assert bucket in report["bucket_distribution"]

    def test_bucket_sums_equal_total(self):
        g = MemoryGraph()
        for i in range(10):
            g.add(f"fact {i}", kind="fact")
        report = g.knowledge_freshness_report()
        total = sum(report["bucket_distribution"].values())
        assert total == 10


class TestKnowledgeFreshnessReportScoring:
    """Freshness score correctness."""

    def test_new_node_high_freshness(self):
        g = MemoryGraph()
        g.add("brand new", kind="fact")
        report = g.knowledge_freshness_report()
        assert report["freshness_score"] > 0.95

    def test_touched_node_fresher(self):
        g = MemoryGraph()
        node = g.add("old node", kind="fact")
        # Make it old by backdating accessed time
        old_time = time.time() - 86400 * 10  # 10 days ago
        g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                       (old_time, node.id))
        g.conn.commit()

        report_before = g.knowledge_freshness_report()
        # Touch it
        g.touch(node.id)
        report_after = g.knowledge_freshness_report()

        assert report_after["freshness_score"] > report_before["freshness_score"]

    def test_freshness_score_between_0_and_1(self):
        g = MemoryGraph()
        g.add("a", kind="fact")
        g.add("b", kind="event")
        report = g.knowledge_freshness_report()
        assert 0.0 <= report["freshness_score"] <= 1.0

    def test_all_fresh_nodes(self):
        g = MemoryGraph()
        for i in range(20):
            g.add(f"fresh {i}", kind="fact")
        report = g.knowledge_freshness_report()
        assert report["bucket_distribution"]["fresh"] == 20
        assert report["stale_percentage"] == 0.0


class TestKnowledgeFreshnessReportStale:
    """Stale node detection."""

    def test_stale_node_detected(self):
        g = MemoryGraph()
        node = g.add("stale fact", kind="fact")
        # Backdate to 100 days ago
        old_time = time.time() - 86400 * 100
        g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                       (old_time, node.id))
        g.conn.commit()

        report = g.knowledge_freshness_report()
        assert report["bucket_distribution"]["decayed"] == 1
        assert report["stale_percentage"] == 1.0

    def test_mixed_freshness(self):
        g = MemoryGraph()
        # Fresh
        g.add("fresh 1", kind="fact")
        g.add("fresh 2", kind="fact")
        # Old
        old_node = g.add("old 1", kind="event")
        old_time = time.time() - 86400 * 60  # 60 days
        g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                       (old_time, old_node.id))
        g.conn.commit()

        report = g.knowledge_freshness_report()
        assert report["bucket_distribution"]["fresh"] == 2
        assert report["stale_percentage"] > 0

    def test_stalest_nodes_list(self):
        g = MemoryGraph()
        # Create nodes with different ages
        for i in range(15):
            n = g.add(f"node {i}", kind="fact")
            if i < 5:
                old_time = time.time() - 86400 * (50 + i)
                g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                               (old_time, n.id))
        g.conn.commit()
        report = g.knowledge_freshness_report()
        assert len(report["stalest_nodes"]) <= 10
        # Stalest should have low freshness scores
        assert report["stalest_nodes"][0]["freshness"] < 0.5

    def test_freshest_nodes_list(self):
        g = MemoryGraph()
        for i in range(15):
            g.add(f"node {i}", kind="fact")
        report = g.knowledge_freshness_report()
        assert len(report["freshest_nodes"]) <= 10
        # Freshest should have high scores
        assert report["freshest_nodes"][0]["freshness"] > 0.9


class TestKnowledgeFreshnessReportByKind:
    """Per-kind breakdown tests."""

    def test_by_kind_counts(self):
        g = MemoryGraph()
        g.add("fact 1", kind="fact")
        g.add("fact 2", kind="fact")
        g.add("event 1", kind="event")
        report = g.knowledge_freshness_report()
        assert report["by_kind"]["fact"]["count"] == 2
        assert report["by_kind"]["event"]["count"] == 1

    def test_by_kind_avg_freshness(self):
        g = MemoryGraph()
        g.add("a", kind="fact")
        g.add("b", kind="fact")
        report = g.knowledge_freshness_report()
        assert "avg_freshness" in report["by_kind"]["fact"]
        assert report["by_kind"]["fact"]["avg_freshness"] > 0.9

    def test_by_kind_min_max(self):
        g = MemoryGraph()
        fresh = g.add("fresh", kind="fact")
        old = g.add("old", kind="fact")
        old_time = time.time() - 86400 * 30
        g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                       (old_time, old.id))
        g.conn.commit()
        report = g.knowledge_freshness_report()
        fk = report["by_kind"]["fact"]
        assert fk["min_freshness"] < fk["max_freshness"]


class TestKnowledgeFreshnessReportRecommendation:
    """Recommendation text tests."""

    def test_fresh_graph_recommendation(self):
        g = MemoryGraph()
        g.add("a", kind="fact")
        report = g.knowledge_freshness_report()
        assert "fresh" in report["recommendation"].lower()

    def test_stale_graph_recommendation(self):
        g = MemoryGraph()
        for i in range(10):
            n = g.add(f"node {i}", kind="fact")
            old_time = time.time() - 86400 * 100
            g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                           (old_time, n.id))
        g.conn.commit()
        report = g.knowledge_freshness_report()
        assert "stale" in report["recommendation"].lower() or \
               "decay" in report["recommendation"].lower() or \
               "consolidate" in report["recommendation"].lower()

    def test_moderate_stale_recommendation(self):
        g = MemoryGraph()
        # 8 fresh, 2 stale = 20% stale
        for i in range(8):
            g.add(f"fresh {i}", kind="fact")
        for i in range(2):
            n = g.add(f"stale {i}", kind="fact")
            old_time = time.time() - 86400 * 100
            g.conn.execute("UPDATE nodes SET accessed=? WHERE id=?",
                           (old_time, n.id))
        g.conn.commit()
        report = g.knowledge_freshness_report()
        assert report["stale_percentage"] >= 0.1
        assert len(report["recommendation"]) > 10


class TestKnowledgeFreshnessReportWeighted:
    """Weighted freshness tests."""

    def test_high_weight_node_dominates(self):
        g = MemoryGraph()
        low = g.add("low weight fresh", kind="fact")
        # Set low weight
        g.conn.execute("UPDATE nodes SET weight=0.01 WHERE id=?", (low.id,))
        # Add stale high-weight node
        high = g.add("high weight stale", kind="fact")
        old_time = time.time() - 86400 * 30
        g.conn.execute("UPDATE nodes SET weight=10.0, accessed=? WHERE id=?",
                       (old_time, high.id))
        g.conn.commit()
        report = g.knowledge_freshness_report()
        # Weighted score should be pulled down by the heavy stale node
        assert report["freshness_score"] < 0.7

    def test_bucket_weight_populated(self):
        g = MemoryGraph()
        g.add("normal", kind="fact")
        report = g.knowledge_freshness_report()
        assert report["bucket_weight"]["fresh"] > 0
