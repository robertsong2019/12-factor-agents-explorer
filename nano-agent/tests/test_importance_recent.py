"""Tests for search_by_importance() and top_recent()."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory


class TestSearchByImportance:
    def test_basic_threshold(self):
        m = Memory()
        m.add("low", importance=0.1)
        m.add("medium", importance=0.5)
        m.add("high", importance=0.9)
        results = m.search_by_importance(0.5)
        assert len(results) == 2
        contents = [e.content for e in results]
        assert "medium" in contents
        assert "high" in contents

    def test_threshold_zero(self):
        m = Memory()
        m.add("a", importance=0.1)
        m.add("b", importance=0.9)
        results = m.search_by_importance(0.0)
        assert len(results) == 2

    def test_threshold_one(self):
        m = Memory()
        m.add("a", importance=0.5)
        m.add("b", importance=1.0)
        results = m.search_by_importance(1.0)
        assert len(results) == 1
        assert results[0].importance == 1.0

    def test_sorted_descending(self):
        m = Memory()
        m.add("a", importance=0.3)
        m.add("b", importance=0.9)
        m.add("c", importance=0.5)
        results = m.search_by_importance(0.0)
        scores = [e.importance for e in results]
        assert scores == sorted(scores, reverse=True)

    def test_limit(self):
        m = Memory()
        for i in range(10):
            m.add(f"entry_{i}", importance=0.8)
        results = m.search_by_importance(0.0, limit=3)
        assert len(results) == 3

    def test_no_match(self):
        m = Memory()
        m.add("a", importance=0.1)
        results = m.search_by_importance(0.5)
        assert results == []

    def test_empty_memory(self):
        m = Memory()
        assert m.search_by_importance(0.5) == []


class TestTopRecent:
    def test_all_recent(self):
        m = Memory()
        m.add("first")
        m.add("second")
        results = m.top_recent(minutes=60)
        assert len(results) == 2
        # Most recent first
        assert results[0].content == "second"

    def test_minutes_zero_returns_all(self):
        m = Memory()
        m.add("a")
        m.add("b")
        results = m.top_recent(minutes=0)
        assert len(results) == 2

    def test_empty_memory(self):
        m = Memory()
        assert m.top_recent() == []

    def test_time_filter(self):
        m = Memory()
        m.add("old")
        # Manually set an old timestamp
        from datetime import datetime, timedelta
        m._entries[0].timestamp = datetime.now() - timedelta(minutes=120)
        m.add("new")
        results = m.top_recent(minutes=60)
        contents = [e.content for e in results]
        assert "old" not in contents
        assert "new" in contents
