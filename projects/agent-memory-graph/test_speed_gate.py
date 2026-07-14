"""Tests for semantic_speed_gate + selective_filter — Cycle 243.

RoMem-inspired edge volatility detection + Context Engineering selective filter.

semantic_speed_gate: measures how fast a node's neighborhood is changing.
selective_filter: prunes nodes by weight/kind/staleness/quarantine before LLM context.
"""
import json
import time
import pytest
from memory_graph import MemoryGraph


@pytest.fixture
def mg():
    return MemoryGraph()


@pytest.fixture
def connected_graph(mg):
    """Create a graph with nodes of varying edge recency."""
    a = mg.add("alpha", "concept")
    b = mg.add("beta", "concept")
    c = mg.add("gamma", "fact")
    d = mg.add("delta", "event")
    mg.link(a.id, b.id, "related")
    mg.link(a.id, c.id, "supports")
    mg.link(b.id, d.id, "triggers")
    return {"mg": mg, "a": a, "b": b, "c": c, "d": d}


# ─── semantic_speed_gate ────────────────────────────────────────────

class TestSemanticSpeedGate:

    def test_all_recent_edges_give_high_speed(self, connected_graph):
        """Newly created graph: all edges recent → speed ≈ 1.0."""
        mg = connected_graph["mg"]
        a = connected_graph["a"]
        result = mg.semantic_speed_gate(a.id)
        assert result["speed"] == pytest.approx(1.0, abs=0.01)
        assert result["verdict"] == "volatile"
        assert result["edge_count"] == 2
        assert result["recent_edges"] == 2
        assert result["stability"] == pytest.approx(0.0, abs=0.01)

    def test_no_edges_gives_zero_speed(self, mg):
        """Isolated node: speed = 0, verdict = stable."""
        n = mg.add("lonely", "fact")
        result = mg.semantic_speed_gate(n.id)
        assert result["speed"] == 0.0
        assert result["edge_count"] == 0
        assert result["recent_edges"] == 0
        assert result["verdict"] == "stable"
        assert result["stability"] == 1.0

    def test_old_edges_give_low_speed(self, mg):
        """Edges created long ago → low speed."""
        a = mg.add("old source", "concept")
        b = mg.add("old target", "concept")
        mg.link(a.id, b.id, "ancient")
        # Backdate clock_log entries
        old_time = time.time() - 72 * 3600  # 3 days ago
        mg.conn.execute(
            "UPDATE clock_log SET wall_time=? WHERE op='link'", (old_time,)
        )
        mg.conn.commit()
        result = mg.semantic_speed_gate(a.id, window_hours=24.0)
        assert result["speed"] == pytest.approx(0.0, abs=0.01)
        assert result["verdict"] == "stable"
        assert result["edge_count"] == 1
        assert result["recent_edges"] == 0

    def test_partial_recency(self, mg):
        """Mix of recent and old edges → intermediate speed."""
        a = mg.add("hub", "concept")
        # First edge (will be backdated)
        b1 = mg.add("old neighbor", "concept")
        mg.link(a.id, b1.id, "old_rel")
        # Backdate first link
        old = time.time() - 48 * 3600
        # Get the lamport of the first link to backdate just it
        link_logs = mg.conn.execute(
            "SELECT lamport FROM clock_log WHERE op='link' ORDER BY lamport"
        ).fetchall()
        first_link_lamport = link_logs[0]["lamport"]
        mg.conn.execute(
            "UPDATE clock_log SET wall_time=? WHERE lamport=?", (old, first_link_lamport)
        )
        mg.conn.commit()
        # Second edge (recent)
        b2 = mg.add("new neighbor", "concept")
        mg.link(a.id, b2.id, "new_rel")
        result = mg.semantic_speed_gate(a.id, window_hours=24.0)
        assert 0.3 < result["speed"] < 0.7
        assert result["edge_count"] == 2
        assert result["recent_edges"] == 1

    def test_velocity_calculation(self, mg):
        """Velocity = recent_edges / window_hours."""
        a = mg.add("hub", "concept")
        b = mg.add("neighbor", "concept")
        mg.link(a.id, b.id, "rel")
        result = mg.semantic_speed_gate(a.id, window_hours=24.0)
        # 1 recent edge / 24 hours ≈ 0.0417 edges/hour
        assert result["velocity"] == pytest.approx(1 / 24, abs=0.01)

    def test_verdict_thresholds(self, mg):
        """Verdict mapping: volatile >= 0.6, active >= 0.25, stable < 0.25."""
        a = mg.add("node", "fact")
        b = mg.add("b", "fact")
        mg.link(a.id, b.id, "rel")
        # All edges recent → volatile (speed = 1.0)
        r = mg.semantic_speed_gate(a.id)
        assert r["verdict"] == "volatile"

        # Backdate → stable
        old = time.time() - 100 * 3600
        mg.conn.execute("UPDATE clock_log SET wall_time=? WHERE op='link'", (old,))
        mg.conn.commit()
        r2 = mg.semantic_speed_gate(a.id, window_hours=24.0)
        assert r2["verdict"] == "stable"

    def test_weighted_speed(self, mg):
        """Higher-weight recent edges should contribute more to speed."""
        a = mg.add("hub", "concept")
        b1 = mg.add("low w", "concept")
        b2 = mg.add("high w", "concept")
        # Old low-weight edge
        mg.link(a.id, b1.id, "weak", weight=0.1)
        old = time.time() - 48 * 3600
        link_logs = mg.conn.execute(
            "SELECT lamport FROM clock_log WHERE op='link' ORDER BY lamport"
        ).fetchall()
        mg.conn.execute(
            "UPDATE clock_log SET wall_time=? WHERE lamport=?",
            (old, link_logs[0]["lamport"])
        )
        mg.conn.commit()
        # Recent high-weight edge
        mg.link(a.id, b2.id, "strong", weight=0.9)
        result = mg.semantic_speed_gate(a.id, window_hours=24.0)
        # recent_weight=0.9, total_weight=1.0 → speed=0.9
        assert result["speed"] == pytest.approx(0.9, abs=0.05)

    def test_not_found_node(self, mg):
        """Non-existent node returns not_found flag."""
        result = mg.semantic_speed_gate("nonexistent-id")
        assert result.get("not_found") is True
        assert result["speed"] == 0.0

    def test_custom_window_hours(self, mg):
        """Larger window should include older edges."""
        a = mg.add("hub", "concept")
        b = mg.add("neighbor", "concept")
        mg.link(a.id, b.id, "rel")
        # Backdate 12 hours ago
        semi_old = time.time() - 12 * 3600
        mg.conn.execute("UPDATE clock_log SET wall_time=? WHERE op='link'", (semi_old,))
        mg.conn.commit()
        # 24h window → recent
        r24 = mg.semantic_speed_gate(a.id, window_hours=24.0)
        assert r24["recent_edges"] == 1
        # 6h window → not recent
        r6 = mg.semantic_speed_gate(a.id, window_hours=6.0)
        assert r6["recent_edges"] == 0

    def test_query_time_override(self, mg):
        """Using a future query_time should make all edges seem recent."""
        a = mg.add("hub", "concept")
        b = mg.add("neighbor", "concept")
        mg.link(a.id, b.id, "rel")
        future = time.time() + 100 * 3600
        result = mg.semantic_speed_gate(a.id, query_time=future, window_hours=200.0)
        assert result["speed"] == pytest.approx(1.0, abs=0.01)


