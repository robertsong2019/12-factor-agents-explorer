"""Tests for F49 (Archive System) and F50 (forget_older_than)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from nano_agent.memory import Memory, MemoryEntry
from datetime import datetime, timedelta


class TestF49Archive:
    """F49: Memory.archive / unarchive / archived."""

    def test_archive_removes_from_active(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("keep this", importance=0.8)
        m.add("archive this", importance=0.2)
        assert m.count() == 2

        result = m.archive(1)
        assert result is True
        assert m.count() == 1
        assert m._entries[0].content == "keep this"

    def test_archive_returns_list(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("entry A")
        m.add("entry B")
        m.archive(0)

        archived = m.archived()
        assert len(archived) == 1
        assert archived[0].content == "entry A"

    def test_archive_invalid_index(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("only entry")
        result = m.archive(5)
        assert result is False
        assert m.count() == 1

    def test_archive_negative_index(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("entry")
        result = m.archive(-1)
        assert result is False

    def test_unarchive_restores_entry(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("active")
        m.add("to archive")
        m.archive(1)

        assert m.count() == 1
        assert len(m.archived()) == 1

        result = m.unarchive(0)
        assert result is True
        assert m.count() == 2
        assert len(m.archived()) == 0

    def test_unarchive_invalid_index(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("entry")
        m.archive(0)
        result = m.unarchive(5)
        assert result is False

    def test_archived_returns_copy(self):
        """archived() returns a copy — mutating it doesn't affect internal state."""
        m = Memory(max_entries=100, persistence_path=None)
        m.add("entry")
        m.archive(0)

        arch = m.archived()
        arch.clear()
        assert len(m.archived()) == 1  # internal unchanged

    def test_archive_multiple_entries(self):
        m = Memory(max_entries=100, persistence_path=None)
        for i in range(5):
            m.add(f"entry-{i}")
        # Archive entries 0,1,2 (but indices shift!)
        m.archive(0)  # removes entry-0, now entry-1..4 at 0..3
        m.archive(0)  # removes entry-1
        m.archive(0)  # removes entry-2
        assert m.count() == 2
        assert len(m.archived()) == 3

    def test_archive_unarchive_roundtrip(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("important", importance=0.9)
        m.add("less important", importance=0.1)
        m.archive(1)

        # Search should not find archived entries
        results = m.search("less important")
        assert len(results) == 0

        # Unarchive and search again
        m.unarchive(0)
        results = m.search("less important")
        assert len(results) == 1

    def test_clear_clears_archive_too(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("entry")
        m.archive(0)
        assert len(m.archived()) == 1

        m.clear()
        assert m.count() == 0
        assert len(m.archived()) == 0

    def test_unarchive_respects_max_entries(self):
        m = Memory(max_entries=2, persistence_path=None)
        m.add("e1")
        m.add("e2")
        m.archive(0)  # archive e1
        m.add("e3")
        m.add("e4")  # now active: e2, e3, e4 trimmed to e3, e4

        # Unarchive e1 — should respect max_entries
        m.unarchive(0)
        assert m.count() <= 2


class TestF50ForgetOlderThan:
    """F50: Memory.forget_older_than(days)."""

    def test_removes_old_entries(self):
        m = Memory(max_entries=100, persistence_path=None)
        # Manually create entries with old timestamps
        old_entry = MemoryEntry(content="old memory", timestamp=datetime.now() - timedelta(days=10))
        new_entry = MemoryEntry(content="recent memory", timestamp=datetime.now())
        m._entries = [old_entry, new_entry]

        removed = m.forget_older_than(5)
        assert removed == 1
        assert m.count() == 1
        assert m._entries[0].content == "recent memory"

    def test_keeps_recent_entries(self):
        m = Memory(max_entries=100, persistence_path=None)
        m.add("recent 1")
        m.add("recent 2")
        removed = m.forget_older_than(7)
        assert removed == 0
        assert m.count() == 2

    def test_boundary_condition(self):
        """Entry exactly at cutoff should be kept (>=)."""
        m = Memory(max_entries=100, persistence_path=None)
        boundary_entry = MemoryEntry(
            content="boundary",
            timestamp=datetime.now() - timedelta(days=3, seconds=-1)  # just under 3 days
        )
        m._entries = [boundary_entry]
        removed = m.forget_older_than(3)
        assert removed == 0

    def test_all_entries_old(self):
        m = Memory(max_entries=100, persistence_path=None)
        old1 = MemoryEntry(content="old1", timestamp=datetime.now() - timedelta(days=30))
        old2 = MemoryEntry(content="old2", timestamp=datetime.now() - timedelta(days=60))
        m._entries = [old1, old2]

        removed = m.forget_older_than(7)
        assert removed == 2
        assert m.count() == 0

    def test_zero_days_removes_all(self):
        """0 days = remove everything older than now (effectively all)."""
        m = Memory(max_entries=100, persistence_path=None)
        past = MemoryEntry(content="past", timestamp=datetime.now() - timedelta(seconds=1))
        m._entries = [past]

        removed = m.forget_older_than(0)
        # entry is 1 second old, cutoff is "now", so it should be removed
        assert removed == 1

    def test_mixed_entries(self):
        m = Memory(max_entries=100, persistence_path=None)
        e1 = MemoryEntry(content="ancient", timestamp=datetime.now() - timedelta(days=100))
        e2 = MemoryEntry(content="old", timestamp=datetime.now() - timedelta(days=10))
        e3 = MemoryEntry(content="recent", timestamp=datetime.now() - timedelta(hours=1))
        m._entries = [e1, e2, e3]

        removed = m.forget_older_than(5)
        assert removed == 2
        assert m.count() == 1
        assert m._entries[0].content == "recent"

    def test_empty_memory(self):
        m = Memory(max_entries=100, persistence_path=None)
        removed = m.forget_older_than(7)
        assert removed == 0
