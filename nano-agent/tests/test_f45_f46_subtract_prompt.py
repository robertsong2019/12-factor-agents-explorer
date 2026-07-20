"""Tests for F45 (subtract) and F46 (to_prompt)."""
import pytest
from nano_agent.memory import Memory, MemoryEntry


# ── F45: subtract ──────────────────────────────────────────────

class TestSubtract:
    def test_basic_difference(self):
        """Entries in self but not in other should remain."""
        a = Memory()
        a.add("alpha", tags=["x"])
        a.add("beta", tags=["y"])
        a.add("gamma", tags=["z"])

        b = Memory()
        b.add("beta")
        b.add("delta")

        result = a.subtract(b)
        contents = [e.content for e in result.get_all()]
        assert contents == ["alpha", "gamma"]

    def test_returns_new_memory_instance(self):
        a = Memory()
        a.add("hello")
        b = Memory()
        b.add("world")
        result = a.subtract(b)
        assert isinstance(result, Memory)
        assert result is not a

    def test_no_overlap_returns_copy_of_self(self):
        a = Memory()
        a.add("one")
        a.add("two")
        b = Memory()
        b.add("three")
        result = a.subtract(b)
        contents = sorted(e.content for e in result.get_all())
        assert contents == ["one", "two"]

    def test_total_overlap_returns_empty(self):
        a = Memory()
        a.add("x")
        a.add("y")
        b = Memory()
        b.add("x")
        b.add("y")
        result = a.subtract(b)
        assert result.count() == 0

    def test_empty_self(self):
        a = Memory()
        b = Memory()
        b.add("a")
        result = a.subtract(b)
        assert result.count() == 0

    def test_empty_other(self):
        a = Memory()
        a.add("a")
        a.add("b")
        b = Memory()
        result = a.subtract(b)
        assert result.count() == 2

    def test_original_not_modified(self):
        a = Memory()
        a.add("keep")
        a.add("remove")
        b = Memory()
        b.add("remove")
        a.subtract(b)
        assert a.count() == 2  # original unchanged

    def test_preserves_metadata_and_tags(self):
        a = Memory()
        a.add("alpha", tags=["important"], importance=0.9, metadata={"src": "test"})
        b = Memory()
        b.add("beta")
        result = a.subtract(b)
        entry = result.get_all()[0]
        assert entry.content == "alpha"
        assert entry.tags == ["important"]
        assert entry.importance == 0.9
        assert entry.metadata == {"src": "test"}

    def test_content_based_not_identity_based(self):
        """Two entries with same content but different metadata should still be removed."""
        a = Memory()
        a.add("shared", tags=["from_a"], importance=0.8)
        b = Memory()
        b.add("shared", tags=["from_b"], importance=0.3)
        result = a.subtract(b)
        assert result.count() == 0

    def test_subtract_then_union_roundtrip(self):
        """subtract followed by union of the removed set should equal original."""
        a = Memory()
        for i in range(5):
            a.add(f"item_{i}")
        b = Memory()
        b.add("item_1")
        b.add("item_3")

        diff = a.subtract(b)
        restored = diff.union(b.subtract(a).union(b))  # diff ∪ removed = original set
        contents_original = sorted(e.content for e in a.get_all())
        contents_restored = sorted(e.content for e in restored.get_all())
        assert contents_original == contents_restored


# ── F46: to_prompt ─────────────────────────────────────────────

class TestToPrompt:
    def test_empty_memory(self):
        m = Memory()
        assert m.to_prompt() == ""

    def test_basic_format(self):
        m = Memory()
        m.add("Hello world", importance=0.8)
        result = m.to_prompt()
        assert "Memory Store" in result
        assert "Hello world" in result
        assert "1 of 1 entries" in result

    def test_sorted_by_importance(self):
        m = Memory()
        m.add("low", importance=0.2)
        m.add("high", importance=0.9)
        m.add("mid", importance=0.5)
        result = m.to_prompt()
        lines = result.split("\n\n")
        # First entry after header should be "high"
        assert "high" in lines[1]
        assert "[0.9]" in lines[1]
        assert "[0.2]" in lines[3]

    def test_max_entries_limit(self):
        m = Memory()
        for i in range(10):
            m.add(f"entry_{i}", importance=i / 10.0)
        result = m.to_prompt(max_entries=3)
        assert "3 of 10 entries" in result

    def test_include_tags(self):
        m = Memory()
        m.add("tagged entry", tags=["red", "blue"], importance=0.7)
        result = m.to_prompt(include_tags=True)
        assert "tags:" in result
        assert "red" in result
        assert "blue" in result

    def test_exclude_tags(self):
        m = Memory()
        m.add("tagged entry", tags=["red", "blue"], importance=0.7)
        result = m.to_prompt(include_tags=False)
        assert "tags:" not in result

    def test_include_metadata(self):
        m = Memory()
        m.add("meta entry", metadata={"source": "api", "version": 2}, importance=0.6)
        result = m.to_prompt(include_metadata=True)
        assert "metadata:" in result
        assert "source=api" in result
        assert "version=2" in result

    def test_exclude_metadata(self):
        m = Memory()
        m.add("meta entry", metadata={"source": "api"}, importance=0.6)
        result = m.to_prompt(include_metadata=False)
        assert "metadata:" not in result

    def test_timestamp_always_included(self):
        m = Memory()
        m.add("test entry", importance=0.5)
        result = m.to_prompt()
        assert "timestamp:" in result

    def test_importance_score_in_output(self):
        m = Memory()
        m.add("scored", importance=0.75)
        result = m.to_prompt()
        assert "[0.8]" in result  # rounded to 1 decimal

    def test_numbered_entries(self):
        m = Memory()
        for i in range(3):
            m.add(f"entry_{i}", importance=0.5)
        result = m.to_prompt()
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_no_tags_no_tag_line(self):
        m = Memory()
        m.add("no tags here", importance=0.5)
        result = m.to_prompt(include_tags=True)
        assert "tags:" not in result  # no tags to show

    def test_no_metadata_no_meta_line(self):
        m = Memory()
        m.add("no meta", importance=0.5)
        result = m.to_prompt(include_metadata=True)
        assert "metadata:" not in result
