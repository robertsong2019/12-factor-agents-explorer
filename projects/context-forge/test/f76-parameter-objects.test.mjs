import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeParameterObjects, formatParameterObjectsReport } from '../context-forge.mjs';

describe('analyzeParameterObjects', () => {
  it('returns clean result for empty file list', () => {
    const result = analyzeParameterObjects([]);
    assert.equal(result.stats.totalFunctions, 0);
    assert.equal(result.stats.longParamFunctions, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it('skips non-JS files', () => {
    const result = analyzeParameterObjects([
      { path: 'script.py', content: 'def fn(a, b, c, d, e):\n  pass' },
    ]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('skips files with no content', () => {
    const result = analyzeParameterObjects([
      { path: 'test.js', content: null },
    ]);
    assert.equal(result.stats.totalFunctions, 0);
  });

  it('detects functions with 4+ scalar params', () => {
    const code = 'function create(name, age, email, phone, role) { return { name, age, email, phone, role }; }';
    const result = analyzeParameterObjects([{ path: 'long.js', content: code }]);
    assert.ok(result.stats.longParamFunctions >= 1, `expected >= 1, got ${result.stats.longParamFunctions}`);
    assert.ok(result.issues.some(i => i.label.includes('5 parameters')), 'should detect 5 params');
  });

  it('detects functions with 6+ params as high severity', () => {
    const code = 'function init(host, port, user, pass, db, timeout, retries) { return null; }';
    const result = analyzeParameterObjects([{ path: 'very-long.js', content: code }]);
    const highIssues = result.issues.filter(i => i.severity === 'high');
    assert.ok(highIssues.length >= 1, 'should have high severity issue');
  });

  it('does not flag functions with 3 or fewer params', () => {
    const code = 'function add(a, b, c) { return a + b + c; }';
    const result = analyzeParameterObjects([{ path: 'ok.js', content: code }]);
    assert.equal(result.stats.longParamFunctions, 0);
  });

  it('detects boolean parameter confusion', () => {
    const code = 'function config(isActive, isVisible, isEnabled) { return null; }';
    const result = analyzeParameterObjects([{ path: 'bools.js', content: code }]);
    assert.ok(result.stats.booleanParamFunctions >= 1, `expected >= 1, got ${result.stats.booleanParamFunctions}`);
  });

  it('detects boolean params via TypeScript annotations', () => {
    const code = 'function setOptions(verbose: boolean, debug: boolean, dryRun: boolean) { return null; }';
    const result = analyzeParameterObjects([{ path: 'ts.ts', content: code }]);
    assert.ok(result.stats.booleanParamFunctions >= 1);
  });

  it('counts functions correctly', () => {
    const code = [
      'function one(a) { return a; }',
      'function two(a, b) { return a + b; }',
      'function three(a, b, c) { return a + b + c; }',
    ].join('\n');
    const result = analyzeParameterObjects([{ path: 'count.js', content: code }]);
    assert.equal(result.stats.totalFunctions, 3);
    assert.equal(result.stats.longParamFunctions, 0);
  });

  it('handles arrow functions with many params', () => {
    const code = 'const handler = (req, res, next, ctx, opts) => { res.json(req.body); };';
    const result = analyzeParameterObjects([{ path: 'arrow.js', content: code }]);
    assert.ok(result.stats.longParamFunctions >= 1);
  });

  it('handles class methods', () => {
    const code = [
      'class Service {',
      '  fetch(query, page, limit, sort, filter) {',
      '    return this.db.find(query);',
      '  }',
      '}',
    ].join('\n');
    const result = analyzeParameterObjects([{ path: 'cls.js', content: code }]);
    assert.ok(result.stats.totalFunctions >= 1);
    assert.ok(result.stats.longParamFunctions >= 1);
  });

  it('skips destructured params (not scalar)', () => {
    const code = 'function process({ name, age, email, phone }) { return name; }';
    const result = analyzeParameterObjects([{ path: 'destructure.js', content: code }]);
    assert.equal(result.stats.longParamFunctions, 0);
  });

  it('skips rest params', () => {
    const code = 'function format(...args) { return args.join(" "); }';
    const result = analyzeParameterObjects([{ path: 'rest.js', content: code }]);
    assert.equal(result.stats.longParamFunctions, 0);
  });

  it('calculates score and grade correctly with many issues', () => {
    let code = '';
    for (let n = 0; n < 10; n++) {
      code += `function fn${n}(a, b, c, d, e, f) { return null; }\n`;
    }
    const result = analyzeParameterObjects([{ path: 'many.js', content: code }]);
    assert.ok(result.score < 100, `score should be < 100, got ${result.score}`);
    assert.ok(['C', 'D', 'F'].includes(result.grade), `expected C/D/F, got ${result.grade}`);
  });

  it('formats report with issues', () => {
    const code = 'function big(a, b, c, d, e) { return null; }';
    const result = analyzeParameterObjects([{ path: 'big.js', content: code }]);
    const report = formatParameterObjectsReport(result);
    assert.match(report, /Parameter Object Analysis/);
    assert.match(report, /Health Score:/);
    assert.match(report, /Summary/);
  });

  it('formats report without issues', () => {
    const result = analyzeParameterObjects([]);
    const report = formatParameterObjectsReport(result);
    assert.match(report, /clean and use parameter objects/);
  });
});
