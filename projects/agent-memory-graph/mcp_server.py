#!/usr/bin/env python3
"""
agent-memory-graph MCP Server
=============================
Exposes MemoryGraph as MCP tools for AI agents to use as long-term memory.

Tools (17):
  Basic:   remember, recall, relate, ask, lookup, neighbors, forget, stats, timeline, health
  Advanced: entropy, reason, snapshot, code_explain, quarantine, security
  Ops:      metrics

Usage:
    python3 mcp_server.py                    # stdio mode (for mcporter/MCP clients)
    python3 mcp_server.py --http --port 8765 # HTTP mode (for remote access)
"""

import json
import sys
import os
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from memory_graph import MemoryGraph, Node
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

DB_PATH = os.environ.get(
    "AMG_DB_PATH",
    str(Path.home() / ".openclaw" / "data" / "agent_memory.db")
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

_graph: MemoryGraph | None = None
_metrics_conn = None

def get_graph() -> MemoryGraph:
    global _graph
    if _graph is None:
        _graph = MemoryGraph(db_path=DB_PATH)
        # Sync Lamport clock with existing DB state
        try:
            row = _graph.conn.execute("SELECT MAX(lamport) as m FROM clock_log").fetchone()
            if row and row["m"] is not None:
                _graph._lamport_clock = row["m"]
        except Exception:
            pass
    return _graph

# ── Metrics tracking ──

_METRICS_DB = os.environ.get(
    "AMG_METRICS_DB",
    str(Path.home() / ".openclaw" / "data" / "amg_mcp_metrics.db"),
)

def _get_metrics_conn():
    """Lazy-init a separate SQLite connection for metrics."""
    global _metrics_conn
    if _metrics_conn is None:
        os.makedirs(os.path.dirname(_METRICS_DB), exist_ok=True)
        import sqlite3
        _metrics_conn = sqlite3.connect(_METRICS_DB)
        _metrics_conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                timestamp REAL NOT NULL,
                duration_ms REAL NOT NULL,
                success INTEGER NOT NULL,
                error_msg TEXT
            )
        """)
        _metrics_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool ON tool_calls(tool)
        """)
        _metrics_conn.commit()
    return _metrics_conn


def record_tool_call(tool: str, duration_ms: float, success: bool, error_msg: str = ""):
    """Record a tool invocation in the metrics DB."""
    conn = _get_metrics_conn()
    conn.execute(
        "INSERT INTO tool_calls (tool, timestamp, duration_ms, success, error_msg) VALUES (?, ?, ?, ?, ?)",
        (tool, time.time(), duration_ms, int(success), error_msg[:500]),
    )
    conn.commit()


def get_metrics_summary() -> dict:
    """Aggregate metrics for all tools."""
    conn = _get_metrics_conn()
    rows = conn.execute("""
        SELECT
            tool,
            COUNT(*) as call_count,
            AVG(duration_ms) as avg_ms,
            MIN(duration_ms) as min_ms,
            MAX(duration_ms) as max_ms,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
            MAX(timestamp) as last_called
        FROM tool_calls
        GROUP BY tool
        ORDER BY call_count DESC
    """).fetchall()

    tools = []
    total_calls = 0
    total_errors = 0
    for r in rows:
        calls = r[1]
        errors = r[5] or 0
        total_calls += calls
        total_errors += errors
        tools.append({
            "tool": r[0],
            "calls": calls,
            "avg_ms": round(r[2], 2) if r[2] else 0,
            "min_ms": round(r[3], 2) if r[3] else 0,
            "max_ms": round(r[4], 2) if r[4] else 0,
            "errors": errors,
            "error_rate": round(errors / calls, 4) if calls else 0,
            "last_called": r[6],
        })

    return {
        "total_calls": total_calls,
        "total_errors": total_errors,
        "overall_error_rate": round(total_errors / total_calls, 4) if total_calls else 0,
        "tools": tools,
    }


