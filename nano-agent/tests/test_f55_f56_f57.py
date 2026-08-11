"""Tests for F55 batch_add, F56 search_snippet, F57 health_check."""
import pytest
from nano_agent.memory import Memory, MemoryEntry


# ═══════════════════════════════════════════════════════════════
# F55: batch_add
# ═══════════════════════════════════════════════════════════════

class TestBatchAdd:
    def test_basic_batch_add(self):
        m = Memory(max_entries=100)
        entries = [
            {"content": "first"},
            {"content": "second"},
            {"content": "third"},
        ]
        indices = m.batch_add(entries)
        assert len(indices) == 3
        assert m.count() == 3
        assert m._entries[0].content == "first"
        assert m._entries[1].content == "second"
        assert m._entries[2].content == "third"

    def test_batch_add_returns_correct_indices(self):
        m = Memory(max_entries=100)
        m.add("existing")  # index 0
        indices = m.batch_add([{"content": "a"}, {"content": "b"}])
        assert indices == [1, 2]

    def test_batch_add_empty_list(self):
        m = Memory()
        indices = m.batch_add([])
        assert indices == []
        assert m.count() == 0

    def test_batch_add_with_metadata_tags_importance(self):
        m = Memory()
        entries = [
            {"content": "task A", "tags": ["work"], "importance": 0.9, "metadata": {"id": 1}},
            {"content": "task B", "tags": ["personal"], "importance": 0.3},
        ]
        indices = m.batch_add(entries)
        assert len(indices) == 2
        assert m._entries[0].tags == ["work"]
        assert m._entries[0].importance == 0.9
        assert m._entries[0].metadata == {"id": 1}
        assert m._entries[1].importance == 0.3

    def test_batch_add_eviction_shifts_indices(self):
        m = Memory(max_entries=3)
        m.add("old1")  # index 0
        m.add("old2")  # index 1
        # Now add 3 more, total will be 5, evicted 2
        indices = m.batch_add([
            {"content": "new1"},
            {"content": "new2"},
            {"content": "new3"},
        ])
        assert m.count() == 3  # capped
        # After eviction, entries are [new1, new2, new3] at indices [0, 1, 2]
        assert m._entries[0].content == "new1"
        # Original indices were [2, 3, 4], shift by -2 → [0, 1, 2]
        assert indices == [0, 1, 2]

    def test_batch_add_empty_content_skipped(self):
        m = Memory()
        entries = [
            {"content": "valid"},
            {"content": ""},  # empty, skipped
            {"content": "also valid"},
        ]
        indices = m.batch_add(entries)
        assert indices[0] == 0
        assert indices[1] == -1  # marked as skipped
        assert indices[2] == 1  # second valid entry gets index 1
        assert m.count() == 2

    def test_batch_add_missing_content_key(self):
        m = Memory()
        entries = [
            {"tags": ["nope"]},  # no content key
            {"content": "yes"},
        ]
        indices = m.batch_add(entries)
        assert indices[0] == -1
        assert m.count() == 1

    def test_batch_add_default_importance(self):
        m = Memory()
        m.batch_add([{"content": "test"}])
        assert m._entries[0].importance == 0.5

    def test_batch_add_preserves_order(self):
        m = Memory()
        items = [{"content": f"item-{i}"} for i in range(10)]
        indices = m.batch_add(items)
        assert len(indices) == 10
        for i, entry in enumerate(m._entries):
            assert entry.content == f"item-{i}"

    def test_batch_add_single_entry(self):
        m = Memory()
        indices = m.batch_add([{"content": "only one"}])
        assert indices == [0]
        assert m.count() == 1


# ═══════════════════════════════════════════════════════════════
# F56: search_snippet
# ═══════════════════════════════════════════════════════════════

