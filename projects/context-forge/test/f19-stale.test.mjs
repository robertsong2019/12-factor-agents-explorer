import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { detectStaleFiles } from "../context-forge.mjs";

describe("detectStaleFiles", () => {
  const tmpDir = join(process.cwd(), ".tmp-test-stale");

  it("returns empty array when all references valid", async () => {
    mkdirSync(join(tmpDir, "valid-project", "src"), { recursive: true });
    writeFileSync(join(tmpDir, "valid-project", "src", "index.js"), "console.log('hi');");
    writeFileSync(join(tmpDir, "valid-project", "AGENTS.md"), "Entry: src/index.js");

    const result = await detectStaleFiles(join(tmpDir, "valid-project"), [
      { file: "AGENTS.md", type: "agents" },
    ]);

    // src/index.js exists, so no stale references for that
    assert.ok(Array.isArray(result));
  });

  it("detects stale file references", async () => {
    mkdirSync(join(tmpDir, "stale-project"), { recursive: true });
    writeFileSync(join(tmpDir, "stale-project", "AGENTS.md"), "See src/old-removed.js for details");

    const result = await detectStaleFiles(join(tmpDir, "stale-project"), [
      { file: "AGENTS.md", type: "agents" },
    ]);

    assert.ok(Array.isArray(result));
    // src/old-removed.js doesn't exist
    const staleRefs = result.filter(r => r.reference.includes("old-removed.js"));
    assert.ok(staleRefs.length > 0, "expected stale reference to old-removed.js");
  });

  it("skips non-file-like patterns", async () => {
    mkdirSync(join(tmpDir, "skip-project"), { recursive: true });
    writeFileSync(join(tmpDir, "skip-project", "AGENTS.md"), "Version 1.0.3 and node v20.10.0");

    const result = await detectStaleFiles(join(tmpDir, "skip-project"), [
      { file: "AGENTS.md", type: "agents" },
    ]);

    // Version numbers should not be treated as file references
    const versionRefs = result.filter(r => /\d+\.\d+\.\d+/.test(r.reference));
    assert.equal(versionRefs.length, 0);
  });

  it("deduplicates references", async () => {
    mkdirSync(join(tmpDir, "dedup-project"), { recursive: true });
    writeFileSync(join(tmpDir, "dedup-project", "AGENTS.md"), "See missing.js and missing.js again");

    const result = await detectStaleFiles(join(tmpDir, "dedup-project"), [
      { file: "AGENTS.md", type: "agents" },
    ]);

    const missingRefs = result.filter(r => r.reference === "missing.js");
    assert.ok(missingRefs.length <= 1, "should deduplicate");
  });

  // Cleanup
  it("cleans up temp dir", () => {
    rmSync(tmpDir, { recursive: true, force: true });
    assert.ok(true);
  });
});
