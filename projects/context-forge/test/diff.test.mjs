import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { generateDiff, formatDiff } from "../context-forge.mjs";

describe("generateDiff", () => {
  it("returns empty array for identical content", () => {
    const diffs = generateDiff("hello\nworld", "hello\nworld");
    assert.deepEqual(diffs, []);
  });

  it("detects added lines", () => {
    const diffs = generateDiff("line1\nline3", "line1\nline2\nline3");
    const added = diffs.filter((d) => d.type === "added");
    assert.ok(added.length >= 1);
    assert.ok(added.some((d) => d.line === "line2"));
  });

  it("detects removed lines", () => {
    const diffs = generateDiff("line1\nline2\nline3", "line1\nline3");
    const removed = diffs.filter((d) => d.type === "removed");
    assert.ok(removed.length >= 1);
    assert.ok(removed.some((d) => d.line === "line2"));
  });

  it("detects modified lines (remove + add)", () => {
    const diffs = generateDiff("old value", "new value");
    const removed = diffs.filter((d) => d.type === "removed");
    const added = diffs.filter((d) => d.type === "added");
    assert.ok(removed.some((d) => d.line === "old value"));
    assert.ok(added.some((d) => d.line === "new value"));
  });

  it("preserves context lines around changes", () => {
    const existing = "a\nb\nc\nd\ne";
    const updated = "a\nb\nX\nd\ne";
    const diffs = generateDiff(existing, updated);
    const contextLines = diffs.filter((d) => d.type === "context").map((d) => d.line);
    // Should include unchanged lines around the modification
    assert.ok(contextLines.includes("a") || contextLines.includes("b"));
    assert.ok(contextLines.includes("d") || contextLines.includes("e"));
  });

  it("handles completely different content", () => {
    const diffs = generateDiff("aaa", "bbb");
    assert.ok(diffs.some((d) => d.type === "removed" && d.line === "aaa"));
    assert.ok(diffs.some((d) => d.type === "added" && d.line === "bbb"));
  });

  it("handles empty existing content", () => {
    const diffs = generateDiff("", "new content");
    assert.ok(diffs.some((d) => d.type === "added" && d.line === "new content"));
  });

  it("handles empty updated content", () => {
    const diffs = generateDiff("old content", "");
    assert.ok(diffs.some((d) => d.type === "removed" && d.line === "old content"));
  });

  it("adds separators for distant changes", () => {
    const existing = Array.from({ length: 20 }, (_, i) => `line${i}`).join("\n");
    const updated = existing.replace("line3", "CHANGED3").replace("line17", "CHANGED17");
    const diffs = generateDiff(existing, updated);
    const separators = diffs.filter((d) => d.type === "separator");
    assert.ok(separators.length >= 1, "should have at least one separator for distant changes");
  });
});

describe("formatDiff", () => {
  it("returns '(no changes)' for empty diff", () => {
    assert.equal(formatDiff([]), "(no changes)");
  });

  it("formats added lines with +", () => {
    const diffs = [{ type: "added", line: "new", newLine: 1 }];
    const out = formatDiff(diffs);
    assert.ok(out.includes("+ new"));
  });

  it("formats removed lines with -", () => {
    const diffs = [{ type: "removed", line: "old", oldLine: 1 }];
    const out = formatDiff(diffs);
    assert.ok(out.includes("- old"));
  });

  it("formats context lines with leading spaces", () => {
    const diffs = [{ type: "context", line: "same", oldLine: 1, newLine: 1 }];
    const out = formatDiff(diffs);
    assert.ok(out.includes("  same"));
  });

  it("formats separators as ...", () => {
    const diffs = [{ type: "separator" }];
    const out = formatDiff(diffs);
    assert.ok(out.includes("..."));
  });

  it("formats mixed diff output", () => {
    const diffs = [
      { type: "context", line: "header", oldLine: 1, newLine: 1 },
      { type: "removed", line: "old", oldLine: 2 },
      { type: "added", line: "new", newLine: 2 },
      { type: "context", line: "footer", oldLine: 3, newLine: 3 },
    ];
    const out = formatDiff(diffs);
    assert.ok(out.includes("  header"));
    assert.ok(out.includes("- old"));
    assert.ok(out.includes("+ new"));
    assert.ok(out.includes("  footer"));
  });
});