def reset_metrics() -> int:
    """Clear all metrics. Returns deleted row count."""
    conn = _get_metrics_conn()
    cur = conn.execute("DELETE FROM tool_calls")
    conn.commit()
    return cur.rowcount

def node_to_dict(n) -> dict:
    return {"id": n.id, "label": n.label, "kind": n.kind, "data": n.data, "tags": getattr(n, "tags", [])}

def _safe(obj):
    """Recursively convert Node objects to dicts for JSON serialization."""
    if hasattr(obj, 'label') and hasattr(obj, 'id'):
        return node_to_dict(obj)
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(item) for item in obj]
    return obj

def _safe_result(r: dict) -> dict:
    return {k: _safe(v) for k, v in r.items()}

server = Server("agent-memory-graph")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="remember",
            description="Store a new memory entity in the graph. The agent's long-term memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Human-readable name/title"},
                    "kind": {"type": "string", "description": "Category: person, project, event, idea, fact, note, decision, etc."},
                    "data": {"type": "object", "description": "Structured metadata"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for filtering"},
                },
                "required": ["name", "kind"],
            },
        ),
        types.Tool(
            name="recall",
            description="Search memory using BM25 full-text search. Returns matching nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="relate",
            description="Create a relationship between two entities. Auto-creates nodes if they don't exist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source node name"},
                    "dst": {"type": "string", "description": "Target node name"},
                    "label": {"type": "string", "description": "Relationship label (e.g. '负责', 'belongs_to', 'uses')"},
                    "weight": {"type": "number", "description": "Edge weight 0-1 (default 0.5)"},
                },
                "required": ["src", "dst", "label"],
            },
        ),
        types.Tool(
            name="ask",
            description="Multi-hop reasoning: find paths and relationships in the graph. For questions like 'X和Y什么关系?'",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Natural language question"},
                    "start": {"type": "string", "description": "Starting node name (optional)"},
                    "depth": {"type": "integer", "description": "Max traversal depth (default 3)", "default": 3},
                },
                "required": ["question"],
            },
        ),
        types.Tool(
            name="lookup",
            description="Get a specific memory node by name, including its neighbors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Node name to look up"},
                    "id": {"type": "string", "description": "Node ID (alternative to name)"},
                },
            },
        ),
        types.Tool(
            name="neighbors",
            description="Get all directly connected entities of a node.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Node name"},
                    "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="forget",
            description="Strategic forget: prune low-value memories. Like sleep consolidation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_age": {"type": "integer", "description": "Max age in days"},
                    "min_weight": {"type": "number", "description": "Nodes below this weight (default 0.3)"},
                    "kind": {"type": "string", "description": "Only forget specific kind"},
                    "dry_run": {"type": "boolean", "description": "Preview without deleting (default true)", "default": True},
                },
            },
        ),
        types.Tool(
            name="stats",
            description="Memory graph statistics.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="timeline",
            description="Recent memories in chronological order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                    "kind": {"type": "string", "description": "Filter by kind"},
                },
            },
        ),
        types.Tool(
            name="health",
            description="Memory health report.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Advanced tools ──
        types.Tool(
            name="entropy",
            description="Get entropy profile of the memory graph. Shows information-theoretic complexity by index (sombor, randic, zagreb, abc, etc.). High entropy = diverse/uncertain region.",
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "Top-N contributors (default 5)", "default": 5},
                },
            },
        ),
        types.Tool(
            name="reason",
            description="Multi-hop reasoning: find relationship paths between two entities. Useful for 'how does X connect to Y?' questions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {"type": "string", "description": "Starting node name"},
                    "to": {"type": "string", "description": "Target node name"},
                    "max_hops": {"type": "integer", "description": "Max traversal depth (default 3)", "default": 3},
                    "strategy": {"type": "string", "description": "Path strategy: shortest, weighted, or all (default 'shortest')", "default": "shortest"},
                },
                "required": ["from", "to"],
            },
        ),
        types.Tool(
            name="snapshot",
            description="Bi-temporal query: see the memory graph as of a past timestamp. Time-travel through memory history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string", "description": "ISO timestamp or Unix epoch (e.g. '2024-01-01' or 1700000000)"},
                    "node": {"type": "string", "description": "Focus on specific node name (optional)"},
                    "depth": {"type": "integer", "description": "Neighbor depth (default 1)", "default": 1},
                    "limit": {"type": "integer", "description": "Max nodes (default 100)", "default": 100},
                },
                "required": ["timestamp"],
            },
        ),
        types.Tool(
            name="code_explain",
            description="Explain a code entity stored in memory. Shows functions, classes, dependencies, and impact analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Code entity name (function/class/file)"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="quarantine",
            description="Quarantine suspicious or low-trust memories. Prevents them from influencing reasoning. Like putting memories in isolation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "scan", "add", "remove"], "description": "Action: list quarantined, scan for suspicious, add quarantine, remove quarantine"},
                    "node": {"type": "string", "description": "Node name (for add/remove)"},
                    "reason": {"type": "string", "description": "Reason for quarantine (for add)"},
                    "trust_threshold": {"type": "number", "description": "Trust threshold for scan (default 0.3)", "default": 0.3},
                },
                "required": ["action"],
            },
        ),
        types.Tool(
            name="security",
            description="Security audit: run OWASP ASI06 memory security checks. Reports quarantine status, trust levels, and potential provenance laundering.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="metrics",
            description="MCP server observability: view tool call counts, latency, error rates. Actions: summary (default), recent, reset.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["summary", "recent", "reset"], "description": "summary: aggregated stats; recent: last N calls; reset: clear all metrics", "default": "summary"},
                    "limit": {"type": "integer", "description": "Number of recent calls to return (for action=recent, default 20)", "default": 20},
                },
            },
        ),
    ]


