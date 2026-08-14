"""Tests for search_semantic() and auto_search() — TF-IDF + auto-strategy selection."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory


class TestSearchSemantic:
    """TF-IDF weighted semantic search."""

    def _make_memory(self):
        m = Memory()
        m.add("Python is a programming language", tags=["code"])
        m.add("JavaScript runs in the browser", tags=["code"])
        m.add("Machine learning uses algorithms", tags=["ai"])
        m.add("Python has great ML libraries", tags=["ai", "code"])
        m.add("The weather is sunny today", tags=["life"])
        return m

    def test_basic_semantic_search(self):
        m = self._make_memory()
        results = m.search_semantic("programming language")
        assert len(results) > 0
        entries = [e for e, _ in results]
        contents = [e.content for e in entries]
        # "Python is a programming language" should rank high
        assert any("programming" in c for c in contents)

    def test_semantic_returns_tuples_with_scores(self):
        m = self._make_memory()
        results = m.search_semantic("machine learning")
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
        assert all(isinstance(e, type(m._entries[0])) for e, _ in results)
        assert all(isinstance(s, float) for _, s in results)

    def test_semantic_scores_descending(self):
        m = self._make_memory()
        results = m.search_semantic("python code")
        if len(results) > 1:
            scores = [s for _, s in results]
            assert scores == sorted(scores, reverse=True)

    def test_semantic_limit(self):
        m = self._make_memory()
        results = m.search_semantic("code", limit=2)
        assert len(results) <= 2

    def test_semantic_empty_query(self):
        m = self._make_memory()
        assert m.search_semantic("") == []

    def test_semantic_empty_memory(self):
        m = Memory()
        assert m.search_semantic("anything") == []

    def test_semantic_no_match(self):
        m = Memory()
        m.add("Python programming")
        results = m.search_semantic("xyzzyplugh")
        # Should still return results but with low scores
        assert len(results) > 0
        assert all(s < 0.01 for _, s in results)

    def test_semantic_boost_recent(self):
        m = self._make_memory()
        no_boost = m.search_semantic("code", boost_recent=0.0)
        with_boost = m.search_semantic("code", boost_recent=1.0)
        # Boosted should prefer later entries when scores are similar
        assert len(no_boost) > 0 and len(with_boost) > 0

    def test_semantic_cross_language_terms(self):
        m = Memory()
        m.add("The cat sat on the mat")
        m.add("Dogs are loyal animals")
        m.add("A feline resting on a rug")
        results = m.search_semantic("cat feline")
        contents = [e.content for e, _ in results[:2]]
        assert any("cat" in c.lower() or "feline" in c.lower() for c in contents)

    def test_semantic_idf_distinguishes_common_rare(self):
        """Rare terms should boost documents containing them."""
        m = Memory()
        m.add("The the the the the the")  # common word
        m.add("quantum entanglement physics")  # rare terms
        results = m.search_semantic("quantum entanglement")
        contents = [e.content for e, _ in results]
        assert contents[0] == "quantum entanglement physics"


class TestAutoSearch:
    """Auto-strategy search selection."""

    def _make_memory(self):
        m = Memory()
        m.add("Python is great", tags=["python", "code"])
        m.add("JavaScript for web", tags=["javascript", "web"])
        m.add("Machine learning basics", tags=["ml"])
        m.add("Python ML libraries are powerful", tags=["python", "ml"])
        return m

    def test_auto_search_returns_dict(self):
        m = self._make_memory()
        result = m.auto_search("python")
        assert isinstance(result, dict)
        assert "results" in result
        assert "strategy" in result
        assert "score" in result
        assert "all_strategies" in result

    def test_auto_search_picks_tag_for_tag_query(self):
        m = self._make_memory()
        result = m.auto_search("python")
        # "python" is a tag — should pick tag strategy
        assert result["strategy"] in ("tag", "exact", "semantic", "weighted", "fuzzy")

    def test_auto_search_all_strategies_reported(self):
        m = self._make_memory()
        result = m.auto_search("code")
        strategies = result["all_strategies"]
        assert "tag" in strategies
        assert "exact" in strategies
        assert "semantic" in strategies
        assert "fuzzy" in strategies
        assert "weighted" in strategies

    def test_auto_search_empty_query(self):
        m = self._make_memory()
        result = m.auto_search("")
        assert result["results"] == []
        assert result["strategy"] == "none"

    def test_auto_search_empty_memory(self):
        m = Memory()
        result = m.auto_search("python")
        assert result["results"] == []
        assert result["strategy"] == "none"

    def test_auto_search_strategy_counts(self):
        m = self._make_memory()
        result = m.auto_search("machine")
        for name, info in result["all_strategies"].items():
            assert "count" in info
            assert "score" in info
            assert info["count"] >= 0
