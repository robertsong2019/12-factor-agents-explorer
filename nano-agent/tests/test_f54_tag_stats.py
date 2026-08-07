"""Tests for F54 (tag_stats)."""

import pytest
from nano_agent.memory import Memory


class TestTagStats:
    def test_empty_memory(self):
        m = Memory(max_entries=100)
        stats = m.tag_stats()
        assert stats["frequency"] == {}
        assert stats["total_tags"] == 0
        assert stats["tagged_entries"] == 0
        assert stats["untagged_entries"] == 0
        assert stats["co_occurrence"] == {}

    def test_all_untagged(self):
        m = Memory(max_entries=100)
        m.add("no tags here")
        m.add("no tags either")
        stats = m.tag_stats()
        assert stats["total_tags"] == 0
        assert stats["tagged_entries"] == 0
        assert stats["untagged_entries"] == 2

    def test_frequency_count(self):
        m = Memory(max_entries=100)
        m.add("a", tags=["python", "ai"])
        m.add("b", tags=["python"])
        m.add("c", tags=["rust", "ai"])
        stats = m.tag_stats()
        assert stats["frequency"]["python"] == 2
        assert stats["frequency"]["ai"] == 2
        assert stats["frequency"]["rust"] == 1
        assert stats["total_tags"] == 3

    def test_tagged_vs_untagged(self):
        m = Memory(max_entries=100)
        m.add("tagged", tags=["x"])
        m.add("untagged")
        stats = m.tag_stats()
        assert stats["tagged_entries"] == 1
        assert stats["untagged_entries"] == 1

    def test_co_occurrence(self):
        m = Memory(max_entries=100)
        m.add("entry1", tags=["python", "ai", "ml"])
        m.add("entry2", tags=["python", "ai"])
        stats = m.tag_stats()
        co = stats["co_occurrence"]
        # python+ai appear together twice
        assert co["python"]["ai"] == 2
        # python+ml once, ai+ml once
        assert co["python"]["ml"] == 1
        assert co["ai"]["ml"] == 1

    def test_no_self_co_occurrence(self):
        m = Memory(max_entries=100)
        m.add("entry1", tags=["python"])
        stats = m.tag_stats()
        co = stats["co_occurrence"]
        # A tag shouldn't co-occur with itself
        assert "python" not in co or "python" not in co.get("python", {})

    def test_duplicate_tags_in_one_entry(self):
        """Duplicate tags in the same entry should be deduplicated."""
        m = Memory(max_entries=100)
        m.add("entry", tags=["python", "python", "ai"])
        stats = m.tag_stats()
        assert stats["frequency"]["python"] == 1  # counted once per entry
        assert stats["frequency"]["ai"] == 1

    def test_frequency_sorted_by_count_desc(self):
        m = Memory(max_entries=100)
        m.add("a", tags=["rare"])
        m.add("b", tags=["common"])
        m.add("c", tags=["common"])
        stats = m.tag_stats()
        items = list(stats["frequency"].items())
        # common (2) should come before rare (1)
        assert items[0][0] == "common"
        assert items[0][1] == 2
