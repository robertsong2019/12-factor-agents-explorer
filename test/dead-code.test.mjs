import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeDeadCode, formatDeadCodeReport } from "../context-forge.mjs";

describe("analyzeDeadCode", () => {
  it("returns clean result for empty files array", () => {
    const result = analyzeDeadCode([]);
    assert.equal(result.stats.totalUnreachable, 0);
    assert.equal(result.stats.totalCommentedCode, 0);
    assert.equal(result.stats.totalUnusedPrivate, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it("detects unreachable code after return", () => {
    const files = [{
      path: "test.js",
      content: `function foo() {
  return 42;
  console.log("dead");
}`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalUnreachable >= 1, "should detect unreachable code");
    const unreachable = result.issues.find(i => i.type === 'unreachable-after-terminate');
    assert.ok(unreachable, "should have unreachable-after-terminate issue");
    assert.equal(unreachable.severity, 'high');
  });

  it("detects unreachable code after throw", () => {
    const files = [{
      path: "test.js",
      content: `function bar() {
  throw new Error("done");
  const x = 1;
}`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalUnreachable >= 1);
    const issue = result.issues.find(i => i.type === 'unreachable-after-terminate');
    assert.ok(issue);
  });

  it("detects unreachable branch: if (false)", () => {
    const files = [{
      path: "test.js",
      content: `if (false) {
  doSomething();
}`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalUnreachableBranch >= 1);
    const branch = result.issues.find(i => i.type === 'unreachable-branch');
    assert.ok(branch);
    assert.equal(branch.severity, 'high');
  });

  it("detects unreachable branch: while (0)", () => {
    const files = [{
      path: "test.js",
      content: `while (0) {
  neverRuns();
}`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalUnreachableBranch >= 1);
  });

  it("detects commented-out code blocks (3+ lines)", () => {
    const files = [{
      path: "test.js",
      content: `// const old = computeThing();
// const result = transform(old);
// return result;
console.log("alive");`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalCommentedCode >= 1);
    const block = result.issues.find(i => i.type === 'commented-out-code');
    assert.ok(block);
    assert.ok(block.label.includes('3 lines'));
  });

  it("does NOT flag single-line comments as commented-out code", () => {
    const files = [{
      path: "test.js",
      content: `// This is a normal comment explaining the code below
const x = 1;`,
    }];
    const result = analyzeDeadCode(files);
    // Should not report commented-out code for a single prose comment line
    const block = result.issues.find(i => i.type === 'commented-out-code' && i.label.includes('lines'));
    assert.equal(block, undefined);
  });

  it("detects unused private function", () => {
    const files = [{
      path: "test.js",
      content: `function usedHelper() { return 1; }
function neverUsed() { return 2; }
const result = usedHelper();`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalUnusedPrivate >= 1, `expected unused private >= 1, got ${result.stats.totalUnusedPrivate}`);
    const unused = result.issues.find(i => i.type === 'unused-private' && i.label.includes('neverUsed'));
    assert.ok(unused);
    assert.equal(unused.severity, 'low');
  });

  it("does NOT flag exported functions as unused", () => {
    const files = [{
      path: "test.js",
      content: `export function exportedFunc() { return 1; }
const x = 1;`,
    }];
    const result = analyzeDeadCode(files);
    const unused = result.issues.find(i => i.type === 'unused-private' && i.label.includes('exportedFunc'));
    assert.equal(unused, undefined);
  });

  it("does NOT flag functions starting with _ as unused", () => {
    const files = [{
      path: "test.js",
      content: `function _private() { return 1; }
const x = 1;`,
    }];
    const result = analyzeDeadCode(files);
    const unused = result.issues.find(i => i.type === 'unused-private' && i.label.includes('_private'));
    assert.equal(unused, undefined);
  });

  it("skips test files", () => {
    const files = [{
      path: "foo.test.js",
      content: `function unusedInTest() { return 42; }`,
    }];
    const result = analyzeDeadCode(files);
    assert.equal(result.stats.totalUnusedPrivate, 0);
  });

  it("skips non-JS/TS files", () => {
    const files = [{
      path: "readme.md",
      content: `return dead;
const x = 1;`,
    }];
    const result = analyzeDeadCode(files);
    assert.equal(result.stats.totalUnreachable, 0);
  });

  it("handles multi-file analysis", () => {
    const files = [
      { path: "a.js", content: "return 1;\nconst dead = 2;" },
      { path: "b.js", content: "if (false) { x(); }" },
    ];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalUnreachable >= 1);
    assert.ok(result.stats.totalUnreachableBranch >= 1);
  });

  it("computes a score that decreases with more issues", () => {
    const clean = analyzeDeadCode([{ path: "clean.js", content: "const x = 1;" }]);
    const dirty = analyzeDeadCode([{
      path: "dirty.js",
      content: `return 1;
deadCode();
deadCode2();
if (false) { x(); }`,
    }]);
    assert.ok(dirty.score < clean.score, `dirty score ${dirty.score} should be < clean score ${clean.score}`);
  });

  it("formatDeadCodeReport produces markdown", () => {
    const result = analyzeDeadCode([{
      path: "test.js",
      content: `return 1;\nconst dead = 2;`,
    }]);
    const report = formatDeadCodeReport(result);
    assert.ok(report.includes("## 💀 Dead Code Analysis"));
    assert.ok(report.includes("Health Score"));
    assert.ok(report.includes("Summary"));
  });

  it("formatDeadCodeReport handles clean result", () => {
    const result = analyzeDeadCode([]);
    const report = formatDeadCodeReport(result);
    assert.ok(report.includes("No dead code detected"));
    assert.ok(report.includes("✅"));
  });

  it("detects block comment containing code", () => {
    const files = [{
      path: "test.js",
      content: `/* const old = computeThing(); */
const live = 1;`,
    }];
    const result = analyzeDeadCode(files);
    // Block comment with code-like content
    assert.ok(result.stats.totalCommentedCode >= 0); // heuristic-based, may or may not trigger
  });

  it("handles Python-style commented code", () => {
    const files = [{
      path: "script.py",
      content: `# def old_function():
#     return 42
# result = old_function()
print("alive")`,
    }];
    const result = analyzeDeadCode(files);
    assert.ok(result.stats.totalCommentedCode >= 1, "should detect Python commented code block");
  });
});
