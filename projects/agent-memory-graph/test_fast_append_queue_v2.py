"""Tests for FastAppendQueue — System-1/System-2 dual-process write path.

Cycle 425. Research #033: Engram 83.6% vs 73.2%, every SOTA system
separates hot write path from cold async consolidation.
"""
import json
import time
import pytest
import memory_graph as mg
from memory_graph import MemoryGraph, FastAppendQueue


def _node_count(g):
    """Helper: count nodes in a MemoryGraph."""
    return g.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]


class TestFastAppendQueueBasic:
    """Basic lifecycle tests."""

    def test_create_queue(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        assert q.graph is g
        assert q._buffer == []
        assert q._auto_flush == 50
        assert q._consistency == "session"

    def test_create_queue_custom_threshold(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=10)
        assert q._auto_flush == 10

    def test_create_queue_disabled_auto_flush(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        assert q._auto_flush == 0

    def test_append_returns_slot(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        slot = q.append("test fact")
        assert slot == 0

    def test_append_increments_slot(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        s1 = q.append("fact 1")
        s2 = q.append("fact 2")
        s3 = q.append("fact 3")
        assert s1 == 0
        assert s2 == 1
        assert s3 == 2

    def test_append_stores_all_fields(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("Python fact", kind="skill", data={"level": "expert"},
                 tags=["lang", "coding"], category="preference")
        entry = q._buffer[0]
        assert entry["label"] == "Python fact"
        assert entry["kind"] == "skill"
        assert entry["data"] == {"level": "expert"}
        assert entry["tags"] == ["lang", "coding"]
        assert entry["category"] == "preference"
        assert "timestamp" in entry

    def test_append_default_kind(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("something")
        assert q._buffer[0]["kind"] == "fact"

    def test_append_does_not_touch_graph(self):
        """System-1 must NOT modify the graph."""
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("buffered fact")
        assert _node_count(g) == 0


class TestFastAppendQueueBuffer:
    """Buffer management tests."""

    def test_buffer_grows(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(5):
            q.append(f"fact {i}")
        assert len(q._buffer) == 5

    def test_search_buffer_finds_match(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("User likes python")
        q.append("User knows rust")
        q.append("User dislikes java")
        results = q.search_buffer("python")
        assert len(results) == 1
        assert results[0]["label"] == "User likes python"

    def test_search_buffer_case_insensitive(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("Python is great")
        results = q.search_buffer("python")
        assert len(results) == 1

    def test_search_buffer_limit(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(10):
            q.append(f"python fact {i}")
        results = q.search_buffer("python", limit=3)
        assert len(results) == 3

    def test_search_buffer_no_match(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("hello world")
        results = q.search_buffer("nonexistent")
        assert len(results) == 0

    def test_search_buffer_empty_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        results = q.search_buffer("anything")
        assert results == []

    def test_drain_returns_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        buf = q.drain()
        assert len(buf) == 2
        assert buf[0]["label"] == "a"
        assert buf[1]["label"] == "b"

    def test_drain_clears_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.drain()
        assert len(q._buffer) == 0

    def test_drain_does_not_flush(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.drain()
        assert _node_count(g) == 0


class TestFastAppendQueueFlush:
    """System-2 flush tests."""

    def test_flush_empty_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        result = q.flush()
        assert result["flushed"] == 0
        assert result["merged"] == 0

    def test_flush_creates_nodes(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("fact A")
        q.append("fact B")
        result = q.flush()
        assert result["flushed"] == 2
        assert result["merged"] == 2
        assert _node_count(g) == 2

    def test_flush_clears_buffer(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("fact A")
        q.flush()
        assert len(q._buffer) == 0

    def test_flush_deduplicates_same_label(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("same label")
        q.append("same label")
        result = q.flush()
        assert result["deduplicated"] == 1
        assert result["merged"] == 1
        assert _node_count(g) == 1

    def test_flush_deduplicate_disabled(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("same label")
        q.append("same label")
        result = q.flush(deduplicate=False)
        assert result["deduplicated"] == 0
        assert result["merged"] == 2
        assert _node_count(g) == 2

    def test_flush_against_existing_graph(self):
        """Dedup should detect nodes already in the graph."""
        g = MemoryGraph()
        g.add("existing fact", kind="fact")
        q = FastAppendQueue(g)
        q.append("existing fact")  # same label as existing node
        result = q.flush()
        assert result["deduplicated"] == 1
        assert result["merged"] == 0
        assert _node_count(g) == 1  # no new node

    def test_flush_links_related_same_kind(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("fact A", kind="fact")
        q.append("fact B", kind="fact")
        result = q.flush(link_related=True)
        assert result["linked"] == 1
        assert result["merged"] == 2

    def test_flush_links_related_shared_tags(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("node A", kind="concept", tags=["python", "ai"])
        q.append("node B", kind="event", tags=["python", "coding"])
        result = q.flush(link_related=True)
        assert result["linked"] == 1  # shared "python" tag

    def test_flush_no_link_different_kinds(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("node A", kind="fact")
        q.append("node B", kind="event")
        result = q.flush(link_related=True)
        assert result["linked"] == 0

    def test_flush_link_disabled(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a", kind="fact")
        q.append("b", kind="fact")
        result = q.flush(link_related=False)
        assert result["linked"] == 0

    def test_flush_preserves_node_data(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("data node", kind="fact", data={"key": "value"})
        q.flush()
        nodes = g.find_by_kind("fact")
        assert len(nodes) == 1
        assert nodes[0].data == {"key": "value"}

    def test_flush_preserves_tags(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("tagged node", kind="fact", tags=["alpha", "beta"])
        q.flush()
        row = g.conn.execute("SELECT tags FROM nodes LIMIT 1").fetchone()
        tags = json.loads(row["tags"])
        assert set(tags) == {"alpha", "beta"}

    def test_flush_preserves_category(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("cat node", kind="fact", category="preference")
        q.flush()
        row = g.conn.execute("SELECT category FROM nodes LIMIT 1").fetchone()
        assert row["category"] == "preference"

    def test_multiple_flushes(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("fact 1")
        r1 = q.flush()
        q.append("fact 2")
        r2 = q.flush()
        assert r1["flush_number"] == 1
        assert r2["flush_number"] == 2
        assert _node_count(g) == 2


class TestFastAppendQueueAutoFlush:
    """Auto-flush threshold tests."""

    def test_auto_flush_triggers(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=3)
        q.append("a")
        q.append("b")
        assert len(q._buffer) == 2  # not yet
        q.append("c")  # triggers auto-flush
        assert len(q._buffer) == 0
        assert _node_count(g) == 3

    def test_auto_flush_disabled(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        for i in range(100):
            q.append(f"fact {i}")
        assert len(q._buffer) == 100
        assert _node_count(g) == 0


class TestFastAppendQueueStatus:
    """Status and diagnostics tests."""

    def test_status_empty(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        s = q.status()
        assert s["buffer_size"] == 0
        assert s["total_appended"] == 0
        assert s["total_flushed"] == 0
        assert s["flush_count"] == 0
        assert s["last_flush_time"] is None
        assert s["auto_flush_threshold"] == 50
        assert s["consistency_mode"] == "session"

    def test_status_after_appends(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        s = q.status()
        assert s["buffer_size"] == 2
        assert s["total_appended"] == 2
        assert s["total_flushed"] == 0
        assert s["pending_labels"] == ["a", "b"]

    def test_status_after_flush(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        q.flush()
        s = q.status()
        assert s["buffer_size"] == 0
        assert s["total_appended"] == 2
        assert s["total_flushed"] == 2
        assert s["flush_count"] == 1
        assert s["last_flush_time"] is not None

    def test_status_pending_labels_capped(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for i in range(30):
            q.append(f"fact {i}")
        s = q.status()
        assert len(s["pending_labels"]) == 20  # capped at 20

    def test_status_shows_dedup_count(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("same")
        q.append("same")
        q.flush()
        s = q.status()
        assert s["total_deduplicated"] >= 1


class TestFastAppendQueueConsistencyModes:
    """Consistency mode configuration tests."""

    def test_session_mode(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, consistency_mode="session")
        assert q._consistency == "session"

    def test_causal_mode(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, consistency_mode="causal")
        assert q._consistency == "causal"

    def test_eventual_mode(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, consistency_mode="eventual")
        assert q._consistency == "eventual"

    def test_committed_mode(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, consistency_mode="committed")
        assert q._consistency == "committed"

    def test_status_reflects_mode(self):
        g = MemoryGraph()
        q = FastAppendQueue(g, consistency_mode="eventual")
        assert q.status()["consistency_mode"] == "eventual"


class TestFastAppendQueueIntegration:
    """Integration with MemoryGraph operations."""

    def test_flushed_nodes_searchable(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("python programming", kind="skill")
        q.flush()
        # Node should be findable via label search
        results = g.search_by_label("python")
        assert len(results) > 0

    def test_flushed_nodes_linkable(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("base fact", kind="fact")
        q.flush()
        node = g.find_by_kind("fact")[0]
        other = g.add("related fact", kind="fact")
        g.link(node.id, other.id, "depends_on")
        # Verify link exists
        neighbors = g.neighbors(node.id)
        assert any(n.id == other.id for n in neighbors)

    def test_flush_then_consolidate(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        # Add some overlapping content
        q.append("user likes python", kind="fact", tags=["preference"])
        q.append("user likes python", kind="fact", tags=["preference"])
        q.append("user knows rust", kind="fact", tags=["skill"])
        q.flush()
        # After flush, dedup should have caught the duplicate
        assert _node_count(g) == 2

    def test_interleaved_append_flush(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.flush()
        q.append("b")
        q.flush()
        q.append("c")
        q.flush()
        assert _node_count(g) == 3
        assert q.status()["flush_count"] == 3

    def test_large_batch_performance(self):
        """System-1 should handle 1000 appends quickly."""
        g = MemoryGraph()
        q = FastAppendQueue(g, auto_flush_threshold=0)
        start = time.time()
        for i in range(1000):
            q.append(f"fact {i}")
        elapsed = time.time() - start
        # Should be well under 1 second for 1000 O(1) appends
        assert elapsed < 1.0
        assert len(q._buffer) == 1000

    def test_flush_with_metadata_rich_nodes(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("rich node", kind="event",
                 data={"timestamp": 12345, "source": "test", "confidence": 0.95},
                 tags=["important", "verified"])
        result = q.flush()
        assert result["merged"] == 1
        nodes = g.find_by_kind("event")
        assert nodes[0].data["source"] == "test"

    def test_queue_works_with_existing_graph(self):
        """Queue should coexist with manually added nodes."""
        g = MemoryGraph()
        g.add("manual node", kind="fact")
        q = FastAppendQueue(g)
        q.append("queued node", kind="fact")
        q.flush()
        assert _node_count(g) == 2

    def test_repeated_flush_correctness(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        for batch in range(3):
            for i in range(5):
                q.append(f"batch {batch} fact {i}")
            q.flush()
        assert _node_count(g) == 15
        assert q.status()["total_flushed"] == 15
        assert q.status()["flush_count"] == 3

    def test_search_buffer_after_partial_drain(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("alpha")
        q.append("beta")
        q.append("gamma")
        # Drain removes everything from buffer
        buf = q.drain()
        # Add a new entry
        q.append("delta")
        results = q.search_buffer("delta")
        assert len(results) == 1

    def test_total_appended_persists_across_flushes(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("a")
        q.append("b")
        q.flush()
        q.append("c")
        q.append("d")
        q.flush()
        assert q.status()["total_appended"] == 4

    def test_mixed_kinds_in_single_flush(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("fact 1", kind="fact")
        q.append("event 1", kind="event")
        q.append("concept 1", kind="concept")
        result = q.flush()
        assert result["merged"] == 3
        assert len(g.find_by_kind("fact")) == 1
        assert len(g.find_by_kind("event")) == 1
        assert len(g.find_by_kind("concept")) == 1

    def test_flush_summary_has_all_fields(self):
        g = MemoryGraph()
        q = FastAppendQueue(g)
        q.append("test", kind="fact")
        result = q.flush()
        for key in ("flushed", "merged", "deduplicated", "linked",
                    "skipped", "flush_number"):
            assert key in result, f"Missing key: {key}"
