"""Tests for F51: batch_remove() and batch_update()."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from nano_agent.memory import Memory


class TestBatchRemove:
    """F51a: batch_remove()."""

    def test_remove_single(self):
        m = Memory()
        m.add("a")
        m.add("b")
        m.add("c")
        removed = m.batch_remove([1])
        assert removed == 1
        assert m.count() == 2
        assert m.get_all()[0].content == "a"
        assert m.get_all()[1].content == "c"

    def test_remove_multiple(self):
        m = Memory()
        for i in range(10):
            m.add(f"entry {i}")
        removed = m.batch_remove([2, 5, 7])
        assert removed == 3
        assert m.count() == 7

    def test_remove_all(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry {i}")
        removed = m.batch_remove([0, 1, 2, 3, 4])
        assert removed == 5
        assert m.count() == 0

    def test_remove_with_duplicates(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry {i}")
        removed = m.batch_remove([1, 1, 1])
        assert removed == 1
        assert m.count() == 4

    def test_remove_invalid_indices(self):
        m = Memory()
        m.add("a")
        removed = m.batch_remove([-1, 100, "bad"])
        assert removed == 0
        assert m.count() == 1

    def test_remove_empty_list(self):
        m = Memory()
        m.add("a")
        removed = m.batch_remove([])
        assert removed == 0

    def test_remove_from_empty_memory(self):
        m = Memory()
        removed = m.batch_remove([0])
        assert removed == 0

    def test_reverse_order_preserves_indices(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry {i}")
        # Remove indices 0 and 4
        removed = m.batch_remove([0, 4])
        assert removed == 2
        assert m.count() == 3
        contents = [e.content for e in m.get_all()]
        assert contents == ["entry 1", "entry 2", "entry 3"]

    def test_not_list_input(self):
        m = Memory()
        m.add("a")
        assert m.batch_remove("not a list") == 0

    def test_preserves_order(self):
        m = Memory()
        for c in "abcde":
            m.add(c)
        m.batch_remove([1, 3])
        contents = [e.content for e in m.get_all()]
        assert contents == ["a", "c", "e"]


class TestBatchUpdate:
    """F51b: batch_update()."""

    def test_update_single_content(self):
        m = Memory()
        m.add("old")
        updated = m.batch_update([{"index": 0, "content": "new"}])
        assert updated == 1
        assert m.get_all()[0].content == "new"

    def test_update_multiple_fields(self):
        m = Memory()
        m.add("hello", tags=["old"], importance=0.3)
        updated = m.batch_update([{
            "index": 0,
            "content": "world",
            "importance": 0.9,
            "tags": ["new"],
            "metadata": {"key": "val"}
        }])
        assert updated == 1
        entry = m.get_all()[0]
        assert entry.content == "world"
        assert entry.importance == 0.9
        assert entry.tags == ["new"]
        assert entry.metadata == {"key": "val"}

    def test_update_multiple_entries(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry {i}", importance=0.5)
        updated = m.batch_update([
            {"index": 0, "importance": 1.0},
            {"index": 2, "importance": 0.0},
            {"index": 4, "content": "last updated"},
        ])
        assert updated == 3
        assert m.get_all()[0].importance == 1.0
        assert m.get_all()[2].importance == 0.0
        assert m.get_all()[4].content == "last updated"

    def test_importance_clamped(self):
        m = Memory()
        m.add("test", importance=0.5)
        m.batch_update([{"index": 0, "importance": 1.5}])
        assert m.get_all()[0].importance == 1.0
        m.batch_update([{"index": 0, "importance": -0.5}])
        assert m.get_all()[0].importance == 0.0

    def test_invalid_updates_skipped(self):
        m = Memory()
        m.add("a")
        m.add("b")
        updated = m.batch_update([
            {"index": 0, "content": "ok"},
            {"no_index": True},
            "not a dict",
            {"index": 999, "content": "out of bounds"},
            {"index": "bad", "content": "wrong type"},
        ])
        assert updated == 1
        assert m.get_all()[0].content == "ok"
        assert m.get_all()[1].content == "b"

    def test_empty_updates(self):
        m = Memory()
        m.add("a")
        assert m.batch_update([]) == 0

    def test_not_list_input(self):
        m = Memory()
        assert m.batch_update("not a list") == 0

    def test_update_timestamp_refreshes(self):
        m = Memory()
        m.add("old")
        import time
        time.sleep(0.01)
        m.batch_update([{"index": 0, "content": "new"}])
        # The entry timestamp should be recent (within last second)
        entry = m.get_all()[0]
        assert (datetime.now() - entry.timestamp).total_seconds() < 1

    def test_update_only_importance_doesnt_change_timestamp(self):
        m = Memory()
        m.add("content")
        original_ts = m.get_all()[0].timestamp
        import time
        time.sleep(0.01)
        m.batch_update([{"index": 0, "importance": 0.9}])
        # Only content update refreshes timestamp
        assert m.get_all()[0].timestamp == original_ts
