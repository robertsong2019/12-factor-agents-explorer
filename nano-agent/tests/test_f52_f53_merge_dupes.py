"""Tests for F52 (merge_metadata) and F53 (find_duplicates)."""

import pytest
from nano_agent.memory import Memory


# ── F52: merge_metadata ─────────────────────────────────────────────

class TestMergeMetadata:
    def test_merge_adds_new_keys(self):
        m = Memory(max_entries=100)
        m.add("hello", metadata={"a": 1})
        assert m.merge_metadata(0, {"b": 2}) is True
        assert m._entries[0].metadata == {"a": 1, "b": 2}

    def test_merge_overwrites_existing_key(self):
        m = Memory(max_entries=100)
        m.add("hello", metadata={"a": 1, "b": 2})
        assert m.merge_metadata(0, {"a": 99}) is True
        assert m._entries[0].metadata == {"a": 99, "b": 2}

    def test_merge_empty_dict_no_change(self):
        m = Memory(max_entries=100)
        m.add("hello", metadata={"a": 1})
        assert m.merge_metadata(0, {}) is True
        assert m._entries[0].metadata == {"a": 1}

    def test_merge_invalid_index_returns_false(self):
        m = Memory(max_entries=100)
        m.add("hello")
        assert m.merge_metadata(5, {"x": 1}) is False
        assert m.merge_metadata(-1, {"x": 1}) is False

    def test_merge_on_entry_with_no_metadata(self):
        m = Memory(max_entries=100)
        m.add("hello")  # no metadata kwarg → defaults to {}
        assert m.merge_metadata(0, {"source": "test"}) is True
        assert m._entries[0].metadata == {"source": "test"}

    def test_merge_does_not_affect_other_entries(self):
        m = Memory(max_entries=100)
        m.add("first", metadata={"keep": True})
        m.add("second", metadata={"keep": False})
        m.merge_metadata(1, {"extra": "yes"})
        assert m._entries[0].metadata == {"keep": True}
        assert m._entries[1].metadata == {"keep": False, "extra": "yes"}

    def test_merge_nested_dict_update(self):
        m = Memory(max_entries=100)
        m.add("hello", metadata={"stats": {"views": 10}})
        m.merge_metadata(0, {"stats": {"clicks": 5}})
        # .update replaces top-level key, so stats becomes the new dict
        assert m._entries[0].metadata["stats"] == {"clicks": 5}

    def test_merge_persists_after_save(self, tmp_path):
        path = str(tmp_path / "mem.json")
        m = Memory(max_entries=100, persistence_path=path)
        m.add("hello", metadata={"a": 1})
        m.merge_metadata(0, {"b": 2})
        # Reload
        m2 = Memory(max_entries=100, persistence_path=path)
        assert m2._entries[0].metadata == {"a": 1, "b": 2}


# ── F53: find_duplicates ────────────────────────────────────────────

class TestFindDuplicates:
    def test_exact_duplicates_found(self):
        m = Memory(max_entries=100)
        m.add("The quick brown fox")
        m.add("The quick brown fox")
        dupes = m.find_duplicates(threshold=0.85)
        assert len(dupes) == 1
        assert dupes[0]["similarity"] == 1.0
        assert dupes[0]["i"] == 0
        assert dupes[0]["j"] == 1

    def test_no_duplicates_below_threshold(self):
        m = Memory(max_entries=100)
        m.add("The quick brown fox jumps over the lazy dog")
        m.add("Python programming is fun and rewarding")
        dupes = m.find_duplicates(threshold=0.85)
        assert len(dupes) == 0

    def test_near_duplicates_above_threshold(self):
        m = Memory(max_entries=100)
        m.add("The quick brown fox jumps over the lazy dog")
        m.add("The quick brown fox jumps over the lazy cat")
        dupes = m.find_duplicates(threshold=0.85)
        assert len(dupes) >= 1
        assert dupes[0]["similarity"] >= 0.85

    def test_empty_memory(self):
        m = Memory(max_entries=100)
        assert m.find_duplicates() == []

    def test_single_entry(self):
        m = Memory(max_entries=100)
        m.add("only one")
        assert m.find_duplicates() == []

    def test_sorted_by_descending_similarity(self):
        m = Memory(max_entries=100)
        m.add("hello world")           # 0
        m.add("hello world")           # 1 — exact dup of 0
        m.add("hello world foo")       # 2 — near dup of 0
        m.add("goodbye universe")      # 3 — no dup
        dupes = m.find_duplicates(threshold=0.5)
        assert len(dupes) >= 2
        # First pair should have highest similarity
        assert dupes[0]["similarity"] >= dupes[1]["similarity"]

    def test_case_insensitive_comparison(self):
        m = Memory(max_entries=100)
        m.add("Hello World")
        m.add("hello world")
        dupes = m.find_duplicates(threshold=0.85)
        assert len(dupes) == 1
        assert dupes[0]["similarity"] == 1.0

    def test_multiple_pairs(self):
        m = Memory(max_entries=100)
        m.add("aaa")
        m.add("aaa")
        m.add("bbb")
        m.add("bbb")
        dupes = m.find_duplicates(threshold=0.85)
        assert len(dupes) == 2
        # pairs: (0,1) and (2,3)

    def test_threshold_boundary(self):
        m = Memory(max_entries=100)
        m.add("abcdef")
        m.add("abcdeg")  # 5/6 chars match → ~0.833 similarity
        # At threshold 0.83 should find it
        dupes = m.find_duplicates(threshold=0.83)
        assert len(dupes) == 1
        # At threshold 0.90 should not
        dupes_strict = m.find_duplicates(threshold=0.90)
        assert len(dupes_strict) == 0

    def test_content_fields_populated(self):
        m = Memory(max_entries=100)
        m.add("hello world")
        m.add("hello world")
        dupes = m.find_duplicates()
        assert dupes[0]["content_i"] == "hello world"
        assert dupes[0]["content_j"] == "hello world"
