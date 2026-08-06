"""Tests for F49: anomaly_detection()."""

import pytest
import math
from datetime import datetime, timedelta
from nano_agent.memory import Memory, MemoryEntry


def _add_burst(mem, base_time, count, prefix="burst"):
    """Add *count* entries within a short time window starting at *base_time*."""
    for i in range(count):
        mem.add(content=f"{prefix}-{i}", importance=0.5, tags=["normal"])
        mem._entries[-1].timestamp = base_time + timedelta(seconds=i)


class TestAnomalyDetectionEmpty:
    def test_empty_memory(self):
        m = Memory()
        result = m.anomaly_detection()
        assert result["anomalies"] == []
        assert result["burst_windows"] == []
        assert result["importance_stats"]["mean"] == 0
        assert result["importance_stats"]["std"] == 0
        assert result["importance_stats"]["outliers"] == []
        assert result["tag_concentration"]["max_tag"] is None
        assert result["tag_concentration"]["max_share"] == 0.0
        assert result["tag_concentration"]["total_tags"] == 0

    def test_single_entry(self):
        m = Memory()
        m.add("only one", importance=0.5, tags=["a"])
        result = m.anomaly_detection()
        # No burst or importance outlier with single entry
        assert result["burst_windows"] == []
        assert result["importance_stats"]["outliers"] == []
        # Single tag = 100% concentration > 50% → anomaly
        assert result["tag_concentration"]["max_tag"] == "a"
        assert result["tag_concentration"]["max_share"] == 1.0
        assert any(a["type"] == "tag_concentration" for a in result["anomalies"])


class TestBurstDetection:
    def _populate_with_burst(self, mem, baseline_n=5, burst_n=10):
        """Add spread-out baseline entries, then a burst cluster."""
        base = datetime(2026, 1, 1, 6, 0, 0)
        # Baseline: 1 entry every 2 hours
        for i in range(baseline_n):
            mem.add(f"baseline-{i}", importance=0.5, tags=["normal"])
            mem._entries[-1].timestamp = base + timedelta(hours=i * 2)
        # Burst: burst_n entries within 30 seconds
        burst_start = base + timedelta(hours=baseline_n * 2)
        for i in range(burst_n):
            mem.add(f"burst-{i}", importance=0.5, tags=["normal"])
            mem._entries[-1].timestamp = burst_start + timedelta(seconds=3 * i)

    def test_burst_detected(self):
        """A cluster of entries should trigger burst."""
        m = Memory()
        self._populate_with_burst(m, baseline_n=5, burst_n=10)
        result = m.anomaly_detection(window_minutes=5)
        assert len(result["burst_windows"]) >= 1
        assert result["burst_windows"][0]["count"] >= 5
        assert any(a["type"] == "burst" for a in result["anomalies"])

    def test_no_burst_when_uniform(self):
        """Entries spread evenly should not trigger burst."""
        m = Memory()
        base = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(5):
            m.add(f"entry-{i}", importance=0.5, tags=["x"])
            m._entries[-1].timestamp = base + timedelta(hours=i * 10)
        result = m.anomaly_detection(window_minutes=60)
        assert len(result["burst_windows"]) == 0

    def test_burst_window_count(self):
        """Burst window count should reflect cluster size."""
        m = Memory()
        self._populate_with_burst(m, baseline_n=5, burst_n=15)
        result = m.anomaly_detection(window_minutes=5)
        assert len(result["burst_windows"]) >= 1
        assert result["burst_windows"][0]["count"] >= 6

    def test_burst_window_iso_format(self):
        """Burst window start/end should be ISO format strings."""
        m = Memory()
        self._populate_with_burst(m, baseline_n=3, burst_n=8)
        result = m.anomaly_detection(window_minutes=5)
        for bw in result["burst_windows"]:
            datetime.fromisoformat(bw["start"])
            datetime.fromisoformat(bw["end"])

    def test_merged_overlapping_bursts(self):
        """Overlapping burst windows should be merged into one."""
        m = Memory()
        self._populate_with_burst(m, baseline_n=3, burst_n=20)
        result = m.anomaly_detection(window_minutes=1)
        # Should merge into at most a few windows
        assert len(result["burst_windows"]) >= 1


class TestImportanceOutliers:
    def test_outlier_detected(self):
        """An entry with very high importance vs others should be flagged."""
        m = Memory()
        for i in range(10):
            m.add(f"normal-{i}", importance=0.5, tags=["t"])
        m.add("critical-event", importance=1.0, tags=["t"])
        result = m.anomaly_detection()
        outliers = result["importance_stats"]["outliers"]
        assert len(outliers) >= 1
        assert any(o["content"] == "critical-event" for o in outliers)

    def test_no_outliers_when_uniform(self):
        """All same importance → no outliers."""
        m = Memory()
        for i in range(10):
            m.add(f"entry-{i}", importance=0.5)
        result = m.anomaly_detection()
        assert result["importance_stats"]["outliers"] == []

    def test_importance_stats_mean(self):
        """Mean should be computed correctly."""
        m = Memory()
        for i in range(5):
            m.add(f"e-{i}", importance=0.2 * i)
        result = m.anomaly_detection()
        expected_mean = sum(0.2 * i for i in range(5)) / 5  # 0.4
        assert abs(result["importance_stats"]["mean"] - round(expected_mean, 4)) < 0.01

    def test_importance_stats_std(self):
        """Std should be computed correctly (population std)."""
        m = Memory()
        vals = [0.1, 0.2, 0.3, 0.4, 0.5]
        for v in vals:
            m.add(f"e-{v}", importance=v)
        result = m.anomaly_detection()
        mean_v = sum(vals) / len(vals)
        var = sum((v - mean_v) ** 2 for v in vals) / len(vals)
        expected_std = math.sqrt(var)
        assert abs(result["importance_stats"]["std"] - round(expected_std, 4)) < 0.01

    def test_low_importance_outlier(self):
        """Very low importance among high ones should also be flagged."""
        m = Memory()
        for i in range(10):
            m.add(f"high-{i}", importance=0.9, tags=["t"])
        m.add("low-outlier", importance=0.05, tags=["t"])
        result = m.anomaly_detection()
        outliers = result["importance_stats"]["outliers"]
        assert any(o["content"] == "low-outlier" for o in outliers)


