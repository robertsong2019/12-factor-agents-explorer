"""Tests for FastAppendQueue.peek() and end-to-end integration.

Cycle 427: peek() API + multi-agent simulation + performance edge cases.
"""
import time
import pytest
import memory_graph as mg
from memory_graph import MemoryGraph, FastAppendQueue


class TestPeek:

    def test_peek_empty(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        assert q.peek() == []

    def test_peek_default_n(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(3):
            q.append(f"item {i}")
        result = q.peek()
        assert len(result) == 3

    def test_peek_custom_n(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(10):
            q.append(f"item {i}")
        result = q.peek(3)
        assert len(result) == 3
        assert result[0]["label"] == "item 0"

    def test_peek_more_than_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("only one")
        result = q.peek(10)
        assert len(result) == 1

    def test_peek_does_not_remove(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        q.peek()
        assert len(q._buffer) == 2

    def test_peek_returns_copies(self):
        """peek() should return copies, not references."""
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("original")
        result = q.peek()
        result[0]["label"] = "modified"
        assert q._buffer[0]["label"] == "original"


class TestEndToEndAgentSimulation:
    """Simulate real agent write patterns."""

    def test_agent_session_lifecycle(self):
        """Simulate: agent receives messages → buffers → flushes at end."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)

        # Agent receives messages during a session
        messages = [
            ("User mentioned Python expertise", "fact", {"confidence": 0.9}),
            ("User asked about ML frameworks", "event", {"topic": "ml"}),
            ("User prefers TypeScript over JavaScript", "fact", {"category": "preference"}),
            ("Meeting scheduled for Friday", "event", {"time": "Friday"}),
            ("Project deadline approaching", "event", {"urgency": "high"}),
        ]

        for label, kind, data in messages:
            q.append(label, kind=kind, data=data)

        # Buffer should hold everything
        assert q.status()["buffer_size"] == 5
        assert g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0

        # Session ends → flush
        result = q.flush()
        assert result["merged"] == 5
        assert g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 5

    def test_repeated_short_sessions(self):
        """Multiple agent sessions with small flushes."""
        g = MemoryGraph()
        q = FastAppendQueue(g)

        for session in range(5):
            for i in range(3):
                q.append(f"session {session} item {i}", kind="fact")
            q.flush()

        assert q.status()["flush_count"] == 5
        assert q.status()["total_flushed"] == 15
        assert g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 15

    def test_burst_then_quiet_pattern(self):
        """Realistic: burst of activity, then quiet period."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)

        # Burst: 50 items in quick succession
        for i in range(50):
            q.append(f"burst item {i}", kind="event")

        # System-1 should handle this without touching the graph
        assert g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0

        # Flush
        result = q.flush()
        assert result["merged"] == 50

        # Quiet period: no new items
        assert q.status()["buffer_size"] == 0
        assert q.is_healthy()["healthy"] is True

    def test_dedup_across_sessions(self):
        """Same fact arriving in different sessions should deduplicate."""
        g = MemoryGraph()
        q = FastAppendQueue(g)

        q.append("User likes Python")
        q.flush()

        q.append("User likes Python")  # same fact again
        q.flush()

        # Should have only 1 node
        assert g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 1

    def test_mixed_priority_writes(self):
        """Mix of high-priority and normal writes."""
        g = MemoryGraph()
        q = FastAppendQueue(g)

        # Normal writes
        q.append("casual note 1", kind="fact")
        q.append("casual note 2", kind="fact")

        # High-priority (categorized)
        q.append("CRITICAL: security alert", kind="event",
                 data={"priority": "critical"}, tags=["urgent"])

        result = q.flush()
        assert result["merged"] == 3
        assert result["deduplicated"] == 0

    def test_health_check_after_long_operation(self):
        """Queue health after extended operation."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=10)

        # Normal operation: fill and auto-flush repeatedly
        for i in range(100):
            q.append(f"fact {i}")

        h = q.is_healthy()
        assert h["healthy"] is True
        assert h["buffer_size"] == 0  # all auto-flushed
        assert h["flush_ratio"] == 1.0  # everything flushed


class TestPerformanceEdgeCases:

    def test_rapid_append_performance(self):
        """1000 appends should complete in <0.5s."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        start = time.time()
        for i in range(1000):
            q.append(f"perf test {i}")
        elapsed = time.time() - start
        assert elapsed < 0.5

    def test_large_flush_performance(self):
        """Flushing 500 items should complete in <2s."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        for i in range(500):
            q.append(f"bulk item {i}")
        start = time.time()
        q.flush()
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_search_buffer_large(self):
        """Buffer search on 500 items should be fast."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        for i in range(500):
            q.append(f"item {i}")
        start = time.time()
        results = q.search_buffer("item 250")
        elapsed = time.time() - start
        assert elapsed < 0.1
        assert len(results) >= 1

    def test_peek_does_not_copy_large_buffer_slowly(self):
        """peek(5) on a large buffer should be near-instant."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        for i in range(1000):
            q.append(f"x {i}")
        start = time.time()
        q.peek(5)
        elapsed = time.time() - start
        assert elapsed < 0.01
