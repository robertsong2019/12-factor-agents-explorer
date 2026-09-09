# OpenClaw MCP Server

> Expose OpenClaw capabilities (memory, search, status) via the [Model Context Protocol](https://modelcontextprotocol.io/).

## Overview

An MCP Server implementation using **Streamable HTTP** transport, allowing any MCP-compatible client (Claude Desktop, Cursor, etc.) to interact with Catalyst's workspace.

```
MCP Client → Streamable HTTP → openclaw-mcp-server → OpenClaw APIs
```

Supports **multiple concurrent clients**: each MCP session gets its own dedicated server + transport pair.

## Tools Provided

| Tool | Description |
|------|-------------|
| `query_memory` | Search Catalyst's memory for past work and decisions |
| `web_search` | Search the web for latest information |
| `get_status` | Get system status: active projects, test coverage |

## Quick Start

```bash
# Install dependencies
npm install

# Development (with tsx)
npm run dev

# Production build + run
npm run build && npm start
```

Server starts at `http://localhost:3001/mcp` by default. Set `PORT` env var to change.

### Environment Variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `PORT` | `3001` | HTTP listen port |
| `SESSION_TTL_MS` | `1800000` (30 min) | Idle-session lifetime. A session is reaped after this much silence; every request refreshes it. Invalid values (NaN, ≤0) fall back to the default. Set low (e.g. `500`) to watch reaping in tests. |

### Hardening Guarantees

- **Crash-safe request path**: a client aborting mid-request never kills the process (all handler errors are contained; the response is destroyed cleanly).
- **Bounded memory**: request bodies are capped at 1 MB — larger uploads are drained and answered `413`, never buffered.
- **Correct JSON-RPC diagnosis**: malformed JSON on POST returns `-32700 Parse error` even without a session header (GET/DELETE keep transport semantics).
- **No session leaks**: idle sessions are reaped after `SESSION_TTL_MS`; reaping is best-effort and can never crash the server.

## Connecting a Client

Configure your MCP client to connect via Streamable HTTP:

```json
{
  "mcpServers": {
    "openclaw": {
      "url": "http://localhost:3001/mcp",
      "transport": "streamable-http"
    }
  }
}
```

## Session Lifecycle

MCP Streamable HTTP is a **stateful** protocol:

1. **Initialize** — client sends an `initialize` request without a session id. The server creates a dedicated `McpServer` + `StreamableHTTPServerTransport` pair, generates a UUID session id, and returns it in the `mcp-session-id` response header.
2. **Operate** — every subsequent request carries `mcp-session-id` and is routed to that session's transport. Requests with an unknown/expired session id get **404**; non-initialize requests with no session id get **400**.
3. **Close** — a `DELETE` request terminates the session; the transport's `onclose` handler removes it from the session map.

```
POST /mcp   (initialize, no session id) ──▶ create session ──▶ mcp-session-id: <uuid>
POST /mcp   (tools/call, session id)    ──▶ route to session
DELETE /mcp (session id)                ──▶ close session
```

## Why One Transport Per Session?

A subtle but important MCP server design point — getting it wrong yields a server that works for the first client and silently rejects everyone else.

`StreamableHTTPServerTransport` is stateful: once it answers an `initialize`, it considers itself initialized. If you create **one shared transport** at startup and route all clients through it:

- Client A initializes → the transport is now "initialized".
- Client B initializes → the transport sees an `initialize` on an already-initialized session and returns `"Server already initialized"`. B can never connect.

The fix (matching the official SDK pattern) is a **factory**: `createMcpServer()` builds a fresh server + transport pair per session, indexed by session id in a `Map`. Sessions are removed via `transport.onclose`. A side benefit: session ids are now actually validated — an unknown id gets a 404 instead of silent acceptance.

Additional hardening: `transport.handleRequest` runs inside try/catch so an async throw can never crash the process via unhandled rejection.

## Architecture

- **Transport**: `@modelcontextprotocol/sdk` StreamableHTTPServerTransport — **one instance per session** (stateful)
- **Session store**: in-memory `Map<sessionId, {server, transport}>`, cleaned up via `transport.onclose`
- **Schema**: Zod for input validation
- **Runtime**: Node.js 22+ with ESM

## Project Structure

```
src/
  index.ts    # Server entry, per-session factory, tool definitions, HTTP handler
dist/         # Compiled JS output
test/         # protocol.test.js + server.test.js
```

## Testing

```bash
npm test   # builds, then runs node --test (17 tests)
```

Coverage includes: concurrent dual-client interleaved use, session id validation (unknown → 404, missing → 400), malformed JSON (`-32700`), unknown tool / invalid args (`isError` paths), `limit` slicing, GET rejection, DELETE-then-404.

## Status

🚧 MVP — transport layer is production-hardened (per-session, validated, crash-safe). Tool handlers still return mock data; production integration with actual OpenClaw APIs is pending.

## License

MIT

---

*Part of the [OpenClaw workspace](https://github.com/robertsong2019)*
