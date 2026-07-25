import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeCyclomaticComplexity, formatCyclomaticComplexityReport } from '../context-forge.mjs';

describe('analyzeCyclomaticComplexity', () => {
  it('returns clean result for empty file list', () => {
    const result = analyzeCyclomaticComplexity([]);
    assert.equal(result.stats.totalFunctions, 0);
    assert.equal(result.stats.complexFunctions, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it('skips non-JS files', () => {
    const result = analyzeCyclomaticComplexity([
      { path: 'script.py', content: 'def fn(a):\n  if a:\n    pass' },
    ]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('skips files with no content', () => {
    const result = analyzeCyclomaticComplexity([
      { path: 'test.js', content: null },
    ]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('counts a simple function with complexity 1', () => {
    const code = 'function simple() { return 42; }';
    const result = analyzeCyclomaticComplexity([{ path: 'simple.js', content: code }]);
    assert.equal(result.stats.totalFunctions, 1);
    assert.equal(result.stats.complexFunctions, 0);
    assert.equal(result.stats.avgComplexity, 1);
  });

  it('detects if/else branches', () => {
    const code = [
      'function classify(n) {',
      '  if (n > 0) { return "positive"; }',
      '  else if (n < 0) { return "negative"; }',
      '  else { return "zero"; }',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'branch.js', content: code }]);
    assert.equal(result.stats.totalFunctions, 1);
    // complexity should be at least 3 (base 1 + 2 if branches)
    assert.ok(result.stats.avgComplexity >= 3, `expected >= 3, got ${result.stats.avgComplexity}`);
  });

  it('detects loops adding to complexity', () => {
    const code = [
      'function process(items) {',
      '  for (let i = 0; i < items.length; i++) {',
      '    while (true) { break; }',
      '  }',
      '  return items;',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'loop.js', content: code }]);
    assert.ok(result.stats.avgComplexity >= 3, `expected >= 3, got ${result.stats.avgComplexity}`);
  });

  it('detects switch case branches', () => {
    const code = [
      'function handle(status) {',
      '  switch (status) {',
      '    case "active": return 1;',
      '    case "inactive": return 0;',
      '    case "pending": return -1;',
      '    default: return null;',
      '  }',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'switch.js', content: code }]);
    assert.ok(result.stats.avgComplexity >= 4, `expected >= 4, got ${result.stats.avgComplexity}`);
  });

  it('detects ternary operators', () => {
    const code = 'function bool(b) { return b ? "yes" : "no"; }';
    const result = analyzeCyclomaticComplexity([{ path: 'ternary.js', content: code }]);
    assert.ok(result.stats.avgComplexity >= 2, `expected >= 2, got ${result.stats.avgComplexity}`);
  });

  it('detects logical operators as decision points', () => {
    const code = [
      'function check(a, b, c) {',
      '  if (a && b || c) { return true; }',
      '  return false;',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'logical.js', content: code }]);
    // base 1 + if(1) + &&(1) + ||(1) = 4
    assert.ok(result.stats.avgComplexity >= 4, `expected >= 4, got ${result.stats.avgComplexity}`);
  });

  it('flags high-complexity functions', () => {
    const lines = ['function complex(x) {'];
    for (let i = 0; i < 12; i++) {
      lines.push(`  if (x === ${i}) { return ${i}; }`);
    }
    lines.push('  return -1;');
    lines.push('}');
    const result = analyzeCyclomaticComplexity([{ path: 'complex.js', content: lines.join('\n') }]);
    assert.ok(result.stats.complexFunctions >= 1, 'should detect complex function');
    assert.ok(result.issues.length >= 1);
    assert.ok(result.issues[0].complexity >= 10);
  });

  it('assigns high severity for very complex functions (≥15)', () => {
    const lines = ['function huge(x) {'];
    for (let i = 0; i < 18; i++) {
      lines.push(`  if (x === ${i}) { return ${i}; }`);
    }
    lines.push('  return -1;');
    lines.push('}');
    const result = analyzeCyclomaticComplexity([{ path: 'huge.js', content: lines.join('\n') }]);
    const highIssues = result.issues.filter(i => i.severity === 'high');
    assert.ok(highIssues.length >= 1, 'should have high severity');
  });

  it('handles arrow functions', () => {
    const code = 'const fn = (x) => { if (x) { return 1; } return 0; }';
    const result = analyzeCyclomaticComplexity([{ path: 'arrow.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
    assert.ok(result.stats.avgComplexity >= 2);
  });

  it('skips test files', () => {
    const code = 'function fake() { if (true) { return 1; } }';
    const result = analyzeCyclomaticComplexity([{ path: 'foo.test.js', content: code }]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('calculates max complexity correctly', () => {
    const code = [
      'function simple() { return 1; }',
      'function hard(x) {',
      '  if (x === 1) { return 1; }',
      '  if (x === 2) { return 2; }',
      '  if (x === 3) { return 3; }',
      '  if (x === 4) { return 4; }',
      '  return 0;',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'multi.js', content: code }]);
    assert.ok(result.stats.maxComplexity >= 5);
  });

  it('handles catch blocks as decision points', () => {
    const code = [
      'function risky() {',
      '  try { return JSON.parse("{}"); }',
      '  catch (e) { return null; }',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'catch.js', content: code }]);
    assert.ok(result.stats.avgComplexity >= 2);
  });

  it('handles do-while loops', () => {
    const code = [
      'function loop(items) {',
      '  let i = 0;',
      '  do {',
      '    i++;',
      '  } while (i < items.length);',
      '  return i;',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'dowhile.js', content: code }]);
    assert.ok(result.stats.avgComplexity >= 2);
  });

  it('does not flag simple functions as complex', () => {
    const code = [
      'function add(a, b) { return a + b; }',
      'function sub(a, b) { return a - b; }',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'simple2.js', content: code }]);
    assert.equal(result.stats.complexFunctions, 0);
    assert.equal(result.grade, 'A');
  });

  it('deducts score for multiple complex functions', () => {
    const lines = [''];
    // Two complex functions
    for (const fnName of ['fn1', 'fn2']) {
      lines.push(`function ${fnName}(x) {`);
      for (let i = 0; i < 12; i++) {
        lines.push(`  if (x === ${i}) { return ${i}; }`);
      }
      lines.push('  return -1;');
      lines.push('}');
    }
    const result = analyzeCyclomaticComplexity([{ path: 'multi-complex.js', content: lines.join('\n') }]);
    assert.ok(result.score < 100, `score should be < 100, got ${result.score}`);
    assert.ok(result.grade !== 'A', `grade should not be A, got ${result.grade}`);
  });

  it('handles nullish coalescing operator', () => {
    const code = 'function fallback(x) { return x ?? "default"; }';
    const result = analyzeCyclomaticComplexity([{ path: 'nullish.js', content: code }]);
    assert.ok(result.stats.avgComplexity >= 2);
  });

  it('ignores comments when counting decision points', () => {
    const code = [
      'function commented(x) {',
      '  // if (x) { return 1; }',
      '  /* if (x) return 2; */',
      '  return x;',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'commented.js', content: code }]);
    assert.equal(result.stats.avgComplexity, 1);
  });

  it('formats report with issues', () => {
    const lines = ['function complex(x) {'];
    for (let i = 0; i < 12; i++) {
      lines.push(`  if (x === ${i}) { return ${i}; }`);
    }
    lines.push('  return -1;');
    lines.push('}');
    const result = analyzeCyclomaticComplexity([{ path: 'report.js', content: lines.join('\n') }]);
    const report = formatCyclomaticComplexityReport(result);
    assert.ok(report.includes('Cyclomatic Complexity'));
    assert.ok(report.includes('complex'));
    assert.ok(report.includes('Health Score'));
  });

  it('formats report without issues', () => {
    const result = analyzeCyclomaticComplexity([{ path: 'ok.js', content: 'function ok() { return 1; }' }]);
    const report = formatCyclomaticComplexityReport(result);
    assert.ok(report.includes('manageable complexity'));
  });

  it('handles class methods', () => {
    const code = [
      'class Service {',
      '  process(data) {',
      '    if (data) { return data.value; }',
      '    return null;',
      '  }',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'class.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
    assert.ok(result.stats.avgComplexity >= 2);
  });

  it('handles multiple functions in one file', () => {
    const code = [
      'function fn1(x) { if (x) { return 1; } return 0; }',
      'function fn2(x) { return x; }',
      'function fn3(x) {',
      '  for (let i = 0; i < x; i++) {',
      '    if (i % 2 === 0) { continue; }',
      '  }',
      '  return x;',
      '}',
    ].join('\n');
    const result = analyzeCyclomaticComplexity([{ path: 'multi-fn.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 3, `expected >= 3, got ${result.stats.totalFunctions}`);
  });

  it('handles empty content gracefully', () => {
    const result = analyzeCyclomaticComplexity([{ path: 'empty.js', content: '' }]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('returns proper grade scale', () => {
    const lines = ['function big(x) {'];
    for (let i = 0; i < 20; i++) {
      lines.push(`  if (x === ${i}) { return ${i}; }`);
    }
    lines.push('  return -1;');
    lines.push('}');
    const result = analyzeCyclomaticComplexity([{ path: 'big.js', content: lines.join('\n') }]);
    assert.ok(['A', 'B', 'C', 'D', 'F'].includes(result.grade));
    assert.ok(result.score >= 0 && result.score <= 100);
  });
});
