import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeEqualityChecks, formatEqualityChecksReport } from '../context-forge.mjs';

describe('analyzeEqualityChecks', () => {
  it('returns clean result for empty file list', () => {
    const result = analyzeEqualityChecks([]);
    assert.equal(result.stats.totalComparisons, 0);
    assert.equal(result.stats.looseComparisons, 0);
    assert.equal(result.stats.strictComparisons, 0);
    assert.equal(result.issues.length, 0);
    assert.equal(result.grade, 'A');
  });

  it('skips non-JS files', () => {
    const result = analyzeEqualityChecks([
      { path: 'script.py', content: 'if x == 1:\n  pass' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('skips files with no content', () => {
    const result = analyzeEqualityChecks([
      { path: 'test.js', content: null },
    ]);
    assert.equal(result.stats.totalComparisons, 0);
  });

  it('skips test files', () => {
    const result = analyzeEqualityChecks([
      { path: 'foo.test.js', content: 'const x = a == b;' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('skips spec files', () => {
    const result = analyzeEqualityChecks([
      { path: 'foo.spec.ts', content: 'const x = a == b;' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('detects loose == operator', () => {
    const result = analyzeEqualityChecks([
      { path: 'check.js', content: 'if (x == 1) { doSomething(); }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
    assert.equal(result.issues.length, 1);
    assert.equal(result.issues[0].operator, '==');
    assert.equal(result.issues[0].suggestion, '===');
  });

  it('detects loose != operator', () => {
    const result = analyzeEqualityChecks([
      { path: 'check.js', content: 'if (x != 1) { doSomething(); }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
    assert.equal(result.issues[0].operator, '!=');
    assert.equal(result.issues[0].suggestion, '!==');
  });

  it('does NOT flag === operator', () => {
    const result = analyzeEqualityChecks([
      { path: 'strict.js', content: 'if (x === 1) { doSomething(); }' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
    assert.equal(result.stats.strictComparisons, 1);
    assert.equal(result.issues.length, 0);
  });

  it('does NOT flag !== operator', () => {
    const result = analyzeEqualityChecks([
      { path: 'strict.js', content: 'if (x !== 1) { doSomething(); }' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
    assert.equal(result.stats.strictComparisons, 1);
    assert.equal(result.issues.length, 0);
  });

  it('does NOT flag >= operator', () => {
    const result = analyzeEqualityChecks([
      { path: 'gte.js', content: 'if (x >= 10) { doSomething(); }' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('does NOT flag <= operator', () => {
    const result = analyzeEqualityChecks([
      { path: 'lte.js', content: 'if (x <= 10) { doSomething(); }' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('does NOT flag => arrow function', () => {
    const result = analyzeEqualityChecks([
      { path: 'arrow.js', content: 'const fn = (x) => { return x; };' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('handles multiple loose comparisons on one line', () => {
    const result = analyzeEqualityChecks([
      { path: 'multi.js', content: 'if (a == 1 && b != 2) { return; }' },
    ]);
    assert.equal(result.stats.looseComparisons, 2);
  });

  it('identifies null-safe loose equality as low severity', () => {
    const result = analyzeEqualityChecks([
      { path: 'null.js', content: 'if (x == null) { return; }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
    assert.equal(result.stats.nullSafeLoose, 1);
    assert.equal(result.issues[0].severity, 'low');
    assert.equal(result.issues[0].isNullCheck, true);
  });

  it('identifies null-safe loose inequality as low severity', () => {
    const result = analyzeEqualityChecks([
      { path: 'null.js', content: 'if (x != null) { return; }' },
    ]);
    assert.equal(result.stats.nullSafeLoose, 1);
    assert.equal(result.issues[0].severity, 'low');
    assert.equal(result.issues[0].isNullCheck, true);
  });

  it('identifies undefined loose equality as null-safe', () => {
    const result = analyzeEqualityChecks([
      { path: 'undef.js', content: 'if (x == undefined) { return; }' },
    ]);
    assert.equal(result.stats.nullSafeLoose, 1);
    assert.equal(result.issues[0].isNullCheck, true);
  });

  it('flags non-null loose equality as medium severity', () => {
    const result = analyzeEqualityChecks([
      { path: 'coerce.js', content: 'if (x == "hello") { return; }' },
    ]);
    assert.equal(result.stats.nonNullLoose, 1);
    assert.equal(result.issues[0].severity, 'medium');
    assert.equal(result.issues[0].isNullCheck, false);
  });

  it('counts both strict and loose comparisons', () => {
    const code = [
      'const a = x === y;',
      'const b = x == y;',
      'const c = x !== z;',
      'const d = x != z;',
    ].join('\n');
    const result = analyzeEqualityChecks([{ path: 'mixed.js', content: code }]);
    assert.equal(result.stats.strictComparisons, 2);
    assert.equal(result.stats.looseComparisons, 2);
    assert.equal(result.stats.totalComparisons, 4);
  });

  it('deducts more score for non-null loose comparisons', () => {
    const loose = analyzeEqualityChecks([
      { path: 'a.js', content: 'if (x == 42) {}' },
    ]);
    const nullSafe = analyzeEqualityChecks([
      { path: 'a.js', content: 'if (x == null) {}' },
    ]);
    assert.ok(loose.score < nullSafe.score, `non-null (${loose.score}) should be < null-safe (${nullSafe.score})`);
  });

  it('returns grade A for clean code', () => {
    const result = analyzeEqualityChecks([
      { path: 'clean.js', content: 'if (x === y && a !== b) { return; }' },
    ]);
    assert.equal(result.grade, 'A');
    assert.equal(result.score, 100);
  });

  it('handles empty content gracefully', () => {
    const result = analyzeEqualityChecks([{ path: 'empty.js', content: '' }]);
    assert.equal(result.stats.totalComparisons, 0);
    assert.equal(result.grade, 'A');
  });

  it('ignores == inside comments', () => {
    const result = analyzeEqualityChecks([
      { path: 'comment.js', content: '// check if x == y\nconst z = 1;' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('ignores == inside string literals', () => {
    const result = analyzeEqualityChecks([
      { path: 'str.js', content: "const msg = 'a == b means equality';" },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
  });

  it('handles == with various spacing', () => {
    const result = analyzeEqualityChecks([
      { path: 'space.js', content: 'if (x  ==  y) { return; }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
  });

  it('handles != with no spacing', () => {
    const result = analyzeEqualityChecks([
      { path: 'tight.js', content: 'if (x!=y) { return; }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
  });

  it('handles multiple files', () => {
    const result = analyzeEqualityChecks([
      { path: 'a.js', content: 'const x = a == b;' },
      { path: 'b.js', content: 'const y = c === d;' },
      { path: 'c.js', content: 'const z = e != f;' },
    ]);
    assert.equal(result.stats.looseComparisons, 2);
    assert.equal(result.stats.strictComparisons, 1);
  });

  it('handles TypeScript files', () => {
    const result = analyzeEqualityChecks([
      { path: 'types.ts', content: 'if (val == 0) { return; }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
  });

  it('handles TSX files', () => {
    const result = analyzeEqualityChecks([
      { path: 'component.tsx', content: 'if (props.id == props.ref) { return; }' },
    ]);
    assert.equal(result.stats.looseComparisons, 1);
  });

  it('handles null on left side of ==', () => {
    const result = analyzeEqualityChecks([
      { path: 'null-first.js', content: 'if (null == x) { return; }' },
    ]);
    assert.equal(result.stats.nullSafeLoose, 1);
    assert.equal(result.issues[0].isNullCheck, true);
  });

  it('provides context in issues', () => {
    const result = analyzeEqualityChecks([
      { path: 'ctx.js', content: 'const isValid = userInput == expectedValue;' },
    ]);
    assert.ok(result.issues[0].context);
    assert.ok(result.issues[0].context.length > 0);
  });

  it('calculates nonNullLoose correctly', () => {
    const code = [
      'if (a == null) {}',
      'if (b == 42) {}',
      'if (c == "hello") {}',
    ].join('\n');
    const result = analyzeEqualityChecks([{ path: 'calc.js', content: code }]);
    assert.equal(result.stats.looseComparisons, 3);
    assert.equal(result.stats.nullSafeLoose, 1);
    assert.equal(result.stats.nonNullLoose, 2);
  });

  it('score decreases with more loose comparisons', () => {
    const oneLoose = analyzeEqualityChecks([
      { path: 'a.js', content: 'if (x == 1) {}' },
    ]);
    const fiveLoose = analyzeEqualityChecks([
      { path: 'a.js', content: 'if (a==1) {}\nif (b==2) {}\nif (c==3) {}\nif (d==4) {}\nif (e==5) {}' },
    ]);
    assert.ok(fiveLoose.score < oneLoose.score);
  });

  it('handles === immediately after a variable', () => {
    const result = analyzeEqualityChecks([
      { path: 'strict2.js', content: 'const ok = (x===y);' },
    ]);
    assert.equal(result.stats.looseComparisons, 0);
    assert.equal(result.stats.strictComparisons, 1);
  });

  it('handles mixed === and == on same line', () => {
    const result = analyzeEqualityChecks([
      { path: 'mixed.js', content: 'if (a === b && c == d) {}' },
    ]);
    assert.equal(result.stats.strictComparisons, 1);
    assert.equal(result.stats.looseComparisons, 1);
  });
});

describe('formatEqualityChecksReport', () => {
  it('formats report with no issues', () => {
    const result = analyzeEqualityChecks([
      { path: 'clean.js', content: 'if (x === y) {}' },
    ]);
    const report = formatEqualityChecksReport(result);
    assert.ok(report.includes('Equality Check'));
    assert.ok(report.includes('Health Score'));
    assert.ok(report.includes('strict comparison'));
  });

  it('formats report with issues', () => {
    const result = analyzeEqualityChecks([
      { path: 'bad.js', content: 'if (x == 1) {}' },
    ]);
    const report = formatEqualityChecksReport(result);
    assert.ok(report.includes('Issues Found'));
    assert.ok(report.includes('Use ==='));
    assert.ok(report.includes('bad.js'));
  });

  it('includes summary stats in report', () => {
    const result = analyzeEqualityChecks([
      { path: 'a.js', content: 'if (x === y) {}\nif (a != b) {}' },
    ]);
    const report = formatEqualityChecksReport(result);
    assert.ok(report.includes('Total comparisons'));
    assert.ok(report.includes('Loose'));
    assert.ok(report.includes('Strict'));
  });

  it('truncates issues list at 30', () => {
    const lines = [];
    for (let i = 0; i < 35; i++) {
      lines.push(`const r${i} = a${i} == b${i};`);
    }
    const result = analyzeEqualityChecks([{ path: 'many.js', content: lines.join('\n') }]);
    const report = formatEqualityChecksReport(result);
    assert.ok(report.includes('and 5 more'));
  });
});
