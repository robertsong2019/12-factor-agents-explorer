// Protocol-level tests: concurrent sessions, session validation, error paths.
// Covers the per-session transport contract that server.test.js does not.
import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";

const BASE = "http://localhost:3198";
let serverProc;

const HEADERS = {
  "Content-Type": "application/json",
  Accept: "application/json, text/event-stream",
};

async function post(body, sessionId, extraHeaders = {}) {
  const headers = { ...HEADERS, ...extraHeaders };
  if (sessionId) headers["Mcp-Session-Id"] = sessionId;
  return fetch(BASE, { method: "POST", headers, body });
}

async function init(clientName) {
  const res = await post(JSON.stringify({
    jsonrpc: "2.0", id: 1, method: "initialize",
    params: {
      protocolVersion: "2025-06-18", capabilities: {},
      clientInfo: { name: clientName, version: "1.0.0" },
    },
  }));
  const sid = res.headers.get("mcp-session-id");
  const text = await res.text();
  return { status: res.status, sid, body: text };
}

async function parseSSE(response) {
  const text = await response.text();
  for (const line of text.split("\n")) {
    if (line.startsWith("data: ")) return JSON.parse(line.slice(6));
  }
  return JSON.parse(text);
}

let sessionA, sessionB;

before(async () => {
  serverProc = spawn("node", ["dist/index.js"], {
    env: { ...process.env, PORT: "3198" },
    stdio: ["pipe", "pipe", "pipe"],
  });
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Server startup timeout")), 5000);
    serverProc.stdout.on("data", (data) => {
      if (data.toString().includes("OpenClaw MCP Server running")) {
        clearTimeout(timeout);
        resolve();
      }
    });
    serverProc.on("error", (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
});

after(() => {
  serverProc?.kill();
});

describe("MCP protocol: sessions", () => {
  it("client A initializes and gets a session id", async () => {
    sessionA = await init("client-A");
    assert.equal(sessionA.status, 200);
    assert.ok(sessionA.sid, "session A should have id");
  });

  it("second concurrent client initializes independently (was: Server already initialized)", async () => {
    sessionB = await init("client-B");
    assert.equal(sessionB.status, 200, `client-B init failed: ${sessionB.body.slice(0, 200)}`);
    assert.ok(sessionB.sid, "session B should have id");
    assert.notEqual(sessionB.sid, sessionA.sid, "sessions must be distinct");
  });

  it("both sessions stay usable in interleaved order", async () => {
    const rB = await post(JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" }), sessionB.sid);
    assert.equal(rB.status, 200);
    const bB = await parseSSE(rB);
    assert.equal(bB.result.tools.length, 3);

    const rA = await post(JSON.stringify({ jsonrpc: "2.0", id: 3, method: "tools/list" }), sessionA.sid);
    assert.equal(rA.status, 200);
    const bA = await parseSSE(rA);
    assert.equal(bA.result.tools.length, 3);
  });

  it("unknown session id is rejected with 404 (was: silently accepted)", async () => {
    const res = await post(JSON.stringify({ jsonrpc: "2.0", id: 4, method: "tools/list" }), "bogus-session-123");
    assert.equal(res.status, 404, `expected 404 for unknown session, got ${res.status}`);
    const body = await res.json();
    assert.equal(body.jsonrpc, "2.0");
    assert.ok(body.error, "should carry JSON-RPC error");
  });

  it("missing session header is rejected with 400", async () => {
    const res = await post(JSON.stringify({ jsonrpc: "2.0", id: 5, method: "tools/list" }), null);
    assert.equal(res.status, 400);
    const body = await res.json();
    assert.equal(body.error.code, -32000);
  });
});

describe("MCP protocol: error paths", () => {
  it("malformed JSON body returns 400 parse error -32700", async () => {
    const res = await post("{bad json", sessionA.sid);
    assert.equal(res.status, 400);
    const body = await res.json();
    assert.equal(body.error.code, -32700);
  });

  it("unknown tool returns isError result, not a crash", async () => {
    const res = await post(JSON.stringify({
      jsonrpc: "2.0", id: 6, method: "tools/call",
      params: { name: "no_such_tool", arguments: {} },
    }), sessionA.sid);
    assert.equal(res.status, 200);
    const body = await parseSSE(res);
    assert.ok(body.result.isError, "unknown tool should set isError");
    assert.ok(body.result.content[0].text.includes("no_such_tool"));
  });

  it("invalid arguments return isError with validation detail", async () => {
    const res = await post(JSON.stringify({
      jsonrpc: "2.0", id: 7, method: "tools/call",
      params: { name: "query_memory", arguments: {} },
    }), sessionA.sid);
    assert.equal(res.status, 200);
    const body = await parseSSE(res);
    assert.ok(body.result.isError);
    assert.ok(body.result.content[0].text.includes("query"), "should mention required field");
  });
});

describe("MCP protocol: tool semantics over wire", () => {
  it("query_memory honors limit=1 (slice contract)", async () => {
    const res = await post(JSON.stringify({
      jsonrpc: "2.0", id: 8, method: "tools/call",
      params: { name: "query_memory", arguments: { query: "k", limit: 1 } },
    }), sessionA.sid);
    assert.equal(res.status, 200);
    const body = await parseSSE(res);
    assert.equal(body.result.content.length, 1);
    assert.ok(body.result.content[0].text.includes("[0.95]"));
  });

  it("get_status returns parseable JSON payload with timestamp", async () => {
    const res = await post(JSON.stringify({
      jsonrpc: "2.0", id: 9, method: "tools/call",
      params: { name: "get_status", arguments: {} },
    }), sessionB.sid);
    assert.equal(res.status, 200);
    const body = await parseSSE(res);
    const status = JSON.parse(body.result.content[0].text);
    assert.equal(status.projects.ams.tests, "640/640");
    assert.ok(!Number.isNaN(Date.parse(status.timestamp)));
  });

  it("GET requests are rejected (no SSE stream in this server)", async () => {
    const res = await fetch(BASE, { headers: { "Mcp-Session-Id": sessionA.sid } });
    assert.ok(res.status >= 400 && res.status < 500, `expected 4xx, got ${res.status}`);
  });

  it("DELETE terminates a session; reuse gets 404; other session unaffected", async () => {
    const del = await fetch(BASE, { method: "DELETE", headers: { "Mcp-Session-Id": sessionA.sid } });
    assert.ok(del.status >= 200 && del.status < 300, `DELETE should succeed, got ${del.status}`);
    await del.text();

    const reuse = await post(JSON.stringify({ jsonrpc: "2.0", id: 10, method: "tools/list" }), sessionA.sid);
    assert.equal(reuse.status, 404, "terminated session must be gone");
    await reuse.text();

    const rB = await post(JSON.stringify({ jsonrpc: "2.0", id: 11, method: "tools/list" }), sessionB.sid);
    assert.equal(rB.status, 200, "session B unaffected by A's termination");
  });
});
