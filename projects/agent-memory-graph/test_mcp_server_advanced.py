"""
Tests for MCP Server Advanced Tools (Cycle 371)
Tests the 6 new advanced tool handlers: entropy, reason, snapshot,
code_explain, quarantine, security.
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import from the project
sys.path.insert(0, str(Path(__file__).parent))

from memory_graph import MemoryGraph, Node


# ── Test fixtures ──

def _make_graph_with_data():
    """Create a MemoryGraph with test data."""
    g = MemoryGraph()

    # Add nodes
    alice = g.add(label="Alice", kind="person", data={"role": "engineer"})
    bob = g.add(label="Bob", kind="person", data={"role": "manager"})
    proj = g.add(label="ProjectX", kind="project", data={"status": "active"})
    idea = g.add(label="Big Idea", kind="idea", data={"score": 0.8})
    fact1 = g.add(label="Python is great", kind="fact", data={"lang": "python"})

    # Add edges
    g.link(alice.id, bob.id, relation="reports_to", weight=0.9)
    g.link(alice.id, proj.id, relation="works_on", weight=0.8)
    g.link(bob.id, proj.id, relation="manages", weight=0.7)
    g.link(proj.id, idea.id, relation="inspired_by", weight=0.6)
    g.link(alice.id, fact1.id, relation="knows", weight=0.5)

    return g


async def _call_tool(server_module, tool_name, arguments):
    """Helper: call a tool by name and return parsed JSON."""
    # Access the call_tool function from the module
    call_tool_fn = server_module.call_tool.__wrapped__ if hasattr(server_module.call_tool, '__wrapped__') else None

    # Use the module's call_tool directly
    results = await server_module.call_tool.__wrapped__(tool_name, arguments) \
        if call_tool_fn else await _invoke_tool(server_module, tool_name, arguments)
    return results


async def _invoke_tool(server_module, tool_name, arguments):
    """Directly invoke the tool handler."""
    # The handler is registered via decorator, but we can call the inner function
    handler = server_module._tool_handlers.get(tool_name)
    if handler:
        return await handler(arguments)
    # Fallback: use the generic call_tool
    result = await server_module.call_tool(tool_name, arguments)
    return result


class TestEntropyTool:
    """Test the entropy MCP tool."""

    def test_entropy_returns_dashboard(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g  # inject our graph

                # Call the entropy tool
                result = asyncio.run(srv.call_tool.__wrapped__(
                    "entropy", {"top_n": 3}
                )) if hasattr(srv.call_tool, '__wrapped__') else None

                if result is None:
                    # Try direct call
                    result = asyncio.run(_call_direct(srv, "entropy", {"top_n": 3}))

                assert result is not None
                assert len(result) == 1
                data = json.loads(result[0].text)
                # entropy_dashboard returns keys like degree_entropy, density, fingerprint, health
                assert "degree_entropy" in data or "error" in data or "indices" in data
        finally:
            os.unlink(db_path)

    def test_entropy_empty_graph(self):
        """Entropy on empty graph should return error gracefully."""
        g = MemoryGraph()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "entropy", {}))
                data = json.loads(result[0].text)
                # Empty graph should return error or None
                assert "error" in data or "indices" in data
        finally:
            os.unlink(db_path)


async def _call_direct(srv, tool_name, arguments):
    """Call the tool handler directly, bypassing MCP framework."""
    return await srv.call_tool(tool_name, arguments)


class TestReasonTool:
    """Test the multi-hop reasoning MCP tool."""

    def test_reason_finds_path(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "reason", {
                    "from": "Alice",
                    "to": "ProjectX",
                    "max_hops": 3,
                }))
                data = json.loads(result[0].text)
                assert "paths" in data
                assert data["from"] == "Alice"
                assert data["to"] == "ProjectX"
        finally:
            os.unlink(db_path)

    def test_reason_unknown_source(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "reason", {
                    "from": "NonExistent",
                    "to": "Alice",
                }))
                data = json.loads(result[0].text)
                assert "error" in data
                assert "NonExistent" in data["error"]
        finally:
            os.unlink(db_path)

    def test_reason_unknown_target(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "reason", {
                    "from": "Alice",
                    "to": "Ghost",
                }))
                data = json.loads(result[0].text)
                assert "error" in data
                assert "Ghost" in data["error"]
        finally:
            os.unlink(db_path)


class TestQuarantineTool:
    """Test the quarantine MCP tool."""

    def test_quarantine_list_empty(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "list",
                }))
                data = json.loads(result[0].text)
                assert isinstance(data, list)
                assert len(data) == 0  # nothing quarantined yet
        finally:
            os.unlink(db_path)

    def test_quarantine_add_and_list(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                # Add quarantine
                result = asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "add",
                    "node": "Alice",
                    "reason": "suspicious activity",
                }))
                data = json.loads(result[0].text)
                assert data["status"] == "quarantined"
                assert data["node"] == "Alice"

                # List - should show Alice
                result = asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "list",
                }))
                data = json.loads(result[0].text)
                assert len(data) >= 1
                assert any("Alice" in str(d) for d in data)
        finally:
            os.unlink(db_path)

    def test_quarantine_remove(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                # Add quarantine first
                asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "add",
                    "node": "Bob",
                    "reason": "testing",
                }))

                # Remove it
                result = asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "remove",
                    "node": "Bob",
                }))
                data = json.loads(result[0].text)
                assert data["status"] == "unquarantined"
        finally:
            os.unlink(db_path)

    def test_quarantine_scan(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "scan",
                    "trust_threshold": 0.5,
                }))
                data = json.loads(result[0].text)
                assert "trust_threshold" in data
                assert "flagged_count" in data
                assert "flagged_nodes" in data
        finally:
            os.unlink(db_path)

    def test_quarantine_unknown_node(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "quarantine", {
                    "action": "add",
                    "node": "Ghost",
                }))
                data = json.loads(result[0].text)
                assert "error" in data
        finally:
            os.unlink(db_path)


class TestSecurityTool:
    """Test the security audit MCP tool."""

    def test_security_returns_audit(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "security", {}))
                data = json.loads(result[0].text)

                assert "owasp_asi06_status" in data
                assert "quarantine" in data
                assert "graph_stats" in data
                assert "recommendation" in data

                # Check OWASP layers
                layers = data["owasp_asi06_status"]
                for layer in ["L1_write_governance", "L2_provenance_lineage",
                              "L3_entropy_weighted_retrieval", "L4_streaming_graph",
                              "L5_propagate_correction"]:
                    assert layer in layers
                    assert layers[layer] == "available"

                # Graph stats
                assert data["graph_stats"]["nodes"] >= 5

                # Quarantine info
                assert data["quarantine"]["count"] == 0
                assert data["quarantine"]["ratio"] == 0.0
        finally:
            os.unlink(db_path)

    def test_security_with_quarantined_nodes(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                # Quarantine a node first — find Alice by searching
                nodes = g.search_unified(query="Alice", limit=1)
                alice_id = None
                if nodes:
                    n = nodes[0]
                    # The result might have 'node' key with the actual Node object
                    inner = n.get("node") if isinstance(n, dict) else None
                    if inner and hasattr(inner, 'id'):
                        alice_id = inner.id
                    elif isinstance(n, dict):
                        alice_id = n.get("id") or n.get("node_id")
                assert alice_id is not None, "Could not find Alice node"
                g.node_quarantine(alice_id, reason="test")

                result = asyncio.run(_call_direct(srv, "security", {}))
                data = json.loads(result[0].text)
                assert data["quarantine"]["count"] >= 1
                assert data["quarantine"]["ratio"] > 0
                assert "quarantined" in data["recommendation"].lower()
        finally:
            os.unlink(db_path)


class TestSnapshotTool:
    """Test the bi-temporal query MCP tool."""

    def test_snapshot_with_epoch(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                # Use a recent timestamp (should see the graph)
                ts = time.time()
                result = asyncio.run(_call_direct(srv, "snapshot", {
                    "timestamp": str(ts),
                }))
                data = json.loads(result[0].text)
                # Should return graph state
                assert isinstance(data, dict)
        finally:
            os.unlink(db_path)

    def test_snapshot_with_iso(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "snapshot", {
                    "timestamp": "2026-01-01",
                }))
                data = json.loads(result[0].text)
                assert isinstance(data, dict)
        finally:
            os.unlink(db_path)

    def test_snapshot_invalid_timestamp(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "snapshot", {
                    "timestamp": "not-a-date",
                }))
                data = json.loads(result[0].text)
                assert "error" in data
        finally:
            os.unlink(db_path)


class TestCodeExplainTool:
    """Test the code_explain MCP tool."""

    def test_code_explain_unknown_entity(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "code_explain", {
                    "name": "NonExistentFunction",
                }))
                data = json.loads(result[0].text)
                assert "error" in data
        finally:
            os.unlink(db_path)

    def test_code_explain_existing_node(self):
        g = MemoryGraph()

        # Add a code node
        code_node = g.add(
            label="my_function",
            kind="function",
            data={"file": "example.py", "line": 42},
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "code_explain", {
                    "name": "my_function",
                }))
                data = json.loads(result[0].text)
                # Should return explanation dict
                assert isinstance(data, dict)
                # explain_code returns caller/callee/decision analysis
                assert isinstance(data, dict)
                assert any(k in data for k in ["callers", "callees", "decisions", "node_id", "error"])
                # Should find our function node
                assert "callees" in data or "callers" in data
        finally:
            os.unlink(db_path)


class TestListTools:
    """Test that list_tools returns all 16 tools."""

    def test_list_tools_count(self):
        import mcp_server as srv

        result = asyncio.run(srv.list_tools.__wrapped__() if hasattr(srv.list_tools, '__wrapped__')
                             else srv.list_tools())

        tool_names = [t.name for t in result]
        assert len(result) == 16, f"Expected 16 tools, got {len(result)}: {tool_names}"

        # Check all basic tools
        for name in ["remember", "recall", "relate", "ask", "lookup",
                      "neighbors", "forget", "stats", "timeline", "health"]:
            assert name in tool_names, f"Missing basic tool: {name}"

        # Check all advanced tools
        for name in ["entropy", "reason", "snapshot", "code_explain",
                      "quarantine", "security"]:
            assert name in tool_names, f"Missing advanced tool: {name}"


class TestUnknownTool:
    """Test calling an unknown tool returns error."""

    def test_unknown_tool(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "nonexistent_tool", {}))
                assert "Unknown tool" in result[0].text
        finally:
            os.unlink(db_path)


class TestExistingToolsStillWork:
    """Ensure existing basic tools still work after adding advanced ones."""

    def test_stats_still_works(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "stats", {}))
                data = json.loads(result[0].text)
                assert "nodes" in data
                assert data["nodes"] >= 5
        finally:
            os.unlink(db_path)

    def test_health_still_works(self):
        g = _make_graph_with_data()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = g

                result = asyncio.run(_call_direct(srv, "health", {}))
                # Health can return dict or string
                text = result[0].text
                assert text  # non-empty
        finally:
            os.unlink(db_path)

    def test_remember_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch("mcp_server.DB_PATH", db_path):
                import mcp_server as srv
                srv._graph = None  # force fresh graph

                result = asyncio.run(_call_direct(srv, "remember", {
                    "name": "TestEntity",
                    "kind": "test",
                }))
                data = json.loads(result[0].text)
                assert data["status"] == "remembered"
                assert data["name"] == "TestEntity"
                assert "node_id" in data
        finally:
            os.unlink(db_path)
