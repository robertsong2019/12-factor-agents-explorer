"""
F22-F23 测试: Memory.snapshot()/restore() + Memory.search_regex()
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nano_agent.memory import Memory, MemoryEntry


# ─── F22: snapshot / restore ───

class TestSnapshotRestore:
    def test_snapshot_returns_list_of_dicts(self):
        m = Memory()
        m.add("hello", tags=["greeting"])
        m.add("world", importance=0.9)
        snap = m.snapshot()
        assert isinstance(snap, list)
        assert len(snap) == 2
        assert all(isinstance(item, dict) for item in snap)

    def test_snapshot_is_deep_copy(self):
        m = Memory()
        m.add("original")
        snap = m.snapshot()
        snap[0]["content"] = "mutated"
        # Original memory should be unaffected
        assert m.get_all()[0].content == "original"

    def test_snapshot_preserves_all_fields(self):
        m = Memory()
        m.add("test content", metadata={"key": "val"}, tags=["a", "b"], importance=0.8)
        snap = m.snapshot()
        assert snap[0]["content"] == "test content"
        assert snap[0]["metadata"] == {"key": "val"}
        assert snap[0]["tags"] == ["a", "b"]
        assert snap[0]["importance"] == 0.8
        assert "timestamp" in snap[0]

    def test_snapshot_empty_memory(self):
        m = Memory()
        snap = m.snapshot()
        assert snap == []

    def test_restore_replaces_all_entries(self):
        m = Memory()
        m.add("old1")
        m.add("old2")
        m.add("old3")

        snap = m.snapshot()
        m.clear()
        assert m.count() == 0

        restored = m.restore(snap)
        assert restored == 3
        assert m.count() == 3
        assert m.get_all()[0].content == "old1"

    def test_restore_with_empty_snapshot(self):
        m = Memory()
        m.add("data")
        result = m.restore([])
        assert result == 0
        assert m.count() == 0

    def test_restore_invalid_data_returns_zero(self):
        m = Memory()
        result = m.restore("not a list")  # type: ignore
        assert result == 0

    def test_restore_skips_corrupt_entries(self):
        m = Memory()
        snapshot = [
            {"content": "good"},
            {"missing_content": "bad"},  # no "content" key
            {"content": "also good"},
        ]
        result = m.restore(snapshot)
        assert result == 2

    def test_snapshot_restore_roundtrip_preserves_state(self):
        m = Memory(persistence_path=None)
        m.add("entry1", tags=["x"], importance=0.7)
        m.add("entry2", tags=["y"], importance=0.3)

        snap = m.snapshot()
        m.clear()
        m.restore(snap)

        all_entries = m.get_all()
        assert len(all_entries) == 2
        assert all_entries[0].content == "entry1"
        assert all_entries[0].tags == ["x"]
        assert all_entries[0].importance == 0.7

    def test_snapshot_after_modifications(self):
        m = Memory()
        m.add("a")
        m.add("b")
        snap1 = m.snapshot()
        m.add("c")
        snap2 = m.snapshot()

        assert len(snap1) == 2
        assert len(snap2) == 3

        # Restore to snap1 state (undo adding "c")
        m.restore(snap1)
        assert m.count() == 2
        assert m.get_all()[-1].content == "b"

    def test_restore_preserves_importance_and_tags(self):
        m = Memory()
        m.add("important", tags=["critical"], importance=1.0)
        m.add("trivial", tags=["misc"], importance=0.1)

        snap = m.snapshot()
        m.clear()
        m.restore(snap)

        entries = m.get_all()
        assert entries[0].importance == 1.0
        assert entries[0].tags == ["critical"]
        assert entries[1].importance == 0.1

    def test_snapshot_is_safe_to_serialize(self):
        import json
        m = Memory()
        m.add("test", tags=["a"], importance=0.5)
        snap = m.snapshot()
        # Should be JSON serializable
        json_str = json.dumps(snap)
        restored = json.loads(json_str)
        assert restored[0]["content"] == "test"


# ─── F23: search_regex ───

class TestSearchRegex:
    def test_basic_pattern_match(self):
        m = Memory()
        m.add("Hello World 123")
        m.add("Goodbye World 456")
        results = m.search_regex(r"Hello")
        assert len(results) == 1
        assert results[0].content == "Hello World 123"

    def test_case_insensitive_by_default(self):
        m = Memory()
        m.add("Python is great")
        m.add("JAVA is also fine")
        results = m.search_regex(r"python")
        assert len(results) == 1
        assert results[0].content == "Python is great"

    def test_digit_pattern(self):
        m = Memory()
        m.add("Order #12345")
        m.add("No number here")
        m.add("Ref: 999")
        results = m.search_regex(r"\d+")
        assert len(results) == 2

    def test_alternation_pattern(self):
        m = Memory()
        m.add("cat")
        m.add("dog")
        m.add("bird")
        m.add("fish")
        results = m.search_regex(r"cat|dog")
        assert len(results) == 2

    def test_anchored_pattern(self):
        m = Memory()
        m.add("start here")
        m.add("here start")
        m.add("starting now")
        results = m.search_regex(r"^start")
        assert len(results) == 2  # "start here" and "starting now"

    def test_email_pattern(self):
        m = Memory()
        m.add("Contact: alice@example.com")
        m.add("No email here")
        m.add("bob@test.org is another")
        results = m.search_regex(r"[\w.]+@[\w.]+")
        assert len(results) == 2

    def test_limit_parameter(self):
        m = Memory()
        for i in range(10):
            m.add(f"item_{i}")
        results = m.search_regex(r"item_\d", limit=3)
        assert len(results) == 3

    def test_limit_zero_returns_all(self):
        m = Memory()
        m.add("test1")
        m.add("test2")
        m.add("test3")
        results = m.search_regex(r"test", limit=0)
        assert len(results) == 3

    def test_no_matches_returns_empty(self):
        m = Memory()
        m.add("hello world")
        results = m.search_regex(r"xyz\d+")
        assert results == []

    def test_empty_memory_returns_empty(self):
        m = Memory()
        results = m.search_regex(r".*")
        assert results == []

    def test_empty_pattern_matches_all(self):
        m = Memory()
        m.add("data1")
        m.add("data2")
        # Empty pattern is valid in Python regex, matches everything
        results = m.search_regex("")
        assert len(results) == 2

    def test_invalid_regex_raises(self):
        m = Memory()
        m.add("data")
        with pytest.raises(Exception):
            m.search_regex("[unclosed")

    def test_results_ordered_by_time(self):
        m = Memory()
        m.add("first hit")
        m.add("no connexion")
        m.add("second hit")
        results = m.search_regex(r"hit")
        assert len(results) == 2
        # Should be in insertion order (oldest first by default)
        assert results[0].content == "first hit"
        assert results[1].content == "second hit"

    def test_complex_pattern(self):
        m = Memory()
        m.add("2026-07-19")
        m.add("19/07/2026")
        m.add("not a date")
        m.add("2026-12-25")
        # ISO date pattern
        results = m.search_regex(r"\d{4}-\d{2}-\d{2}")
        assert len(results) == 2

    def test_unicode_pattern(self):
        m = Memory()
        m.add("你好世界")
        m.add("Hello World")
        results = m.search_regex(r"你好")
        assert len(results) == 1
        assert results[0].content == "你好世界"

    def test_whitespace_pattern(self):
        m = Memory()
        m.add("  leading spaces")
        m.add("normal")
        m.add("trailing  ")
        results = m.search_regex(r"^\s+")
        assert len(results) == 1
        assert results[0].content == "  leading spaces"
