#!/usr/bin/env python3
"""
agent-memory-graph MCP Server
=============================
Exposes MemoryGraph as MCP tools for AI agents to use as long-term memory.

Usage:
    python3 mcp_server.py                    # stdio mode (for mcporter/MCP clients)
    python3 mcp_server.py --http --port 8765 # HTTP mode (for remote access)
"""

import json
import sys
import os
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
