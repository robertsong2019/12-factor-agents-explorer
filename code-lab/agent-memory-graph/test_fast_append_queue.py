"""
Tests for FastAppendQueue — System-1/System-2 dual-process write path.
Research #033: Engram pattern (83.6% vs 73.2%), Mem0 v3 ADD-only.
"""

import pytest
import time
from memory_graph import MemoryGraph, FastAppendQueue


@pytest.fixture
def faq():
    """FastAppendQueue with a fresh MemoryGraph."""
    mg = MemoryGraph()
    return FastAppendQueue(mg, threshold=5, max_age_seconds=2)


class TestAppend:
    def test_append_returns_queued(self, faq):
        result = faq.append("hello", "greeting")
        assert result["status"] == "queued"
        assert result["queue_position"] == 1

    def test_append_increments_position(self, faq):
        faq.append("a", "test")
        r2 = faq.append("b", "test")
        assert r2["queue_position"] == 2

    def test_should_consolidate_at_threshold(self, faq):
        for i in range(4):
            r = faq.append(f"item_{i}", "test")
            assert r["should_consolidate"] is False
        r = faq.append("item_4", "test")
        assert r["should_consolidate"] is True

    def test_should_consolidate_at_max_age(self, faq):
        faq.max_age = 0.1  # 100ms
        faq.append("old_item", "test")
        time.sleep(0.15)
        assert faq._should_consolidate() is True

    def test_append_stores_data(self, faq):
        faq.append("test", "fact", {"key": "value"}, ["tag1"])
        entry = faq._queue[0]
        assert entry["label"] == "test"
        assert entry["data"]["key"] == "value"
        assert entry["tags"] == ["tag1"]

    def test_append_records_timestamp(self, faq):
        before = time.time()
        faq.append("timed", "event")
        after = time.time()
        assert before <= faq._queue[0]["appended_at"] <= after


class TestConsolidate:
    def test_consolidate_empty_queue(self, faq):
        result = faq.consolidate()
        assert result["status"] == "empty"
        assert result["consolidated"] == 0

    def test_consolidate_adds_to_graph(self, faq):
        faq.append("alpha", "concept")
        faq.append("beta", "concept")
        result = faq.consolidate()
        assert result["status"] == "consolidated"
        assert result["nodes_added"] == 2
        # Verify in base graph
        nodes = faq.graph.search_by_label("alpha")
        assert len(nodes) >= 1

    def test_consolidate_clears_queue(self, faq):
        faq.append("x", "test")
        faq.consolidate()
        assert len(faq._queue) == 0

    def test_consolidate_increments_counter(self, faq):
        faq.append("a", "test")
        faq.consolidate()
        faq.append("b", "test")
        faq.consolidate()
        assert faq._consolidation_count == 2

    def test_consolidate_with_dedup(self, faq):
        # Add a node to graph first
        faq.graph.add("duplicate", "concept")
        # Now queue same label
        faq.append("duplicate", "concept")
        faq.append("unique", "concept")
        result = faq.consolidate(deduplicate=True)
        assert result["duplicates_skipped"] == 1
        assert result["nodes_added"] == 1

    def test_consolidate_without_dedup(self, faq):
        faq.graph.add("duplicate", "concept")
        faq.append("duplicate", "concept")
        result = faq.consolidate(deduplicate=False)
        assert result["duplicates_skipped"] == 0
        assert result["nodes_added"] == 1

    def test_consolidate_returns_batch_info(self, faq):
        for i in range(3):
            faq.append(f"item_{i}", "test")
        result = faq.consolidate()
        assert result["batch_size"] == 3
        assert "consolidation_round" in result


class TestMaybeConsolidate:
    def test_maybe_consolidate_below_threshold(self, faq):
        faq.append("x", "test")
        result = faq.maybe_consolidate()
        assert result is None

    def test_maybe_consolidate_at_threshold(self, faq):
        for i in range(5):
            faq.append(f"item_{i}", "test")
        result = faq.maybe_consolidate()
        assert result is not None
        assert result["status"] == "consolidated"

    def test_maybe_consolidate_at_max_age(self, faq):
        faq.max_age = 0.1
        faq.append("old", "test")
        time.sleep(0.15)
        result = faq.maybe_consolidate()
        assert result is not None


