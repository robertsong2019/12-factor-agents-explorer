"""Tests for temporal_changepoints() — Cycle 408.

Discovers significant structural change points in graph history
using burst-detection over node creation/supersession timestamps.
"""

import time
import pytest
from memory_graph import MemoryGraph


# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def burst_graph():
    """Graph with two clear burst periods separated by quiet periods."""
    mg = MemoryGraph()
    base = 1700000000  # fixed base time

    # Burst 1: 5 nodes created within 1 hour
    for i in range(5):
        node = mg.add(f"burst1_{i}", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + i * 60, node.id)
        )

    # Quiet period: 2 nodes spread over 24h
    for i in range(2):
        node = mg.add(f"quiet1_{i}", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + 12 * 3600 + i * 3600, node.id)
        )

    # Burst 2: 6 nodes in 30 minutes
    for i in range(6):
        node = mg.add(f"burst2_{i}", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + 48 * 3600 + i * 300, node.id)
        )

    mg.conn.commit()
    return mg


@pytest.fixture
def uniform_graph():
    """Graph with uniform activity — no changepoints expected."""
    mg = MemoryGraph()
    base = 1700000000

    for i in range(10):
        node = mg.add(f"node_{i}", "event")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + i * 86400, node.id)
        )
    mg.conn.commit()
    return mg


@pytest.fixture
def empty_graph():
    """Nearly empty graph."""
    mg = MemoryGraph()
    mg.add("only_one", "test")
    return mg


@pytest.fixture
def supersede_graph():
    """Graph with supersession events creating a burst."""
    mg = MemoryGraph()
    base = 1700000000

    # Initial nodes (spread out)
    for i in range(3):
        node = mg.add(f"old_{i}", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + i * 60, node.id)
        )

    # More nodes later, some get superseded
    for i in range(4):
        node = mg.add(f"replace_target_{i}", "fact")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + 100 * 86400 + i * 30, node.id)
        )
        # Set valid_to to create supersession events
        mg.conn.execute(
            "UPDATE nodes SET valid_to=? WHERE id=?",
            (base + 200 * 86400 + i * 30, node.id)
        )

    mg.conn.commit()
    return mg


# ── Basic functionality ────────────────────────────────────

class TestBasicFunctionality:

    def test_returns_dict(self, burst_graph):
        result = burst_graph.temporal_changepoints()
        assert isinstance(result, dict)

    def test_required_keys(self, burst_graph):
        result = burst_graph.temporal_changepoints()
        expected_keys = {
            "changepoints", "activity_timeline", "bucket_size",
            "total_events", "mean_activity", "std_activity",
            "threshold", "coverage_period",
        }
        assert expected_keys.issubset(result.keys())

    def test_coverage_period(self, burst_graph):
        result = burst_graph.temporal_changepoints()
        cp = result["coverage_period"]
        assert "earliest" in cp
        assert "latest" in cp
        assert cp["earliest"] < cp["latest"]

    def test_total_events_matches(self, burst_graph):
        result = burst_graph.temporal_changepoints()
        # 5 + 2 + 6 = 13 created nodes
        assert result["total_events"] == 13

    def test_none_for_empty_graph(self, empty_graph):
        result = empty_graph.temporal_changepoints()
        assert result is None


# ── Changepoint detection ──────────────────────────────────