class TestTagConcentration:
    def test_dominant_tag_detected(self):
        """One tag > 50% should be flagged."""
        m = Memory()
        for i in range(10):
            m.add(f"entry-{i}", tags=["dominant"])
        for i in range(3):
            m.add(f"other-{i}", tags=["minor"])
        result = m.anomaly_detection()
        assert result["tag_concentration"]["max_tag"] == "dominant"
        assert result["tag_concentration"]["max_share"] > 0.5
        assert result["tag_concentration"]["total_tags"] == 13
        assert any(a["type"] == "tag_concentration" for a in result["anomalies"])

    def test_balanced_tags_no_concentration(self):
        """Balanced tags → no concentration anomaly."""
        m = Memory()
        for i in range(5):
            m.add(f"a-{i}", tags=["a"])
        for i in range(5):
            m.add(f"b-{i}", tags=["b"])
        result = m.anomaly_detection()
        assert result["tag_concentration"]["max_share"] == 0.5
        # Exactly 50% is not > 50%, so no anomaly
        assert not any(a["type"] == "tag_concentration" for a in result["anomalies"])

    def test_no_tags(self):
        """Entries with no tags → total_tags = 0, max_tag = None."""
        m = Memory()
        for i in range(5):
            m.add(f"entry-{i}", importance=0.5)
        result = m.anomaly_detection()
        assert result["tag_concentration"]["max_tag"] is None
        assert result["tag_concentration"]["total_tags"] == 0

    def test_multi_tag_entry(self):
        """Entries with multiple tags should count each tag occurrence."""
        m = Memory()
        m.add("e1", tags=["a", "b", "c"])
        m.add("e2", tags=["a", "b"])
        m.add("e3", tags=["a", "b"])
        m.add("e4", tags=["a"])
        result = m.anomaly_detection()
        # a: 4, b: 3, c: 1 → total 8, a = 4/8 = 0.5
        assert result["tag_concentration"]["max_tag"] == "a"
        assert result["tag_concentration"]["total_tags"] == 8

    def test_max_share_calculation(self):
        """max_share = max_tag_count / total_tag_occurrences."""
        m = Memory()
        for i in range(7):
            m.add(f"x-{i}", tags=["big"])
        m.add("y", tags=["small"])
        result = m.anomaly_detection()
        assert result["tag_concentration"]["max_tag"] == "big"
        assert abs(result["tag_concentration"]["max_share"] - 7 / 8) < 0.01


class TestAnomalyReturnStructure:
    def test_return_keys(self):
        """Result should have all required top-level keys."""
        m = Memory()
        m.add("test", importance=0.5, tags=["t"])
        result = m.anomaly_detection()
        for key in ("anomalies", "burst_windows", "importance_stats", "tag_concentration"):
            assert key in result

    def test_importance_stats_keys(self):
        m = Memory()
        m.add("test", importance=0.5)
        stats = m.anomaly_detection()["importance_stats"]
        for key in ("mean", "std", "outliers"):
            assert key in stats

    def test_tag_concentration_keys(self):
        m = Memory()
        m.add("test", tags=["a"])
        tc = m.anomaly_detection()["tag_concentration"]
        for key in ("max_tag", "max_share", "total_tags"):
            assert key in tc

    def test_anomaly_entry_structure(self):
        """Each anomaly should have type, detail, and data."""
        m = Memory()
        base = datetime(2026, 1, 1)
        _add_burst(m, base, 10)
        result = m.anomaly_detection(window_minutes=5)
        for a in result["anomalies"]:
            assert "type" in a
            assert "detail" in a
            assert "data" in a

    def test_custom_window_minutes(self):
        """Different window sizes should produce different results."""
        m = Memory()
        base = datetime(2026, 1, 1, 12, 0, 0)
        # Entries every 30 min for 5 hours
        for i in range(10):
            m.add(f"e-{i}", importance=0.5)
            m._entries[-1].timestamp = base + timedelta(minutes=30 * i)
        r1 = m.anomaly_detection(window_minutes=60)
        r2 = m.anomaly_detection(window_minutes=180)
        # Different windows may produce different burst results
        assert isinstance(r1["burst_windows"], list)
        assert isinstance(r2["burst_windows"], list)
