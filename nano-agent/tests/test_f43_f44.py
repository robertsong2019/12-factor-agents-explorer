"""
Tests for F43 (import_jsonl) and F44 (union)
"""

import json
import sys
import os
import pytest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry


# ========== F43: import_jsonl ==========

class TestImportJsonl:
    def test_empty_string(self):
        m = Memory()
        assert m.import_jsonl("") == 0
        assert m.count() == 0

    def test_single_line(self):
        m = Memory()
        entry_dict = {
            "content": "hello world",
            "timestamp": datetime.now().isoformat(),
            "metadata": {},
            "importance": 0.7,
        }
        m.import_jsonl(json.dumps(entry_dict, ensure_ascii=False))
        assert m.count() == 1
        assert m.get_all()[0].content == "hello world"
        assert m.get_all()[0].importance == 0.7

    def test_multiple_lines(self):
        m = Memory()
        data = "\n".join(
            json.dumps({"content": f"entry {i}", "timestamp": datetime.now().isoformat(),
                        "metadata": {}, "importance": 0.5}, ensure_ascii=False)
            for i in range(5)
        )
        count = m.import_jsonl(data)
        assert count == 5
        assert m.count() == 5

    def test_with_tags(self):
        m = Memory()
        data = json.dumps({
            "content": "tagged entry",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"src": "test"},
            "tags": ["a", "b"],
            "importance": 0.9,
        }, ensure_ascii=False)
        m.import_jsonl(data)
        e = m.get_all()[0]
        assert set(e.tags) == {"a", "b"}
        assert e.metadata == {"src": "test"}
        assert e.importance == 0.9

    def test_merge_mode(self):
        m = Memory()
        m.add("existing")
        data = json.dumps({"content": "new", "timestamp": datetime.now().isoformat(),
                           "metadata": {}, "importance": 0.5}, ensure_ascii=False)
        count = m.import_jsonl(data, merge=True)
        assert count == 1
        assert m.count() == 2

    def test_replace_mode(self):
        m = Memory()
        m.add("old entry")
        data = json.dumps({"content": "new entry", "timestamp": datetime.now().isoformat(),
                           "metadata": {}, "importance": 0.5}, ensure_ascii=False)
        count = m.import_jsonl(data, merge=False)
        assert count == 1
        assert m.count() == 1
        assert m.get_all()[0].content == "new entry"

    def test_invalid_json_line_skipped(self):
        m = Memory()
        data = '{"content": "good", "timestamp": "' + datetime.now().isoformat() + '", "metadata": {}, "importance": 0.5}\nnot valid json\n{"content": "also good", "timestamp": "' + datetime.now().isoformat() + '", "metadata": {}, "importance": 0.5}'
        count = m.import_jsonl(data)
        assert count == 2
        assert m.count() == 2

    def test_missing_content_skipped(self):
        m = Memory()
        data = json.dumps({"timestamp": datetime.now().isoformat(), "metadata": {}}, ensure_ascii=False)
        count = m.import_jsonl(data)
        assert count == 0
        assert m.count() == 0

    def test_default_importance(self):
        m = Memory()
        data = json.dumps({"content": "no importance field",
                           "timestamp": datetime.now().isoformat(), "metadata": {}},
                          ensure_ascii=False)
        m.import_jsonl(data)
        assert m.get_all()[0].importance == 0.5

    def test_round_trip_with_export(self):
        """export_jsonl -> import_jsonl should preserve data."""
        m1 = Memory()
        m1.add("first", tags=["a"], importance=0.8)
        m1.add("second", tags=["b"], importance=0.3)
        m1.add("third", importance=0.5)

        exported = m1.export_jsonl()
        m2 = Memory()
        count = m2.import_jsonl(exported)
        assert count == 3
        assert m2.count() == 3
        assert m2.get_all()[0].content == "first"
        assert m2.get_all()[0].importance == 0.8
        assert m2.get_all()[2].content == "third"

    def test_max_entries_limit(self):
        m = Memory(max_entries=3)
        data = "\n".join(
            json.dumps({"content": f"e{i}", "timestamp": datetime.now().isoformat(),
                        "metadata": {}, "importance": 0.5}, ensure_ascii=False)
            for i in range(5)
        )
        m.import_jsonl(data)
        assert m.count() == 3  # capped

    def test_empty_lines_ignored(self):
        m = Memory()
        data = '\n{"content": "only", "timestamp": "' + datetime.now().isoformat() + '", "metadata": {}, "importance": 0.5}\n\n'
        count = m.import_jsonl(data)
        assert count == 1
        assert m.count() == 1

    def test_non_string_input(self):
        m = Memory()
        assert m.import_jsonl(None) == 0
        assert m.import_jsonl(123) == 0


