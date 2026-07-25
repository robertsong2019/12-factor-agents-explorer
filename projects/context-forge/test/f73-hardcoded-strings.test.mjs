import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeHardcodedStrings, formatHardcodedStringsReport } from "../context-forge.mjs";

function makeFile(path, content) {
  return { path, content };
}

// ─── analyzeHardcodedStrings ─────────────────────────────────────

describe("analyzeHardcodedStrings", () => {
  // ─── Empty / baseline ─────────────────────────────────────────

  it("returns perfect score for empty file list", () => {
    const result = analyzeHardcodedStrings([]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.totalStringsAnalyzed, 0);
    assert.equal(result.issues.length, 0);
  });

  it("handles files with no string literals", () => {
    const result = analyzeHardcodedStrings([
      makeFile("clean.js", "const x = 1;\nlet y = 2;\n"),
    ]);
    assert.equal(result.score, 100);
  });

  it("ignores non-string content", () => {
    const result = analyzeHardcodedStrings([
      makeFile("a.js", null),
      makeFile("b.js", undefined),
    ]);
    assert.equal(result.score, 100);
  });

  // ─── Hardcoded URLs ───────────────────────────────────────────

  it("detects hardcoded URLs", () => {
    const result = analyzeHardcodedStrings([
      makeFile("url.js", 'const endpoint = "https://api.example.com/v1";\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "hardcoded-url"));
    assert.ok(result.stats.hardcodedUrls >= 1);
  });

  it("detects http URLs", () => {
    const result = analyzeHardcodedStrings([
      makeFile("url2.js", "const old = 'http://legacy.server.internal/health';\n"),
    ]);
    assert.ok(result.stats.hardcodedUrls >= 1);
  });

  // ─── Hardcoded file paths ─────────────────────────────────────

  it("detects hardcoded unix paths", () => {
    const result = analyzeHardcodedStrings([
      makeFile("path.js", 'const log = "/var/log/app.log";\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "hardcoded-path"));
  });

  it("detects /tmp paths", () => {
    const result = analyzeHardcodedStrings([
      makeFile("tmp.js", 'const tmp = "/tmp/cache.json";\n'),
    ]);
    assert.ok(result.stats.hardcodedPaths >= 1);
  });

  // ─── Magic numbers ────────────────────────────────────────────

  it("detects large magic numbers", () => {
    const result = analyzeHardcodedStrings([
      makeFile("magic.js", "const timeout = 86400000;\n"),
    ]);
    assert.ok(result.issues.some(i => i.label === "magic-number"));
  });

  it("does not flag 0, 1, 2 as magic numbers", () => {
    const result = analyzeHardcodedStrings([
      makeFile("ok.js", "const a = 0;\nconst b = 1;\nconst c = 2;\n"),
    ]);
    assert.equal(result.stats.magicNumbers, 0);
  });

  it("skips magic numbers in comments", () => {
    const result = analyzeHardcodedStrings([
      makeFile("cmt.js", "// timeout is 86400000\n"),
    ]);
    assert.equal(result.stats.magicNumbers, 0);
  });

  // ─── Repeated strings ─────────────────────────────────────────

  it("detects strings repeated 3+ times", () => {
    const result = analyzeHardcodedStrings([
      makeFile("rep.js", [
        'const a = "processing";',
        'const b = "processing";',
        'const c = "processing";',
      ].join("\n")),
    ]);
    assert.ok(result.repeatedStrings.length >= 1);
    assert.equal(result.repeatedStrings[0].count, 3);
  });

  it("detects high-severity strings repeated 5+ times", () => {
    const result = analyzeHardcodedStrings([
      makeFile("many.js", [
        'log("started")',
        'log("started")',
        'log("started")',
        'log("started")',
        'log("started")',
      ].join("\n")),
    ]);
    assert.ok(result.repeatedStrings.some(r => r.severity === "high"));
  });

  it("does not flag strings appearing only twice", () => {
    const result = analyzeHardcodedStrings([
      makeFile("pair.js", 'const a = "hello world";\nconst b = "hello world";\n'),
    ]);
    assert.equal(result.repeatedStrings.length, 0);
  });

  it("respects custom minRepeats option", () => {
    const result = analyzeHardcodedStrings([
      makeFile("custom.js", 'const a = "custom val";\nconst b = "custom val";\n'),
    ], { minRepeats: 2 });
    assert.ok(result.repeatedStrings.length >= 1);
  });

  it("skips short strings (< 5 chars)", () => {
    const result = analyzeHardcodedStrings([
      makeFile("short.js", 'const a = "ab";\nconst b = "ab";\nconst c = "ab";\n'),
    ]);
    assert.equal(result.repeatedStrings.length, 0);
  });

  // ─── Comment / import skipping ────────────────────────────────

  it("skips string detection in comments", () => {
    const result = analyzeHardcodedStrings([
      makeFile("cmt.js", '// const url = "https://example.com";\n'),
    ]);
    assert.equal(result.stats.hardcodedUrls, 0);
  });

  it("skips import statements", () => {
    const result = analyzeHardcodedStrings([
      makeFile("imp.js", 'import foo from "https://example.com/module";\n'),
    ]);
    assert.equal(result.stats.hardcodedUrls, 0);
  });

  // ─── Score calculation ────────────────────────────────────────

  it("calculates non-100 score when issues exist", () => {
    const result = analyzeHardcodedStrings([
      makeFile("bad.js", 'const u = "https://api.example.com";\nconst p = "/var/log/app.log";\n'),
    ]);
    assert.ok(result.score < 100);
  });

  // ─── Multi-file ───────────────────────────────────────────────

  it("tracks repeated strings across files", () => {
    const result = analyzeHardcodedStrings([
      makeFile("f1.js", 'const ev = "user_created";\n'),
      makeFile("f2.js", 'const ev = "user_created";\n'),
      makeFile("f3.js", 'const ev = "user_created";\n'),
    ]);
    assert.ok(result.repeatedStrings.length >= 1);
    assert.ok(result.repeatedStrings[0].count >= 3);
  });

  // ─── Stats ────────────────────────────────────────────────────

  it("tracks severity counts", () => {
    const result = analyzeHardcodedStrings([
      makeFile("multi.js", [
        'const a = "https://example.com";',  // medium url
        'const b = "/var/log/x";',            // low path
        'const c = 10000;',                   // low magic number
      ].join("\n")),
    ]);
    assert.ok(result.stats.mediumSeverity >= 1);
    assert.ok(result.stats.lowSeverity >= 2);
  });

  it("sorts repeated strings by count descending", () => {
    const result = analyzeHardcodedStrings([
      makeFile("sort.js", [
        '"least repeated value here"',
        '"least repeated value here"',
        '"least repeated value here"',
        '"most repeated string right here"',
        '"most repeated string right here"',
        '"most repeated string right here"',
        '"most repeated string right here"',
        '"most repeated string right here"',
      ].join("\n")),
    ]);
    assert.ok(result.repeatedStrings.length >= 2);
    assert.ok(result.repeatedStrings[0].count >= result.repeatedStrings[1].count);
  });
});

// ─── formatHardcodedStringsReport ────────────────────────────────

describe("formatHardcodedStringsReport", () => {
  it("formats empty result", () => {
    const report = formatHardcodedStringsReport(analyzeHardcodedStrings([]));
    assert.ok(report.includes("Hardcoded Strings"));
    assert.ok(report.includes("No string"));
  });

  it("formats result with issues", () => {
    const result = analyzeHardcodedStrings([
      makeFile("bad.js", 'const u = "https://example.com";\n'),
    ]);
    const report = formatHardcodedStringsReport(result);
    assert.ok(report.includes("hardcoded-url"));
  });

  it("formats repeated strings section", () => {
    const result = analyzeHardcodedStrings([
      makeFile("rep.js", [
        '"test string value"',
        '"test string value"',
        '"test string value"',
      ].join("\n")),
    ]);
    const report = formatHardcodedStringsReport(result);
    assert.ok(report.includes("Top Repeated Strings"));
    assert.ok(report.includes("3 times"));
  });

  it("formats other issues section", () => {
    const result = analyzeHardcodedStrings([
      makeFile("other.js", 'const u = "https://example.com";\n'),
    ]);
    const report = formatHardcodedStringsReport(result);
    assert.ok(report.includes("Other Issues"));
  });

  it("includes issue breakdown", () => {
    const result = analyzeHardcodedStrings([
      makeFile("brk.js", 'const u = "https://example.com";\n'),
    ]);
    const report = formatHardcodedStringsReport(result);
    assert.ok(report.includes("Hardcoded URLs:"));
    assert.ok(report.includes("Hardcoded paths:"));
    assert.ok(report.includes("Magic numbers:"));
  });
});