class TestSearchSnippet:
    def test_basic_snippet(self):
        m = Memory()
        m.add("The quick brown fox jumps over the lazy dog")
        results = m.search_snippet("fox")
        assert len(results) == 1
        assert "[[HIGHLIGHT]]fox[[/HIGHLIGHT]]" in results[0]["snippet"]

    def test_snippet_with_context(self):
        m = Memory()
        m.add("AAAAABBBBBfoxCCCCCDDDDD")
        results = m.search_snippet("fox", context_chars=5)
        assert len(results) == 1
        snippet = results[0]["snippet"]
        assert "BBBBB" in snippet  # before context
        assert "CCCCC" in snippet  # after context
        assert "[[HIGHLIGHT]]fox[[/HIGHLIGHT]]" in snippet

    def test_snippet_truncation_with_ellipsis(self):
        m = Memory()
        long_text = "x" * 100 + "target" + "y" * 100
        m.add(long_text)
        results = m.search_snippet("target", context_chars=10)
        assert results[0]["snippet"].startswith("...")
        assert results[0]["snippet"].endswith("...")

    def test_snippet_no_truncation_at_boundaries(self):
        m = Memory()
        m.add("target at start")
        results = m.search_snippet("target", context_chars=50)
        assert not results[0]["snippet"].startswith("...")
        # end might or might not have ... depending on content length

    def test_snippet_case_insensitive(self):
        m = Memory()
        m.add("The FOX jumped")
        results = m.search_snippet("fox")
        assert len(results) == 1
        assert "FOX" in results[0]["snippet"]

    def test_snippet_match_pos(self):
        m = Memory()
        m.add("hello world")
        results = m.search_snippet("world")
        assert results[0]["match_pos"] == 6

    def test_snippet_index_field(self):
        m = Memory()
        m.add("first entry")
        m.add("second entry with target")
        results = m.search_snippet("target")
        assert len(results) == 1
        assert results[0]["index"] == 1

    def test_snippet_limit(self):
        m = Memory()
        for i in range(10):
            m.add(f"entry {i} has target word")
        results = m.search_snippet("target", limit=3)
        assert len(results) == 3

    def test_snippet_no_match(self):
        m = Memory()
        m.add("nothing relevant here")
        results = m.search_snippet("xyz123")
        assert len(results) == 0

    def test_snippet_returns_entry_reference(self):
        m = Memory()
        m.add("find this text")
        results = m.search_snippet("find")
        assert isinstance(results[0]["entry"], MemoryEntry)
        assert results[0]["entry"].content == "find this text"

    def test_snippet_multiple_matches_returns_first(self):
        m = Memory()
        m.add("cat and cat and cat")
        results = m.search_snippet("cat")
        assert len(results) == 1
        # match_pos should be the first occurrence
        assert results[0]["match_pos"] == 0

    def test_snippet_default_context(self):
        m = Memory()
        m.add("a" * 100 + "keyword" + "b" * 100)
        results = m.search_snippet("keyword")  # default context_chars=50
        snippet = results[0]["snippet"]
        # Should have 50 chars before + highlight + 50 chars after
        # Plus ellipsis on both sides
        assert snippet.startswith("...")


# ═══════════════════════════════════════════════════════════════
# F57: health_check
# ═══════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_healthy_memory(self):
        m = Memory(max_entries=100)
        for i in range(10):
            m.add(f"entry {i}", tags=["t1"], importance=0.5)
        report = m.health_check()
        assert report["status"] == "healthy"
        assert len(report["issues"]) == 0
        assert report["stats"]["total"] == 10

    def test_capacity_warning(self):
        m = Memory(max_entries=10)
        for i in range(9):
            m.add(f"entry {i}", tags=["t"], importance=0.5)
        report = m.health_check()
        assert report["status"] == "warning"
        assert any("80%" in i or "90%" in i for i in report["issues"])

    def test_critical_capacity(self):
        m = Memory(max_entries=10)
        for i in range(10):
            m.add(f"entry {i}", tags=["t"], importance=0.5)
        report = m.health_check()
        assert report["status"] in ("warning", "critical")
        assert any("100%" in i or "capacity" in i.lower() for i in report["issues"])

    def test_duplicate_warning(self):
        m = Memory(max_entries=100)
        m.add("duplicate content here", tags=["t"])
        m.add("duplicate content here", tags=["t"])
        m.add("duplicate content here", tags=["t"])
        report = m.health_check()
        assert any("duplicate" in i.lower() for i in report["issues"])

    def test_low_importance_warning(self):
        m = Memory(max_entries=100)
        for i in range(15):
            m.add(f"low importance entry {i}", importance=0.05)
        report = m.health_check()
        assert any("importance" in i.lower() for i in report["issues"])

    def test_untagged_warning(self):
        m = Memory(max_entries=100)
        for i in range(10):
            m.add(f"no tags entry {i}", importance=0.5)
        report = m.health_check()
        assert any("tag" in i.lower() for i in report["issues"])

    def test_stats_fields(self):
        m = Memory(max_entries=50)
        m.add("tagged", tags=["a"], importance=0.7)
        m.add("untagged", importance=0.3)
        report = m.health_check()
        stats = report["stats"]
        assert stats["total"] == 2
        assert stats["tagged"] == 1
        assert stats["untagged"] == 1
        assert "avg_importance" in stats
        assert "oldest_days" in stats
        assert "capacity_ratio" in stats

    def test_recommendations_present_when_issues(self):
        m = Memory(max_entries=10)
        for i in range(10):
            m.add(f"entry {i}", importance=0.05)
        report = m.health_check()
        assert len(report["issues"]) > 0
        assert len(report["recommendations"]) > 0

    def test_empty_memory_healthy(self):
        m = Memory()
        report = m.health_check()
        assert report["status"] == "healthy"
        assert report["stats"]["total"] == 0
        assert report["stats"]["avg_importance"] == 0.0

    def test_archived_count_in_stats(self):
        m = Memory(max_entries=100)
        m.add("entry 0", tags=["t"])
        m.add("entry 1", tags=["t"])
        m.archive(0)
        report = m.health_check()
        # archived is tracked in _archived list
        assert report["stats"]["archived"] == 1

    def test_status_values(self):
        """Status must be one of the three valid values."""
        m = Memory()
        report = m.health_check()
        assert report["status"] in ("healthy", "warning", "critical")

    def test_no_side_effects(self):
        """health_check should not modify memory."""
        m = Memory(max_entries=100)
        for i in range(10):
            m.add(f"entry {i}", tags=["t"], importance=0.5)
        before_count = m.count()
        m.health_check()
        assert m.count() == before_count