# ========== F44: union ==========

class TestUnion:
    def test_empty_both(self):
        m1 = Memory()
        m2 = Memory()
        result = m1.union(m2)
        assert result.count() == 0

    def test_empty_other(self):
        m1 = Memory()
        m1.add("a")
        m2 = Memory()
        result = m1.union(m2)
        assert result.count() == 1
        assert result.get_all()[0].content == "a"

    def test_empty_self(self):
        m1 = Memory()
        m2 = Memory()
        m2.add("b")
        result = m1.union(m2)
        assert result.count() == 1
        assert result.get_all()[0].content == "b"

    def test_no_overlap(self):
        m1 = Memory()
        m1.add("apple")
        m2 = Memory()
        m2.add("banana")
        result = m1.union(m2)
        assert result.count() == 2
        contents = {e.content for e in result.get_all()}
        assert contents == {"apple", "banana"}

    def test_with_overlap(self):
        m1 = Memory()
        m1.add("shared")
        m1.add("only1")
        m2 = Memory()
        m2.add("shared")
        m2.add("only2")
        result = m1.union(m2)
        assert result.count() == 3  # shared dedup
        contents = {e.content for e in result.get_all()}
        assert contents == {"shared", "only1", "only2"}

    def test_self_union(self):
        m1 = Memory()
        m1.add("a")
        m1.add("b")
        result = m1.union(m1)
        assert result.count() == 2

    def test_preserves_self_metadata_on_conflict(self):
        m1 = Memory()
        m1.add("same content", metadata={"src": "m1"}, importance=0.9)
        m2 = Memory()
        m2.add("same content", metadata={"src": "m2"}, importance=0.1)
        result = m1.union(m2)
        assert result.count() == 1
        entry = result.get_all()[0]
        assert entry.metadata == {"src": "m1"}
        assert entry.importance == 0.9

    def test_returns_new_instance(self):
        m1 = Memory()
        m1.add("a")
        m2 = Memory()
        m2.add("b")
        result = m1.union(m2)
        assert result is not m1
        assert result is not m2
        # originals unchanged
        assert m1.count() == 1
        assert m2.count() == 1

    def test_respects_max_entries(self):
        m1 = Memory(max_entries=3)
        for i in range(3):
            m1.add(f"self{i}")
        m2 = Memory()
        for i in range(3):
            m2.add(f"other{i}")
        result = m1.union(m2)
        assert result.count() <= 3

    def test_preserves_tags(self):
        m1 = Memory()
        m1.add("tagged1", tags=["x", "y"])
        m2 = Memory()
        m2.add("tagged2", tags=["z"])
        result = m1.union(m2)
        entries = result.get_all()
        tag_sets = {e.content: set(e.tags) for e in entries}
        assert tag_sets["tagged1"] == {"x", "y"}
        assert tag_sets["tagged2"] == {"z"}

    def test_three_way_via_chaining(self):
        m1 = Memory()
        m1.add("a")
        m2 = Memory()
        m2.add("b")
        m3 = Memory()
        m3.add("c")
        result = m1.union(m2).union(m3)
        assert result.count() == 3
