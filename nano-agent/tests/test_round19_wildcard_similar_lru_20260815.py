"""Round 19 (2026-08-15): F64 search_wildcard + F65 similar_to + F66 touch/lru."""

from datetime import datetime, timedelta

import pytest

from nano_agent.memory import Memory, MemoryEntry


def _mem(*contents, **kw):
    m = Memory(**kw)
    for c in contents:
        m.add(c)
    return m


# ---------------------------------------------------------------- F64

class TestSearchWildcard:
    def test_star_matches_all(self):
        m = _mem("alpha", "beta", "gamma")
        assert len(m.search_wildcard("*", limit=0)) == 3

    def test_single_char_wildcard(self):
        m = _mem("hello", "hallo", "hxllo", "hxllx")
        hits = m.search_wildcard("h?llo", limit=0)
        assert [e.content for e in hits] == ["hello", "hallo", "hxllo"]

    def test_case_insensitive(self):
        m = _mem("Deploy Failed", "deploy ok")
        assert [e.content for e in m.search_wildcard("DEPLOY*", limit=0)] == \
            ["Deploy Failed", "deploy ok"]

    def test_char_class(self):
        m = _mem("log 1 ok", "log 2 ok", "log x bad", "log 10 ok")
        hits = m.search_wildcard("log [0-9] ok", limit=0)
        assert [e.content for e in hits] == ["log 1 ok", "log 2 ok"]

    def test_prefix_star_vs_search_prefix(self):
        m = _mem("cat", "catamaran", "dog")
        # "cat*" matches cat AND catamaran — superset of search_prefix("cat")
        assert len(m.search_wildcard("cat*", limit=0)) == 2
        assert len(m.search_prefix("cat")) == 2

    def test_empty_pattern_returns_empty(self):
        m = _mem("anything")
        assert m.search_wildcard("") == []

    def test_no_match(self):
        m = _mem("alpha", "beta")
        assert m.search_wildcard("zzz*") == []

    def test_limit_returns_most_recent_in_chronological_order(self):
        m = _mem("e1 x", "e2 x", "e3 x", "e4 x", "e5 x")
        hits = m.search_wildcard("*x", limit=2)
        assert [e.content for e in hits] == ["e4 x", "e5 x"]

    def test_limit_zero_or_negative_unlimited(self):
        m = _mem("a1", "a2", "a3")
        assert len(m.search_wildcard("a?", limit=0)) == 3
        assert len(m.search_wildcard("a?", limit=-1)) == 3

    def test_literal_escaped_meaning_no_regex(self):
        # '.' is a literal in glob, not regex any-char
        m = _mem("a.b", "axb")
        assert [e.content for e in m.search_wildcard("a.b", limit=0)] == ["a.b"]

    def test_ignores_archived(self):
        m = _mem("arc me", "keep me")
        m.archive(0)
        assert [e.content for e in m.search_wildcard("*me", limit=0)] == ["keep me"]


# ---------------------------------------------------------------- F65

