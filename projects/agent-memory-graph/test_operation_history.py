"""Tests for get_operation_history() — Cycle 324.

MemOps-compatible operation-level audit trail.
Maps clock_log events into 6-category taxonomy: remember/link/update/forget/reflect/retrieve.
"""
import time
import pytest
from memory_graph import MemoryGraph


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def graph_with_ops():
    """Graph with varied operations for testing."""
    mg = MemoryGraph()
    a = mg.add("Alice", kind="entity")
    b = mg.add("Bob", kind="entity")
    mg.link(a.id, b.id, "knows", weight=0.9)
    c = mg.add("Coding", kind="skill")
    mg.link(a.id, c.id, "has_skill", weight=0.8)
    mg.link(b.id, c.id, "has_skill", weight=0.6)
    return mg


@pytest.fixture
def empty_graph():
    return MemoryGraph()


# ─── Structure tests ──────────────────────────────────────────────

class TestStructure:
    def test_returns_dict(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        assert isinstance(r, dict)

    def test_has_required_keys(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        for key in ("operations", "total", "summary", "time_range",
                     "limit", "offset"):
            assert key in r, f"Missing key: {key}"

    def test_operations_is_list(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        assert isinstance(r["operations"], list)

    def test_summary_has_by_type(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        assert "by_type" in r["summary"]
        assert isinstance(r["summary"]["by_type"], dict)


# ─── MemOps mapping tests ─────────────────────────────────────────

class TestMemOpsMapping:
    def test_add_mapped_to_remember(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(operation_type="remember")
        assert r["total"] == 3  # 3 add() calls

    def test_link_mapped_to_link(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(operation_type="link")
        assert r["total"] == 3  # 3 link() calls

    def test_each_op_has_memops_type(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        for op in r["operations"]:
            assert "memops_type" in op
            assert op["memops_type"] in (
                "remember", "link", "update", "forget", "reflect", "retrieve", "other"
            )

    def test_all_categories_present(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        cats = set(r["summary"]["by_type"].keys())
        assert "remember" in cats
        assert "link" in cats

    def test_unknown_op_mapped_to_other(self):
        """Unknown ops should map to 'other'."""
        mg = MemoryGraph()
        # Insert a fake unknown op
        mg._tick("unknown_op", "fake_node", {"test": True})
        r = mg.get_operation_history()
        assert "other" in r["summary"]["by_type"]


# ─── Filtering tests ──────────────────────────────────────────────

class TestFiltering:
    def test_filter_by_operation_type(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(operation_type="remember")
        for op in r["operations"]:
            assert op["memops_type"] == "remember"

    def test_filter_by_raw_op_name(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(operation_type="add")
        assert r["total"] >= 3
        for op in r["operations"]:
            assert op["op"] == "add"

    def test_filter_by_node_id(self, graph_with_ops):
        nodes = graph_with_ops.conn.execute("SELECT id FROM nodes LIMIT 1").fetchall()
        if nodes:
            nid = nodes[0]["id"]
            r = graph_with_ops.get_operation_history(node_id=nid)
            for op in r["operations"]:
                assert op["node_id"] == nid

    def test_filter_by_time_range(self, graph_with_ops):
        now = time.time()
        # Future window — should be empty
        r = graph_with_ops.get_operation_history(start_time=now + 100)
        assert r["total"] == 0

    def test_filter_by_past_time(self, graph_with_ops):
        now = time.time()
        # All ops happened just before now
        r = graph_with_ops.get_operation_history(end_time=now)
        assert r["total"] > 0

    def test_combined_filters(self, graph_with_ops):
        nodes = graph_with_ops.conn.execute("SELECT id FROM nodes LIMIT 1").fetchall()
        nid = nodes[0]["id"] if nodes else None
        r = graph_with_ops.get_operation_history(
            operation_type="remember", node_id=nid)
        for op in r["operations"]:
            assert op["memops_type"] == "remember"
            assert op["node_id"] == nid


# ─── Pagination tests ─────────────────────────────────────────────

class TestPagination:
    def test_limit(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(limit=2)
        assert len(r["operations"]) <= 2
        # Total should still reflect all matching
        assert r["total"] >= 5

    def test_offset(self, graph_with_ops):
        r1 = graph_with_ops.get_operation_history(limit=3, offset=0)
        r2 = graph_with_ops.get_operation_history(limit=3, offset=1)
        # Second page should skip first entry
        if len(r1["operations"]) > 1 and len(r2["operations"]) > 0:
            assert r1["operations"][0]["lamport"] != r2["operations"][0]["lamport"]

    def test_offset_beyond_end(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(offset=9999)
        assert len(r["operations"]) == 0
        assert r["total"] >= 0

    def test_default_limit_100(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        assert r["limit"] == 100


# ─── Grouping tests ───────────────────────────────────────────────

class TestGrouping:
    def test_group_by_type(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(group_by="type")
        assert "grouped" in r
        for cat, ops in r["grouped"].items():
            for op in ops:
                assert op["memops_type"] == cat

    def test_group_by_time(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(group_by="time")
        assert "grouped" in r
        # All ops are in the same second, so same hour bucket
        assert len(r["grouped"]) >= 1

    def test_group_none_no_grouped_key(self, graph_with_ops):
        r = graph_with_ops.get_operation_history(group_by="none")
        assert "grouped" not in r


# ─── Summary tests ────────────────────────────────────────────────

class TestSummary:
    def test_summary_total_matches(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        assert r["summary"]["total_ops"] == r["total"]

    def test_by_type_counts_correct(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        by_type = r["summary"]["by_type"]
        total_from_type = sum(by_type.values())
        # Operations returned may be < total due to limit, but by_type
        # only counts returned operations
        assert total_from_type == len(r["operations"])

    def test_categories_sorted(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        cats = r["summary"]["categories"]
        assert cats == sorted(cats)


# ─── Time range tests ─────────────────────────────────────────────

class TestTimeRange:
    def test_time_range_populated(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        assert r["time_range"]["earliest"] is not None
        assert r["time_range"]["latest"] is not None
        assert r["time_range"]["earliest"] <= r["time_range"]["latest"]

    def test_empty_graph_time_range(self, empty_graph):
        r = empty_graph.get_operation_history()
        assert r["time_range"]["earliest"] is None
        assert r["time_range"]["latest"] is None

    def test_timestamp_iso_present(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        for op in r["operations"]:
            assert op.get("timestamp_iso") is not None


# ─── Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_graph(self, empty_graph):
        r = empty_graph.get_operation_history()
        assert r["total"] == 0
        assert len(r["operations"]) == 0
        assert r["summary"]["total_ops"] == 0

    def test_single_operation(self):
        mg = MemoryGraph()
        mg.add("Lonely")
        r = mg.get_operation_history()
        assert r["total"] == 1
        assert r["operations"][0]["op"] == "add"
        assert r["operations"][0]["memops_type"] == "remember"

    def test_operations_ordered_by_lamport_desc(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        lamports = [op["lamport"] for op in r["operations"]]
        assert lamports == sorted(lamports, reverse=True)


# ─── Consistency ──────────────────────────────────────────────────

class TestConsistency:
    def test_idempotent(self, graph_with_ops):
        r1 = graph_with_ops.get_operation_history()
        r2 = graph_with_ops.get_operation_history()
        assert r1["total"] == r2["total"]
        assert len(r1["operations"]) == len(r2["operations"])

    def test_details_parsed_as_dict(self, graph_with_ops):
        r = graph_with_ops.get_operation_history()
        for op in r["operations"]:
            assert isinstance(op["details"], dict)
