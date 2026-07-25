import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeErrorMessages, formatErrorMessagesReport } from "../context-forge.mjs";

function makeFile(path, content) {
  return { path, content };
}

// ─── analyzeErrorMessages ────────────────────────────────────────

describe("analyzeErrorMessages", () => {
  // ─── Empty / baseline ─────────────────────────────────────────

  it("returns perfect score for empty file list", () => {
    const result = analyzeErrorMessages([]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.throwStatements, 0);
    assert.equal(result.stats.catchBlocks, 0);
    assert.equal(result.issues.length, 0);
  });

  it("handles files with no throw/catch", () => {
    const result = analyzeErrorMessages([
      makeFile("clean.js", "const x = 1;\nfunction foo() { return 42; }\n"),
    ]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.throwStatements, 0);
  });

  it("ignores non-string content", () => {
    const result = analyzeErrorMessages([
      makeFile("a.js", null),
      makeFile("b.js", undefined),
    ]);
    assert.equal(result.score, 100);
  });

  // ─── Empty error messages ─────────────────────────────────────

  it("flags throw new Error() with no message", () => {
    const result = analyzeErrorMessages([
      makeFile("empty.js", "throw new Error();\n"),
    ]);
    assert.ok(result.issues.some(i => i.label === "empty-error-message"));
    assert.equal(result.issues[0].severity, "high");
  });

  it("flags throw new TypeError() with no message", () => {
    const result = analyzeErrorMessages([
      makeFile("type.js", "throw new TypeError();\n"),
    ]);
    assert.ok(result.issues.some(i => i.label === "empty-error-message"));
  });

  // ─── Generic messages ─────────────────────────────────────────

  it("flags throw with generic string message", () => {
    const result = analyzeErrorMessages([
      makeFile("generic.js", 'throw new Error("Something went wrong");\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "generic-error-message"));
    assert.equal(result.issues[0].severity, "high");
  });

  it("flags throw with generic 'error' message", () => {
    const result = analyzeErrorMessages([
      makeFile("g2.js", 'throw new Error("error");\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "generic-error-message"));
  });

  // ─── String throws ────────────────────────────────────────────

  it("flags throwing raw string", () => {
    const result = analyzeErrorMessages([
      makeFile("str.js", 'throw "something specific happened";\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "string-throw"));
    assert.equal(result.issues[0].severity, "medium");
  });

  it("flags throwing generic string", () => {
    const result = analyzeErrorMessages([
      makeFile("str2.js", 'throw "error";\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "generic-string-throw"));
    assert.equal(result.issues[0].severity, "high");
  });

  // ─── String concatenation ─────────────────────────────────────

  it("flags string concatenation in error messages", () => {
    const result = analyzeErrorMessages([
      makeFile("concat.js", 'throw new Error("Failed to process " + name + " at " + time);\n'),
    ]);
    assert.ok(result.issues.some(i => i.label === "string-concat-error"));
    assert.equal(result.issues[0].severity, "low");
  });

  // ─── Good messages ────────────────────────────────────────────

  it("counts descriptive messages as good", () => {
    const result = analyzeErrorMessages([
      makeFile("good.js", 'throw new Error(`User ${userId} not found in database`);\n'),
    ]);
    assert.equal(result.stats.goodMessages, 1);
    assert.equal(result.issues.length, 0);
  });

  it("counts descriptive string literal messages as good", () => {
    const result = analyzeErrorMessages([
      makeFile("good2.js", 'throw new Error("Database connection pool exhausted after 30s retry");\n'),
    ]);
    assert.equal(result.stats.goodMessages, 1);
  });

  // ─── Template literal with generic content ────────────────────

  it("flags template literal with generic message", () => {
    const result = analyzeErrorMessages([
      makeFile("tmpl.js", "throw new Error(`An error occurred: ${detail}`);\n"),
    ]);
    assert.ok(result.issues.some(i => i.label === "generic-template-message"));
  });

  // ─── Catch block analysis ─────────────────────────────────────

  it("detects catch blocks", () => {
    const result = analyzeErrorMessages([
      makeFile("catch.js", "try { foo(); } catch (e) { console.error(e); }\n"),
    ]);
    assert.ok(result.stats.catchBlocks >= 1);
  });

  it("flags catch blocks that swallow errors", () => {
    const result = analyzeErrorMessages([
      makeFile("swallow.js", "try {\n  foo();\n} catch (e) {\n  // ignore\n}\n"),
    ]);
    assert.ok(result.issues.some(i => i.label === "weak-catch"));
  });

  it("flags catch blocks that blindly re-throw", () => {
    const result = analyzeErrorMessages([
      makeFile("rethrow.js", "try {\n  foo();\n} catch (e) {\n  throw e;\n}\n"),
    ]);
    assert.ok(result.issues.some(i => i.label === "weak-catch"));
  });

  // ─── Score calculation ────────────────────────────────────────

  it("calculates score from good/total ratio", () => {
    const result = analyzeErrorMessages([
      makeFile("mix.js", [
        'throw new Error("Descriptive error with enough context");',
        "throw new Error();",
      ].join("\n")),
    ]);
    // 1 good, 1 empty = 50%
    assert.equal(result.score, 50);
  });

  it("returns 0 score when all throws are bad", () => {
    const result = analyzeErrorMessages([
      makeFile("bad.js", 'throw new Error("error");\nthrow new Error();\n'),
    ]);
    assert.equal(result.score, 0);
  });

  // ─── Multiple files ───────────────────────────────────────────

  it("analyzes errors across multiple files", () => {
    const result = analyzeErrorMessages([
      makeFile("f1.js", 'throw new Error("Good message with context");\n'),
      makeFile("f2.js", "throw new Error();\n"),
    ]);
    assert.equal(result.stats.throwStatements, 2);
    assert.equal(result.stats.goodMessages, 1);
  });

  // ─── Line tracking ────────────────────────────────────────────

  it("tracks line numbers", () => {
    const result = analyzeErrorMessages([
      makeFile("lines.js", "const a = 1;\nconst b = 2;\nthrow new Error();\n"),
    ]);
    assert.equal(result.issues[0].line, 3);
  });

  // ─── Severity counting ────────────────────────────────────────

  it("counts severities correctly", () => {
    const result = analyzeErrorMessages([
      makeFile("multi.js", [
        "throw new Error();",           // high (empty)
        'throw "error";',               // high (generic string)
        'throw "specific detail";',     // medium (string throw)
        'throw new Error("a" + b);',    // low (concat)
      ].join("\n")),
    ]);
    assert.ok(result.stats.highSeverity >= 2);
    assert.ok(result.stats.mediumSeverity >= 1);
    assert.ok(result.stats.lowSeverity >= 1);
  });

  // ─── Custom error classes ─────────────────────────────────────

  it("handles custom error class names", () => {
    const result = analyzeErrorMessages([
      makeFile("custom.js", "throw new CustomError();\n"),
    ]);
    assert.ok(result.stats.throwStatements >= 1);
  });

  // ─── Throw variable (not assessable) ──────────────────────────

  it("counts throw variable without flagging", () => {
    const result = analyzeErrorMessages([
      makeFile("var.js", "const err = new Error('ctx');\nthrow err;\n"),
    ]);
    assert.ok(result.stats.throwStatements >= 1);
  });
});

// ─── formatErrorMessagesReport ───────────────────────────────────

describe("formatErrorMessagesReport", () => {
  it("formats empty result", () => {
    const report = formatErrorMessagesReport(analyzeErrorMessages([]));
    assert.ok(report.includes("Error Message Quality"));
    assert.ok(report.includes("No throw/catch"));
  });

  it("formats result with good messages only", () => {
    const result = analyzeErrorMessages([
      makeFile("ok.js", 'throw new Error("Detailed message with enough context for debugging");\n'),
    ]);
    const report = formatErrorMessagesReport(result);
    assert.ok(report.includes("Score:** 100"));
    assert.ok(report.includes("well-structured"));
  });

  it("formats result with issues", () => {
    const result = analyzeErrorMessages([
      makeFile("bad.js", "throw new Error();\n"),
    ]);
    const report = formatErrorMessagesReport(result);
    assert.ok(report.includes("Issues Found"));
    assert.ok(report.includes("empty-error-message"));
  });

  it("includes severity distribution", () => {
    const result = analyzeErrorMessages([
      makeFile("bad.js", "throw new Error();\n"),
    ]);
    const report = formatErrorMessagesReport(result);
    assert.ok(report.includes("High severity"));
    assert.ok(report.includes("Medium severity"));
    assert.ok(report.includes("Low severity"));
  });

  it("truncates long issue lists", () => {
    const lines = [];
    for (let i = 0; i < 35; i++) {
      lines.push("throw new Error();");
    }
    const result = analyzeErrorMessages([
      makeFile("many.js", lines.join("\n") + "\n"),
    ]);
    const report = formatErrorMessagesReport(result);
    assert.ok(report.includes("more"));
  });
});
