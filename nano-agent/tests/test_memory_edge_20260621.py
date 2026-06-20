"""
Additional edge-case tests for nano-agent memory module.

Focuses on uncovered branches:
- search() with tag filtering
- to_context() with max_tokens truncation
- MemoryEntry.to_dict() serialization (with and without tags)
- remove() out of bounds
- update() with metadata replacement
- get_recent(n=0) boundary
- clear() preserves max_entries
- max_entries eviction on add()
"""

import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from nano_agent.memory import Memory, MemoryEntry
from datetime import datetime


class TestSearchWithTagFilter:
    """search() with tags parameter — covers the tag filtering branch."""

    def test_search_with_tags_filters_results(self):
        m = Memory()
        m.add("hello world", tags=["greeting"])
        m.add("hello there", tags=["informal"])
        m.add("goodbye world", tags=["farewell"])
        results = m.search("hello", tags=["greeting"])
        assert len(results) == 1
        assert results[0].content == "hello world"

    def test_search_with_multiple_tags_union(self):
        m = Memory()
        m.add("a", tags=["x"])
        m.add("b", tags=["y"])
        m.add("c", tags=["z"])
        results = m.search("", tags=["x", "y"])  # "" matches all
        assert len(results) == 2

    def test_search_with_tags_no_match(self):
        m = Memory()
        m.add("hello", tags=["greeting"])
        results = m.search("hello", tags=["nonexistent"])
        assert len(results) == 0

    def test_search_with_tags_but_entry_has_no_tags(self):
        m = Memory()
        m.add("hello")  # no tags
        results = m.search("hello", tags=["greeting"])
        assert len(results) == 0

    def test_search_limit_zero_returns_all(self):
        """limit=0 should return all matches without truncation."""
        m = Memory()
        for i in range(10):
            m.add(f"item {i}")
        results = m.search("item", limit=0)
        assert len(results) == 10


class TestToContextTruncation:
    """to_context() with max_tokens — covers the truncation branch."""

    def test_to_context_truncates_small_max_tokens(self):
        m = Memory()
        m.add("short")
        m.add("another entry")
        ctx = m.to_context(max_tokens=20)  # very small
        assert "## 记忆" in ctx
        # Not all entries should fit
        assert len(ctx.encode("utf-8")) <= 100  # reasonable upper bound

    def test_to_context_large_max_tokens_includes_all(self):
        m = Memory()
        m.add("first entry")
        m.add("second entry")
        ctx = m.to_context(max_tokens=10000)
        assert "first entry" in ctx
        assert "second entry" in ctx

    def test_to_context_includes_timestamp_format(self):
        m = Memory()
        m.add("test entry")
        ctx = m.to_context()
        # Should contain a date-like pattern
        assert "-" in ctx  # YYYY-MM-DD format


class TestMemoryEntrySerialization:
    """MemoryEntry.to_dict() — covers tag inclusion/exclusion."""

    def test_to_dict_with_tags(self):
        entry = MemoryEntry(content="hello", tags=["a", "b"])
        d = entry.to_dict()
        assert d["tags"] == ["a", "b"]
        assert d["content"] == "hello"

    def test_to_dict_without_tags_omits_key(self):
        entry = MemoryEntry(content="hello", tags=[])
        d = entry.to_dict()
        assert "tags" not in d

    def test_to_dict_includes_metadata(self):
        entry = MemoryEntry(content="hello", metadata={"key": "value"})
        d = entry.to_dict()
        assert d["metadata"]["key"] == "value"

    def test_to_dict_timestamp_is_iso_string(self):
        entry = MemoryEntry(content="hello")
        d = entry.to_dict()
        assert "timestamp" in d
        # Should be parseable as ISO format
        datetime.fromisoformat(d["timestamp"])


class TestRemoveEdgeCases:
    """remove() boundary conditions."""

    def test_remove_negative_index(self):
        m = Memory()
        m.add("a")
        assert m.remove(-1) is False

    def test_remove_out_of_bounds(self):
        m = Memory()
        m.add("a")
        assert m.remove(1) is False

    def test_remove_empty_memory(self):
        m = Memory()
        assert m.remove(0) is False


class TestUpdateEdgeCases:
    """update() with metadata."""

    def test_update_replaces_metadata(self):
        m = Memory()
        m.add("original", metadata={"old": True})
        assert m.update(0, "updated", metadata={"new": True}) is True
        assert m.get_all()[0].content == "updated"
        assert m.get_all()[0].metadata == {"new": True}

    def test_update_preserves_old_metadata_when_none(self):
        m = Memory()
        m.add("original", metadata={"keep": True})
        assert m.update(0, "updated") is True
        assert m.get_all()[0].metadata == {"keep": True}

    def test_update_out_of_bounds(self):
        m = Memory()
        assert m.update(0, "x") is False


class TestGetRecentBoundary:
    """get_recent() with boundary values."""

    def test_get_recent_zero_returns_empty(self):
        m = Memory()
        m.add("a")
        assert m.get_recent(0) == []

    def test_get_recent_negative_returns_empty(self):
        m = Memory()
        m.add("a")
        assert m.get_recent(-1) == []

    def test_get_recent_more_than_available(self):
        m = Memory()
        m.add("a")
        m.add("b")
        result = m.get_recent(10)
        assert len(result) == 2


class TestMaxEntriesEviction:
    """max_entries enforcement on add()."""

    def test_add_evicts_oldest(self):
        m = Memory(max_entries=3)
        m.add("first")
        m.add("second")
        m.add("third")
        m.add("fourth")
        assert m.count() == 3
        all_entries = m.get_all()
        assert all_entries[0].content == "second"

    def test_add_at_limit_no_eviction(self):
        m = Memory(max_entries=3)
        m.add("a")
        m.add("b")
        m.add("c")
        assert m.count() == 3

    def test_clear_then_add_works(self):
        m = Memory(max_entries=5)
        m.add("a")
        m.add("b")
        m.clear()
        assert m.count() == 0
        m.add("c")
        assert m.count() == 1
