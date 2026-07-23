import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeFunctionMetrics, formatFunctionMetricsReport } from '../context-forge.mjs';

describe('F58: analyzeFunctionMetrics()', () => {
  it('returns empty result for no files', () => {
    const result = analyzeFunctionMetrics([]);
    assert.equal(result.fileCount, 0);
    assert.equal(result.totalFunctions, 0);
    assert.equal(result.grade, 'F');
  });

  it('skips non-JS files', () => {
    const result = analyzeFunctionMetrics([
      { path: 'script.py', content: 'def foo():\n  pass' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('detects function declarations', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'function foo(a, b) {\n  return a + b;\n}' },
    ]);
    assert.equal(result.totalFunctions, 1);
    assert.equal(result.files[0].functions[0].name, 'foo');
    assert.equal(result.files[0].functions[0].params, 2);
  });

  it('detects arrow functions', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'const add = (a, b) => {\n  return a + b;\n};' },
    ]);
    assert.equal(result.totalFunctions, 1);
    assert.ok(result.totalArrowFunctions >= 1);
  });

  it('detects async functions', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'async function fetchData() {\n  return await fetch("/api");\n}' },
    ]);
    assert.ok(result.totalAsyncFunctions >= 1);
  });

  it('counts function length in lines', () => {
    const content = 'function longFn() {\n  let a = 1;\n  let b = 2;\n  let c = 3;\n  let d = 4;\n  return a + b + c + d;\n}';
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.files[0].functions[0].length >= 6);
  });

  it('counts return statements', () => {
    const content = 'function multiReturn(x) {\n  if (x > 0) return "pos";\n  if (x < 0) return "neg";\n  return "zero";\n}';
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.files[0].functions[0].returns >= 3);
  });

  it('flags long functions (>50 lines)', () => {
    const lines = Array.from({ length: 55 }, (_, i) => `  let v${i} = ${i};`).join('\n');
    const content = `function huge() {\n${lines}\n  return "done";\n}`;
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.totalLongFunctions >= 1);
    assert.ok(result.files[0].issues.some(i => i.type === 'long_function'));
  });

  it('flags high parameter count (>5)', () => {
    const content = 'function many(a, b, c, d, e, f, g) {\n  return a;\n}';
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.totalHighParamFunctions >= 1);
    assert.ok(result.files[0].issues.some(i => i.type === 'too_many_params'));
  });

  it('detects method shorthand', () => {
    const content = 'const obj = {\n  greet(name) {\n    return "hi " + name;\n  }\n};';
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.totalFunctions >= 1);
  });

  it('detects function expressions', () => {
    const content = 'const fn = function(x) {\n  return x * 2;\n};';
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.totalFunctions >= 1);
  });

  it('handles empty content', () => {
    const result = analyzeFunctionMetrics([{ path: 'a.js', content: '' }]);
    assert.equal(result.fileCount, 0);
  });

  it('skips comment lines', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: '// function fake() {\n//   return 42;\n// }' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('handles .ts files', () => {
    const result = analyzeFunctionMetrics([
      { path: 'svc.ts', content: 'function init(): void {\n  console.log("init");\n}' },
    ]);
    assert.ok(result.totalFunctions >= 1);
  });

  it('computes avgLength and maxLength', () => {
    const content = 'function a() { return 1; }\nfunction b() {\n  let x = 2;\n  let y = 3;\n  return x + y;\n}';
    const result = analyzeFunctionMetrics([{ path: 'a.js', content }]);
    assert.ok(result.files[0].maxLength >= 4);
    assert.ok(result.files[0].avgLength > 0);
  });

  it('healthScore is 0-100', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'function f() { return 1; }' },
    ]);
    assert.ok(result.healthScore >= 0 && result.healthScore <= 100);
  });

  it('grade is valid letter', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'function f() { return 1; }' },
    ]);
    assert.ok(['A', 'B', 'C', 'D', 'F'].includes(result.grade));
  });

  it('handles generator functions', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'function* gen() {\n  yield 1;\n  yield 2;\n}' },
    ]);
    assert.ok(result.totalFunctions >= 1);
  });

  it('handles exported functions', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'export function exported() {\n  return 42;\n}' },
    ]);
    assert.ok(result.totalFunctions >= 1);
    assert.equal(result.files[0].functions[0].name, 'exported');
  });
});

describe('F58: formatFunctionMetricsReport()', () => {
  it('handles empty result', () => {
    const report = formatFunctionMetricsReport({ fileCount: 0 });
    assert.ok(report.includes('No functions'));
  });

  it('includes health grade and stats', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'function foo(a, b) {\n  return a + b;\n}' },
    ]);
    const report = formatFunctionMetricsReport(result);
    assert.ok(report.includes('Health Grade'));
    assert.ok(report.includes('Total functions'));
    assert.ok(report.includes('Arrow functions'));
  });

  it('includes longest functions section', () => {
    const lines = Array.from({ length: 25 }, (_, i) => `  let v${i} = ${i};`).join('\n');
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: `function big() {\n${lines}\n  return "done";\n}` },
    ]);
    const report = formatFunctionMetricsReport(result);
    assert.ok(report.includes('Longest Functions') || report.includes('Per-file'));
  });

  it('includes per-file summary', () => {
    const result = analyzeFunctionMetrics([
      { path: 'a.js', content: 'function f() { return 1; }' },
      { path: 'b.js', content: 'function g() { return 2; }' },
    ]);
    const report = formatFunctionMetricsReport(result);
    assert.ok(report.includes('Per-file Summary'));
    assert.ok(report.includes('a.js'));
  });
});
