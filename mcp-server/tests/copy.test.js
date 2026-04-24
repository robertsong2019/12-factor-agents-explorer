import { describe, it, after } from "node:test";
import assert from "node:assert/strict";
import { mkdir, rm, readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { toolHandlers } from "../dist/tools.js";

const { copy, write } = toolHandlers;
const TEST_DIR = "test-copy-dir";

describe("copy tool", () => {
  after(async () => {
    try { await rm(TEST_DIR, { recursive: true, force: true }); } catch {}
    try { await rm("test-copy-src.txt", { force: true }); } catch {}
    try { await rm("test-copy-dst.txt", { force: true }); } catch {}
    try { await rm("test-copy-deep", { recursive: true, force: true }); } catch {}
  });

  it("should copy a file to a new name", async () => {
    await write({ path: "test-copy-src.txt", content: "copy me" });
    const result = await copy({ source: "test-copy-src.txt", destination: "test-copy-dst.txt" });
    assert.equal(result.success, true);
    assert.equal(result.source, "test-copy-src.txt");
    assert.equal(result.destination, "test-copy-dst.txt");
    // Source still exists (copy, not move)
    const srcContent = await readFile("test-copy-src.txt", "utf-8");
    assert.equal(srcContent, "copy me");
    const dstContent = await readFile("test-copy-dst.txt", "utf-8");
    assert.equal(dstContent, "copy me");
  });

  it("should copy a file into a subdirectory", async () => {
    await write({ path: "test-copy-sub-src.txt", content: "payload" });
    await mkdir(TEST_DIR, { recursive: true });
    const result = await copy({ source: "test-copy-sub-src.txt", destination: `${TEST_DIR}/data.txt` });
    assert.equal(result.success, true);
    const content = await readFile(join(TEST_DIR, "data.txt"), "utf-8");
    assert.equal(content, "payload");
    // Source still exists
    const src = await readFile("test-copy-sub-src.txt", "utf-8");
    assert.equal(src, "payload");
  });

  it("should copy a directory recursively", async () => {
    await mkdir("test-copy-deep/folder", { recursive: true });
    await write({ path: "test-copy-deep/folder/item.txt", content: "inside" });
    const result = await copy({ source: "test-copy-deep/folder", destination: "test-copy-deep/folder-copy" });
    assert.equal(result.success, true);
    const content = await readFile("test-copy-deep/folder-copy/item.txt", "utf-8");
    assert.equal(content, "inside");
    // Original still exists
    const orig = await readFile("test-copy-deep/folder/item.txt", "utf-8");
    assert.equal(orig, "inside");
  });

  it("should create destination parent dirs", async () => {
    await write({ path: "test-copy-deep/a.txt", content: "deep" });
    const result = await copy({ source: "test-copy-deep/a.txt", destination: "test-copy-deep/x/y/z/a.txt" });
    assert.equal(result.success, true);
    const content = await readFile("test-copy-deep/x/y/z/a.txt", "utf-8");
    assert.equal(content, "deep");
  });

  it("should fail if source does not exist", async () => {
    const result = await copy({ source: "nonexistent-copy.txt", destination: "target.txt" });
    assert.equal(result.success, false);
    assert.equal(result.error, "Source not found");
  });

  it("should reject path traversal in source", async () => {
    await assert.rejects(
      () => copy({ source: "../../etc/passwd", destination: "stolen.txt" }),
      /Path traversal/
    );
  });

  it("should reject path traversal in destination", async () => {
    await assert.rejects(
      () => copy({ source: "safe.txt", destination: "../../tmp/evil.txt" }),
      /Path traversal/
    );
  });
});
