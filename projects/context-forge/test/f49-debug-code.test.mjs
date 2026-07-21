import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { detectDebugCode, formatDebugCodeReport } from '../context-forge.mjs';

describe('F49: detectDebugCode', () => {
  it('returns zero findings for empty input', () => {
    const result = detectDebugCode([]);
    assert.equal(result.total, 0);
    assert.equal(result.fileCount, 0);
    assert.deepEqual(result.bySeverity, { high: 0, medium: 0, low: 0 });
  });

  it('returns zero findings for clean code', () => {
    const result = detectDebugCode([
      { path: 'src/clean.js', content: 'function add(a, b) { return a + b; }', lang: 'js' },
    ]);
    assert.equal(result.total, 0);
  });

  it('detects debugger statements', () => {
    const result = detectDebugCode([
      { path: 'src/app.js', content: 'function test() {\n  debugger;\n  return 1;\n}', lang: 'js' },
    ]);
    assert.ok(result.byType.debugger);
    assert.equal(result.byType.debugger.length, 1);
    assert.equal(result.byType.debugger[0].severity, 'high');
    assert.equal(result.byType.debugger[0].line, 2);
  });

  it('detects console.log calls', () => {
    const result = detectDebugCode([
      { path: 'src/index.js', content: 'console.log("hello");\nconsole.warn("oops");', lang: 'js' },
    ]);
    assert.ok(result.byType.console_log);
    assert.equal(result.byType.console_log.length, 2);
    assert.equal(result.byType.console_log[0].severity, 'medium');
  });

  it('detects print statements', () => {
    const result = detectDebugCode([
      { path: 'src/main.py', content: 'print("debug value")\nx = 1', lang: 'py' },
    ]);
    assert.ok(result.byType.print_stmt);
    assert.equal(result.byType.print_stmt.length, 1);
    assert.equal(result.byType.print_stmt[0].severity, 'low');
  });

  it('detects System.out.println', () => {
    const result = detectDebugCode([
      { path: 'src/Main.java', content: 'System.out.println("test");', lang: 'java' },
    ]);
    assert.ok(result.byType.system_out);
    assert.equal(result.byType.system_out.length, 1);
  });

  it('detects commented-out code', () => {
    const result = detectDebugCode([
      { path: 'src/legacy.js', content: '// const old = compute();\n// if (old > 0) {\n//   return old;\n// }', lang: 'js' },
    ]);
    assert.ok(result.byType.commented_code);
    assert.ok(result.byType.commented_code.length >= 2);
  });

  it('detects stale TODOs', () => {
    const result = detectDebugCode([
      { path: 'src/todo.js', content: '// TODO: fix this later\n// FIXME: urgent bug', lang: 'js' },
    ]);
    assert.ok(result.byType.todo_derelict);
    assert.equal(result.byType.todo_derelict.length, 2);
  });

  it('detects alert() calls', () => {
    const result = detectDebugCode([
      { path: 'src/ui.js', content: 'alert("warning!");', lang: 'js' },
    ]);
    assert.ok(result.byType.alert);
    assert.equal(result.byType.alert.length, 1);
    assert.equal(result.byType.alert[0].severity, 'high');
  });

  it('handles multiple files and aggregates correctly', () => {
    const result = detectDebugCode([
      { path: 'a.js', content: 'console.log("a");\ndebugger;', lang: 'js' },
      { path: 'b.py', content: 'print("b")', lang: 'py' },
    ]);
    assert.ok(result.total >= 3);
    assert.equal(result.fileCount, 2);
    assert.deepEqual(result.affectedFiles.sort(), ['a.js', 'b.py']);
  });

  it('tracks severity counts correctly', () => {
    const result = detectDebugCode([
      { path: 'x.js', content: 'debugger;\nalert("x");\nconsole.log("y");', lang: 'js' },
    ]);
    assert.equal(result.bySeverity.high, 2); // debugger + alert
    assert.equal(result.bySeverity.medium, 1); // console.log
  });

  it('handles files with no content gracefully', () => {
    const result = detectDebugCode([
      { path: 'empty.js', content: null, lang: 'js' },
    ]);
    assert.equal(result.total, 0);
  });

  it('captures snippet text from the matching line', () => {
    const result = detectDebugCode([
      { path: 'src/app.js', content: 'function init() {\n  console.log("starting app", config);\n}', lang: 'js' },
    ]);
    const finding = result.byType.console_log[0];
    assert.ok(finding.snippet.includes('console.log'));
    assert.ok(finding.snippet.length <= 120);
  });
});

describe('F49: formatDebugCodeReport', () => {
  it('returns clean message for no findings', () => {
    const report = formatDebugCodeReport({ total: 0, byType: {}, bySeverity: { high: 0, medium: 0, low: 0 }, fileCount: 0 });
    assert.ok(report.includes('✅ No debug statements'));
  });

  it('includes total count and file count', () => {
    const report = formatDebugCodeReport({
      total: 5,
      byType: { console_log: [{ file: 'a.js', line: 1, snippet: 'console.log("x")', severity: 'medium' }] },
      bySeverity: { high: 0, medium: 5, low: 0 },
      fileCount: 2,
    });
    assert.ok(report.includes('5'));
    assert.ok(report.includes('2 file(s)'));
  });

  it('includes severity table', () => {
    const report = formatDebugCodeReport({
      total: 3,
      byType: { debugger: [{ file: 'a.js', line: 1, snippet: 'debugger;', severity: 'high' }] },
      bySeverity: { high: 1, medium: 2, low: 0 },
      fileCount: 1,
    });
    assert.ok(report.includes('🔴 high'));
    assert.ok(report.includes('🟡 medium'));
  });

  it('truncates long finding lists', () => {
    const items = Array.from({ length: 25 }, (_, i) => ({
      file: `file${i}.js`, line: i + 1, snippet: `console.log(${i})`, severity: 'medium',
    }));
    const report = formatDebugCodeReport({
      total: 25,
      byType: { console_log: items },
      bySeverity: { high: 0, medium: 25, low: 0 },
      fileCount: 25,
    });
    assert.ok(report.includes('and 5 more'));
  });

  it('handles null result', () => {
    const report = formatDebugCodeReport(null);
    assert.ok(report.includes('✅'));
  });

  it('formats full report with multiple types', () => {
    const report = formatDebugCodeReport({
      total: 4,
      byType: {
        debugger: [{ file: 'a.js', line: 1, snippet: 'debugger;', severity: 'high' }],
        console_log: [
          { file: 'a.js', line: 2, snippet: 'console.log("x")', severity: 'medium' },
          { file: 'b.js', line: 3, snippet: 'console.log("y")', severity: 'medium' },
        ],
        alert: [{ file: 'c.js', line: 1, snippet: 'alert("z")', severity: 'high' }],
      },
      bySeverity: { high: 2, medium: 2, low: 0 },
      fileCount: 3,
    });
    assert.ok(report.includes('## Debug Code Analysis'));
    assert.ok(report.includes('debugger'));
    assert.ok(report.includes('console log'));
    assert.ok(report.includes('alert'));
  });
});
