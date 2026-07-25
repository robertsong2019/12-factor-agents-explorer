import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeImportHygiene, formatImportHygieneReport } from "../context-forge.mjs";

function makeFile(path, content) {
  return { path, content };
}

// ─── analyzeImportHygiene ────────────────────────────────────────

describe("analyzeImportHygiene", () => {
  // ─── Empty / baseline ─────────────────────────────────────────

  it("returns perfect score for empty file list", () => {
    const result = analyzeImportHygiene([]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.totalImports, 0);
    assert.equal(result.issues.length, 0);
  });

  it("handles files with no imports", () => {
    const result = analyzeImportHygiene([
      makeFile("clean.js", "const x = 1;\nfunction foo() {}\n"),
    ]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.totalImports, 0);
  });

  it("ignores non-string content", () => {
    const result = analyzeImportHygiene([
      makeFile("a.js", null),
      makeFile("b.js", undefined),
    ]);
    assert.equal(result.score, 100);
  });

  it("ignores non-JS files", () => {
    const result = analyzeImportHygiene([
      makeFile("readme.md", "import foo from 'bar'\n"),
      makeFile("data.json", '{"import": "foo"}\n'),
    ]);
    assert.equal(result.stats.totalImports, 0);
  });

  // ─── Import detection ─────────────────────────────────────────

  it("detects ES module imports", () => {
    const result = analyzeImportHygiene([
      makeFile("mod.js", [
        'import foo from "aaa";',
        'import bar from "bbb";',
        'import baz from "ccc";',
      ].join("\n")),
    ]);
    assert.equal(result.stats.totalImports, 3);
    assert.equal(result.stats.sortedFiles, 1);
    assert.equal(result.stats.unsortedFiles, 0);
  });

  it("detects named imports", () => {
    const result = analyzeImportHygiene([
      makeFile("named.js", [
        'import { foo, bar } from "mod-a";',
        'import { baz } from "mod-b";',
      ].join("\n")),
    ]);
    assert.equal(result.stats.totalImports, 2);
  });

  it("detects side-effect-only imports", () => {
    const result = analyzeImportHygiene([
      makeFile("side.js", [
        'import "polyfill";',
        'import foo from "aaa";',
      ].join("\n")),
    ]);
    assert.equal(result.stats.totalImports, 2);
  });

  // ─── Sorting detection ────────────────────────────────────────

  it("flags unsorted imports", () => {
    const result = analyzeImportHygiene([
      makeFile("unsorted.js", [
        'import zebra from "zzz";',
        'import alpha from "aaa";',
        'import mike from "mmm";',
      ].join("\n")),
    ]);
    assert.equal(result.stats.unsortedFiles, 1);
    assert.ok(result.issues.some(i => i.label === "unsorted-imports"));
  });

  it("does not flag sorted imports", () => {
    const result = analyzeImportHygiene([
      makeFile("sorted.js", [
        'import alpha from "aaa";',
        'import mike from "mmm";',
        'import zebra from "zzz";',
      ].join("\n")),
    ]);
    assert.equal(result.stats.sortedFiles, 1);
    assert.equal(result.stats.unsortedFiles, 0);
    assert.ok(!result.issues.some(i => i.label === "unsorted-imports"));
  });

  it("handles single import (no sorting needed)", () => {
    const result = analyzeImportHygiene([
      makeFile("single.js", 'import foo from "bar";\n'),
    ]);
    assert.equal(result.stats.filesChecked, 0);
  });

  // ─── Duplicate imports ────────────────────────────────────────

  it("flags duplicate imports from same module", () => {
    const result = analyzeImportHygiene([
      makeFile("dup.js", [
        'import { foo } from "mod-a";',
        'import { bar } from "aaa";',
        'import { baz } from "mod-a";',
      ].join("\n")),
    ]);
    assert.ok(result.issues.some(i => i.label === "duplicate-import"));
  });

  it("does not flag single imports from different modules", () => {
    const result = analyzeImportHygiene([
      makeFile("ok.js", [
        'import foo from "aaa";',
        'import bar from "bbb";',
      ].join("\n")),
    ]);
    assert.ok(!result.issues.some(i => i.label === "duplicate-import"));
  });

  // ─── Self-import detection ────────────────────────────────────

  it("detects potential self-imports", () => {
    const result = analyzeImportHygiene([
      makeFile("my-module.js", [
        'import something from "./my-module";',
        'import other from "aaa";',
      ].join("\n")),
    ]);
    assert.ok(result.issues.some(i => i.label === "self-import"));
  });

  // ─── Side-effect ordering ─────────────────────────────────────

  it("flags side-effect imports after regular imports", () => {
    const result = analyzeImportHygiene([
      makeFile("mixed.js", [
        'import foo from "aaa";',
        'import bar from "bbb";',
        'import "polyfill";',
      ].join("\n")),
    ]);
    assert.ok(result.issues.some(i => i.label === "mixed-import-order"));
  });

  it("does not flag side-effect imports before regular imports", () => {
    const result = analyzeImportHygiene([
      makeFile("order.js", [
        'import "polyfill";',
        'import foo from "aaa";',
        'import bar from "bbb";',
      ].join("\n")),
    ]);
    assert.ok(!result.issues.some(i => i.label === "mixed-import-order"));
  });

  // ─── Score calculation ────────────────────────────────────────

  it("returns 100 for clean imports", () => {
    const result = analyzeImportHygiene([
      makeFile("clean.js", [
        'import aaa from "aaa";',
        'import bbb from "bbb";',
      ].join("\n")),
    ]);
    assert.equal(result.score, 100);
  });

  it("returns lower score for messy imports", () => {
    const result = analyzeImportHygiene([
      makeFile("messy.js", [
        'import z from "zzz";',
        'import a from "aaa";',
        'import { x } from "zzz";',
      ].join("\n")),
    ]);
    assert.ok(result.score < 100);
  });

  // ─── TypeScript files ─────────────────────────────────────────

  it("handles TypeScript files", () => {
    const result = analyzeImportHygiene([
      makeFile("comp.ts", [
        'import foo from "bbb";',
        'import bar from "aaa";',
      ].join("\n")),
    ]);
    assert.equal(result.stats.totalImports, 2);
    assert.equal(result.stats.unsortedFiles, 1);
  });

  it("handles .tsx files", () => {
    const result = analyzeImportHygiene([
      makeFile("view.tsx", 'import React from "react";\n'),
    ]);
    assert.ok(result.stats.totalImports >= 1);
  });

  // ─── Multi-file ───────────────────────────────────────────────

  it("analyzes imports across multiple files", () => {
    const result = analyzeImportHygiene([
      makeFile("f1.js", 'import a from "aaa";\nimport b from "bbb";\n'),
      makeFile("f2.js", 'import z from "zzz";\nimport a from "aaa";\n'),
    ]);
    assert.equal(result.stats.totalImports, 4);
    assert.equal(result.stats.sortedFiles, 1);
    assert.equal(result.stats.unsortedFiles, 1);
  });
});

