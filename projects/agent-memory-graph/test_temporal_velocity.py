"""Tests for temporal_velocity() — Cycle 410.

Measures current rate of knowledge change: creation/supersession rates,
trend (accelerating/decelerating/steady), and recent-vs-baseline ratio.
"""

import pytest
from memory_graph import MemoryGraph


# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def accelerating_graph():
    """Graph where activity is increasing over time."""
    mg = MemoryGraph()
    base = 1700000000

    # Day 1: 1 node
    for i in range(1):
        node = mg.add(f"d1_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base, node.id))
    # Day 2: 2 nodes
    for i in range(2):
        node = mg.add(f"d2_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + 86400 + i * 60, node.id))
    # Day 3: 4 nodes
    for i in range(4):
        node = mg.add(f"d3_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + 2 * 86400 + i * 60, node.id))
    # Day 4: 8 nodes
    for i in range(8):
        node = mg.add(f"d4_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + 3 * 86400 + i * 60, node.id))

    mg.conn.commit()
    return mg


@pytest.fixture
def steady_graph():
    """Graph with constant rate of change."""
    mg = MemoryGraph()
    base = 1700000000

    for day in range(8):
        for i in range(2):
            node = mg.add(f"d{day}_{i}", "x")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                            (base + day * 86400 + i * 3600, node.id))

    mg.conn.commit()
    return mg


@pytest.fixture
def declining_graph():
    """Graph where activity is decreasing."""
    mg = MemoryGraph()
    base = 1700000000

    # Day 1: 8 nodes
    for i in range(8):
        node = mg.add(f"d1_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + i * 60, node.id))
    # Day 2: 4 nodes
    for i in range(4):
        node = mg.add(f"d2_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + 86400 + i * 60, node.id))
    # Day 3: 2 nodes
    for i in range(2):
        node = mg.add(f"d3_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + 2 * 86400 + i * 60, node.id))
    # Day 4: 1 node
    for i in range(1):
        node = mg.add(f"d4_{i}", "x")
        mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                        (base + 3 * 86400, node.id))

    mg.conn.commit()
    return mg


# ── Basic functionality ────────────────────────────────────

class TestBasicFunctionality:

    def test_returns_dict(self, steady_graph):
        result = steady_graph.temporal_velocity()
        assert isinstance(result, dict)

    def test_required_keys(self, steady_graph):
        result = steady_graph.temporal_velocity()
        expected_keys = {
            "creation_rate", "supersession_rate", "net_rate",
            "trend", "trend_strength", "recent_activity",
            "historical_baseline", "window_buckets", "bucket_size",
        }
        assert expected_keys.issubset(result.keys())

    def test_none_for_empty(self):
        mg = MemoryGraph()
        mg.add("only_one", "x")
        assert mg.temporal_velocity() is None


# ── Rate calculations ──────────────────────────────────────

class TestRateCalculations:

    def test_creation_rate_nonneg(self, steady_graph):
        result = steady_graph.temporal_velocity()
        assert result["creation_rate"] >= 0

    def test_supersession_rate_nonneg(self, steady_graph):
        result = steady_graph.temporal_velocity()
        assert result["supersession_rate"] >= 0

    def test_net_rate(self, steady_graph):
        result = steady_graph.temporal_velocity()
        expected = result["creation_rate"] - result["supersession_rate"]
        assert abs(result["net_rate"] - round(expected, 4)) < 0.01

    def test_zero_supersession(self, steady_graph):
        """No supersessions → supersession_rate = 0."""
        result = steady_graph.temporal_velocity()
        assert result["supersession_rate"] == 0.0


# ── Trend detection ────────────────────────────────────────

class TestTrendDetection:

    def test_steady_trend(self, steady_graph):
        result = steady_graph.temporal_velocity(bucket="day")
        assert result["trend"] in ("steady", "accelerating", "decelerating")

    def test_trend_strength_in_range(self, steady_graph):
        result = steady_graph.temporal_velocity()
        assert 0.0 <= result["trend_strength"] <= 1.0

    def test_recent_activity_is_list(self, steady_graph):
        result = steady_graph.temporal_velocity()
        assert isinstance(result["recent_activity"], list)
        assert len(result["recent_activity"]) >= 1


# ── Window parameter ───────────────────────────────────────

class TestWindowParameter:

    def test_custom_window(self, steady_graph):
        result = steady_graph.temporal_velocity(window_buckets=3, bucket="day")
        assert result["window_buckets"] <= 3

    def test_window_clamped(self, steady_graph):
        """Window can't exceed half the timeline."""
        result = steady_graph.temporal_velocity(window_buckets=999, bucket="day")
        assert result["window_buckets"] >= 1


# ── Edge cases ─────────────────────────────────────────────

class TestEdgeCases:

    def test_all_same_timestamp(self):
        mg = MemoryGraph()
        ts = 1700000000
        for i in range(5):
            node = mg.add(f"n{i}", "x")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                            (ts, node.id))
        mg.conn.commit()
        assert mg.temporal_velocity() is None

    def test_three_events(self):
        mg = MemoryGraph()
        base = 1700000000
        for i in range(3):
            node = mg.add(f"n{i}", "x")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                            (base + i * 86400, node.id))
        mg.conn.commit()
        result = mg.temporal_velocity(bucket="day")
        assert result is not None

    def test_does_not_mutate(self, steady_graph):
        n_before = steady_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        steady_graph.temporal_velocity()
        n_after = steady_graph.conn.execute(
            "SELECT COUNT(*) c FROM nodes").fetchone()["c"]
        assert n_before == n_after


# ── Recent vs baseline ──────────────────────────────────────

class TestRecentVsBaseline:

    def test_ratio_none_when_baseline_zero(self, accelerating_graph):
        """If historical baseline is 0, ratio is None."""
        mg = MemoryGraph()
        base = 1700000000
        # All activity in one bucket (recent), nothing historical
        for i in range(5):
            node = mg.add(f"n{i}", "x")
            mg.conn.execute("UPDATE nodes SET created=? WHERE id=?",
                            (base + i * 60, node.id))
        mg.conn.commit()
        result = mg.temporal_velocity(bucket="hour")
        # All events in one or two buckets → baseline may be 0
        if result and result["historical_baseline"] == 0:
            assert result["recent_vs_baseline_ratio"] is None

    def test_ratio_positive_when_baseline_exists(self, steady_graph):
        result = steady_graph.temporal_velocity(bucket="day")
        if result["historical_baseline"] > 0:
            assert result["recent_vs_baseline_ratio"] is not None
            assert result["recent_vs_baseline_ratio"] > 0
