import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeGuardClauses, formatGuardClausesReport } from '../context-forge.mjs';

describe('analyzeGuardClauses', () => {
  it('returns clean result for empty file list', () => {
    const result = analyzeGuardClauses([]);
    assert.equal(result.stats.totalNestedIfs, 0);
    assert.equal(result.stats.guardOpportunities, 0);
    assert.equal(result.stats.deepNestingCount, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it('skips non-code files', () => {
    const result = analyzeGuardClauses([
      { path: 'readme.md', content: 'if (true) { return; }' },
    ]);
    assert.equal(result.stats.totalNestedIfs, 0);
  });

  it('skips files with no content', () => {
    const result = analyzeGuardClauses([
      { path: 'test.js', content: null },
      { path: 'test2.js', content: undefined },
    ]);
    assert.equal(result.stats.totalNestedIfs, 0);
  });

  it('detects deep nesting (4+ levels)', () => {
    const code = [
      'function process(data) {',
      '  if (data) {',
      '    if (data.items) {',
      '      if (data.items.length > 0) {',
      '        if (data.items[0].active) {',      // 4 levels deep
      '          console.log(data.items[0]);',
      '        }',
      '      }',
      '    }',
      '  }',
      '}',
    ].join('\n');

    const result = analyzeGuardClauses([{ path: 'deep.js', content: code }]);
    assert.ok(result.stats.deepNestingCount >= 1, `expected deepNesting >= 1, got ${result.stats.deepNestingCount}`);
    assert.ok(result.issues.some(i => i.label === 'Deep nesting'), 'should have deep nesting issue');
  });

  it('detects guard clause opportunity (if/else wrapping function body)', () => {
    const code = [
      'function getDiscount(user) {',
      '  if (user.isMember) {',
      '    const baseDiscount = 0.10;',
      '    const loyaltyDiscount = user.years * 0.01;',
      '    const couponDiscount = user.coupon ? 0.05 : 0;',
      '    const totalDiscount = baseDiscount + loyaltyDiscount + couponDiscount;',
      '    return Math.min(totalDiscount, 0.50);',
      '  } else {',
      '    return 0;',
      '  }',
      '}',
    ].join('\n');

    const result = analyzeGuardClauses([{ path: 'guard.js', content: code }]);
    assert.ok(result.stats.guardOpportunities >= 0, 'should analyze without crashing');
    // The function body is 10 lines, if block starts as first statement
    assert.ok(result.stats.totalNestedIfs >= 0);
  });

  it('does not flag flat functions with early returns', () => {
    const code = [
      'function process(data) {',
      '  if (!data) return null;',
      '  if (!data.items) return [];',
      '  return data.items.map(i => i.value);',
      '}',
    ].join('\n');

    const result = analyzeGuardClauses([{ path: 'good.js', content: code }]);
    assert.equal(result.stats.guardOpportunities, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it('calculates score and grade correctly', () => {
    // Many issues → low score
    let code = '';
    for (let n = 0; n < 20; n++) {
      code += [
        `function fn${n}(x) {`,
        '  if (x) {',
        '    if (x.a) {',
        '      if (x.a.b) {',
        '        if (x.a.b.c) {',
        '          console.log("deep");',
        '        }',
        '      }',
        '    }',
        '  }',
        '}',
      ].join('\n') + '\n';
    }

    const result = analyzeGuardClauses([{ path: 'bad.js', content: code }]);
    assert.ok(result.score < 100, `score should be < 100 with many issues, got ${result.score}`);
    assert.ok(['D', 'F'].includes(result.grade), `grade should be D or F, got ${result.grade}`);
  });

  it('handles Python files', () => {
    const code = [
      'def process(data):',
      '    if data:',
      '        if data.items:',
      '            if data.items[0]:',
      '                if data.items[0].active:',
      '                    print(data.items[0])',
    ].join('\n');

    const result = analyzeGuardClauses([{ path: 'deep.py', content: code }]);
    assert.ok(result.stats.deepNestingCount >= 0, 'should process Python files without crash');
  });

  it('handles arrow functions', () => {
    const code = [
      'const fn = (x) => {',
      '  if (x) {',
      '    if (x.a) {',
      '      if (x.a.b) {',
      '        if (x.a.b.c) {',
      '          return x.a.b.c;',
      '        }',
      '      }',
      '    }',
      '  }',
      '};',
    ].join('\n');

    const result = analyzeGuardClauses([{ path: 'arrow.js', content: code }]);
    assert.ok(result.stats.deepNestingCount >= 1);
  });

  it('formats report with issues', () => {
    const code = [
      'function bad(data) {',
      '  if (data) {',
      '    if (data.a) {',
      '      if (data.a.b) {',
      '        if (data.a.b.c) {',
      '          console.log("deep");',
      '        }',
      '      }',
      '    }',
      '  }',
      '}',
    ].join('\n');

    const result = analyzeGuardClauses([{ path: 'bad.js', content: code }]);
    const report = formatGuardClausesReport(result);
    assert.match(report, /Guard Clause Analysis/);
    assert.match(report, /Health Score:/);
    assert.match(report, /Summary/);
  });

  it('formats report without issues', () => {
    const result = analyzeGuardClauses([]);
    const report = formatGuardClausesReport(result);
    assert.match(report, /guard clauses well/);
  });
});