# ─── speed_gate_batch ───────────────────────────────────────────────

class TestSpeedGateBatch:

    def test_batch_returns_all_nodes(self, connected_graph):
        """Batch without node_ids returns all non-quarantined nodes."""
        mg = connected_graph["mg"]
        results = mg.speed_gate_batch()
        assert len(results) == 4  # a, b, c, d
        # Sorted by speed descending
        speeds = [r["speed"] for r in results]
        assert speeds == sorted(speeds, reverse=True)

    def test_batch_with_specific_ids(self, connected_graph):
        """Batch with explicit node_ids returns only those."""
        mg = connected_graph["mg"]
        a = connected_graph["a"]
        b = connected_graph["b"]
        results = mg.speed_gate_batch([a.id, b.id])
        assert len(results) == 2
        ids = {r["node_id"] for r in results}
        assert ids == {a.id, b.id}

    def test_batch_min_speed_filter(self, mg):
        """min_speed filters out low-speed nodes."""
        a = mg.add("hub", "fact")
        b = mg.add("isolated", "fact")
        mg.link(a.id, b.id, "rel")
        # a has edges → speed > 0; b also has edges actually
        # Let's add a truly isolated node
        c = mg.add("lonely", "fact")
        results = mg.speed_gate_batch(min_speed=0.01)
        ids = {r["node_id"] for r in results}
        assert a.id in ids
        assert b.id in ids
        assert c.id not in ids  # no edges → speed 0

    def test_batch_includes_label_and_kind(self, connected_graph):
        """Each result includes label and kind for convenience."""
        mg = connected_graph["mg"]
        a = connected_graph["a"]
        results = mg.speed_gate_batch([a.id])
        assert results[0]["label"] == "alpha"
        assert results[0]["kind"] == "concept"

    def test_batch_empty_input(self, mg):
        """Empty node_ids returns empty list."""
        assert mg.speed_gate_batch([]) == []

    def test_batch_skips_nonexistent(self, mg):
        """Non-existent node_ids are silently skipped."""
        a = mg.add("real", "fact")
        results = mg.speed_gate_batch([a.id, "fake-id"])
        assert len(results) == 1
        assert results[0]["node_id"] == a.id


