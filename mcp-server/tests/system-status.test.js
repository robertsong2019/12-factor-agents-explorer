import { describe, it, before } from "node:test";
import assert from "node:assert/strict";

describe("system_status tool", () => {
  let toolHandlers;

  before(async () => {
    const mod = await import("../dist/tools.js");
    toolHandlers = mod.toolHandlers;
  });

  it("should return system status information", async () => {
    const result = await toolHandlers.system_status({});
    assert.equal(result.tool, "system_status");
    assert.ok(result.platform);
    assert.ok(result.nodeVersion);
    assert.ok(result.pid);
    assert.ok(typeof result.uptime === "number");
    assert.ok(result.memory);
    assert.ok(result.memory.rss);
    assert.ok(result.memory.heapUsed);
    assert.ok(result.memory.heapTotal);
    assert.ok(result.workspace);
  });

  it("should include platform information", async () => {
    const result = await toolHandlers.system_status({});
    assert.ok(["darwin", "linux", "win32"].includes(result.platform));
  });

  it("should include Node.js version", async () => {
    const result = await toolHandlers.system_status({});
    assert.ok(result.nodeVersion.startsWith("v"));
  });

  it("should include memory info in MB format", async () => {
    const result = await toolHandlers.system_status({});
    assert.ok(result.memory.rss.endsWith("MB"));
    assert.ok(result.memory.heapUsed.endsWith("MB"));
    assert.ok(result.memory.heapTotal.endsWith("MB"));
  });

  it("should include workspace root", async () => {
    const result = await toolHandlers.system_status({});
    assert.ok(typeof result.workspace === "string");
    assert.ok(result.workspace.length > 0);
  });
});
