"""Tests for F13 search_by_tag and F14 merge"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry


class TestSearchByTag:
    """F13: Memory.search_by_tag(tag, limit)"""

    def test_single_tag_match(self):
        m = Memory()
        m.add("hello", tags=["greeting"])
        m.add("world", tags=["topic"])
        m.add("hi there", tags=["greeting"])
        results = m.search_by_tag("greeting")
        assert len(results) == 2
        assert all("greeting" in e.tags for e in results)

    def test_no_match(self):
        m = Memory()
        m.add("hello", tags=["greeting"])
        results = m.search_by_tag("nonexistent")
        assert results == []

    def test_empty_memory(self):
        m = Memory()
        results = m.search_by_tag("anything")
        assert results == []

    def test_limit(self):
        m = Memory()
        for i in range(10):
            m.add(f"item {i}", tags=["data"])
        results = m.search_by_tag("data", limit=3)
        assert len(results) == 3
        # Should return most recent 3
        assert "item 9" in results[-1].content
        assert "item 7" in results[0].content

    def test_limit_zero_means_all(self):
        m = Memory()
        for i in range(5):
            m.add(f"item {i}", tags=["data"])
        results = m.search_by_tag("data", limit=0)
        assert len(results) == 5

    def test_multi_tag_entry(self):
        m = Memory()
        m.add("important note", tags=["work", "urgent", "project"])
        results = m.search_by_tag("urgent")
        assert len(results) == 1
        results = m.search_by_tag("project")
        assert len(results) == 1
        results = m.search_by_tag("work")
        assert len(results) == 1

    def test_results_ordered_by_time(self):
        m = Memory()
        m.add("first", tags=["log"])
        m.add("second", tags=["log"])
        m.add("third", tags=["log"])
        results = m.search_by_tag("log")
        assert results[0].content == "first"
        assert results[-1].content == "third"


class TestMerge:
    """F14: Memory.merge(other)"""

    def test_basic_merge(self):
        m1 = Memory()
        m1.add("alpha")
        m1.add("beta")
        m2 = Memory()
        m2.add("gamma")
        m2.add("delta")
        added = m1.merge(m2)
        assert added == 2
        assert m1.count() == 4

    def test_dedup_by_content(self):
        m1 = Memory()
        m1.add("hello")
        m1.add("world")
        m2 = Memory()
        m2.add("hello")
        m2.add("earth")
        added = m1.merge(m2)
        assert added == 1  # "hello" deduped
        assert m1.count() == 3

    def test_merge_empty_other(self):
        m1 = Memory()
        m1.add("data")
        m2 = Memory()
        added = m1.merge(m2)
        assert added == 0
        assert m1.count() == 1

    def test_merge_into_empty(self):
        m1 = Memory()
        m2 = Memory()
        m2.add("a")
        m2.add("b")
        added = m1.merge(m2)
        assert added == 2
        assert m1.count() == 2

    def test_merge_respects_max_entries(self):
        m1 = Memory(max_entries=5)
        for i in range(4):
            m1.add(f"orig-{i}")
        m2 = Memory(max_entries=10)
        for i in range(10):
            m2.add(f"new-{i}")
        added = m1.merge(m2)
        assert m1.count() <= 5

    def test_merge_returns_correct_count_with_all_dupes(self):
        m1 = Memory()
        m1.add("same")
        m2 = Memory()
        m2.add("same")
        added = m1.merge(m2)
        assert added == 0

    def test_merge_preserves_tags_and_importance(self):
        m1 = Memory()
        m2 = Memory()
        m2.add("important", tags=["urgent"], importance=0.9)
        m1.merge(m2)
        entries = m1.get_all()
        assert any(e.content == "important" for e in entries)
        merged_entry = [e for e in entries if e.content == "important"][0]
        assert "urgent" in merged_entry.tags
        assert merged_entry.importance == 0.9

    def test_merge_multiple_calls(self):
        m1 = Memory()
        m1.add("base")
        for i in range(3):
            m2 = Memory()
            m2.add(f"batch-{i}")
            m1.merge(m2)
        assert m1.count() == 4