# ─── volatile_nodes ─────────────────────────────────────────────────

class TestVolatileNodes:

    def test_returns_most_volatile(self, connected_graph):
        """volatile_nodes returns sorted list with limit."""
        mg = connected_graph["mg"]
        results = mg.volatile_nodes(min_speed=0.5, limit=2)
        assert len(results) <= 2
        for r in results:
            assert r["speed"] >= 0.5

    def test_limit_respected(self, mg):
        """limit parameter truncates results."""
        for i in range(5):
            n = mg.add(f"node-{i}", "fact")
            mg.link(n.id, mg.add(f"target-{i}", "fact").id, "rel")
        results = mg.volatile_nodes(limit=3)
        assert len(results) <= 3

    def test_no_volatile_returns_empty(self, mg):
        """With high min_speed and no edges, returns empty."""
        mg.add("lonely", "fact")
        results = mg.volatile_nodes(min_speed=0.9)
        assert results == []


# ─── selective_filter ───────────────────────────────────────────────

class TestSelectiveFilter:

    def test_min_weight_filter(self, mg):
        """Nodes below min_weight are filtered out."""
        a = mg.add("heavy", "fact")
        b = mg.add("light", "fact")
        mg.update_node(a.id, weight=0.9)
        mg.update_node(b.id, weight=0.1)
        result = mg.selective_filter([a.id, b.id], min_weight=0.5)
        assert a.id in result
        assert b.id not in result

    def test_max_weight_filter(self, mg):
        """Nodes above max_weight are filtered out."""
        a = mg.add("heavy", "fact")
        b = mg.add("light", "fact")
        mg.update_node(a.id, weight=0.9)
        mg.update_node(b.id, weight=0.1)
        result = mg.selective_filter([a.id, b.id], max_weight=0.5)
        assert a.id not in result
        assert b.id in result

    def test_kinds_whitelist(self, mg):
        """Only specified kinds pass through."""
        a = mg.add("fact node", "fact")
        b = mg.add("concept node", "concept")
        c = mg.add("event node", "event")
        result = mg.selective_filter([a.id, b.id, c.id], kinds=["fact", "event"])
        assert a.id in result
        assert b.id not in result
        assert c.id in result

    def test_exclude_kinds_blacklist(self, mg):
        """Excluded kinds are filtered out."""
        a = mg.add("fact node", "fact")
        b = mg.add("concept node", "concept")
        result = mg.selective_filter([a.id, b.id], exclude_kinds=["concept"])
        assert a.id in result
        assert b.id not in result

    def test_exclude_quarantined(self, mg):
        """Quarantined nodes are excluded by default."""
        a = mg.add("clean", "fact")
        b = mg.add("dirty", "fact")
        mg.conn.execute("UPDATE nodes SET quarantined=1 WHERE id=?", (b.id,))
        mg.conn.commit()
        result = mg.selective_filter([a.id, b.id])
        assert a.id in result
        assert b.id not in result

    def test_include_quarantined(self, mg):
        """exclude_quarantined=False includes them."""
        a = mg.add("clean", "fact")
        b = mg.add("dirty", "fact")
        mg.conn.execute("UPDATE nodes SET quarantined=1 WHERE id=?", (b.id,))
        mg.conn.commit()
        result = mg.selective_filter([a.id, b.id], exclude_quarantined=False)
        assert a.id in result
        assert b.id in result

    def test_max_staleness_filter(self, mg):
        """Nodes with staleness above threshold are dropped."""
        a = mg.add("fresh", "fact")
        b = mg.add("stale", "fact")
        # Make b very stale (both created and accessed)
        old = time.time() - 500 * 3600
        mg.conn.execute(
            "UPDATE nodes SET accessed=?, created=? WHERE id=?", (old, old, b.id)
        )
        mg.conn.commit()
        result = mg.selective_filter([a.id, b.id], max_staleness=0.5)
        assert a.id in result
        assert b.id not in result

    def test_require_fresh(self, mg):
        """require_fresh only keeps staleness < 0.3."""
        a = mg.add("fresh", "fact")
        b = mg.add("stale", "fact")
        old = time.time() - 500 * 3600
        mg.conn.execute("UPDATE nodes SET accessed=? WHERE id=?", (old, b.id))
        mg.conn.commit()
        result = mg.selective_filter([a.id, b.id], require_fresh=True)
        assert a.id in result
        assert b.id not in result

    def test_limit_truncation(self, mg):
        """limit parameter truncates the output."""
        ids = []
        for i in range(5):
            n = mg.add(f"node-{i}", "fact")
            ids.append(n.id)
        result = mg.selective_filter(ids, limit=3)
        assert len(result) == 3

    def test_preserves_input_order(self, mg):
        """Output order matches input order (after filtering)."""
        ids = []
        for i in range(5):
            n = mg.add(f"node-{i}", "fact")
            ids.append(n.id)
        result = mg.selective_filter(ids)
        assert result == ids  # all pass, order preserved

    def test_empty_input(self, mg):
        """Empty list returns empty list."""
        assert mg.selective_filter([]) == []

    def test_nonexistent_id_skipped(self, mg):
        """Non-existent IDs are silently dropped."""
        a = mg.add("real", "fact")
        result = mg.selective_filter([a.id, "fake-id"])
        assert result == [a.id]

    def test_combined_filters(self, mg):
        """Multiple filters applied simultaneously."""
        a = mg.add("keep", "fact")
        b = mg.add("drop_low_w", "fact")
        c = mg.add("drop_wrong_kind", "event")
        d = mg.add("drop_quarantined", "fact")
        mg.update_node(a.id, weight=0.8)
        mg.update_node(b.id, weight=0.1)
        mg.conn.execute("UPDATE nodes SET quarantined=1 WHERE id=?", (d.id,))
        mg.conn.commit()
        result = mg.selective_filter(
            [a.id, b.id, c.id, d.id],
            min_weight=0.5,
            kinds=["fact"],
        )
        assert result == [a.id]


