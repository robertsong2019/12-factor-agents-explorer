import { describe, it, before } from "node:test";
import assert from "node:assert/strict";

describe("parseArgs", () => {
  let parseArgs, createServerInstance;

  before(async () => {
    const mod = await import("../dist/index.js");
    parseArgs = mod.parseArgs;
    createServerInstance = mod.createServerInstance;
  });

  it("should default to stdio transport", () => {
    const result = parseArgs(["node", "script.js"]);
    assert.equal(result.transport, "stdio");
    assert.equal(result.port, 3000);
    assert.equal(result.host, "127.0.0.1");
  });

  it("should parse --transport http", () => {
    const result = parseArgs(["node", "script.js", "--transport", "http"]);
    assert.equal(result.transport, "http");
  });

  it("should parse --transport stdio explicitly", () => {
    const result = parseArgs(["node", "script.js", "--transport", "stdio"]);
    assert.equal(result.transport, "stdio");
  });

  it("should parse --http as shorthand", () => {
    const result = parseArgs(["node", "script.js", "--http"]);
    assert.equal(result.transport, "http");
  });

  it("should parse --port and --host", () => {
    const result = parseArgs(["node", "script.js", "--transport", "http", "--port", "8080", "--host", "0.0.0.0"]);
    assert.equal(result.transport, "http");
    assert.equal(result.port, 8080);
    assert.equal(result.host, "0.0.0.0");
  });

  it("should default port to 3000 for invalid value", () => {
    const result = parseArgs(["node", "script.js", "--transport", "http", "--port", "abc"]);
    assert.equal(result.port, 3000);
  });

  it("should create a server instance", () => {
    const server = createServerInstance();
    assert.ok(server);
  });
});
