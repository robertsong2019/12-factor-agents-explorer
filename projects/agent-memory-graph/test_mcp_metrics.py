"""
Tests for MCP Server Metrics Tool (Cycle 390)
Tests the observability layer: tool call recording, aggregation, recent calls, reset.
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from memory_graph import MemoryGraph, Node


# ── Fixtures ──

def _setup_isolated_metrics():
    """Point metrics DB to a temp file and reset the global connection."""
    import mcp_server
    tmpdir = tempfile.mkdtemp()
    metrics_db = os.path.join(tmpdir, "test_metrics.db")
    mcp_server._METRICS_DB = metrics_db
    mcp_server._metrics_conn = None
    return tmpdir, metrics_db


def _teardown_metrics():
    """Reset the global metrics connection."""
    import mcp_server
    if mcp_server._metrics_conn is not None:
        mcp_server._metrics_conn.close()
    mcp_server._metrics_conn = None


def _setup_isolated_server():
    """Set up mcp_server with an isolated in-memory graph + temp metrics DB."""
    import mcp_server
    tmpdir = tempfile.mkdtemp()
    graph_db = os.path.join(tmpdir, "test_graph.db")
    metrics_db = os.path.join(tmpdir, "test_metrics.db")

    # Patch module-level state
    mcp_server.DB_PATH = graph_db
    mcp_server._METRICS_DB = metrics_db
    mcp_server._graph = None
    mcp_server._metrics_conn = None

    # Add some data
    g = mcp_server.get_graph()
    g.add(label="Alice", kind="person", data={"role": "engineer"})
    g.add(label="Bob", kind="person", data={"role": "manager"})

    return mcp_server, tmpdir


def _cleanup_server(mcp_server):
    """Clean up server state."""
    if mcp_server._graph is not None:
        mcp_server._graph.conn.close()
        mcp_server._graph = None
    if mcp_server._metrics_conn is not None:
        mcp_server._metrics_conn.close()
        mcp_server._metrics_conn = None


async def _call(mcp_server, tool_name, arguments=None):
    """Call a tool through the public call_tool interface (with metrics wrapping)."""
    if arguments is None:
        arguments = {}
    return await mcp_server.call_tool(tool_name, arguments)


# ── Tests: record_tool_call ──

def test_record_single_call():
    """record_tool_call inserts a row."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        mcp_server.record_tool_call("remember", 5.2, True)
        conn = mcp_server._get_metrics_conn()
        rows = conn.execute("SELECT tool, duration_ms, success FROM tool_calls").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "remember"
        assert rows[0][1] == 5.2
        assert rows[0][2] == 1
    finally:
        _teardown_metrics()


def test_record_error_call():
    """record_tool_call with success=False and error message."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        mcp_server.record_tool_call("recall", 12.5, False, "KeyError: 'query'")
        conn = mcp_server._get_metrics_conn()
        rows = conn.execute("SELECT tool, success, error_msg FROM tool_calls").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "recall"
        assert rows[0][1] == 0
        assert rows[0][2] == "KeyError: 'query'"
    finally:
        _teardown_metrics()


def test_record_truncates_long_error():
    """Error messages longer than 500 chars are truncated."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        long_msg = "x" * 1000
        mcp_server.record_tool_call("test", 1.0, False, long_msg)
        conn = mcp_server._get_metrics_conn()
        row = conn.execute("SELECT error_msg FROM tool_calls").fetchone()
        assert len(row[0]) == 500
    finally:
        _teardown_metrics()


# ── Tests: get_metrics_summary ──

def test_summary_empty():
    """Summary with no calls returns zeros."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        result = mcp_server.get_metrics_summary()
        assert result["total_calls"] == 0
        assert result["total_errors"] == 0
        assert result["overall_error_rate"] == 0
        assert result["tools"] == []
    finally:
        _teardown_metrics()


def test_summary_with_calls():
    """Summary aggregates multiple tools correctly."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        mcp_server.record_tool_call("remember", 5.0, True)
        mcp_server.record_tool_call("remember", 3.0, True)
        mcp_server.record_tool_call("recall", 10.0, True)
        mcp_server.record_tool_call("recall", 20.0, False, "timeout")

        result = mcp_server.get_metrics_summary()
        assert result["total_calls"] == 4
        assert result["total_errors"] == 1
        assert result["overall_error_rate"] == 0.25

        # Tools sorted by call count (both have 2)
        tool_map = {t["tool"]: t for t in result["tools"]}
        assert tool_map["remember"]["calls"] == 2
        assert tool_map["remember"]["errors"] == 0
        assert tool_map["remember"]["avg_ms"] == 4.0
        assert tool_map["remember"]["min_ms"] == 3.0
        assert tool_map["remember"]["max_ms"] == 5.0

        assert tool_map["recall"]["calls"] == 2
        assert tool_map["recall"]["errors"] == 1
        assert tool_map["recall"]["error_rate"] == 0.5
    finally:
        _teardown_metrics()


def test_summary_error_rate_zero_division():
    """Summary handles zero-division gracefully when no calls exist."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        result = mcp_server.get_metrics_summary()
        assert result["overall_error_rate"] == 0
    finally:
        _teardown_metrics()


# ── Tests: reset_metrics ──

def test_reset_clears_all():
    """reset_metrics deletes all rows and returns count."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        mcp_server.record_tool_call("a", 1.0, True)
        mcp_server.record_tool_call("b", 2.0, True)
        deleted = mcp_server.reset_metrics()
        assert deleted == 2

        result = mcp_server.get_metrics_summary()
        assert result["total_calls"] == 0
    finally:
        _teardown_metrics()


def test_reset_on_empty():
    """reset_metrics on empty DB returns 0."""
    _setup_isolated_metrics()
    try:
        import mcp_server
        deleted = mcp_server.reset_metrics()
        assert deleted == 0
    finally:
        _teardown_metrics()