// ─── formatImportHygieneReport ───────────────────────────────────

describe("formatImportHygieneReport", () => {
  it("formats empty result", () => {
    const report = formatImportHygieneReport(analyzeImportHygiene([]));
    assert.ok(report.includes("Import Hygiene"));
    assert.ok(report.includes("No import"));
  });

  it("formats clean result", () => {
    const result = analyzeImportHygiene([
      makeFile("clean.js", [
        'import a from "aaa";',
        'import b from "bbb";',
      ].join("\n")),
    ]);
    const report = formatImportHygieneReport(result);
    assert.ok(report.includes("Score:** 100"));
    assert.ok(report.includes("well-organized"));
  });

  it("formats result with issues", () => {
    const result = analyzeImportHygiene([
      makeFile("bad.js", [
        'import z from "zzz";',
        'import a from "aaa";',
      ].join("\n")),
    ]);
    const report = formatImportHygieneReport(result);
    assert.ok(report.includes("Issues Found"));
    assert.ok(report.includes("unsorted-imports"));
  });

  it("includes summary stats", () => {
    const result = analyzeImportHygiene([
      makeFile("stats.js", [
        'import a from "aaa";',
        'import b from "bbb";',
      ].join("\n")),
    ]);
    const report = formatImportHygieneReport(result);
    assert.ok(report.includes("Sorted files:"));
    assert.ok(report.includes("Unsorted files:"));
    assert.ok(report.includes("Duplicate imports:"));
  });

  it("truncates long issue lists", () => {
    const files = [];
    for (let i = 0; i < 35; i++) {
      files.push(makeFile(`f${i}.js`, 'import z from "zzz";\nimport a from "aaa";\n'));
    }
    const result = analyzeImportHygiene(files);
    const report = formatImportHygieneReport(result);
    assert.ok(report.includes("more"));
  });
});
