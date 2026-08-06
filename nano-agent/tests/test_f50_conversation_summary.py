"""Tests for F50: conversation_summary()."""

import pytest
from datetime import datetime, timedelta
from nano_agent.memory import Memory, MemoryEntry


class TestConversationSummaryEmpty:
    def test_empty_memory(self):
        m = Memory()
        result = m.conversation_summary()
        assert result["entry_count"] == 0
        assert result["time_span"] is None
        assert result["top_tags"] == []
        assert result["importance_distribution"] is None
        assert result["content_themes"] == {}
        assert result["activity_pattern"] is None

    def test_single_entry(self):
        m = Memory()
        m.add("hello world", importance=0.5, tags=["greeting"])
        result = m.conversation_summary()
        assert result["entry_count"] == 1
        assert result["time_span"]["duration_seconds"] == 0.0
        assert result["importance_distribution"]["mean"] == 0.5
        assert result["importance_distribution"]["min"] == 0.5
        assert result["importance_distribution"]["max"] == 0.5


class TestSummaryBasics:
    def _populate(self, mem, n=10):
        base = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(n):
            mem.add(
                content=f"task number {i} completed",
                importance=0.3 + 0.05 * i,
                tags=[f"tag{i % 3}", f"cat{i % 2}"],
            )
            mem._entries[-1].timestamp = base + timedelta(hours=i)

    def test_entry_count(self):
        m = Memory()
        self._populate(m, 10)
        result = m.conversation_summary()
        assert result["entry_count"] == 10

    def test_time_span(self):
        m = Memory()
        self._populate(m, 5)
        result = m.conversation_summary()
        ts = result["time_span"]
        assert "earliest" in ts
        assert "latest" in ts
        assert "duration_seconds" in ts
        datetime.fromisoformat(ts["earliest"])
        datetime.fromisoformat(ts["latest"])
        # 4 hours between first and last
        assert ts["duration_seconds"] == 4 * 3600

    def test_recent_n_filter(self):
        m = Memory()
        self._populate(m, 10)
        result = m.conversation_summary(recent_n=3)
        assert result["entry_count"] == 3

    def test_recent_n_zero_means_all(self):
        m = Memory()
        self._populate(m, 5)
        result = m.conversation_summary(recent_n=0)
        assert result["entry_count"] == 5

    def test_recent_n_negative_means_all(self):
        m = Memory()
        self._populate(m, 5)
        result = m.conversation_summary(recent_n=-1)
        assert result["entry_count"] == 5

    def test_recent_n_larger_than_entries(self):
        m = Memory()
        self._populate(m, 3)
        result = m.conversation_summary(recent_n=100)
        assert result["entry_count"] == 3


class TestTopTags:
    def test_top_tags_sorted_by_count(self):
        m = Memory()
        for i in range(5):
            m.add(f"a-{i}", tags=["alpha"])
        for i in range(3):
            m.add(f"b-{i}", tags=["beta"])
        for i in range(1):
            m.add(f"c-{i}", tags=["gamma"])
        result = m.conversation_summary()
        tags = result["top_tags"]
        assert tags[0]["tag"] == "alpha"
        assert tags[0]["count"] == 5
        assert tags[1]["tag"] == "beta"
        assert tags[1]["count"] == 3
        assert tags[2]["tag"] == "gamma"
        assert tags[2]["count"] == 1

    def test_no_tags_returns_empty_list(self):
        m = Memory()
        m.add("no tags here", importance=0.5)
        result = m.conversation_summary()
        assert result["top_tags"] == []


class TestImportanceDistribution:
    def test_buckets(self):
        m = Memory()
        m.add("low1", importance=0.1)
        m.add("low2", importance=0.2)
        m.add("med1", importance=0.4)
        m.add("med2", importance=0.6)
        m.add("high1", importance=0.8)
        m.add("high2", importance=0.95)
        result = m.conversation_summary()
        dist = result["importance_distribution"]
        assert dist["buckets"]["low"] == 2
        assert dist["buckets"]["medium"] == 2
        assert dist["buckets"]["high"] == 2

    def test_mean_min_max(self):
        m = Memory()
        vals = [0.1, 0.5, 0.9]
        for v in vals:
            m.add(f"e-{v}", importance=v)
        result = m.conversation_summary()
        dist = result["importance_distribution"]
        assert dist["min"] == 0.1
        assert dist["max"] == 0.9
        assert abs(dist["mean"] - 0.5) < 0.01


class TestContentThemes:
    def test_word_frequency(self):
        m = Memory()
        m.add("deploy the server application")
        m.add("server deployment completed")
        m.add("application server running")
        result = m.conversation_summary()
        themes = result["content_themes"]
        assert "server" in themes
        assert themes["server"] == 3
        assert "deploy" in themes or "deployment" in themes

    def test_stop_words_filtered(self):
        m = Memory()
        m.add("the quick brown fox jumps over the lazy dog")
        result = m.conversation_summary()
        themes = result["content_themes"]
        assert "the" not in themes
        assert "quick" in themes
        assert "fox" in themes

    def test_short_words_filtered(self):
        m = Memory()
        m.add("a b c de fg hijk")
        result = m.conversation_summary()
        themes = result["content_themes"]
        assert "hijk" in themes

    def test_max_20_themes(self):
        m = Memory()
        # 30 distinct words
        for i in range(30):
            m.add(f"word{i} unique")
        result = m.conversation_summary()
        assert len(result["content_themes"]) <= 20


class TestActivityPattern:
    def test_uniform_activity(self):
        m = Memory()
        base = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(5):
            m.add(f"e-{i}", importance=0.5)
            m._entries[-1].timestamp = base + timedelta(hours=i)
        result = m.conversation_summary()
        ap = result["activity_pattern"]
        assert ap["rate_per_hour"] > 0
        assert isinstance(ap["burst_detected"], bool)
        assert ap["gap_seconds"] == 3600.0  # 1 hour gaps

    def test_burst_detected_flag(self):
        m = Memory()
        base = datetime(2026, 1, 1, 6, 0, 0)
        # Baseline spread out
        for i in range(3):
            m.add(f"baseline-{i}", importance=0.5)
            m._entries[-1].timestamp = base + timedelta(hours=i * 3)
        # Burst cluster
        burst_start = base + timedelta(hours=10)
        for i in range(15):
            m.add(f"burst-{i}", importance=0.5)
            m._entries[-1].timestamp = burst_start + timedelta(seconds=i)
        result = m.conversation_summary()
        assert result["activity_pattern"]["burst_detected"] is True

    def test_gap_seconds(self):
        m = Memory()
        base = datetime(2026, 1, 1, 12, 0, 0)
        m.add("first", importance=0.5)
        m._entries[-1].timestamp = base
        m.add("second", importance=0.5)
        m._entries[-1].timestamp = base + timedelta(seconds=30)
        m.add("third", importance=0.5)
        m._entries[-1].timestamp = base + timedelta(seconds=120)
        result = m.conversation_summary()
        assert result["activity_pattern"]["gap_seconds"] == 90.0  # max gap
