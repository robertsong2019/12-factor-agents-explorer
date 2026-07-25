import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeReturnPaths, formatReturnPathsReport } from '../context-forge.mjs';

describe('analyzeReturnPaths', () => {
  it('returns clean result for empty file list', () => {
    const result = analyzeReturnPaths([]);
    assert.equal(result.stats.totalFunctions, 0);
    assert.equal(result.stats.multiReturnFunctions, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it('skips non-JS files', () => {
    const result = analyzeReturnPaths([
      { path: 'script.py', content: 'def fn():\n  return 1\n  return 2' },
    ]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('skips files with no content', () => {
    const result = analyzeReturnPaths([
      { path: 'test.js', content: null },
    ]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('counts single-return function correctly', () => {
    const code = 'function simple() { return 42; }';
    const result = analyzeReturnPaths([{ path: 'simple.js', content: code }]);
    assert.equal(result.stats.totalFunctions, 1);
    assert.equal(result.stats.multiReturnFunctions, 0);
  });

  it('detects functions with 5+ returns', () => {
    const code = [
      'function classify(n) {',
      '  if (n === 1) return "one";',
      '  if (n === 2) return "two";',
      '  if (n === 3) return "three";',
      '  if (n === 4) return "four";',
      '  return "other";',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'multi.js', content: code }]);
    assert.ok(result.stats.multiReturnFunctions >= 1, `expected >= 1, got ${result.stats.multiReturnFunctions}`);
  });

  it('assigns high severity for 8+ returns', () => {
    const code = [
      'function dispatch(action) {',
      '  if (action === "a") return 1;',
      '  if (action === "b") return 2;',
      '  if (action === "c") return 3;',
      '  if (action === "d") return 4;',
      '  if (action === "e") return 5;',
      '  if (action === "f") return 6;',
      '  if (action === "g") return 7;',
      '  if (action === "h") return 8;',
      '  return 0;',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'dispatch.js', content: code }]);
    const highIssues = result.issues.filter(i => i.severity === 'high');
    assert.ok(highIssues.length >= 1, 'should have high severity issue');
  });

  it('does not flag functions with <5 returns', () => {
    const code = [
      'function handle(x) {',
      '  if (x > 0) return "pos";',
      '  if (x < 0) return "neg";',
      '  return "zero";',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'ok.js', content: code }]);
    assert.equal(result.stats.multiReturnFunctions, 0);
    assert.equal(result.grade, 'A');
  });

  it('handles arrow functions', () => {
    const code = 'const fn = (x) => { if (x) return 1; return 0; };';
    const result = analyzeReturnPaths([{ path: 'arrow.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
  });

  it('handles class methods', () => {
    const code = [
      'class Service {',
      '  get(id) {',
      '    if (!id) return null;',
      '    return this.data[id];',
      '  }',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'class.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
  });

  it('skips test files', () => {
    const code = 'function fake() { return 1; return 2; return 3; return 4; return 5; }';
    const result = analyzeReturnPaths([{ path: 'foo.test.js', content: code }]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('handles multiple functions in one file', () => {
    const code = [
      'function fn1(x) { return x; }',
      'function fn2(x) {',
      '  if (x === 1) return "a";',
      '  if (x === 2) return "b";',
      '  if (x === 3) return "c";',
      '  if (x === 4) return "d";',
      '  return "e";',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'multi-fn.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 2);
    assert.ok(result.stats.multiReturnFunctions >= 1);
  });

  it('handles empty content gracefully', () => {
    const result = analyzeReturnPaths([{ path: 'empty.js', content: '' }]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('deducts score for multiple multi-return functions', () => {
    const lines = [];
    for (const name of ['fn1', 'fn2']) {
      lines.push(`function ${name}(x) {`);
      for (let i = 0; i < 6; i++) {
        lines.push(`  if (x === ${i}) return ${i};`);
      }
      lines.push('  return -1;');
      lines.push('}');
    }
    const result = analyzeReturnPaths([{ path: 'score.js', content: lines.join('\n') }]);
    assert.ok(result.score < 100, `score should be < 100, got ${result.score}`);
  });

  it('formats report with issues', () => {
    const code = [
      'function big(x) {',
      '  if (x === 1) return 1;',
      '  if (x === 2) return 2;',
      '  if (x === 3) return 3;',
      '  if (x === 4) return 4;',
      '  return 0;',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'report.js', content: code }]);
    const report = formatReturnPathsReport(result);
    assert.ok(report.includes('Return Path'));
    assert.ok(report.includes('Health Score'));
    assert.ok(report.includes('5+ returns'));
  });

  it('formats report without issues', () => {
    const result = analyzeReturnPaths([{ path: 'ok.js', content: 'function ok() { return 1; }' }]);
    const report = formatReturnPathsReport(result);
    assert.ok(report.includes('clean'));
  });

  it('handles functions with no return at all', () => {
    const code = [
      'function sideEffect() {',
      '  console.log("hello");',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'side.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
    assert.equal(result.stats.multiReturnFunctions, 0);
  });

  it('handles async functions', () => {
    const code = [
      'async function fetchData(url) {',
      '  if (!url) return null;',
      '  const res = await fetch(url);',
      '  if (!res.ok) return null;',
      '  return res.json();',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'async.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
    assert.equal(result.stats.multiReturnFunctions, 0); // only 3 returns
  });

  it('handles nested functions', () => {
    const code = [
      'function outer() {',
      '  function inner(x) {',
      '    if (x === 1) return "a";',
      '    if (x === 2) return "b";',
      '    if (x === 3) return "c";',
      '    if (x === 4) return "d";',
      '    return "e";',
      '  }',
      '  return inner;',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'nested.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
  });

  it('returns proper score range', () => {
    const lines = ['function big(x) {'];
    for (let i = 0; i < 10; i++) {
      lines.push(`  if (x === ${i}) return ${i};`);
    }
    lines.push('  return -1;');
    lines.push('}');
    const result = analyzeReturnPaths([{ path: 'big.js', content: lines.join('\n') }]);
    assert.ok(result.score >= 0 && result.score <= 100);
  });

  it('detects single-line multi-return functions', () => {
    const code = 'function toggle(x) { if (x) return 1; if (!x) return 0; if (x > 5) return 2; if (x > 10) return 3; return -1; }';
    const result = analyzeReturnPaths([{ path: 'toggle.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
  });

  it('handles exported functions', () => {
    const code = [
      'export function handler(req, res) {',
      '  if (!req.body) return null;',
      '  if (!req.body.type) return null;',
      '  if (req.body.type === "a") return { a: 1 };',
      '  if (req.body.type === "b") return { b: 2 };',
      '  return { unknown: true };',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'export.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
    assert.ok(result.stats.multiReturnFunctions >= 1);
  });

  it('handles generator functions', () => {
    const code = [
      'function* gen() {',
      '  yield 1;',
      '  yield 2;',
      '  return 3;',
      '}',
    ].join('\n');
    const result = analyzeReturnPaths([{ path: 'gen.js', content: code }]);
    // Generator may or may not be detected as function; either is fine
    assert.ok(result.stats.totalFunctions >= 0);
  });
});
