import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { compareProjects, formatComparison } from "../context-forge.mjs";

describe("compareProjects", () => {
  it("returns stable when projects are identical", () => {
    const a = {
      languages: [["JavaScript", 10]],
      dependencies: { lodash: "4" },
      scripts: { test: "node --test" },
      entryPoints: ["index.js"],
    };
    const result = compareProjects(a, { ...a });
    assert.equal(result.summary.totalChanges, 0);
    assert.equal(result.summary.trend, 'stable');
    assert.equal(result.added.length, 0);
    assert.equal(result.removed.length, 0);
    assert.equal(result.changed.length, 0);
  });

  it("detects added languages", () => {
    const before = { languages: [["JavaScript", 10]], dependencies: {}, scripts: {}, entryPoints: [] };
    const after = { languages: [["JavaScript", 10], ["TypeScript", 5]], dependencies: {}, scripts: {}, entryPoints: [] };
    const result = compareProjects(before, after);
    assert.ok(result.added.some(c => c.type === 'language' && c.name === 'TypeScript' && c.value === 5));
    assert.equal(result.summary.trend, 'growing');
  });

  it("detects removed dependencies", () => {
    const before = { languages: [], dependencies: { express: "4", lodash: "4" }, scripts: {}, entryPoints: [] };
    const after = { languages: [], dependencies: { lodash: "4" }, scripts: {}, entryPoints: [] };
    const result = compareProjects(before, after);
    assert.ok(result.removed.some(c => c.type === 'dependency' && c.name === 'express'));
    assert.equal(result.summary.trend, 'shrinking');
  });

  it("detects changed file counts in languages", () => {
    const before = { languages: [["JavaScript", 10]], dependencies: {}, scripts: {}, entryPoints: [] };
    const after = { languages: [["JavaScript", 15]], dependencies: {}, scripts: {}, entryPoints: [] };
    const result = compareProjects(before, after);
    assert.ok(result.changed.some(c => c.type === 'language' && c.name === 'JavaScript' && c.delta === 5));
  });

  it("detects version changes in dependencies", () => {
    const before = { languages: [], dependencies: { express: "4.17" }, scripts: {}, entryPoints: [] };
    const after = { languages: [], dependencies: { express: "5.0" }, scripts: {}, entryPoints: [] };
    const result = compareProjects(before, after);
    assert.ok(result.changed.some(c => c.type === 'dependency' && c.name === 'express' && c.before === '4.17' && c.after === '5.0'));
  });

  it("detects added and removed scripts", () => {
    const before = { languages: [], dependencies: {}, scripts: { build: "tsc", test: "jest" }, entryPoints: [] };
    const after = { languages: [], dependencies: {}, scripts: { build: "tsc", lint: "eslint" }, entryPoints: [] };
    const result = compareProjects(before, after);
    assert.ok(result.added.some(c => c.type === 'script' && c.name === 'lint'));
    assert.ok(result.removed.some(c => c.type === 'script' && c.name === 'test'));
    assert.equal(result.summary.trend, 'changing');
  });

  it("detects entry point changes", () => {
    const before = { languages: [], dependencies: {}, scripts: {}, entryPoints: ["index.js"] };
    const after = { languages: [], dependencies: {}, scripts: {}, entryPoints: ["index.js", "cli.js"] };
    const result = compareProjects(before, after);
    assert.ok(result.added.some(c => c.type === 'entryPoint' && c.name === 'cli.js'));
  });

  it("compares complexity scores when available", () => {
    const before = { languages: [], dependencies: {}, scripts: {}, entryPoints: [], complexityScore: 30 };
    const after = { languages: [], dependencies: {}, scripts: {}, entryPoints: [], complexityScore: 55 };
    const result = compareProjects(before, after);
    assert.ok(result.changed.some(c => c.type === 'complexity' && c.delta === 25));
  });

  it("handles empty objects gracefully", () => {
    const result = compareProjects({}, {});
    assert.equal(result.summary.totalChanges, 0);
    assert.equal(result.summary.trend, 'stable');
  });

  it("skips complexity comparison when not available", () => {
    const before = { languages: [], dependencies: {}, scripts: {}, entryPoints: [] };
    const after = { languages: [], dependencies: {}, scripts: {}, entryPoints: [] };
    const result = compareProjects(before, after);
    assert.equal(result.changed.filter(c => c.type === 'complexity').length, 0);
  });
});

describe("formatComparison", () => {
  it("formats stable comparison", () => {
    const changes = compareProjects({}, {});
    const text = formatComparison(changes);
    assert.ok(text.includes("# Project Comparison"));
    assert.ok(text.includes("**Trend:** stable"));
    assert.ok(text.includes("**Total changes:** 0"));
  });

  it("includes added section when items added", () => {
    const before = { languages: [], dependencies: {}, scripts: {}, entryPoints: [] };
    const after = { languages: [["Python", 3]], dependencies: { flask: "2" }, scripts: {}, entryPoints: [] };
    const changes = compareProjects(before, after);
    const text = formatComparison(changes);
    assert.ok(text.includes("## Added ✅"));
    assert.ok(text.includes("[language] Python (3)"));
    assert.ok(text.includes("[dependency] flask (2)"));
  });

  it("includes removed section when items removed", () => {
    const before = { languages: [["Ruby", 5]], dependencies: {}, scripts: {}, entryPoints: [] };
    const after = { languages: [], dependencies: {}, scripts: {}, entryPoints: [] };
    const changes = compareProjects(before, after);
    const text = formatComparison(changes);
    assert.ok(text.includes("## Removed ❌"));
    assert.ok(text.includes("[language] Ruby (5)"));
  });

  it("includes changed section with deltas", () => {
    const before = { languages: [["JavaScript", 10]], dependencies: {}, scripts: {}, entryPoints: [], complexityScore: 20 };
    const after = { languages: [["JavaScript", 20]], dependencies: {}, scripts: {}, entryPoints: [], complexityScore: 45 };
    const changes = compareProjects(before, after);
    const text = formatComparison(changes);
    assert.ok(text.includes("## Changed 🔄"));
    assert.ok(text.includes("10 → 20 (+10)"));
    assert.ok(text.includes("20 → 45 (+25)"));
  });

  it("handles version change formatting", () => {
    const before = { languages: [], dependencies: { pkg: "1.0" }, scripts: {}, entryPoints: [] };
    const after = { languages: [], dependencies: { pkg: "2.0" }, scripts: {}, entryPoints: [] };
    const changes = compareProjects(before, after);
    const text = formatComparison(changes);
    assert.ok(text.includes("1.0 → 2.0"));
  });
});
