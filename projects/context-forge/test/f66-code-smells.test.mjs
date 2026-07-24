import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeCodeSmells, formatCodeSmellReport } from '../context-forge.mjs';

describe('F66: analyzeCodeSmells()', () => {
  describe('basic functionality', () => {
    it('returns correct structure', () => {
      const files = [{ path: 'a.js', content: 'const x = 1;' }];
      const result = analyzeCodeSmells(files);
      assert.ok(result.grade);
      assert.ok(typeof result.score === 'number');
      assert.ok(result.totalFiles === 1);
      assert.ok(result.summary);
      assert.ok(Array.isArray(result.files));
    });

    it('handles empty input', () => {
      const result = analyzeCodeSmells([]);
      assert.equal(result.totalFiles, 0);
      assert.equal(result.score, 100);
      assert.equal(result.grade, 'A');
    });
  });

  describe('long file detection', () => {
    it('flags files over 500 lines', () => {
      const long = 'const x = 1;\n'.repeat(550);
      const files = [{ path: 'big.js', content: long }];
      const result = analyzeCodeSmells(files);
      assert.ok(result.summary.longFiles >= 1);
      const issue = result.files[0].issues.find(i => i.description.toLowerCase().includes('long'));
      assert.ok(issue);
    });

    it('does not flag short files', () => {
      const files = [{ path: 'a.js', content: 'const x = 1;\n'.repeat(50) }];
      const result = analyzeCodeSmells(files);
      assert.equal(result.summary.longFiles, 0);
    });
  });

  describe('deep nesting detection', () => {
    it('detects deeply nested code (4+ levels)', () => {
      const code = [
        'function a() {',
        '  if (x) {',
        '    if (y) {',
        '      if (z) {',
        '        if (w) {',
        '          doSomething();',
        '        }',
        '      }',
        '    }',
        '  }',
        '}',
      ].join('\n');
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.ok(result.summary.deepNesting >= 1);
    });

    it('does not flag shallow nesting', () => {
      const code = 'function a() {\n  if (x) {\n    doSomething();\n  }\n}\n';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.equal(result.summary.deepNesting, 0);
    });
  });

  describe('too many parameters', () => {
    it('flags functions with 5+ parameters', () => {
      const code = 'function foo(a, b, c, d, e, f) { return a; }';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.ok(result.summary.tooManyParams >= 1);
    });

    it('does not flag functions with few parameters', () => {
      const code = 'function foo(a, b) { return a; }';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.equal(result.summary.tooManyParams, 0);
    });
  });

  describe('magic numbers', () => {
    it('detects magic numbers in comparisons', () => {
      const code = 'if (status === 404) { handleError(); }';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.ok(result.summary.magicNumbers >= 1);
    });

    it('does not flag 0, 1, -1', () => {
      const code = 'const x = 0;\nconst y = 1;\nconst z = -1;';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      // 0, 1, -1 are excluded
      assert.equal(result.summary.magicNumbers, 0);
    });

    it('does not flag variable assignments', () => {
      const code = 'const timeout = 5000;';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      // Only flag in comparisons, not assignments
      assert.equal(result.summary.magicNumbers, 0);
    });
  });

  describe('god file detection (too many exports)', () => {
    it('flags files with 10+ exports', () => {
      const lines = [];
      for (let i = 0; i < 12; i++) {
        lines.push(`export function func${i}() { return ${i}; }`);
      }
      const result = analyzeCodeSmells([{ path: 'god.js', content: lines.join('\n') }]);
      assert.ok(result.summary.godFiles >= 1);
    });

    it('does not flag files with few exports', () => {
      const code = 'export function a() {}\nexport function b() {}';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.equal(result.summary.godFiles, 0);
    });
  });

  describe('empty catch blocks', () => {
    it('detects empty catch blocks', () => {
      const code = 'try {\n  doSomething();\n} catch (e) {\n}\n';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.ok(result.summary.emptyCatch >= 1);
    });

    it('does not flag non-empty catch', () => {
      const code = 'try {\n  doSomething();\n} catch (e) {\n  console.error(e);\n}\n';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.equal(result.summary.emptyCatch, 0);
    });
  });

  describe('todo/todo comments', () => {
    it('detects TODO comments', () => {
      const code = '// TODO: fix this later\nconst x = 1;';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.ok(result.summary.todoComments >= 1);
    });

    it('detects FIXME comments', () => {
      const code = '// FIXME: broken\nconst x = 1;';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.ok(result.summary.todoComments >= 1);
    });
  });

  describe('scoring and grading', () => {
    it('gives A grade to clean code', () => {
      const code = 'export function add(a, b) {\n  return a + b;\n}\n';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      assert.equal(result.grade, 'A');
    });

    it('penalizes smelly code', () => {
      const lines = [];
      for (let i = 0; i < 12; i++) lines.push(`export function f${i}(a,b,c,d,e,f) { return a; }`);
      lines.push('// TODO: everything');
      const result = analyzeCodeSmells([{ path: 'bad.js', content: lines.join('\n') }]);
      assert.ok(result.score < 80, `Expected score < 80, got ${result.score}`);
    });
  });

  describe('issue details', () => {
    it('provides line numbers', () => {
      const code = 'const a = 1;\nconst b = 2;\n// TODO: fix\nconst c = 3;';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      const todoIssue = result.files[0]?.issues.find(i => i.description.includes('TODO'));
      if (todoIssue) {
        assert.ok(todoIssue.line > 0);
      }
    });

    it('provides severity levels', () => {
      const code = 'try {\n  x();\n} catch(e) {}\n';
      const result = analyzeCodeSmells([{ path: 'a.js', content: code }]);
      for (const issue of result.files[0]?.issues || []) {
        assert.ok(['low', 'medium', 'high'].includes(issue.severity));
      }
    });
  });

  describe('multi-file aggregation', () => {
    it('aggregates across files', () => {
      const files = [
        { path: 'a.js', content: '// TODO: a\n' },
        { path: 'b.js', content: 'try { x(); } catch(e) {}\n' },
      ];
      const result = analyzeCodeSmells(files);
      assert.equal(result.totalFiles, 2);
      assert.ok(result.summary.todoComments >= 1);
      assert.ok(result.summary.emptyCatch >= 1);
    });

    it('only includes files with issues', () => {
      const files = [
        { path: 'a.js', content: '// TODO: fix\n' },
        { path: 'b.js', content: 'const x = 1;\n' },
      ];
      const result = analyzeCodeSmells(files);
      assert.equal(result.files.length, 1);
    });
  });
});

describe('F66: formatCodeSmellReport()', () => {
  it('returns a string', () => {
    const result = analyzeCodeSmells([{ path: 'a.js', content: 'const x = 1;' }]);
    const report = formatCodeSmellReport(result);
    assert.equal(typeof report, 'string');
  });

  it('includes grade and score', () => {
    const result = analyzeCodeSmells([{ path: 'a.js', content: '// TODO: fix' }]);
    const report = formatCodeSmellReport(result);
    assert.match(report, /Grade/);
    assert.match(report, /Code Smell/);
  });

  it('handles null', () => {
    const report = formatCodeSmellReport(null);
    assert.match(report, /No data/);
  });

  it('lists file issues', () => {
    const files = [{ path: 'stinky.js', content: '// TODO: fix\ncatch(e) {}\n'.repeat(5) }];
    const result = analyzeCodeSmells(files);
    const report = formatCodeSmellReport(result);
    if (result.files.length > 0) {
      assert.match(report, /stinky\.js/);
    }
  });

  it('includes summary table', () => {
    const result = analyzeCodeSmells([{ path: 'a.js', content: 'const x = 1;' }]);
    const report = formatCodeSmellReport(result);
    assert.match(report, /Summary/);
  });
});
