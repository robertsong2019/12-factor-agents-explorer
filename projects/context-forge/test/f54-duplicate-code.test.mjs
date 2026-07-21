import { describe, it } from "node:test";
import assert from "node:assert";
import { analyzeDuplicateCode, formatDuplicateCodeReport } from "../context-forge.mjs";

describe("F54: analyzeDuplicateCode()", () => {
  it("returns zero results for empty input", () => {
    const result = analyzeDuplicateCode([]);
    assert.strictEqual(result.duplicateGroups, 0);
    assert.strictEqual(result.fileCount, 0);
    assert.strictEqual(result.wastedLines, 0);
  });

  it("returns zero results for unique files", () => {
    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: "const alpha = 1;\nconst beta = compute(alpha);\n" },
      { path: "b.mjs", content: "function gamma() {\n  return delta;\n}\n" },
    ]);
    assert.strictEqual(result.duplicateGroups, 0);
  });

  it("detects exact duplicate blocks across files", () => {
    const dup = [
      "function processItem(item) {",
      "  if (!item) return null;",
      "  const result = transform(item);",
      "  return validate(result);",
      "}",
    ].join("\n");

    const result = analyzeDuplicateCode([
      { path: "moduleA.mjs", content: "import { x } from 'y';\n" + dup + "\nexport { processItem };" },
      { path: "moduleB.mjs", content: "// utility\n" + dup + "\nmodule.exports = { processItem };" },
    ], { minLines: 4 });

    assert.ok(result.duplicateGroups >= 1, `Expected at least 1 dup group, got ${result.duplicateGroups}`);
    assert.ok(result.fileCount >= 2);
    assert.ok(result.totalOccurrences >= 2);
  });

  it("normalizes string literals when comparing", () => {
    const block1 = [
      "function greet(name) {",
      '  return "hello " + name;',
      "}",
    ].join("\n");

    const block2 = [
      "function greet(name) {",
      '  return "hi " + name;',
      "}",
    ].join("\n");

    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: block1 + "\n" },
      { path: "b.mjs", content: block2 + "\n" },
    ], { minLines: 3, minNormalizedLines: 2 });

    assert.ok(result.duplicateGroups >= 1);
  });

  it("ignores comments when fingerprinting", () => {
    const block1 = [
      "// This is a comment",
      "function compute(x) {",
      "  return x * 2;",
      "}",
    ].join("\n");

    const block2 = [
      "// Different comment",
      "function compute(x) {",
      "  return x * 2;",
      "}",
    ].join("\n");

    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: block1 + "\n" },
      { path: "b.mjs", content: block2 + "\n" },
    ], { minLines: 3, minNormalizedLines: 2 });

    assert.ok(result.duplicateGroups >= 1);
  });

  it("calculates wasted lines estimate", () => {
    const dup = [
      "function sharedUtil(data) {",
      "  const parsed = JSON.parse(data);",
      "  return parsed.map(x => x.id);",
      "}",
    ].join("\n");

    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: dup + "\n" },
      { path: "b.mjs", content: dup + "\n" },
      { path: "c.mjs", content: dup + "\n" },
    ], { minLines: 4 });

    assert.ok(result.wastedLines > 0);
    // 3 occurrences of 4 lines = 2 wasted copies * 4 lines = 8
    assert.ok(result.wastedLines >= 4);
  });

  it("respects minLines option", () => {
    const short = "const a = 1;\nconst b = 2;\n";

    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: short },
      { path: "b.mjs", content: short },
    ], { minLines: 6 });

    assert.strictEqual(result.duplicateGroups, 0);
  });

  it("handles null content gracefully", () => {
    const result = analyzeDuplicateCode([{ path: "null.mjs", content: null }]);
    assert.strictEqual(result.duplicateGroups, 0);
  });

  it("sorts by fileCount then totalLines", () => {
    const wideDup = Array.from({ length: 6 }, (_, i) => `const w${i} = ${i};`).join("\n");
    const narrowDup = Array.from({ length: 6 }, (_, i) => `const n${i} = ${i};`).join("\n");

    const result = analyzeDuplicateCode([
      { path: "f1.mjs", content: wideDup + "\n" },
      { path: "f2.mjs", content: wideDup + "\n" },
      { path: "f3.mjs", content: wideDup + "\n" },
      { path: "g1.mjs", content: narrowDup + "\n" },
      { path: "g2.mjs", content: narrowDup + "\n" },
    ], { minLines: 5 });

    // Wide dup (3 files) should rank higher than narrow dup (2 files)
    if (result.topDuplicates.length >= 2) {
      assert.ok(result.topDuplicates[0].fileCount >= result.topDuplicates[1].fileCount);
    }
  });
});

describe("F54: formatDuplicateCodeReport()", () => {
  it("formats clean report", () => {
    const report = formatDuplicateCodeReport({ duplicateGroups: 0 });
    assert.ok(report.includes("✅ No significant duplicate"));
  });

  it("formats report with duplicates", () => {
    const dup = [
      "function helper(x) {",
      "  return x + 1;",
      "  const unused = 99;",
      "}",
    ].join("\n");

    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: dup },
      { path: "b.mjs", content: dup },
    ], { minLines: 4 });

    const report = formatDuplicateCodeReport(result);
    assert.ok(report.includes("## Duplicate Code Analysis"));
    assert.ok(report.includes("Duplicate groups"));
    assert.ok(report.includes("Affected files"));
  });

  it("handles null result", () => {
    const report = formatDuplicateCodeReport(null);
    assert.ok(report.includes("✅"));
  });

  it("shows wasted lines estimate", () => {
    const dup = "const a = 1;\nconst b = 2;\nconst c = 3;\nconst d = 4;\nconst e = 5;\nconst f = 6;\n";

    const result = analyzeDuplicateCode([
      { path: "a.mjs", content: dup },
      { path: "b.mjs", content: dup },
    ], { minLines: 5 });

    const report = formatDuplicateCodeReport(result);
    assert.ok(report.includes("wasted lines"));
  });
});