# ─── selective_filter_report ────────────────────────────────────────

class TestSelectiveFilterReport:

    def test_basic_report(self, mg):
        """Report has correct counts."""
        a = mg.add("keep", "fact")
        b = mg.add("drop", "event")
        report = mg.selective_filter_report(
            [a.id, b.id], kinds=["fact"]
        )
        assert report["input_count"] == 2
        assert report["output_count"] == 1
        assert report["dropped"] == 1
        assert report["drop_rate"] == 0.5
        assert report["filtered_ids"] == [a.id]

    def test_all_filtered_report(self, mg):
        """All nodes dropped → drop_rate = 1.0."""
        a = mg.add("a", "event")
        report = mg.selective_filter_report([a.id], kinds=["fact"])
        assert report["output_count"] == 0
        assert report["drop_rate"] == 1.0

    def test_none_filtered_report(self, mg):
        """No nodes dropped → drop_rate = 0.0."""
        a = mg.add("a", "fact")
        report = mg.selective_filter_report([a.id])
        assert report["output_count"] == 1
        assert report["drop_rate"] == 0.0

    def test_empty_input_report(self, mg):
        """Empty input → zero counts."""
        report = mg.selective_filter_report([])
        assert report["input_count"] == 0
        assert report["output_count"] == 0
        assert report["drop_rate"] == 0.0

    def test_passes_kwargs_to_filter(self, mg):
        """Report forwards kwargs to selective_filter."""
        a = mg.add("heavy", "fact")
        b = mg.add("light", "fact")
        mg.update_node(a.id, weight=0.9)
        mg.update_node(b.id, weight=0.1)
        report = mg.selective_filter_report([a.id, b.id], min_weight=0.5)
        assert report["filtered_ids"] == [a.id]