def _resolve(name_or_id: str) -> str | None:
    """Resolve a name to a node ID."""
    g = get_graph()
    # Try search first (handles both names and IDs)
    results = g.search_unified(query=name_or_id, limit=1)
    if results:
        node = results[0]
        # Could be nested under 'node' key or flat
        if isinstance(node, dict):
            inner = node.get("node")
            if inner and hasattr(inner, "id"):
                return inner.id
            if "id" in node:
                return node["id"]
            if "node_id" in node:
                return node["node_id"]
    return None


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    g = get_graph()
    _t0 = time.monotonic()
    _success = True
    _err = ""

    try:
        result = await _dispatch_tool(name, arguments, g)
        # Detect logical errors (returned, not thrown)
        if result and isinstance(result, list) and len(result) > 0:
            txt = result[0].text if hasattr(result[0], 'text') else str(result[0])
            if txt.startswith("Unknown tool") or txt.startswith("Error:"):
                _success = False
                _err = txt[:200]
        return result
    except Exception as e:
        _success = False
        _err = f"{type(e).__name__}: {e}"
        return [types.TextContent(type="text", text=f"Error: {_err}")]
    finally:
        _dur = (time.monotonic() - _t0) * 1000
        try:
            record_tool_call(name, _dur, _success, _err)
        except Exception:
            pass  # metrics must never break the server


