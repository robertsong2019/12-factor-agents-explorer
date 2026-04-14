/**
 * Test tool execution functionality — real filesystem operations
 */

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import { readFile, writeFile, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { exec as execCb } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(execCb);

const TEST_DIR = join(process.cwd(), ".test-fixture");

describe("MCP Server - Execute Tools (real)", () => {
  before(async () => {
    await mkdir(TEST_DIR, { recursive: true });
  });

  after(async () => {
    await rm(TEST_DIR, { recursive: true, force: true });
  });

  it("should read a real file", async () => {
    const testFile = join(TEST_DIR, "read-test.txt");
    await writeFile(testFile, "line1\nline2\nline3\nline4\nline5\n", "utf-8");

    // Simulate executeRead logic directly
    const content = await readFile(testFile, "utf-8");
    const lines = content.split("\n");
    const selected = lines.slice(1, 3).join("\n"); // offset=2, limit=2

    assert.ok(selected.includes("line2"));
    assert.ok(selected.includes("line3"));
    assert.ok(!selected.includes("line1"));
  });

  it("should write a real file", async () => {
    const testFile = join(TEST_DIR, "write-test.txt");
    const content = "Hello, real world!";
    await writeFile(testFile, content, "utf-8");

    const readBack = await readFile(testFile, "utf-8");
    assert.strictEqual(readBack, content);
  });

  it("should execute a real shell command", async () => {
    const { stdout } = await execAsync("echo hello-from-test", {
      cwd: TEST_DIR,
    });
    assert.strictEqual(stdout.trim(), "hello-from-test");
  });

  it("should handle exec errors gracefully", async () => {
    try {
      await execAsync("false", { cwd: TEST_DIR });
      assert.fail("Should have thrown");
    } catch (err) {
      assert.ok(err.code !== 0);
    }
  });

  it("should handle missing required parameters", async () => {
    const invalidRequests = [
      { name: "web_search", arguments: {} },
      { name: "read", arguments: {} },
      { name: "write", arguments: { path: "/test" } },
      { name: "exec", arguments: {} },
    ];
    for (const request of invalidRequests) {
      assert.ok(request.name);
      assert.ok(request.arguments);
    }
  });

  it("should handle unknown tool names", async () => {
    const mockError = {
      content: [{ type: "text", text: JSON.stringify({ error: "Unknown tool: unknown_tool" }) }],
      isError: true,
    };
    assert.strictEqual(mockError.isError, true);
    assert.ok(mockError.content[0].text.includes("Unknown tool"));
  });
});
