import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeRegexComplexity, formatRegexComplexityReport } from "../context-forge.mjs";

// ─── Helpers ─────────────────────────────────────────────────────

function makeFile(path, content) {
  return { path, content };
}

// ─── analyzeRegexComplexity ──────────────────────────────────────

describe("analyzeRegexComplexity", () => {
  // ─── Baseline & Empty cases ───────────────────────────────────

  it("returns perfect score for empty file list", () => {
    const result = analyzeRegexComplexity([]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.totalRegexes, 0);
    assert.equal(result.stats.riskyRegexes, 0);
    assert.equal(result.issues.length, 0);
  });

  it("handles files with no regexes", () => {
    const result = analyzeRegexComplexity([
      makeFile("a.js", "const x = 1 + 2;\nconsole.log(x);\n"),
      makeFile("b.py", "def foo():\n    return 42\n"),
    ]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.totalRegexes, 0);
    assert.equal(result.stats.riskyRegexes, 0);
  });

  it("ignores non-string content", () => {
    const result = analyzeRegexComplexity([
      makeFile("a.js", null),
      makeFile("b.js", undefined),
      makeFile("c.js", 123),
    ]);
    assert.equal(result.score, 100);
    assert.equal(result.stats.totalRegexes, 0);
  });

  // ─── Regex literal detection ──────────────────────────────────

  it("detects simple safe regex literals", () => {
    const result = analyzeRegexComplexity([
      makeFile("safe.js", "const re = /hello/g;\nconst re2 = /\\d+/g;\n"),
    ]);
    assert.equal(result.stats.totalRegexes, 2);
    assert.equal(result.stats.riskyRegexes, 0);
    assert.equal(result.score, 100);
  });

  it("detects RegExp() constructor calls", () => {
    const result = analyzeRegexComplexity([
      makeFile("ctor.js", 'const re = new RegExp("^foo$");\n'),
    ]);
    assert.equal(result.stats.totalRegexes, 1);
  });

  it("detects RegExp() with template literals", () => {
    const result = analyzeRegexComplexity([
      makeFile("tmpl.js", "const re = new RegExp(`^${prefix}`);\n"),
    ]);
    assert.equal(result.stats.totalRegexes, 1);
  });

  // ─── Nested quantifier detection ──────────────────────────────

  it("flags nested quantifier (a+)+", () => {
    const result = analyzeRegexComplexity([
      makeFile("redo.js", "const evil = /(a+)+/g;\n"),
    ]);
    assert.equal(result.stats.totalRegexes, 1);
    assert.equal(result.stats.riskyRegexes, 1);
    assert.equal(result.issues[0].severity, "high");
    assert.ok(result.issues[0].findings.some(f => f.label === "nested-quantifier"));
  });

  it("flags nested quantifier (a*)*", () => {
    const result = analyzeRegexComplexity([
      makeFile("redo.js", "const evil = /(a*)*b/;\n"),
    ]);
    assert.equal(result.stats.riskyRegexes, 1);
    assert.equal(result.issues[0].findings[0].label, "nested-quantifier");
  });

  it("flags quantified optional group (a?)+", () => {
    const result = analyzeRegexComplexity([
      makeFile("opt.js", "const re = /(a?)+/g;\n"),
    ]);
    assert.equal(result.stats.riskyRegexes, 1);
    assert.ok(result.issues[0].findings.some(f => f.label === "quantified-optional-group"));
  });

  // ─── Overlapping alternation ──────────────────────────────────

  it("flags quantified overlapping alternation (a|a)*", () => {
    const result = analyzeRegexComplexity([
      makeFile("alt.js", "const evil = /(a|a)*/;\n"),
    ]);
    assert.equal(result.stats.riskyRegexes, 1);
    assert.ok(result.issues[0].findings.some(f => f.label === "overlapped-alternation"));
  });

  // ─── Adjacent quantifiers ─────────────────────────────────────

  it("detects adjacent quantifiers as medium risk", () => {
    const result = analyzeRegexComplexity([
      makeFile("adj.js", "const re = /a+b+c/;\n"),
    ]);
    assert.ok(result.stats.riskyRegexes >= 1);
    assert.ok(result.issues[0].findings.some(f => f.label === "adjacent-quantifiers"));
  });

  // ─── Long pattern ─────────────────────────────────────────────

  it("flags very long regex patterns as low severity", () => {
    const longPattern = "a".repeat(110);
    const result = analyzeRegexComplexity([
      makeFile("long.js", `const re = /${longPattern}/;\n`),
    ]);
    assert.ok(result.issues.some(i => i.findings.some(f => f.label === "long-pattern")));
  });

  // ─── Score calculation ────────────────────────────────────────

  it("calculates score based on risky ratio", () => {
    const result = analyzeRegexComplexity([
      makeFile("mix.js", "const safe = /hello/g;\nconst evil = /(a+)+/;\n"),
    ]);
    assert.equal(result.stats.totalRegexes, 2);
    assert.equal(result.stats.riskyRegexes, 1);
    assert.equal(result.score, 50);
  });

  it("gives score 0 when all regexes are risky", () => {
    const result = analyzeRegexComplexity([
      makeFile("bad.js", "const a = /(a+)+/;\nconst b = /(b|b)*/;\n"),
    ]);
    assert.equal(result.stats.riskyRegexes, 2);
    assert.equal(result.score, 0);
  });

  // ─── Severity counting ────────────────────────────────────────

  it("counts high/medium/low severities correctly", () => {
    const result = analyzeRegexComplexity([
      makeFile("multi.js", [
        "const high = /(a+)+/;",
        "const med = /a+b+/;",
        "const safe = /hello/;",
      ].join("\n")),
    ]);
    assert.ok(result.stats.highSeverity >= 1);
    assert.ok(result.stats.mediumSeverity >= 1);
  });

  // ─── Line number tracking ─────────────────────────────────────

  it("tracks line numbers correctly", () => {
    const result = analyzeRegexComplexity([
      makeFile("lines.js", "const x = 1;\nconst y = 2;\nconst re = /(a+)+/;\n"),
    ]);
    assert.equal(result.issues[0].line, 3);
  });

  // ─── Multiple files ───────────────────────────────────────────

  it("analyzes regexes across multiple files", () => {
    const result = analyzeRegexComplexity([
      makeFile("f1.js", "const re = /test/g;\n"),
      makeFile("f2.js", "const re = /(x+)+/;\n"),
      makeFile("f3.py", "import re\npattern = re.compile(r'(a+)+')\n"),
    ]);
    assert.ok(result.stats.totalRegexes >= 2);
    assert.ok(result.stats.riskyRegexes >= 1);
  });

  // ─── Regex type tracking ──────────────────────────────────────

  it("records regex type (literal/constructor/template)", () => {
    const result = analyzeRegexComplexity([
      makeFile("types.js", [
        "const a = /test/g;",
        'const b = new RegExp("^foo");',
        "const c = new RegExp(`bar`);",
      ].join("\n")),
    ]);
    assert.ok(result.stats.totalRegexes >= 3);
  });

  // ─── Flags in regex literals ──────────────────────────────────

  it("handles regex with various flags", () => {
    const result = analyzeRegexComplexity([
      makeFile("flags.js", "const re = /test/gimuy;\n"),
    ]);
    assert.equal(result.stats.totalRegexes, 1);
    assert.equal(result.stats.riskyRegexes, 0);
  });
});