class TestFlush:
    def test_flush_consolidates_all(self, faq):
        faq.append("a", "test")
        faq.append("b", "test")
        faq.append("c", "test")
        result = faq.flush()
        assert result["nodes_added"] == 3
        assert len(faq._queue) == 0

    def test_flush_empty_queue(self, faq):
        result = faq.flush()
        assert result["status"] == "empty"


class TestStats:
    def test_initial_stats(self, faq):
        s = faq.stats()
        assert s["pending"] == 0
        assert s["total_appended"] == 0
        assert s["total_consolidated"] == 0
        assert s["consolidation_rounds"] == 0

    def test_stats_after_append(self, faq):
        faq.append("x", "test")
        s = faq.stats()
        assert s["pending"] == 1
        assert s["total_appended"] == 1

    def test_stats_after_consolidate(self, faq):
        faq.append("x", "test")
        faq.consolidate()
        s = faq.stats()
        assert s["pending"] == 0
        assert s["total_appended"] == 1
        assert s["total_consolidated"] == 1
        assert s["consolidation_rounds"] == 1

    def test_stats_oldest_pending_age(self, faq):
        faq.append("first", "test")
        time.sleep(0.05)
        faq.append("second", "test")
        s = faq.stats()
        assert s["oldest_pending_age"] > 0.04


class TestPending:
    def test_pending_empty(self, faq):
        assert faq.pending() == []

    def test_pending_returns_copy(self, faq):
        faq.append("x", "test")
        p = faq.pending()
        assert len(p) == 1
        # Mutating the returned list should not affect the queue
        p.clear()
        assert len(faq._queue) == 1

    def test_pending_after_consolidate(self, faq):
        faq.append("x", "test")
        faq.consolidate()
        assert faq.pending() == []

    def test_pending_preserves_order(self, faq):
        faq.append("first", "test")
        faq.append("second", "test")
        faq.append("third", "test")
        labels = [e["label"] for e in faq.pending()]
        assert labels == ["first", "second", "third"]


class TestDrain:
    def test_drain_returns_entries(self, faq):
        faq.append("a", "test")
        faq.append("b", "test")
        batch = faq.drain()
        assert len(batch) == 2
        assert batch[0]["label"] == "a"

    def test_drain_clears_queue(self, faq):
        faq.append("a", "test")
        faq.drain()
        assert len(faq._queue) == 0
        assert faq._first_append_ts is None

    def test_drain_does_not_write_to_graph(self, faq):
        faq.append("ghost", "test")
        faq.drain()
        # Graph should have no nodes
        assert faq.graph.stats()["nodes"] == 0

    def test_drain_empty_queue(self, faq):
        assert faq.drain() == []

    def test_drain_resets_consolidation_timer(self, faq):
        faq.append("x", "test")
        assert faq._first_append_ts is not None
        faq.drain()
        assert faq._first_append_ts is None


class TestSourcePropagation:
    def test_source_carried_through_consolidation(self, faq):
        faq.append("sourced", "fact", {"text": "hello"}, source="agent_42")
        faq.consolidate()
        node = faq.graph.search_by_label("sourced", limit=1)[0]
        import json
        data = json.loads(node.data) if isinstance(node.data, str) else node.data
        assert data.get("_source") == "agent_42"

    def test_no_source_when_not_provided(self, faq):
        faq.append("plain", "fact")
        faq.consolidate()
        node = faq.graph.search_by_label("plain", limit=1)[0]
        import json
        data = json.loads(node.data) if isinstance(node.data, str) else node.data
        assert "_source" not in data


class TestIntegration:
    def test_hot_then_cold_workflow(self, faq):
        # System-1: rapid appends (no graph mutation)
        for i in range(10):
            faq.append(f"event_{i}", "event")
            # Graph should be empty during hot phase
        assert len(faq._queue) == 10

        # System-2: consolidate
        result = faq.consolidate()
        assert result["nodes_added"] == 10
        assert len(faq._queue) == 0

        # Verify graph has nodes
        node = faq.graph.search_by_label("event_0")
        assert len(node) >= 1

    def test_threshold_triggers_auto_consolidate(self, faq):
        results = []
        for i in range(10):
            r = faq.append(f"item_{i}", "test")
            results.append(r)

        # Items at positions >= threshold should trigger consolidate recommendation
        triggered = [r for r in results if r["should_consolidate"]]
        assert len(triggered) >= 5