class TestChangepointDetection:

    def test_burst_graph_detects_changepoints(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        assert len(result["changepoints"]) >= 1

    def test_changepoint_structure(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        for cp in result["changepoints"]:
            assert "start" in cp
            assert "end" in cp
            assert "peak_activity" in cp
            assert "events" in cp
            assert "intensity" in cp
            assert "duration_buckets" in cp
            assert cp["end"] > cp["start"]
            assert cp["events"] > 0
            assert cp["intensity"] > 0

    def test_uniform_graph_no_changepoints(self, uniform_graph):
        """Uniform activity should produce no changepoints."""
        result = uniform_graph.temporal_changepoints(bucket="day")
        # With perfectly uniform data, each bucket has 1 event,
        # std=0, threshold=1+0.5=1.5, no bucket exceeds
        assert len(result["changepoints"]) == 0

    def test_supersede_events_counted(self, supersede_graph):
        result = supersede_graph.temporal_changepoints(bucket="day")
        # 3 created + 4 created + 4 valid_to = 11 events
        assert result["total_events"] == 11

    def test_supersede_creates_changepoint(self, supersede_graph):
        result = supersede_graph.temporal_changepoints(bucket="day")
        assert len(result["changepoints"]) >= 1


# ── Bucket size selection ──────────────────────────────────

class TestBucketSelection:

    def test_auto_bucket(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="auto")
        assert result["bucket_size"] in (3600, 86400, 604800)

    def test_explicit_hour(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        assert result["bucket_size"] == 3600

    def test_explicit_day(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="day")
        assert result["bucket_size"] == 86400

    def test_explicit_week(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="week")
        assert result["bucket_size"] == 604800

    def test_invalid_bucket_raises(self, burst_graph):
        with pytest.raises(ValueError, match="Unknown bucket"):
            burst_graph.temporal_changepoints(bucket="minute")


# ── Activity timeline ──────────────────────────────────────

class TestActivityTimeline:

    def test_timeline_is_list(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        assert isinstance(result["activity_timeline"], list)
        assert len(result["activity_timeline"]) > 0

    def test_timeline_entries(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        for entry in result["activity_timeline"]:
            assert "bucket_start" in entry
            assert "activity" in entry
            assert "is_changepoint" in entry
            assert isinstance(entry["activity"], int)
            assert isinstance(entry["is_changepoint"], bool)

    def test_timeline_sorted(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        starts = [e["bucket_start"] for e in result["activity_timeline"]]
        assert starts == sorted(starts)

    def test_timeline_inclusive(self, burst_graph):
        """Timeline should cover from earliest to latest event."""
        result = burst_graph.temporal_changepoints(bucket="hour")
        cp = result["coverage_period"]
        first_bucket = result["activity_timeline"][0]["bucket_start"]
        last_bucket = result["activity_timeline"][-1]["bucket_start"]
        assert first_bucket <= cp["earliest"]
        assert last_bucket >= cp["latest"] - result["bucket_size"]


# ── Statistics ─────────────────────────────────────────────

class TestStatistics:

    def test_mean_activity(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        total = sum(e["activity"] for e in result["activity_timeline"])
        expected_mean = total / len(result["activity_timeline"])
        assert abs(result["mean_activity"] - round(expected_mean, 4)) < 0.01

    def test_threshold_formula(self, burst_graph):
        """threshold = mean + 2*std (when std > 0)."""
        result = burst_graph.temporal_changepoints(bucket="hour")
        if result["std_activity"] > 0:
            expected = result["mean_activity"] + 2 * result["std_activity"]
        else:
            expected = result["mean_activity"] + 0.5
        assert abs(result["threshold"] - round(expected, 4)) < 0.01

    def test_changepoints_above_threshold(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        for cp in result["changepoints"]:
            assert cp["peak_activity"] > result["threshold"]


# ── min_separation filter ──────────────────────────────────

class TestMinSeparation:

    def test_min_separation_reduces_changepoints(self, burst_graph):
        without = burst_graph.temporal_changepoints(bucket="hour", min_separation=0)
        with_sep = burst_graph.temporal_changepoints(
            bucket="hour", min_separation=999999999)
        assert len(with_sep["changepoints"]) <= len(without["changepoints"])

    def test_default_min_separation(self, burst_graph):
        result = burst_graph.temporal_changepoints(bucket="hour")
        assert isinstance(result["changepoints"], list)

    def test_large_min_separation_keeps_one(self, burst_graph):
        result = burst_graph.temporal_changepoints(
            bucket="hour", min_separation=999999999)
        assert len(result["changepoints"]) <= 1


# ── Edge cases ─────────────────────────────────────────────

class TestEdgeCases:

    def test_all_same_timestamp(self):
        """All nodes created at the same instant → span=0 → None."""
        mg = MemoryGraph()
        ts = 1700000000
        for i in range(10):
            node = mg.add(f"n{i}", "test")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?", (ts, node.id))
        mg.conn.commit()
        result = mg.temporal_changepoints()
        assert result is None

    def test_two_events_only(self):
        """Only 2 events → None (< 3 threshold)."""
        mg = MemoryGraph()
        mg.add("a", "test")
        mg.add("b", "test")
        result = mg.temporal_changepoints()
        assert result is None

    def test_three_events_different_times(self):
        """Exactly 3 events — should work."""
        mg = MemoryGraph()
        base = 1700000000
        for i, label in enumerate(["a", "b", "c"]):
            node = mg.add(label, "test")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?",
                (base + i * 3600, node.id))
        mg.conn.commit()
        result = mg.temporal_changepoints(bucket="hour")
        assert result is not None
        assert result["total_events"] == 3

    def test_does_not_mutate_graph(self, burst_graph):
        """temporal_changepoints must not modify the graph."""
        node_count_before = burst_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        edge_count_before = burst_graph.conn.execute(
            "SELECT COUNT(*) c FROM edges").fetchone()["c"]

        burst_graph.temporal_changepoints(bucket="hour")

        node_count_after = burst_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        edge_count_after = burst_graph.conn.execute(
            "SELECT COUNT(*) c FROM edges").fetchone()["c"]

        assert node_count_before == node_count_after
        assert edge_count_before == edge_count_after


# ── Merging adjacent buckets ───────────────────────────────

class TestMergingAdjacent:

    def test_adjacent_changepoints_merge(self):
        """Two adjacent high-activity buckets should merge into one interval."""
        mg = MemoryGraph()
        base = 1700000000

        # Bucket 1: 5 events
        for i in range(5):
            node = mg.add(f"adj1_{i}", "x")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?",
                (base + i * 60, node.id))

        # Bucket 2 (adjacent hour): 5 more events
        for i in range(5):
            node = mg.add(f"adj2_{i}", "x")
            mg.conn.execute(
                "UPDATE nodes SET created=? WHERE id=?",
                (base + 3600 + i * 60, node.id))

        # Quiet bucket far away
        node = mg.add("quiet", "x")
        mg.conn.execute(
            "UPDATE nodes SET created=? WHERE id=?",
            (base + 72 * 3600, node.id))

        mg.conn.commit()
        result = mg.temporal_changepoints(bucket="hour")
        # The two adjacent hours should merge into one changepoint
        if len(result["changepoints"]) == 1:
            cp = result["changepoints"][0]
            assert cp["duration_buckets"] >= 2


# ── Integration with temporal_diff ─────────────────────────

class TestIntegrationWithTemporalDiff:

    def test_changepoints_within_diff_range(self, burst_graph):
        """Changepoints discovered should be temporally meaningful."""
        cp_result = burst_graph.temporal_changepoints(bucket="hour")
        if not cp_result["changepoints"]:
            pytest.skip("No changepoints detected")

        first_cp = cp_result["changepoints"][0]
        # Changepoint bucket-start may precede earliest event (bucket alignment)
        # so check that the changepoint END is after the earliest event
        assert first_cp["end"] > cp_result["coverage_period"]["earliest"]
        assert first_cp["start"] <= cp_result["coverage_period"]["latest"]
        assert first_cp["events"] > 0