// ─── formatRegexComplexityReport ─────────────────────────────────

describe("formatRegexComplexityReport", () => {
  it("formats empty result", () => {
    const report = formatRegexComplexityReport(analyzeRegexComplexity([]));
    assert.ok(report.includes("Regex Complexity"));
    assert.ok(report.includes("No regex"));
  });

  it("formats result with safe regexes", () => {
    const result = analyzeRegexComplexity([
      makeFile("ok.js", "const re = /hello/g;\n"),
    ]);
    const report = formatRegexComplexityReport(result);
    assert.ok(report.includes("Score:** 100"));
    assert.ok(report.includes("safe"));
  });

  it("formats result with issues", () => {
    const result = analyzeRegexComplexity([
      makeFile("bad.js", "const re = /(a+)+/;\n"),
    ]);
    const report = formatRegexComplexityReport(result);
    assert.ok(report.includes("Issues Found"));
    assert.ok(report.includes("nested-quantifier"));
  });

  it("includes severity distribution in report", () => {
    const result = analyzeRegexComplexity([
      makeFile("bad.js", "const re = /(a+)+/;\n"),
    ]);
    const report = formatRegexComplexityReport(result);
    assert.ok(report.includes("High severity"));
    assert.ok(report.includes("Medium severity"));
    assert.ok(report.includes("Low severity"));
  });

  it("truncates long issue lists", () => {
    const files = [];
    for (let i = 0; i < 35; i++) {
      files.push(makeFile(`f${i}.js`, `const re = /(a+)+/;\n`));
    }
    const result = analyzeRegexComplexity(files);
    const report = formatRegexComplexityReport(result);
    assert.ok(report.includes("more"));
  });
});
