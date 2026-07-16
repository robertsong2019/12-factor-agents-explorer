"""Tests for F15 search_all_tags + F16 distinct_tags"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory


class TestSearchAllTags:
    """F15: Memory.search_all_tags(tags) — AND semantics"""

    def test_single_tag(self):
        m = Memory()
        m.add("a", tags=["x"])
        m.add("b", tags=["y"])
        results = m.search_all_tags(["x"])
        assert len(results) == 1
        assert results[0].content == "a"

    def test_multiple_tags_and(self):
        m = Memory()
        m.add("both", tags=["x", "y"])
        m.add("only_x", tags=["x"])
        m.add("only_y", tags=["y"])
        results = m.search_all_tags(["x", "y"])
        assert len(results) == 1
        assert results[0].content == "both"

    def test_no_match(self):
        m = Memory()
        m.add("hello", tags=["greeting"])
        results = m.search_all_tags(["nonexistent"])
        assert results == []

    def test_empty_tags_list(self):
        m = Memory()
        m.add("hello", tags=["x"])
        results = m.search_all_tags([])
        assert results == []

    def test_empty_memory(self):
        m = Memory()
        results = m.search_all_tags(["x", "y"])
        assert results == []

    def test_limit(self):
        m = Memory()
        for i in range(10):
            m.add(f"item-{i}", tags=["x", "y"])
        results = m.search_all_tags(["x", "y"], limit=3)
        assert len(results) == 3

    def test_limit_zero_means_all(self):
        m = Memory()
        for i in range(5):
            m.add(f"item-{i}", tags=["x"])
        results = m.search_all_tags(["x"], limit=0)
        assert len(results) == 5

    def test_three_tags_intersection(self):
        m = Memory()
        m.add("tri", tags=["a", "b", "c"])
        m.add("bi", tags=["a", "b"])
        results = m.search_all_tags(["a", "b", "c"])
        assert len(results) == 1
        assert results[0].content == "tri"

    def test_order_preserved(self):
        m = Memory()
        m.add("first", tags=["tag"])
        m.add("second", tags=["tag"])
        m.add("third", tags=["tag"])
        results = m.search_all_tags(["tag"])
        assert results[0].content == "first"
        assert results[-1].content == "third"


class TestDistinctTags:
    """F16: Memory.distinct_tags()"""

    def test_basic(self):
        m = Memory()
        m.add("a", tags=["x", "y"])
        m.add("b", tags=["y", "z"])
        tags = m.distinct_tags()
        assert tags == ["x", "y", "z"]

    def test_sorted_alphabetically(self):
        m = Memory()
        m.add("a", tags=["zebra", "apple"])
        m.add("b", tags=["mango"])
        tags = m.distinct_tags()
        assert tags == ["apple", "mango", "zebra"]

    def test_empty_memory(self):
        m = Memory()
        assert m.distinct_tags() == []

    def test_no_tags_on_entries(self):
        m = Memory()
        m.add("untagged")
        assert m.distinct_tags() == []

    def test_dedup(self):
        m = Memory()
        m.add("a", tags=["work", "urgent"])
        m.add("b", tags=["work", "important"])
        m.add("c", tags=["urgent"])
        tags = m.distinct_tags()
        assert tags == ["important", "urgent", "work"]

    def test_single_entry_multiple_tags(self):
        m = Memory()
        m.add("multi", tags=["a", "b", "c", "d", "e"])
        tags = m.distinct_tags()
        assert len(tags) == 5
        assert tags == ["a", "b", "c", "d", "e"]

    def test_returns_list_type(self):
        m = Memory()
        m.add("a", tags=["x"])
        result = m.distinct_tags()
        assert isinstance(result, list)
