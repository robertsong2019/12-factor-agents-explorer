"""
Tests for Memory importance scoring + forgetting (F5-F8)
2026-06-25 Cycle 152
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nano_agent.memory import Memory, MemoryEntry


class TestImportanceScoring:
    """F5: set_importance — manually assign importance scores"""

    def test_set_importance_basic(self):
        m = Memory()
        m.add("important fact", importance=0.9)
        assert m._entries[0].importance == 0.9

    def test_set_importance_updates_existing(self):
        m = Memory()
        m.add("entry")
        assert m.set_importance(0, 0.8) is True
        assert m._entries[0].importance == 0.8

    def test_set_importance_invalid_index(self):
        m = Memory()
        m.add("entry")
        assert m.set_importance(99, 0.9) is False

    def test_set_importance_clamps_high(self):
        m = Memory()
        m.add("entry")
        m.set_importance(0, 5.0)
        assert m._entries[0].importance == 1.0

    def test_set_importance_clamps_low(self):
        m = Memory()
        m.add("entry")
        m.set_importance(0, -1.0)
        assert m._entries[0].importance == 0.0

    def test_default_importance_is_half(self):
        m = Memory()
        m.add("entry")
        assert m._entries[0].importance == 0.5

    def test_importance_persists_to_dict(self):
        m = Memory()
        m.add("entry", importance=0.7)
        d = m._entries[0].to_dict()
        assert d["importance"] == 0.7


class TestImportanceDecay:
    """F6: importance_decay — time-based forgetting simulation"""

    def test_decay_reduces_all(self):
        m = Memory()
        m.add("a", importance=1.0)
        m.add("b", importance=0.8)
        count = m.importance_decay(factor=0.9)
        assert count == 2
        assert m._entries[0].importance == pytest.approx(0.9)
        assert m._entries[1].importance == pytest.approx(0.72)

    def test_decay_multiple_rounds(self):
        m = Memory()
        m.add("entry", importance=1.0)
        m.importance_decay(0.9)
        m.importance_decay(0.9)
        assert m._entries[0].importance == pytest.approx(0.81)

    def test_decay_invalid_factor(self):
        m = Memory()
        m.add("entry", importance=1.0)
        assert m.importance_decay(factor=1.5) == 0
        assert m._entries[0].importance == 1.0

    def test_decay_empty_memory(self):
        m = Memory()
        assert m.importance_decay() == 0


class TestForget:
    """F7: forget — remove low-importance entries"""

    def test_forget_removes_below_threshold(self):
        m = Memory()
        m.add("keep", importance=0.8)
        m.add("forget", importance=0.05)
        removed = m.forget(threshold=0.1)
        assert removed == 1
        assert m.count() == 1
        assert m._entries[0].content == "keep"

    def test_forget_keeps_all_above_threshold(self):
        m = Memory()
        for i in range(5):
            m.add(f"entry_{i}", importance=0.3 + i * 0.1)
        # All entries are >= 0.3, so none removed at threshold 0.3
        removed = m.forget(threshold=0.3)
        assert removed == 0
        assert m.count() == 5
        # Now raise threshold to remove the lowest one
        removed = m.forget(threshold=0.35)
        assert removed == 1

    def test_forget_zero_threshold_keeps_all(self):
        m = Memory()
        m.add("a", importance=0.01)
        m.add("b", importance=0.99)
        removed = m.forget(threshold=0.0)
        assert removed == 0
        assert m.count() == 2

    def test_forget_all(self):
        m = Memory()
        m.add("a", importance=0.01)
        m.add("b", importance=0.02)
        removed = m.forget(threshold=0.5)
        assert removed == 2
        assert m.count() == 0


class TestTopImportant:
    """F8: top_important — rank by importance"""

    def test_top_important_returns_sorted(self):
        m = Memory()
        m.add("low", importance=0.2)
        m.add("high", importance=0.9)
        m.add("mid", importance=0.5)
        result = m.top_important(n=2)
        assert len(result) == 2
        assert result[0].content == "high"
        assert result[1].content == "mid"

    def test_top_important_fewer_than_n(self):
        m = Memory()
        m.add("only", importance=0.5)
        result = m.top_important(n=5)
        assert len(result) == 1

    def test_top_important_empty(self):
        m = Memory()
        result = m.top_important(n=5)
        assert result == []


class TestImportanceStatsAndPersistence:
    """Importance in stats + persistence round-trip"""

    def test_stats_includes_avg_importance(self):
        m = Memory()
        m.add("a", importance=0.4)
        m.add("b", importance=0.8)
        stats = m.stats()
        assert "avg_importance" in stats
        assert stats["avg_importance"] == 0.6

    def test_stats_avg_importance_empty(self):
        m = Memory()
        stats = m.stats()
        assert stats["total"] == 0
        assert "avg_importance" not in stats  # early return for empty

    def test_persistence_round_trip_with_importance(self, tmp_path):
        path = str(tmp_path / "mem.json")
        m1 = Memory(persistence_path=path)
        m1.add("important", importance=0.9)
        m1.add("trivial", importance=0.1)
        # Load into new instance
        m2 = Memory(persistence_path=path)
        assert m2._entries[0].importance == 0.9
        assert m2._entries[1].importance == 0.1

    def test_import_json_preserves_importance(self):
        import json
        m1 = Memory()
        m1.add("a", importance=0.7)
        exported = m1.export_json()
        m2 = Memory()
        count = m2.import_json(exported)
        assert count == 1
        assert m2._entries[0].importance == 0.7

    def test_import_json_default_importance_for_old_format(self):
        """Entries without importance field get default 0.5"""
        import json
        old_data = json.dumps([{
            "content": "legacy",
            "timestamp": "2026-01-01T00:00:00",
            "metadata": {}
        }])
        m = Memory()
        count = m.import_json(old_data)
        assert count == 1
        assert m._entries[0].importance == 0.5
