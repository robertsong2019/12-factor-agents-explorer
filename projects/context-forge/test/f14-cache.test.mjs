import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, mkdir, writeFile, readFile, utimes } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { loadCache, saveCache, invalidateCache } from "../context-forge.mjs";

// ─── F14: Analysis Cache ─────────────────────────────────────────

describe("F14: saveCache + loadCache", () => {
  let tmpDir;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-cache-"));
  });

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("saves and loads cache round-trip", async () => {
    await saveCache(tmpDir, { languages: { TypeScript: 1000 }, frameworks: ["React"] });
    const loaded = await loadCache(tmpDir);
    assert.ok(loaded);
    assert.equal(loaded.languages.TypeScript, 1000);
    assert.deepEqual(loaded.frameworks, ["React"]);
    assert.equal(loaded.version, 1);
  });

  it("returns null when no cache exists", async () => {
    const result = await loadCache(tmpDir);
    assert.equal(result, null);
  });

  it("invalidates when directory mtime changes", async () => {
    // Save cache
    await saveCache(tmpDir, { languages: { JavaScript: 500 } });
    
    // Bump directory mtime forward
    const future = new Date(Date.now() + 5000);
    await utimes(tmpDir, future, future);

    const loaded = await loadCache(tmpDir);
    assert.equal(loaded, null, "cache should be invalidated when mtime changes");
  });

  it("handles corrupted cache gracefully", async () => {
    await writeFile(join(tmpDir, ".context-forge-cache.json"), "{ invalid json }");
    const result = await loadCache(tmpDir);
    assert.equal(result, null);
  });

  it("includes rootMtime in saved cache", async () => {
    await saveCache(tmpDir, { languages: {} });
    const raw = JSON.parse(await readFile(join(tmpDir, ".context-forge-cache.json"), "utf8"));
    assert.ok(typeof raw.rootMtime === "number");
    assert.equal(raw.version, 1);
  });
});

describe("F14: invalidateCache", () => {
  let tmpDir;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-invalidate-"));
  });

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("removes existing cache file", async () => {
    await saveCache(tmpDir, { languages: {} });
    invalidateCache(tmpDir);
    const result = await loadCache(tmpDir);
    assert.equal(result, null);
  });

  it("does nothing when no cache exists", () => {
    // Should not throw
    invalidateCache(tmpDir);
  });
});

describe("F14: cache preserves complex data", () => {
  let tmpDir;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "ctxforge-complex-"));
  });

  afterEach(async () => {
    if (tmpDir) await rm(tmpDir, { recursive: true, force: true });
  });

  it("preserves nested objects and arrays", async () => {
    const data = {
      languages: { TypeScript: 5000, JavaScript: 2000 },
      frameworks: ["Next.js", "React", "Testing"],
      entryPoints: ["src/index.ts", "src/server.ts"],
      scripts: { dev: "vite", build: "tsc", test: "node --test" },
      deps: { next: "^14.0.0", react: "^18.0.0" },
      configFiles: ["tsconfig.json", ".eslintrc.json"],
    };
    await saveCache(tmpDir, data);
    const loaded = await loadCache(tmpDir);
    assert.deepEqual(loaded.languages, data.languages);
    assert.deepEqual(loaded.frameworks, data.frameworks);
    assert.deepEqual(loaded.entryPoints, data.entryPoints);
    assert.deepEqual(loaded.scripts, data.scripts);
    assert.deepEqual(loaded.deps, data.deps);
    assert.deepEqual(loaded.configFiles, data.configFiles);
  });
});
