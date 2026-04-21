import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { toolHandlers } from "../dist/tools.js";

const TEST_DIR = join(process.cwd(), ".test-search-files");
const search = toolHandlers.search_files;

describe("search_files tool", () => {
  before(async () => {
    await mkdir(join(TEST_DIR, "sub"), { recursive: true });
    await writeFile(join(TEST_DIR, "hello.txt"), "Hello World\nFoo Bar\nHello Again");
    await writeFile(join(TEST_DIR, "sub", "nested.ts"), "const x = 42;\n// TODO: fix this\nconsole.log(x);");
    await writeFile(join(TEST_DIR, "data.json"), '{"name": "test", "value": 42}');
  });

  after(async () => {
    await rm(TEST_DIR, { recursive: true, force: true });
  });

  it("should find matches by regex pattern", async () => {
    const result = await search({ pattern: "Hello", path: TEST_DIR });
    assert.equal(result.tool, "search_files");
    assert.equal(result.files, 1);
    assert.equal(result.results[0].file, "hello.txt");
    assert.equal(result.results[0].matches.length, 2);
  });

  it("should filter by include glob", async () => {
    const result = await search({ pattern: "42", path: TEST_DIR, include: "*.ts" });
    assert.equal(result.files, 1);
    assert.equal(result.results[0].file, join("sub", "nested.ts"));
  });

  it("should respect maxResults", async () => {
    const result = await search({ pattern: ".", path: TEST_DIR, maxResults: 1 });
    assert.ok(result.totalMatches <= 1);
  });

  it("should search subdirectories recursively", async () => {
    const result = await search({ pattern: "TODO", path: TEST_DIR });
    assert.ok(result.results.some(r => r.file.includes("nested.ts")));
  });

  it("should return empty for no matches", async () => {
    const result = await search({ pattern: "zzzznonexistent", path: TEST_DIR });
    assert.equal(result.files, 0);
    assert.equal(result.totalMatches, 0);
  });

  it("should reject invalid regex", async () => {
    const result = await search({ pattern: "[invalid", path: TEST_DIR });
    assert.equal(result.success, false);
    assert.ok(result.error.includes("Invalid regex"));
  });

  it("should search JSON files", async () => {
    const result = await search({ pattern: '"name"', path: TEST_DIR, include: "*.json" });
    assert.equal(result.files, 1);
    assert.ok(result.results[0].matches.length >= 1);
  });
});
