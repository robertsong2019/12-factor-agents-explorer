import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdir, writeFile, readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { toolHandlers } from "../dist/tools.js";

const { delete: deleteHandler, write: writeHandler } = toolHandlers;
const TEST_DIR = "test-delete-dir";
const TEST_FILE = "test-delete-file.txt";

describe("delete tool", () => {
  after(async () => {
    // cleanup just in case
    try { await toolHandlers.exec({ command: `rm -rf ${TEST_DIR} ${TEST_FILE}` }); } catch {}
  });

  it("should delete an existing file", async () => {
    await writeHandler({ path: TEST_FILE, content: "to be deleted" });
    const result = await deleteHandler({ path: TEST_FILE });
    assert.equal(result.success, true);
    await assert.rejects(() => stat(TEST_FILE));
  });

  it("should return error for non-existent file", async () => {
    const result = await deleteHandler({ path: "nonexistent-file-xyz.txt" });
    assert.equal(result.success, false);
    assert.equal(result.error, "File not found");
  });

  it("should delete an empty directory", async () => {
    await mkdir(TEST_DIR, { recursive: true });
    const result = await deleteHandler({ path: TEST_DIR });
    assert.equal(result.success, true);
    await assert.rejects(() => stat(TEST_DIR));
  });

  it("should refuse to delete non-empty directory", async () => {
    await mkdir(TEST_DIR, { recursive: true });
    await writeFile(join(TEST_DIR, "inner.txt"), "data");
    const result = await deleteHandler({ path: TEST_DIR });
    assert.equal(result.success, false);
    assert.ok(result.error.includes("not empty"));
    // cleanup
    await toolHandlers.exec({ command: `rm -rf ${TEST_DIR}` });
  });

  it("should block path traversal", async () => {
    await assert.rejects(
      () => deleteHandler({ path: "../../etc/passwd" }),
      /Path traversal/
    );
  });
});
