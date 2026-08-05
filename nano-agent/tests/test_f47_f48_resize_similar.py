"""Tests for F47 (resize) and F48 (search_similar)."""

import pytest
from datetime import datetime, timedelta
from nano_agent.memory import Memory, MemoryEntry


# ── F47: resize ──────────────────────────────────────────────

class TestResize:
    def _populate(self, mem, n=10):
        """Add n entries with varying timestamps and importance."""
        base = datetime(2026, 1, 1)
        for i in range(n):
            mem.add(
                content=f"entry-{i}",
                importance=float(i) / n,
                tags=[f"tag{i % 3}"],
            )
            mem._entries[-1].timestamp = base + timedelta(hours=i)

    def test_resize_noop_when_under_limit(self):
        m = Memory()
        self._populate(m, 5)
        result = m.resize(10)
        assert result["removed_count"] == 0
        assert result["remaining_count"] == 5
        assert len(m._entries) == 5

    def test_resize_oldest_strategy(self):
        m = Memory()
        self._populate(m, 10)
        result = m.resize(6, strategy="oldest")
        assert result["removed_count"] == 4
        assert result["remaining_count"] == 6
        # Oldest 4 removed (entries 0-3)
        contents = [e.content for e in m._entries]
        assert "entry-0" not in contents
        assert "entry-3" not in contents
        assert "entry-4" in contents
        assert "entry-9" in contents

    def test_resize_least_important_strategy(self):
        m = Memory()
        self._populate(m, 10)
        result = m.resize(6, strategy="least_important")
        assert result["removed_count"] == 4
        # Importance = i/10, so entries 0-3 have lowest importance
        remaining_importances = [e.importance for e in m._entries]
        assert min(remaining_importances) >= 0.4

    def test_resize_random_strategy(self):
        m = Memory()
        self._populate(m, 10)
        result = m.resize(6, strategy="random")
        assert result["removed_count"] == 4
        assert result["remaining_count"] == 6

    def test_resize_clustered_strategy_removes_near_duplicates(self):
        m = Memory()
        m.add(content="The quick brown fox jumps over the lazy dog", importance=0.9)
        m.add(content="The quick brown fox jumps over the lazy dog!", importance=0.5)  # near-dup
        m.add(content="The quick brown fox jumps over the lazy dog?", importance=0.3)  # near-dup
        m.add(content="Completely different content about AI", importance=0.7)
        m.add(content="Another unique topic: quantum computing", importance=0.8)
        result = m.resize(3, strategy="clustered")
        assert result["removed_count"] == 2
        assert result["remaining_count"] == 3
        # The highest-importance near-dup should survive
        contents = [e.content for e in m._entries]
        assert "The quick brown fox jumps over the lazy dog" in contents

    def test_resize_invalid_strategy_raises(self):
        m = Memory()
        m.add("test")
        with pytest.raises(ValueError, match="Unknown strategy"):
            m.resize(0, strategy="bogus")

    def test_resize_to_zero(self):
        m = Memory()
        self._populate(m, 5)
        result = m.resize(0, strategy="oldest")
        assert result["removed_count"] == 5
        assert result["remaining_count"] == 0
        assert len(m._entries) == 0

    def test_resize_returns_strategy_in_result(self):
        m = Memory()
        m.add("a")
        m.add("b")
        result = m.resize(1, strategy="least_important")
        assert result["strategy"] == "least_important"


# ── F48: search_similar ─────────────────────────────────────

class TestSearchSimilar:
    def test_search_similar_returns_most_similar(self):
        m = Memory()
        m.add(content="Python is a great programming language")
        m.add(content="Python is a great programming language for beginners")
        m.add(content="Java is also a programming language")
        m.add(content="The weather is nice today")
        results = m.search_similar(0)
        assert len(results) > 0
        # The closest should be the near-exact-match extension
        assert "beginners" in results[0].content

    def test_search_similar_excludes_self(self):
        m = Memory()
        m.add(content="unique entry one")
        m.add(content="unique entry two")
        results = m.search_similar(0)
        assert all("one" not in e.content for e in results)

    def test_search_similar_respects_limit(self):
        m = Memory()
        for i in range(10):
            m.add(content=f"similar text variation number {i}")
        results = m.search_similar(0, limit=3)
        assert len(results) == 3

    def test_search_similar_empty_memory(self):
        m = Memory()
        m.add(content="only entry")
        results = m.search_similar(0, limit=5)
        assert results == []

    def test_search_similar_invalid_index_raises(self):
        m = Memory()
        m.add(content="test")
        with pytest.raises(IndexError):
            m.search_similar(5)
        with pytest.raises(IndexError):
            m.search_similar(-1)

    def test_search_similar_exact_match(self):
        m = Memory()
        m.add(content="The cat sat on the mat")
        m.add(content="The cat sat on the mat")  # exact duplicate
        m.add(content="Dogs are great pets")
        results = m.search_similar(0)
        assert results[0].content == "The cat sat on the mat"

    def test_search_similar_two_entries(self):
        m = Memory()
        m.add(content="Hello world")
        m.add(content="Hello world")
        results = m.search_similar(0, limit=5)
        assert len(results) == 1
        assert results[0].content == "Hello world"

    def test_search_similar_ordering_descending(self):
        m = Memory()
        m.add(content="The brown dog barks loudly at night")  # index 0
        m.add(content="The brown dog barks loudly")           # very similar
        m.add(content="A brown dog exists")                    # somewhat similar
        m.add(content="Quantum physics equations")             # not similar
        results = m.search_similar(0, limit=3)
        assert len(results) == 3
        # Most similar first
        assert "barks loudly" in results[0].content
        assert "Quantum" in results[2].content
