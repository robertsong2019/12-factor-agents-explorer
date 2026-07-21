import { describe, it } from "node:test";
import assert from "node:assert";
import { analyzeErrorHandling, formatErrorHandlingReport } from "../context-forge.mjs";

describe("F53: analyzeErrorHandling()", () => {
  it("returns zero results for empty input", () => {
    const result = analyzeErrorHandling([]);
    assert.strictEqual(result.total, 0);
    assert.strictEqual(result.fileCount, 0);
    assert.strictEqual(result.grade, "A");
    assert.strictEqual(result.healthScore, 100);
  });

  it("returns zero results for files with no error handling issues", () => {
    const result = analyzeErrorHandling([
      { path: "clean.mjs", content: "const x = 1;\nconsole.log(x);\n" },
    ]);
    assert.strictEqual(result.total, 0);
  });

  it("detects empty catch blocks", () => {
    const result = analyzeErrorHandling([
      { path: "a.mjs", content: "try {\n  doSomething();\n} catch (e) {\n}\n" },
    ]);
    assert.ok(result.byType.empty_catch);
    assert.strictEqual(result.byType.empty_catch.length, 1);
    assert.strictEqual(result.byType.empty_catch[0].file, "a.mjs");
    assert.strictEqual(result.byType.empty_catch[0].line, 3);
    assert.strictEqual(result.byType.empty_catch[0].severity, "high");
  });

  it("detects catch with underscore (intentional suppression)", () => {
    const result = analyzeErrorHandling([
      { path: "b.mjs", content: "try {\n  risky();\n} catch (_) {\n  fallback();\n}\n" },
    ]);
    assert.ok(result.byType.catch_ignore);
    assert.strictEqual(result.byType.catch_ignore[0].severity, "medium");
  });

  it("detects bare throw statements", () => {
    const result = analyzeErrorHandling([
      { path: "c.mjs", content: "try {\n  work();\n} catch (e) {\n  throw;\n}\n" },
    ]);
    assert.ok(result.byType.bare_throw);
    assert.strictEqual(result.byType.bare_throw.length, 1);
  });

  it("detects console-only catch blocks", () => {
    const result = analyzeErrorHandling([
      { path: "d.mjs", content: "try {\n  fetch();\n} catch (err) {\n  console.error(err);\n}\n" },
    ]);
    assert.ok(result.byType.console_error_catch);
    assert.strictEqual(result.byType.console_error_catch[0].severity, "low");
  });

  it("detects throw string instead of Error", () => {
    const result = analyzeErrorHandling([
      { path: "e.mjs", content: 'if (!x) throw "bad value";\n' },
    ]);
    assert.ok(result.byType.throw_string);
    assert.strictEqual(result.byType.throw_string[0].severity, "high");
  });

  it("detects generic catch-all without type filtering", () => {
    const result = analyzeErrorHandling([
      { path: "f.mjs", content: "try {\n  work();\n} catch (e) {\n  handle(e);\n}\n" },
    ]);
    assert.ok(result.byType.catch_all);
    assert.strictEqual(result.byType.catch_all[0].severity, "low");
  });

  it("counts by severity correctly", () => {
    const result = analyzeErrorHandling([
      { path: "multi.mjs", content: [
        'try { a(); } catch (e) { }',
        'try { b(); } catch (_) { c(); }',
        'throw "oops";',
      ].join("\n") },
    ]);
    assert.ok(result.bySeverity.high >= 2); // empty_catch + throw_string
    assert.ok(result.bySeverity.medium >= 1); // catch_ignore
  });

  it("computes health score that decreases with findings", () => {
    const clean = analyzeErrorHandling([{ path: "ok.mjs", content: "const x = 1;\n" }]);
    const dirty = analyzeErrorHandling([
      { path: "bad.mjs", content: 'try { a(); } catch(e) {} throw "err";' },
    ]);
    assert.ok(clean.healthScore > dirty.healthScore);
    assert.ok(dirty.healthScore < 100);
    assert.ok(dirty.grade !== "A");
  });

  it("tracks affected files", () => {
    const result = analyzeErrorHandling([
      { path: "file1.mjs", content: "try { a(); } catch(e) {}" },
      { path: "file2.mjs", content: 'throw "x";' },
      { path: "file3.mjs", content: "const x = 1;" },
    ]);
    assert.strictEqual(result.fileCount, 2);
    assert.ok(result.affectedFiles.includes("file1.mjs"));
    assert.ok(result.affectedFiles.includes("file2.mjs"));
    assert.ok(!result.affectedFiles.includes("file3.mjs"));
  });

  it("handles files with null content gracefully", () => {
    const result = analyzeErrorHandling([{ path: "null.mjs", content: null }]);
    assert.strictEqual(result.total, 0);
  });
});

describe("F53: formatErrorHandlingReport()", () => {
  it("formats clean report", () => {
    const report = formatErrorHandlingReport({ total: 0 });
    assert.ok(report.includes("✅ No error handling issues"));
  });

  it("formats report with findings", () => {
    const result = analyzeErrorHandling([
      { path: "test.mjs", content: "try { a(); } catch(e) {}" },
    ]);
    const report = formatErrorHandlingReport(result);
    assert.ok(report.includes("## Error Handling Analysis"));
    assert.ok(report.includes("Health Grade"));
    assert.ok(report.includes("empty catch"));
  });

  it("includes severity counts in table", () => {
    const result = analyzeErrorHandling([
      { path: "test.mjs", content: "try { a(); } catch(e) {} throw \"x\";" },
    ]);
    const report = formatErrorHandlingReport(result);
    assert.ok(report.includes("| Severity | Count |"));
    assert.ok(report.includes("high"));
  });

  it("handles null result", () => {
    const report = formatErrorHandlingReport(null);
    assert.ok(report.includes("✅"));
  });

  it("truncates long finding lists", () => {
    const lines = Array.from({ length: 15 }, (_, i) => `try { ${i}(); } catch(e) {}`).join("\n");
    const result = analyzeErrorHandling([{ path: "many.mjs", content: lines }]);
    const report = formatErrorHandlingReport(result);
    assert.ok(report.includes("## Error Handling Analysis"));
  });
});
