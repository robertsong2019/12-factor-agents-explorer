"""
Tests for nano-agent Memory: export/import, stats, tag management
F1-F4 feature coverage
"""

import json
import pytest
import tempfile
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry


class TestExportImport:
    """F1 + F2: export_json / import_json"""

    def test_export_empty(self):
        m = Memory()
        data = json.loads(m.export_json())
        assert data == []

    def test_export_with_entries(self):
        m = Memory()
        m.add("hello", tags=["greeting"])
        m.add("world", tags=["greeting", "place"])
        data = json.loads(m.export_json())
        assert len(data) == 2
        assert data[0]["content"] == "hello"
        assert "greeting" in data[0]["tags"]

    def test_import_to_empty(self):
        m = Memory()
        original = '[{"content": "test", "timestamp": "2026-01-01T00:00:00", "metadata": {}, "tags": ["a"]}]'
        count = m.import_json(original)
        assert count == 1
        assert m.count() == 1
        assert m.get_all()[0].content == "test"

    def test_import_merge_mode(self):
        m = Memory()
        m.add("existing")
        data = '[{"content": "imported", "timestamp": "2026-01-01T00:00:00", "metadata": {}, "tags": []}]'
        count = m.import_json(data, merge=True)
        assert count == 1
        assert m.count() == 2

    def test_import_replace_mode(self):
        m = Memory()
        m.add("old1")
        m.add("old2")
        data = '[{"content": "new", "timestamp": "2026-01-01T00:00:00", "metadata": {}, "tags": []}]'
        count = m.import_json(data, merge=False)
        assert count == 1
        assert m.count() == 1
        assert m.get_all()[0].content == "new"

    def test_import_invalid_json(self):
        m = Memory()
        count = m.import_json("not json")
        assert count == 0
        assert m.count() == 0

    def test_import_non_list_json(self):
        m = Memory()
        count = m.import_json('{"key": "value"}')
        assert count == 0

    def test_import_missing_content_field(self):
        m = Memory()
        data = '[{"timestamp": "2026-01-01T00:00:00", "metadata": {}}]'
        count = m.import_json(data)
        assert count == 0

    def test_import_bad_timestamp_skipped(self):
        m = Memory()
        data = '[{"content": "ok", "timestamp": "bad-date", "metadata": {}, "tags": []}]'
        count = m.import_json(data)
        assert count == 0

    def test_export_import_roundtrip(self):
        m1 = Memory()
        m1.add("entry1", metadata={"k": "v"}, tags=["tag1"])
        m1.add("entry2", metadata={"k2": "v2"}, tags=["tag2", "tag3"])
        exported = m1.export_json()

        m2 = Memory()
        count = m2.import_json(exported, merge=False)
        assert count == 2
        entries = m2.get_all()
        assert entries[0].content == "entry1"
        assert entries[1].content == "entry2"
        assert entries[0].metadata == {"k": "v"}
        assert "tag3" in entries[1].tags

    def test_import_respects_max_entries(self):
        m = Memory(max_entries=3)
        items = [{"content": f"e{i}", "timestamp": "2026-01-01T00:00:00", "metadata": {}, "tags": []} for i in range(10)]
        count = m.import_json(json.dumps(items))
        assert count == 10  # all parsed
        assert m.count() == 3  # but only 3 kept


class TestStats:
    """F3: Memory.stats()"""

    def test_stats_empty(self):
        m = Memory()
        s = m.stats()
        assert s["total"] == 0
        assert s["tags"] == {}
        assert s["date_range"] is None

    def test_stats_total(self):
        m = Memory()
        m.add("a")
        m.add("b")
        m.add("c")
        assert m.stats()["total"] == 3

    def test_stats_tag_counts(self):
        m = Memory()
        m.add("x", tags=["python", "web"])
        m.add("y", tags=["python"])
        m.add("z", tags=["rust", "web"])
        s = m.stats()
        assert s["tags"]["python"] == 2
        assert s["tags"]["web"] == 2
        assert s["tags"]["rust"] == 1

    def test_stats_date_range(self):
        m = Memory()
        # Manually set timestamps
        old = MemoryEntry(content="old", timestamp=datetime(2020, 1, 1))
        new = MemoryEntry(content="new", timestamp=datetime(2026, 6, 24))
        m._entries = [old, new]
        s = m.stats()
        assert s["date_range"]["oldest"] == "2020-01-01T00:00:00"
        assert s["date_range"]["newest"] == "2026-06-24T00:00:00"

    def test_stats_no_tags(self):
        m = Memory()
        m.add("no tags here")
        s = m.stats()
        assert s["tags"] == {}


class TestTagManagement:
    """F4: add_tag / remove_tag by index"""

    def test_add_tag_success(self):
        m = Memory()
        m.add("hello")
        assert m.add_tag(0, "important") is True
        assert "important" in m.get_all()[0].tags

    def test_add_tag_idempotent(self):
        m = Memory()
        m.add("hello", tags=["x"])
        m.add_tag(0, "x")  # already present
        assert m.get_all()[0].tags.count("x") == 1

    def test_add_tag_out_of_bounds(self):
        m = Memory()
        assert m.add_tag(99, "x") is False

    def test_add_tag_negative(self):
        m = Memory()
        assert m.add_tag(-1, "x") is False

    def test_remove_tag_success(self):
        m = Memory()
        m.add("hello", tags=["a", "b", "c"])
        assert m.remove_tag(0, "b") is True
        assert "b" not in m.get_all()[0].tags
        assert "a" in m.get_all()[0].tags
        assert "c" in m.get_all()[0].tags

    def test_remove_tag_not_present(self):
        m = Memory()
        m.add("hello", tags=["a"])
        # Should return True (index valid) even if tag not present
        assert m.remove_tag(0, "z") is True

    def test_remove_tag_out_of_bounds(self):
        m = Memory()
        assert m.remove_tag(0, "x") is False

    def test_tag_management_persists(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            m = Memory(persistence_path=path)
            m.add("persist test", tags=["keep"])
            m.add_tag(0, "added")
            m.remove_tag(0, "keep")

            # Reload
            m2 = Memory(persistence_path=path)
            entries = m2.get_all()
            assert entries[0].content == "persist test"
            assert "added" in entries[0].tags
            assert "keep" not in entries[0].tags
        finally:
            os.unlink(path)
