"""
F24-F25 测试: Memory.filter() + Memory.weighted_search()
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nano_agent.memory import Memory, MemoryEntry


# ─── F24: filter ───

class TestFilter:
    def test_filter_by_importance(self):
        m = Memory()
        m.add("low", importance=0.1)
        m.add("high", importance=0.9)
        m.add("mid", importance=0.5)
        results = m.filter(lambda e: e.importance > 0.4)
        assert len(results) == 2
        assert results[0].content == "high"
        assert results[1].content == "mid"

    def test_filter_by_tag(self):
        m = Memory()
        m.add("a", tags=["urgent"])
        m.add("b", tags=["normal"])
        m.add("c", tags=["urgent"])
        results = m.filter(lambda e: "urgent" in e.tags)
        assert len(results) == 2

    def test_filter_returns_empty_when_no_match(self):
        m = Memory()
        m.add("hello", importance=0.5)
        results = m.filter(lambda e: e.importance > 0.99)
        assert results == []

    def test_filter_empty_memory(self):
        m = Memory()
        results = m.filter(lambda e: True)
        assert results == []

    def test_filter_all_match(self):
        m = Memory()
        m.add("a")
        m.add("b")
        results = m.filter(lambda e: True)
        assert len(results) == 2

    def test_filter_by_content_substring(self):
        m = Memory()
        m.add("error: something failed")
        m.add("all good")
        m.add("error: another issue")
        results = m.filter(lambda e: "error" in e.content)
        assert len(results) == 2

    def test_filter_preserves_order(self):
        m = Memory()
        m.add("first")
        m.add("second")
        m.add("third")
        results = m.filter(lambda e: True)
        assert results[0].content == "first"
        assert results[2].content == "third"

    def test_filter_by_metadata(self):
        m = Memory()
        m.add("x", metadata={"source": "api"})
        m.add("y", metadata={"source": "manual"})
        m.add("z", metadata={"source": "api"})
        results = m.filter(lambda e: e.metadata.get("source") == "api")
        assert len(results) == 2

    def test_filter_complex_predicate(self):
        m = Memory()
        m.add("important urgent", tags=["urgent"], importance=0.9)
        m.add("important but not urgent", importance=0.9)
        m.add("urgent but not important", tags=["urgent"], importance=0.2)
        # Both urgent AND important
        results = m.filter(lambda e: "urgent" in e.tags and e.importance > 0.5)
        assert len(results) == 1
        assert results[0].content == "important urgent"

    def test_filter_returns_memory_entry_objects(self):
        m = Memory()
        m.add("test", importance=0.8, tags=["a"])
        results = m.filter(lambda e: True)
        assert isinstance(results[0], MemoryEntry)


# ─── F25: weighted_search ───

class TestWeightedSearch:
    def test_basic_search_returns_results(self):
        m = Memory()
        m.add("hello world")
        m.add("goodbye world")
        results = m.weighted_search("hello")
        assert len(results) >= 1
        assert "hello" in results[0].content

    def test_empty_memory_returns_empty(self):
        m = Memory()
        results = m.weighted_search("test")
        assert results == []

    def test_empty_query_returns_empty(self):
        m = Memory()
        m.add("data")
        results = m.weighted_search("")
        assert results == []

    def test_content_match_ranks_higher(self):
        m = Memory()
        m.add("python programming language")
        m.add("random unrelated text")
        m.add("python is great for data")
        results = m.weighted_search("python", limit=2)
        # Both python entries should rank above the unrelated one
        assert all("python" in r.content for r in results)

    def test_importance_boosts_ranking(self):
        m = Memory()
        m.add("important match", importance=0.1)
        m.add("important match too", importance=0.9)
        results = m.weighted_search("important", limit=2)
        # The high-importance entry should rank first
        assert results[0].importance == 0.9

    def test_recency_boosts_ranking(self):
        m = Memory()
        m.add("old entry with keyword", importance=0.5)
        m.add("new entry with keyword", importance=0.5)
        m.add("another entry with keyword", importance=0.5)
        results = m.weighted_search("keyword", limit=3)
        # Most recent (last added) should rank first due to recency boost
        assert results[0].content == "another entry with keyword"

    def test_limit_parameter(self):
        m = Memory()
        for i in range(10):
            m.add(f"entry {i}")
        results = m.weighted_search("entry", limit=3)
        assert len(results) == 3

    def test_limit_zero_returns_all(self):
        m = Memory()
        m.add("a entry")
        m.add("b entry")
        results = m.weighted_search("entry", limit=0)
        assert len(results) == 2

    def test_custom_weights_content_only(self):
        m = Memory()
        m.add("exact match", importance=0.1)
        m.add("no match content", importance=1.0)
        results = m.weighted_search("exact", w_content=1.0, w_importance=0.0, w_recency=0.0)
        assert results[0].content == "exact match"

    def test_custom_weights_importance_only(self):
        m = Memory()
        m.add("low importance data", importance=0.1)
        m.add("high importance data", importance=0.9)
        results = m.weighted_search("data", w_content=0.0, w_importance=1.0, w_recency=0.0)
        assert results[0].importance == 0.9

    def test_custom_weights_recency_only(self):
        m = Memory()
        m.add("old data", importance=0.5)
        m.add("new data", importance=0.5)
        results = m.weighted_search("data", w_content=0.0, w_importance=0.0, w_recency=1.0)
        assert results[0].content == "new data"

    def test_weighted_search_returns_memory_entries(self):
        m = Memory()
        m.add("hello")
        results = m.weighted_search("hello")
        assert isinstance(results[0], MemoryEntry)

    def test_results_are_sorted_by_score_descending(self):
        m = Memory()
        m.add("match low", importance=0.1)
        m.add("match high", importance=0.9)
        results = m.weighted_search("match", limit=2)
        # Higher importance should rank first (since content similarity is similar)
        assert results[0].importance >= results[1].importance

    def test_no_content_match_still_returns_by_importance_recency(self):
        m = Memory()
        m.add("alpha", importance=0.9)
        m.add("beta", importance=0.1)
        results = m.weighted_search("gamma")
        # With no content match, results are ranked purely by importance + recency
        # Both entries are returned because limit defaults to 5 and all have some score
        assert len(results) >= 1
        # Highest importance first
        assert results[0].importance == 0.9
