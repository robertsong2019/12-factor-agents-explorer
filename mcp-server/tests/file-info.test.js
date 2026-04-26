import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { mkdir, writeFile, stat } from "node:fs/promises";
import { setWorkspaceRoot } from "../dist/tools.js";

const TEST_DIR = "/tmp/mcp-file-info-test";
setWorkspaceRoot(TEST_DIR);

describe("file_info", () => {
  it("should return metadata for a file", async () => {
    const { toolHandlers } = await import("../dist/tools.js");
    await mkdir(TEST_DIR, { recursive: true });
    await writeFile(join(TEST_DIR, "test.txt"), "hello world");

    const result = await toolHandlers.file_info({ path: "test.txt" });
    assert.equal(result.tool, "file_info");
    assert.equal(result.success, true);
    assert.equal(result.type, "file");
    assert.equal(result.size, 11);
    assert.ok(result.sizeHuman);
    assert.ok(result.modified);
    assert.ok(result.permissions);
    assert.ok(result.created);
  });

  it("should return metadata for a directory", async () => {
    const { toolHandlers } = await import("../dist/tools.js");
    await mkdir(join(TEST_DIR, "subdir"), { recursive: true });

    const result = await toolHandlers.file_info({ path: "subdir" });
    assert.equal(result.type, "directory");
    assert.equal(result.success, true);
  });

  it("should return error for non-existent file", async () => {
    const { toolHandlers } = await import("../dist/tools.js");
    const result = await toolHandlers.file_info({ path: "nonexistent.txt" });
    assert.equal(result.success, false);
    assert.equal(result.error, "File not found");
  });

  it("should show human-readable sizes", async () => {
    const { toolHandlers } = await import("../dist/tools.js");
    // Create a file larger than 1KB
    const bigContent = "x".repeat(2048);
    await writeFile(join(TEST_DIR, "big.txt"), bigContent);

    const result = await toolHandlers.file_info({ path: "big.txt" });
    assert.equal(result.size, 2048);
    assert.match(result.sizeHuman, /KB/);
  });

  it("should reject path traversal", async () => {
    const { toolHandlers } = await import("../dist/tools.js");
    await assert.rejects(
      () => toolHandlers.file_info({ path: "../../etc/passwd" }),
      /traversal/i
    );
  });
});
