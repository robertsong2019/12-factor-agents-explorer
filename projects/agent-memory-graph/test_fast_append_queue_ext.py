"""Tests for FastAppendQueue extended operations.

Cycle 426b: flush_and_consolidate, pending_kinds, pending_categories,
peak_buffer_size, is_healthy.
"""
import pytest
import memory_graph as mg
from memory_graph import MemoryGraph, FastAppendQueue


def _node_count(g):
    return g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]


class TestFlushAndConsolidate:

    def test_flush_and_consolidate_returns_combined_result(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(15):
            q.append(f"fact {i}", kind="fact")
        result = q.flush_and_consolidate()
        assert "flush" in result
        assert "consolidation" in result
        assert result["flush"]["merged"] == 15

    def test_flush_and_consolidate_clears_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(5):
            q.append(f"item {i}")
        q.flush_and_consolidate()
        assert len(q._buffer) == 0

    def test_flush_and_consolidate_creates_nodes(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(12):
            q.append(f"node {i}")
        q.flush_and_consolidate()
        assert _node_count(g) >= 12  # consolidate might merge some

    def test_flush_and_consolidate_empty_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        result = q.flush_and_consolidate()
        assert result["flush"]["flushed"] == 0
        assert "consolidation" in result

    def test_flush_and_consolidate_passes_kwargs(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(20):
            q.append(f"item {i}")
        # dry_run should not modify graph
        result = q.flush_and_consolidate(dry_run=True)
        # flush still creates nodes, but consolidate in dry_run mode
        assert result["flush"]["merged"] > 0


class TestPendingKinds:

    def test_pending_kinds_empty(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        assert q.pending_kinds() == {}

    def test_pending_kinds_single_kind(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a", kind="fact")
        q.append("b", kind="fact")
        result = q.pending_kinds()
        assert result == {"fact": 2}

    def test_pending_kinds_mixed(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a", kind="fact")
        q.append("b", kind="event")
        q.append("c", kind="fact")
        q.append("d", kind="concept")
        result = q.pending_kinds()
        assert result["fact"] == 2
        assert result["event"] == 1
        assert result["concept"] == 1

    def test_pending_kinds_after_flush(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a", kind="fact")
        q.flush()
        assert q.pending_kinds() == {}


class TestPendingCategories:

    def test_pending_categories_empty(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        assert q.pending_categories() == {}

    def test_pending_categories_none_for_default(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("no category")
        result = q.pending_categories()
        assert result.get(None) == 1

    def test_pending_categories_mixed(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a", category="preference")
        q.append("b", category="preference")
        q.append("c", category="skill")
        q.append("d")  # None
        result = q.pending_categories()
        assert result["preference"] == 2
        assert result["skill"] == 1
        assert result[None] == 1


class TestPeakBufferSize:

    def test_peak_empty(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        assert q.peak_buffer_size() == 0

    def test_peak_single(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        assert q.peak_buffer_size() == 1

    def test_peak_multiple(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(10):
            q.append(f"item {i}")
        assert q.peak_buffer_size() == 10

    def test_peak_after_drain(self):
        """peak_buffer_size after drain should be 0 (slots reset)."""
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        q.drain()
        assert q.peak_buffer_size() == 0


class TestIsHealthy:

    def test_healthy_empty_queue(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        h = q.is_healthy()
        assert h["healthy"] is True
        assert h["issues"] == []

    def test_healthy_after_normal_operation(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=5)
        for i in range(10):
            q.append(f"item {i}")
        # auto-flush should have triggered
        h = q.is_healthy()
        assert h["healthy"] is True

    def test_unhealthy_never_flushed(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        for i in range(15):
            q.append(f"item {i}")
        h = q.is_healthy()
        assert h["healthy"] is False
        assert any("never flushed" in issue for issue in h["issues"])

    def test_unhealthy_low_flush_ratio(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        for i in range(20):
            q.append(f"item {i}")
        q.flush()  # flush once
        for i in range(50):
            q.append(f"more {i}")  # accumulate a lot
        h = q.is_healthy()
        # With 20 flushed + 50 pending = low ratio
        assert h["flush_ratio"] < 1.0

    def test_health_shows_buffer_size(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        h = q.is_healthy()
        assert h["buffer_size"] == 2

    def test_health_empty_flush_ratio(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        h = q.is_healthy()
        assert h["flush_ratio"] == 1.0  # nothing appended = "perfect" ratio
