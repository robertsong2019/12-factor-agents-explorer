"""Cycle 395: write_amplification + graph_temporal_summary"""
import time
from memory_graph import MemoryGraph


class TestWriteAmplification:
    def setUp(self):
        self.g = MemoryGraph(":memory:")

    def test_empty_graph(self):
        self.setUp()
        r = self.g.write_amplification()
        assert r["current_edges"] == 0
        assert r["cascade_detected"] is False

    def test_after_writes(self):
        self.setUp()
        a = self.g.add("a").id; b = self.g.add("b").id
        self.g.link(a, b, "r")
        r = self.g.write_amplification()
        assert r["current_edges"] == 1
        # Events may or may not have timestamps depending on _tick impl
        assert isinstance(r["write_ops"], int)

    def test_amplification_ratio(self):
        self.setUp()
        for i in range(5):
            self.g.add(f"n{i}")
        r = self.g.write_amplification()
        assert 0 <= r["amplification_ratio"] <= 1

    def test_top_ops_structure(self):
        self.setUp()
        self.g.add("x")
        r = self.g.write_amplification()
        assert "top_cascading_ops" in r
        assert isinstance(r["top_cascading_ops"], list)

    def test_custom_window(self):
        self.setUp()
        self.g.add("w")
        r1 = self.g.write_amplification(window_seconds=60)
        r2 = self.g.write_amplification(window_seconds=3600)
        assert isinstance(r1["events_in_window"], int)
        assert isinstance(r2["events_in_window"], int)

    def test_baseline_param(self):
        self.setUp()
        r = self.g.write_amplification(baseline_snapshot={"edges": 0})
        assert "current_edges" in r

    def test_structure(self):
        self.setUp()
        r = self.g.write_amplification()
        assert all(k in r for k in [
            "current_edges", "events_in_window", "write_ops",
            "amplification_ratio", "cascade_detected",
            "top_cascading_ops", "window_seconds"])


class TestGraphTemporalSummary:
    def setUp(self):
        self.g = MemoryGraph(":memory:")

    def test_empty_graph(self):
        self.setUp()
        r = self.g.graph_temporal_summary()
        assert r["total_nodes"] == 0
        assert r["age_buckets"] == {}

    def test_fresh_nodes(self):
        self.setUp()
        for i in range(3):
            self.g.add(f"fresh_{i}")
        r = self.g.graph_temporal_summary()
        assert r["total_nodes"] == 3
        assert r["age_buckets"]["<1h"] == 3

    def test_age_buckets(self):
        self.setUp()
        self.g.add("now")
        old = self.g.add("old")
        self.g.conn.execute(
            "UPDATE nodes SET created = ? WHERE id = ?",
            (time.time() - 2 * 86400, old.id)
        )
        self.g.conn.commit()
        r = self.g.graph_temporal_summary()
        assert r["age_buckets"]["<1h"] >= 1
        assert r["age_buckets"]["1-7d"] >= 1

    def test_recency(self):
        self.setUp()
        self.g.add("recent")
        r = self.g.graph_temporal_summary()
        assert r["recency"]["accessed_in_24h"] >= 1
        assert r["recency"]["mean_access_age_hours"] < 1

    def test_structure(self):
        self.setUp()
        self.g.add("s")
        r = self.g.graph_temporal_summary()
        assert set(r.keys()) == {"total_nodes", "age_buckets",
                                  "creation_timeline", "recency"}
        assert set(r["recency"].keys()) == {
            "mean_access_age_hours", "accessed_in_24h",
            "accessed_fraction"}

    def test_stale_access(self):
        self.setUp()
        stale = self.g.add("stale")
        self.g.conn.execute(
            "UPDATE nodes SET accessed = ? WHERE id = ?",
            (time.time() - 48 * 3600, stale.id)
        )
        self.g.conn.commit()
        r = self.g.graph_temporal_summary()
        assert r["recency"]["mean_access_age_hours"] > 10
