"""
Tests for F20: Memory.deduplicate() and F21: Memory.chain_search()
"""
import pytest
from nano_agent.memory import Memory, MemoryEntry


class TestF20Deduplicate:
    """F20: Memory.deduplicate() — remove near-duplicate entries"""

    def test_dedup_removes_exact_duplicates(self):
        """Exact same content should be deduplicated."""
        m = Memory(max_entries=100)
        m.add("Python is great", tags=["lang"])
        m.add("Python is great", tags=["lang"])
        m.add("Python is great")
        assert m.count() == 3
        removed = m.deduplicate()
        assert removed == 2
        assert m.count() == 1

    def test_dedup_removes_near_duplicates(self):
        """Content with high similarity (>= threshold) should be removed."""
        m = Memory(max_entries=100)
        m.add("The quick brown fox jumps over the lazy dog")
        m.add("The quick brown fox jumps over the lazy dog!")  # nearly identical
        m.add("A completely different sentence about weather")
        removed = m.deduplicate(threshold=0.9)
        assert removed == 1
        assert m.count() == 2

    def test_dedup_keeps_all_when_unique(self):
        """No duplicates → nothing removed."""
        m = Memory(max_entries=100)
        m.add("First memory about cats")
        m.add("Second memory about dogs")
        m.add("Third memory about fish")
        removed = m.deduplicate()
        assert removed == 0
        assert m.count() == 3

    def test_dedup_threshold_default(self):
        """Default threshold should be 0.95 (very strict)."""
        m = Memory(max_entries=100)
        m.add("Hello world this is a test")
        m.add("Hello world this is a test with extra words")
        removed = m.deduplicate()  # default threshold=0.95
        # These are similar but not 0.95 similar
        assert removed == 0

    def test_dedup_custom_threshold(self):
        """Lower threshold catches more duplicates."""
        m = Memory(max_entries=100)
        m.add("Hello world this is a test")
        m.add("Hello world this is a test with extra words")
        removed = m.deduplicate(threshold=0.7)
        assert removed == 1
        assert m.count() == 1

    def test_dedup_empty_memory(self):
        """Empty memory → 0 removed."""
        m = Memory(max_entries=100)
        assert m.deduplicate() == 0

    def test_dedup_single_entry(self):
        """Single entry → 0 removed."""
        m = Memory(max_entries=100)
        m.add("Only one memory")
        assert m.deduplicate() == 0
        assert m.count() == 1

    def test_dedup_preserves_earliest(self):
        """When deduplicating, the earliest entry should be kept."""
        m = Memory(max_entries=100)
        m.add("Duplicate content here")
        m.add("Duplicate content here")
        entries_before = m.get_all()
        m.deduplicate()
        entries_after = m.get_all()
        assert len(entries_after) == 1
        assert entries_after[0].content == "Duplicate content here"
        # The first entry should be the one kept
        assert entries_after[0].timestamp == entries_before[0].timestamp

    def test_dedup_with_persistence(self, tmp_path):
        """Dedup should persist changes when persistence_path is set."""
        import json
        store = tmp_path / "dedup_test.json"
        m = Memory(persistence_path=str(store))
        m.add("Same content")
        m.add("Same content")
        m.add("Unique content")
        m.deduplicate()
        # Reload from disk
        m2 = Memory(persistence_path=str(store))
        assert m2.count() == 2

    def test_dedup_groups(self):
        """Multiple clusters of duplicates should all be handled."""
        m = Memory(max_entries=100)
        m.add("Apple pie recipe")
        m.add("Apple pie recipe")
        m.add("Banana bread recipe")
        m.add("Banana bread recipe")
        m.add("Cherry tart recipe")
        removed = m.deduplicate(threshold=1.0)  # only exact duplicates
        assert removed == 2
        assert m.count() == 3


class TestF21ChainSearch:
    """F21: Memory.chain_search(queries) — multi-query merged search with ranking"""

    def test_chain_search_basic(self):
        """Multiple queries should return merged unique results."""
        m = Memory(max_entries=100)
        m.add("Python is a programming language", tags=["tech"])
        m.add("Java is also a programming language", tags=["tech"])
        m.add("I love coffee in the morning", tags=["life"])
        results = m.chain_search(["Python", "Java"])
        assert len(results) == 2
        contents = [r.content for r in results]
        assert "Python is a programming language" in contents
        assert "Java is also a programming language" in contents

    def test_chain_search_deduplicates_overlapping_results(self):
        """If a memory matches multiple queries, it should appear only once."""
        m = Memory(max_entries=100)
        m.add("Python programming is fun and Python is easy")
        results = m.chain_search(["Python", "programming"])
        assert len(results) == 1

    def test_chain_search_empty_queries(self):
        """Empty query list → empty results."""
        m = Memory(max_entries=100)
        m.add("Some content")
        assert m.chain_search([]) == []

    def test_chain_search_no_matches(self):
        """Queries that match nothing → empty results."""
        m = Memory(max_entries=100)
        m.add("Hello world")
        results = m.chain_search(["nonexistent", "missing"])
        assert results == []

    def test_chain_search_ranked_by_match_count(self):
        """Entries matching more queries should rank higher."""
        m = Memory(max_entries=100)
        m.add("Python Python Python")       # matches "Python" only (1 query)
        m.add("Python and Java")            # matches both queries (2 queries)
        results = m.chain_search(["Python", "Java"])
        # The entry matching both queries should rank first
        assert results[0].content == "Python and Java"

    def test_chain_search_with_limit(self):
        """Limit should cap total results."""
        m = Memory(max_entries=100)
        for i in range(10):
            m.add(f"Item {i} about cats")
            m.add(f"Item {i} about dogs")
        results = m.chain_search(["cats", "dogs"], limit=5)
        assert len(results) == 5

    def test_chain_search_preserves_entry_objects(self):
        """Should return actual MemoryEntry objects, not copies."""
        m = Memory(max_entries=100)
        m.add("Test entry", tags=["important"], importance=0.9)
        results = m.chain_search(["Test"])
        assert len(results) == 1
        assert isinstance(results[0], MemoryEntry)
        assert results[0].importance == 0.9
        assert "important" in results[0].tags

    def test_chain_search_case_insensitive(self):
        """Search should be case insensitive."""
        m = Memory(max_entries=100)
        m.add("Python is great")
        results = m.chain_search(["python", "GREAT"])
        assert len(results) == 1

    def test_chain_search_fuzzy_fallback(self):
        """When fuzzy=True, chain_search should find approximate matches too."""
        m = Memory(max_entries=100)
        m.add("The weather is nice today")
        m.add("Completely unrelated content about math")
        results = m.chain_search(["whether is nice"], fuzzy=True, threshold=0.5)
        assert len(results) >= 1
        assert any("weather" in e.content for e in results)