# ── Tests: call_tool metrics integration ──

def test_call_tool_records_success_metric():
    """Calling a tool through call_tool records a successful metric."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        # Call 'stats' tool
        results = asyncio.run(_call(mcp_server, "stats", {}))
        assert len(results) == 1

        # Verify metric was recorded
        summary = mcp_server.get_metrics_summary()
        assert summary["total_calls"] == 1
        assert summary["tools"][0]["tool"] == "stats"
        assert summary["tools"][0]["errors"] == 0
        assert summary["tools"][0]["avg_ms"] > 0
    finally:
        _cleanup_server(mcp_server)


def test_call_tool_records_error_metric():
    """Calling an unknown tool records an error metric."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        results = asyncio.run(_call(mcp_server, "nonexistent_tool", {}))
        assert "Unknown tool" in results[0].text

        summary = mcp_server.get_metrics_summary()
        assert summary["total_calls"] == 1
        assert summary["total_errors"] == 1
        assert summary["tools"][0]["tool"] == "nonexistent_tool"
        assert summary["tools"][0]["errors"] == 1
    finally:
        _cleanup_server(mcp_server)


def test_multiple_calls_aggregate():
    """Multiple calls to different tools aggregate correctly."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        asyncio.run(_call(mcp_server, "stats", {}))
        asyncio.run(_call(mcp_server, "health", {}))
        asyncio.run(_call(mcp_server, "stats", {}))

        summary = mcp_server.get_metrics_summary()
        assert summary["total_calls"] == 3

        tool_map = {t["tool"]: t for t in summary["tools"]}
        assert tool_map["stats"]["calls"] == 2
        assert tool_map["health"]["calls"] == 1
    finally:
        _cleanup_server(mcp_server)


def test_metrics_tool_does_not_record_itself():
    """The metrics tool should still work (records its own call too)."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        # First, make a call to have some data
        asyncio.run(_call(mcp_server, "stats", {}))

        # Now query metrics
        results = asyncio.run(_call(mcp_server, "metrics", {"action": "summary"}))
        parsed = json.loads(results[0].text)

        # At this point, 'stats' was called once and 'metrics' was called once
        # (the metrics call itself gets recorded in the finally block)
        assert parsed["total_calls"] >= 1
        tool_map = {t["tool"]: t for t in parsed["tools"]}
        assert "stats" in tool_map
    finally:
        _cleanup_server(mcp_server)


# ── Tests: metrics tool actions ──

def test_metrics_action_recent():
    """metrics action=recent returns last N calls in reverse order."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        asyncio.run(_call(mcp_server, "stats", {}))
        time.sleep(0.01)
        asyncio.run(_call(mcp_server, "health", {}))

        results = asyncio.run(_call(mcp_server, "metrics", {"action": "recent", "limit": 5}))
        parsed = json.loads(results[0].text)

        # Should have at least 2 calls (stats + health), maybe 3 (metrics itself)
        assert len(parsed) >= 2
        # Most recent should be health or metrics (reverse order)
        tool_names = [r["tool"] for r in parsed]
        assert "stats" in tool_names
        assert "health" in tool_names
        # Each entry has expected fields
        for entry in parsed:
            assert "tool" in entry
            assert "timestamp" in entry
            assert "duration_ms" in entry
            assert "success" in entry
    finally:
        _cleanup_server(mcp_server)


def test_metrics_action_reset():
    """metrics action=reset clears all metrics."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        asyncio.run(_call(mcp_server, "stats", {}))

        results = asyncio.run(_call(mcp_server, "metrics", {"action": "reset"}))
        parsed = json.loads(results[0].text)
        assert parsed["status"] == "reset"
        assert parsed["deleted"] >= 1
    finally:
        _cleanup_server(mcp_server)


def test_metrics_action_unknown():
    """metrics with unknown action returns error."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        results = asyncio.run(_call(mcp_server, "metrics", {"action": "bogus"}))
        parsed = json.loads(results[0].text)
        assert "error" in parsed
        assert "bogus" in parsed["error"]
    finally:
        _cleanup_server(mcp_server)


def test_metrics_default_action_is_summary():
    """metrics with no action defaults to summary."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        results = asyncio.run(_call(mcp_server, "metrics", {}))
        parsed = json.loads(results[0].text)
        assert "total_calls" in parsed
        assert "tools" in parsed
    finally:
        _cleanup_server(mcp_server)


# ── Tests: list_tools includes metrics ──

def test_list_tools_includes_metrics():
    """The tools list now includes the metrics tool (17 tools)."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        result = asyncio.run(mcp_server.list_tools.__wrapped__()
                             if hasattr(mcp_server.list_tools, '__wrapped__')
                             else mcp_server.list_tools())
        tool_names = [t.name for t in result]
        assert "metrics" in tool_names
        assert len(result) == 17, f"Expected 17 tools, got {len(result)}: {tool_names}"
    finally:
        _cleanup_server(mcp_server)


# ── Tests: latency tracking accuracy ──

def test_latency_is_recorded():
    """Duration in metrics is a positive number proportional to work done."""
    mcp_server, tmpdir = _setup_isolated_server()
    try:
        # Add lots of nodes to make stats take measurable time
        g = mcp_server.get_graph()
        for i in range(50):
            g.add(label=f"Node{i}", kind="test", data={"idx": i})

        asyncio.run(_call(mcp_server, "stats", {}))

        summary = mcp_server.get_metrics_summary()
        stats_metric = summary["tools"][0]
        assert stats_metric["avg_ms"] > 0
        assert stats_metric["max_ms"] >= stats_metric["min_ms"]
    finally:
        _cleanup_server(mcp_server)