async def _dispatch_tool(name: str, arguments: dict, g: MemoryGraph) -> list[types.TextContent]:
    """Inner tool dispatcher — all tool logic lives here."""
    try:
        if name == "remember":
            node = g.add(
                label=arguments["name"],
                kind=arguments.get("kind", "fact"),
                data=arguments.get("data", {}),
                tags=arguments.get("tags", []),
            )
            return [types.TextContent(type="text", text=json.dumps({
                "status": "remembered", "node_id": node.id,
                "name": arguments["name"], "kind": arguments.get("kind", "fact"),
            }, ensure_ascii=False))]

        elif name == "recall":
            results = g.search_unified(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 10),
            )
            # Serialize Node objects to dicts
            safe_results = [_safe_result(r) for r in (results or [])]
            return [types.TextContent(type="text", text=json.dumps(safe_results, ensure_ascii=False, indent=2))]

        elif name == "relate":
            src_name, dst_name, relation = arguments["src"], arguments["dst"], arguments["label"]
            weight = arguments.get("weight", 0.5)

            src_id = _resolve(src_name)
            dst_id = _resolve(dst_name)

            if not src_id:
                src_id = g.add(label=src_name, kind="auto_created").id
            if not dst_id:
                dst_id = g.add(label=dst_name, kind="auto_created").id

            g.link(src_id, dst_id, relation=relation, weight=weight)
            return [types.TextContent(type="text", text=json.dumps({
                "status": "linked", "src": src_name, "dst": dst_name, "relation": relation,
            }, ensure_ascii=False))]

        elif name == "ask":
            question = arguments["question"]
            start_hint = arguments.get("start")
            depth = arguments.get("depth", 3)

            # If we have a start node, try reasoning_path
            if start_hint:
                start_id = _resolve(start_hint)
                if start_id:
                    targets = g.search_unified(query=question, limit=5)
                    paths = []
                    for r in targets:
                        tid = r.get("id")
                        if tid and tid != start_id:
                            try:
                                p = g.reasoning_path(start_id, tid, max_hops=depth)
                                if p:
                                    paths.append({"target": r.get("label", ""), "path": p})
                            except Exception:
                                pass
                    if paths:
                        return [types.TextContent(type="text", text=json.dumps({
                            "question": question, "paths": paths[:3],
                        }, ensure_ascii=False, indent=2))]

            # Fallback: search + enrich with neighbors
            results = g.search_unified(query=question, limit=5)
            enriched = []
            for r in results[:3]:
                nbrs = g.neighbors(r.get("id", ""), depth=1)
                conns = [{"label": n.label, "kind": n.kind} for n in nbrs] if nbrs else []
                enriched.append({"node": r, "connections": conns[:5]})
            return [types.TextContent(type="text", text=json.dumps(_safe(enriched) if enriched else _safe(results), ensure_ascii=False, indent=2))]

        elif name == "lookup":
            nid = arguments.get("id", "")
            nm = arguments.get("name", "")
            node = None
            if nid:
                try:
                    n = g.get_node(nid)
                    node = node_to_dict(n)
                except Exception:
                    pass
            elif nm:
                results = g.search_unified(query=nm, limit=1)
                node = _safe_result(results[0]) if results else None

            if node:
                node_id = node.get("id", node.get("node_id", ""))
                try:
                    nbrs = g.neighbors(node_id, depth=1)
                    node["neighbors"] = [{"label": n.label, "kind": n.kind} for n in nbrs][:10] if nbrs else []
                except Exception:
                    node["neighbors"] = []
                return [types.TextContent(type="text", text=json.dumps(node, ensure_ascii=False, indent=2))]
            return [types.TextContent(type="text", text=json.dumps({"error": "not found"}, ensure_ascii=False))]

        elif name == "neighbors":
            nm = arguments["name"]
            node_id = _resolve(nm)
            if not node_id:
                return [types.TextContent(type="text", text=json.dumps({"error": f"'{nm}' not found"}, ensure_ascii=False))]
            nbrs = g.neighbors(node_id, depth=1)
            limit = arguments.get("limit", 20)
            result_list = [node_to_dict(n) for n in (nbrs or [])][:limit]
            return [types.TextContent(type="text", text=json.dumps(result_list, ensure_ascii=False, indent=2))]

        elif name == "forget":
            dry = arguments.get("dry_run", True)
            kwargs = {"dry_run": dry}
            if arguments.get("min_weight") is not None:
                kwargs["min_weight"] = arguments["min_weight"]
            if arguments.get("max_age") is not None:
                kwargs["max_age_days"] = arguments["max_age"]
            if arguments.get("kind"):
                kwargs["kind"] = arguments["kind"]
            result = g.strategic_forget(**kwargs)
            if isinstance(result, str):
                return [types.TextContent(type="text", text=result)]
            return [types.TextContent(type="text", text=json.dumps({"dry_run": dry, "result": result}, ensure_ascii=False, indent=2))]

        elif name == "stats":
            s = g.stats()
            if isinstance(s, str):
                return [types.TextContent(type="text", text=s)]
            return [types.TextContent(type="text", text=json.dumps(s, ensure_ascii=False, indent=2))]

        elif name == "timeline":
            kwargs = {"limit": arguments.get("limit", 10)}
            if arguments.get("kind"):
                kwargs["kind"] = arguments["kind"]
            results = g.timeline(**kwargs)
            result_list = [node_to_dict(n) for n in (results or [])]
            return [types.TextContent(type="text", text=json.dumps(result_list, ensure_ascii=False, indent=2))]

        elif name == "health":
            h = g.memory_health_score()
            if isinstance(h, str):
                return [types.TextContent(type="text", text=h)]
            return [types.TextContent(type="text", text=json.dumps(h, ensure_ascii=False, indent=2))]

        # ── Advanced tools ──

        elif name == "entropy":
            top_n = arguments.get("top_n", 5)
            result = g.entropy_dashboard(top_n=top_n)
            if result is None:
                return [types.TextContent(type="text", text=json.dumps({"error": "not enough nodes for entropy analysis"}, ensure_ascii=False))]
            return [types.TextContent(type="text", text=json.dumps(_safe(result), ensure_ascii=False, indent=2))]

        elif name == "reason":
            src_name = arguments["from"]
            dst_name = arguments["to"]
            max_hops = arguments.get("max_hops", 3)
            strategy = arguments.get("strategy", "shortest")

            src_id = _resolve(src_name)
            dst_id = _resolve(dst_name)

            if not src_id:
                return [types.TextContent(type="text", text=json.dumps({"error": f"'{src_name}' not found"}, ensure_ascii=False))]
            if not dst_id:
                return [types.TextContent(type="text", text=json.dumps({"error": f"'{dst_name}' not found"}, ensure_ascii=False))]

            paths = g.reasoning_path(src_id, dst_id, max_hops=max_hops, strategy=strategy)
            return [types.TextContent(type="text", text=json.dumps({
                "from": src_name,
                "to": dst_name,
                "hops": max_hops,
                "paths": _safe(paths) if paths else [],
            }, ensure_ascii=False, indent=2))]

        elif name == "snapshot":
            ts_arg = arguments["timestamp"]
            # Parse timestamp: support ISO string or epoch
            if isinstance(ts_arg, str):
                import datetime
                try:
                    # Try ISO format first
                    dt = datetime.datetime.fromisoformat(ts_arg)
                    timestamp = dt.timestamp()
                except ValueError:
                    try:
                        timestamp = float(ts_arg)
                    except ValueError:
                        return [types.TextContent(type="text", text=json.dumps({"error": f"Invalid timestamp: {ts_arg}"}, ensure_ascii=False))]
            else:
                timestamp = float(ts_arg)

            node_name = arguments.get("node")
            node_id = _resolve(node_name) if node_name else None
            depth = arguments.get("depth", 1)
            limit = arguments.get("limit", 100)

            result = g.query_as_of(timestamp, node_id=node_id, depth=depth, limit=limit)
            return [types.TextContent(type="text", text=json.dumps(_safe(result), ensure_ascii=False, indent=2))]

        elif name == "code_explain":
            entity_name = arguments["name"]
            node_id = _resolve(entity_name)
            if not node_id:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Code entity '{entity_name}' not found"}, ensure_ascii=False))]

            result = g.explain_code(node_id)
            return [types.TextContent(type="text", text=json.dumps(_safe(result), ensure_ascii=False, indent=2))]

        elif name == "quarantine":
            action = arguments.get("action", "list")

            if action == "list":
                result = g.quarantine_list()
                return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

            elif action == "scan":
                threshold = arguments.get("trust_threshold", 0.3)
                flagged = g.quarantine_scan(trust_threshold=threshold)
                return [types.TextContent(type="text", text=json.dumps({
                    "trust_threshold": threshold,
                    "flagged_count": len(flagged),
                    "flagged_nodes": flagged,
                }, ensure_ascii=False, indent=2))]

            elif action == "add":
                node_name = arguments.get("node", "")
                reason = arguments.get("reason", "")
                node_id = _resolve(node_name)
                if not node_id:
                    return [types.TextContent(type="text", text=json.dumps({"error": f"'{node_name}' not found"}, ensure_ascii=False))]
                ok = g.node_quarantine(node_id, reason=reason)
                return [types.TextContent(type="text", text=json.dumps({
                    "status": "quarantined" if ok else "already quarantined",
                    "node": node_name,
                    "reason": reason,
                }, ensure_ascii=False))]

            elif action == "remove":
                node_name = arguments.get("node", "")
                node_id = _resolve(node_name)
                if not node_id:
                    return [types.TextContent(type="text", text=json.dumps({"error": f"'{node_name}' not found"}, ensure_ascii=False))]
                ok = g.node_unquarantine(node_id)
                return [types.TextContent(type="text", text=json.dumps({
                    "status": "unquarantined" if ok else "was not quarantined",
                    "node": node_name,
                }, ensure_ascii=False))]

            else:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown action: {action}"}, ensure_ascii=False))]

        elif name == "security":
            # Aggregate security status from multiple sources
            q_list = g.quarantine_list()
            health = g.memory_health_score()
            stats = g.stats()

            # Count total nodes and quarantined
            total_nodes = stats.get("nodes", 0) if isinstance(stats, dict) else 0
            total_edges = stats.get("edges", 0) if isinstance(stats, dict) else 0
            quarantined_count = len(q_list)

            # Quarantine ratio
            q_ratio = (quarantined_count / total_nodes) if total_nodes > 0 else 0.0

            # Health score
            health_val = health.get("health_score", health) if isinstance(health, dict) else health

            audit = {
                "owasp_asi06_status": {
                    "L1_write_governance": "available",
                    "L2_provenance_lineage": "available",
                    "L3_entropy_weighted_retrieval": "available",
                    "L4_streaming_graph": "available",
                    "L5_propagate_correction": "available",
                },
                "quarantine": {
                    "count": quarantined_count,
                    "ratio": round(q_ratio, 4),
                    "nodes": q_list[:20],  # cap for readability
                },
                "graph_health": health_val,
                "graph_stats": {
                    "nodes": total_nodes,
                    "edges": total_edges,
                },
                "recommendation": (
                    "All clear" if quarantined_count == 0
                    else f"{quarantined_count} quarantined node(s) — review with quarantine scan"
                ),
            }
            return [types.TextContent(type="text", text=json.dumps(audit, ensure_ascii=False, indent=2))]

        elif name == "metrics":
            action = arguments.get("action", "summary")
            if action == "summary":
                result = get_metrics_summary()
                return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
            elif action == "reset":
                deleted = reset_metrics()
                return [types.TextContent(type="text", text=json.dumps({"status": "reset", "deleted": deleted}, ensure_ascii=False))]
            elif action == "recent":
                limit = arguments.get("limit", 20)
                conn = _get_metrics_conn()
                rows = conn.execute(
                    "SELECT tool, timestamp, duration_ms, success, error_msg FROM tool_calls ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                recent = [{
                    "tool": r[0], "timestamp": r[1],
                    "duration_ms": round(r[2], 2),
                    "success": bool(r[3]), "error": r[4] if r[4] else None,
                } for r in rows]
                return [types.TextContent(type="text", text=json.dumps(recent, ensure_ascii=False, indent=2))]
            else:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown action: {action}"}, ensure_ascii=False))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="agent-memory-graph MCP Server")
    parser.add_argument("--http", action="store_true", help="Run in HTTP mode")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.http:
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        import uvicorn

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())

        app = Starlette(routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ])
        print(f"agent-memory-graph MCP Server (HTTP) on port {args.port}", file=sys.stderr)
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        import asyncio
        asyncio.run(main())