class TestSimilarTo:
    def test_most_similar_first(self):
        m = _mem("alpha beta gamma delta",
                 "alpha beta gamma delta epsilon",
                 "totally unrelated zebra text")
        hits = m.similar_to(0, threshold=0.0)
        assert hits[0].content == "alpha beta gamma delta epsilon"
        assert hits[-1].content == "totally unrelated zebra text"

    def test_excludes_anchor_object(self):
        m = _mem("duplicate text", "duplicate text", "other")
        anchor = m._entries[0]
        hits = m.similar_to(0, threshold=0.0, limit=0)
        # anchor excluded by identity; identical twin may legitimately match
        assert all(e is not anchor for e in hits)
        assert [e.content for e in hits] == ["duplicate text", "other"]

    def test_threshold_filters(self):
        m = _mem("meeting notes q3 revenue", "meeting notes q3 expenses",
                 "random chat about pizza toppings tonight")
        hits = m.similar_to(0, threshold=0.6, limit=0)
        contents = [e.content for e in hits]
        assert "meeting notes q3 expenses" in contents
        assert "random chat about pizza toppings tonight" not in contents

    def test_sorted_descending(self):
        m = _mem("abcdef", "abcdef", "abcxef", "zzzzzz")
        from difflib import SequenceMatcher
        hits = m.similar_to(0, threshold=0.0, limit=0)
        ratios = [SequenceMatcher(None, "abcdef", e.content).ratio()
                  for e in hits]
        assert ratios == sorted(ratios, reverse=True)

    def test_limit_truncates(self):
        m = _mem("one two", "one two x", "one two y", "one two z")
        assert len(m.similar_to(0, threshold=0.0, limit=2)) == 2

    def test_limit_zero_unlimited(self):
        m = _mem("same", "same", "same")
        assert len(m.similar_to(0, threshold=0.0, limit=0)) == 2

    def test_out_of_range_raises(self):
        m = _mem("only")
        with pytest.raises(ValueError):
            m.similar_to(1)
        with pytest.raises(ValueError):
            m.similar_to(-1)

    def test_empty_memory_raises(self):
        with pytest.raises(ValueError):
            Memory().similar_to(0)

    def test_case_insensitive_scoring(self):
        m = _mem("HELLO WORLD", "hello world", "bye")
        hits = m.similar_to(0, threshold=0.99, limit=0)
        assert [e.content for e in hits] == ["hello world"]


# ---------------------------------------------------------------- F66

class TestTouchLru:
    def test_touch_stamps_metadata(self):
        m = _mem("a", "b")
        before = datetime.now()
        assert m.touch(0) is True
        stamp = m._entries[0].metadata["_last_accessed"]
        assert datetime.fromisoformat(stamp) >= before

    def test_touch_out_of_range_false(self):
        m = _mem("a")
        assert m.touch(5) is False
        assert m.touch(-1) is False

    def test_lru_never_touched_orders_by_age(self):
        m = Memory()
        base = datetime(2026, 8, 15, 12, 0, 0)
        for i in range(3):
            e = MemoryEntry(content=f"e{i}", timestamp=base + timedelta(hours=i))
            m._entries.append(e)
        assert [e.content for e in m.lru(2)] == ["e0", "e1"]

    def test_touch_refreshes_ranking(self):
        m = Memory()
        base = datetime(2026, 8, 15, 12, 0, 0)
        for i in range(3):
            e = MemoryEntry(content=f"e{i}", timestamp=base + timedelta(hours=i))
            m._entries.append(e)
        fresh = (base + timedelta(days=1)).isoformat()
        m._entries[0].metadata["_last_accessed"] = fresh  # oldest, but touched
        assert [e.content for e in m.lru(2)] == ["e1", "e2"]

    def test_lru_returns_all_when_n_exceeds(self):
        m = _mem("a", "b")
        assert len(m.lru(10)) == 2

    def test_lru_zero_or_negative_empty(self):
        m = _mem("a", "b")
        assert m.lru(0) == []
        assert m.lru(-3) == []

    def test_lru_empty_memory(self):
        assert Memory().lru(5) == []

    def test_lru_eviction_pipeline(self):
        m = _mem("stale", "mid", "fresh")
        m.touch(2)  # keep 'fresh' alive
        stalest = m.lru(1)[0]
        assert stalest.content == "stale"
        assert m.remove(0) is True
        assert len(m._entries) == 2

    def test_touch_survives_persistence(self, tmp_path):
        path = str(tmp_path / "mem.json")
        m = Memory(persistence_path=path)
        m.add("persist me")
        m.add("other")
        m.touch(0)
        m2 = Memory(persistence_path=path)
        assert "_last_accessed" in m2._entries[0].metadata

    def test_touch_does_not_pollute_content(self):
        m = _mem("clean text")
        m.touch(0)
        assert m._entries[0].content == "clean text"
        assert len(m.search("clean")) == 1
