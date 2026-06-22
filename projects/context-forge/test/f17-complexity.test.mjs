import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeComplexity, summarizeAnalysis } from "../context-forge.mjs";

describe("analyzeComplexity", () => {
  it("returns zero values for empty project", () => {
    const info = { dependencies: {}, devDependencies: {}, scripts: {}, entryPoints: [] };
    const langs = new Map();
    const result = analyzeComplexity(info, langs, { allImports: [] }, [], {});
    assert.equal(result.totalFiles, 0);
    assert.equal(result.totalDeps, 0);
    assert.equal(result.complexityScore, 0);
    assert.equal(result.category, 'minimal');
  });

  it("counts files across languages", () => {
    const info = { dependencies: { lodash: "4.17" }, scripts: { test: "node --test" }, entryPoints: ["index.js"] };
    const langs = new Map([["JavaScript", 10], ["TypeScript", 5], ["CSS", 2]]);
    const result = analyzeComplexity(info, langs, { allImports: ["fs", "path", "fs"] }, [{ name: "foo" }], { eslint: {} });
    assert.equal(result.totalFiles, 17);
    assert.equal(result.totalDeps, 1);
    assert.equal(result.totalScripts, 1);
    assert.equal(result.totalEntryPoints, 1);
    assert.equal(result.totalImports, 3);
    assert.equal(result.uniqueImports, 2);
    assert.equal(result.apiCount, 1);
    assert.equal(result.configCount, 1);
  });

  it("computes language diversity (normalized Shannon entropy)", () => {
    const info = { dependencies: {} };
    const langs = new Map([["JavaScript", 5], ["TypeScript", 5]]);
    const result = analyzeComplexity(info, langs, { allImports: [] }, [], {});
    // Equal split = maximum diversity for 2 languages
    assert.ok(result.languageDiversity > 0.95);
    assert.ok(result.languageDiversity <= 1.0);
  });

  it("computes low diversity for single-language project", () => {
    const info = { dependencies: {} };
    const langs = new Map([["JavaScript", 100]]);
    const result = analyzeComplexity(info, langs, { allImports: [] }, [], {});
    assert.equal(result.languageDiversity, 0);
    assert.equal(result.dominantShare, 1.0);
    assert.equal(result.dominantLanguage, "JavaScript");
  });

  it("computes dominant language share correctly", () => {
    const info = { dependencies: {} };
    const langs = new Map([["JavaScript", 80], ["CSS", 20]]);
    const result = analyzeComplexity(info, langs, { allImports: [] }, [], {});
    assert.equal(result.dominantShare, 0.8);
    assert.equal(result.dominantLanguage, "JavaScript");
  });

  it("assigns correct category based on complexity score", () => {
    const minimalInfo = { dependencies: {}, scripts: {}, entryPoints: [] };
    const minimalLangs = new Map([["JavaScript", 1]]);
    const r1 = analyzeComplexity(minimalInfo, minimalLangs, { allImports: [] }, [], {});
    assert.equal(r1.category, 'minimal');

    const bigInfo = { dependencies: Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`dep${i}`, "1.0"])), scripts: { start: "x" }, entryPoints: ["a"] };
    const bigLangs = new Map([["JavaScript", 25]]);
    const r2 = analyzeComplexity(bigInfo, bigLangs, { allImports: Array.from({ length: 25 }, (_, i) => `mod${i}`) }, Array.from({ length: 16 }, (_, i) => ({ name: `fn${i}` })), {});
    assert.ok(r2.complexityScore >= 40, `expected >=40, got ${r2.complexityScore}`);
    assert.ok(['medium', 'large', 'enterprise'].includes(r2.category), `expected medium+, got ${r2.category}`);
  });

  it("reads dependency info from pkg fallback", () => {
    const info = { pkg: { dependencies: { express: "4" } } };
    const result = analyzeComplexity(info, new Map(), { allImports: [] }, [], {});
    assert.equal(result.totalDeps, 1);
  });

  it("caps complexity score at 100", () => {
    const info = {
      dependencies: Object.fromEntries(Array.from({ length: 50 }, (_, i) => [`dep${i}`, "1"])),
      devDependencies: {},
      scripts: { test: "x" },
      entryPoints: ["a", "b"],
    };
    const langs = new Map([["JavaScript", 50]]);
    const imports = { allImports: Array.from({ length: 50 }, (_, i) => `m${i}`) };
    const api = Array.from({ length: 50 }, (_, i) => ({ name: `f${i}` }));
    const configs = Object.fromEntries(Array.from({ length: 10 }, (_, i) => [`cfg${i}`, {}]));
    const result = analyzeComplexity(info, langs, imports, api, configs);
    assert.ok(result.complexityScore <= 100, `expected <=100, got ${result.complexityScore}`);
    assert.equal(result.category, 'enterprise');
  });
});

describe("summarizeAnalysis", () => {
  it("generates a markdown summary with headers", () => {
    const info = { name: "my-project", type: "npm" };
    const langs = new Map([["JavaScript", 10], ["CSS", 3]]);
    const complexity = analyzeComplexity(info, langs, { allImports: ["fs"] }, [], {});
    const summary = summarizeAnalysis(info, langs, complexity);
    assert.ok(summary.includes("# Analysis Summary"));
    assert.ok(summary.includes("**Project:** my-project"));
    assert.ok(summary.includes("**Type:** npm"));
    assert.ok(summary.includes("## Metrics"));
    assert.ok(summary.includes("| Files | 13 |"));
  });

  it("includes language breakdown with percentages", () => {
    const info = { name: "test" };
    const langs = new Map([["JavaScript", 8], ["TypeScript", 2]]);
    const complexity = analyzeComplexity(info, langs, { allImports: [] }, [], {});
    const summary = summarizeAnalysis(info, langs, complexity);
    assert.ok(summary.includes("## Language Breakdown"));
    assert.ok(summary.includes("**JavaScript**: 8 files (80%)"));
    assert.ok(summary.includes("**TypeScript**: 2 files (20%)"));
  });

  it("handles missing complexity data gracefully", () => {
    const info = { name: "bare" };
    const langs = new Map();
    const summary = summarizeAnalysis(info, langs, {});
    assert.ok(summary.includes("N/A"));
    assert.ok(summary.includes("# Analysis Summary"));
  });

  it("includes complexity score and category", () => {
    const info = { name: "scored" };
    const langs = new Map([["JavaScript", 5]]);
    const complexity = analyzeComplexity(info, langs, { allImports: ["a", "b"] }, [{ name: "x" }], {});
    const summary = summarizeAnalysis(info, langs, complexity);
    assert.ok(summary.includes(`**Complexity:** ${complexity.complexityScore}/100`));
    assert.ok(summary.includes(complexity.category));
  });

  it("sorts languages by file count descending", () => {
    const info = { name: "sorted" };
    const langs = new Map([["CSS", 2], ["JavaScript", 10], ["HTML", 1]]);
    const complexity = analyzeComplexity(info, langs, { allImports: [] }, [], {});
    const summary = summarizeAnalysis(info, langs, complexity);
    const jsIdx = summary.indexOf("**JavaScript**");
    const cssIdx = summary.indexOf("**CSS**");
    const htmlIdx = summary.indexOf("**HTML**");
    assert.ok(jsIdx < cssIdx);
    assert.ok(cssIdx < htmlIdx);
  });
});
