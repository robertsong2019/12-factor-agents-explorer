import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeTypeSafety, formatTypeSafetyReport } from '../context-forge.mjs';

describe('F65: analyzeTypeSafety()', () => {
  describe('basic functionality', () => {
    it('returns correct structure with grade and score', () => {
      const files = [
        { path: 'a.ts', content: 'const x: number = 1;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.grade);
      assert.ok(typeof result.score === 'number');
      assert.ok(result.totalFiles === 1);
      assert.ok(Array.isArray(result.files));
      assert.ok(result.summary);
    });

    it('handles empty files array', () => {
      const result = analyzeTypeSafety([]);
      assert.equal(result.totalFiles, 0);
      assert.equal(result.score, 100);
      assert.equal(result.grade, 'A');
    });

    it('handles non-TS files (ignored)', () => {
      const files = [
        { path: 'a.js', content: 'const x = 1;' },
        { path: 'b.py', content: 'x = 1' },
      ];
      const result = analyzeTypeSafety(files);
      assert.equal(result.totalFiles, 0);
      assert.equal(result.score, 100);
    });
  });

  describe('any type detection', () => {
    it('detects explicit any annotations', () => {
      const files = [
        { path: 'a.ts', content: 'function foo(x: any): any { return x; }' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.anyUsage >= 2);
      assert.equal(result.files[0].issues.length, 2);
      assert.match(result.files[0].issues[0].description, /any/);
    });

    it('detects implicit any in parameters (no type annotation)', () => {
      const files = [
        { path: 'a.ts', content: 'function foo(x) { return x; }' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.implicitAny >= 1);
    });

    it('does not flag implicit any when type is present', () => {
      const files = [
        { path: 'a.ts', content: 'function foo(x: string): void {}' },
      ];
      const result = analyzeTypeSafety(files);
      assert.equal(result.summary.implicitAny, 0);
    });
  });

  describe('@ts-ignore / @ts-nocheck detection', () => {
    it('detects @ts-ignore comments', () => {
      const files = [
        { path: 'a.ts', content: '// @ts-ignore\nconst x = obj.unknownProp;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.tsIgnore >= 1);
    });

    it('detects @ts-nocheck comments', () => {
      const files = [
        { path: 'a.ts', content: '// @ts-nocheck\nconst x = 1;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.tsNocheck >= 1);
    });

    it('detects @ts-expect-error comments', () => {
      const files = [
        { path: 'a.ts', content: '// @ts-expect-error\nconst x = 1;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.tsExpectError >= 1);
    });
  });

  describe('type assertion detection', () => {
    it('detects "as" type assertions', () => {
      const files = [
        { path: 'a.ts', content: 'const x = obj as string;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.typeAssertions >= 1);
    });

    it('detects angle-bracket assertions', () => {
      const files = [
        { path: 'a.ts', content: 'const x = <string>obj;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.typeAssertions >= 1);
    });

    it('does not count "as" in non-assertion context', () => {
      const files = [
        { path: 'a.ts', content: 'const obj = { x: 1 }; const y = 2;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.equal(result.summary.typeAssertions, 0);
    });
  });

  describe('missing return type detection', () => {
    it('detects exported functions without return type', () => {
      const files = [
        { path: 'a.ts', content: 'export function foo(x: string) { return x; }' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.missingReturnType >= 1);
    });

    it('does not flag functions with return type', () => {
      const files = [
        { path: 'a.ts', content: 'export function foo(x: string): string { return x; }' },
      ];
      const result = analyzeTypeSafety(files);
      assert.equal(result.summary.missingReturnType, 0);
    });

    it('detects exported arrow functions without return type', () => {
      const files = [
        { path: 'a.ts', content: 'export const bar = (x: number) => x * 2;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.missingReturnType >= 1);
    });
  });

  describe('non-null assertion detection', () => {
    it('detects non-null assertions (!)', () => {
      const files = [
        { path: 'a.ts', content: 'const x = obj!.prop;' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.summary.nonNullAssertions >= 1);
    });
  });

  describe('scoring and grading', () => {
    it('penalizes any usage heavily', () => {
      const clean = [{ path: 'a.ts', content: 'const x: number = 1;' }];
      const dirty = [{ path: 'a.ts', content: 'function f(a: any, b: any): any { return a; }' }];
      const cleanResult = analyzeTypeSafety(clean);
      const dirtyResult = analyzeTypeSafety(dirty);
      assert.ok(cleanResult.score > dirtyResult.score);
    });

    it('gives A grade to clean TS files', () => {
      const files = [
        { path: 'a.ts', content: 'export function foo(x: string): string { return x; }' },
      ];
      const result = analyzeTypeSafety(files);
      assert.equal(result.grade, 'A');
    });

    it('gives worse grade for many violations', () => {
      const files = [
        { path: 'a.ts', content: '// @ts-nocheck\nfunction f(a: any): any { const x = obj as any; return x; }' },
      ];
      const result = analyzeTypeSafety(files);
      assert.ok(result.score < 70, `Score should be < 70, got ${result.score}`);
    });
  });

  describe('issue details', () => {
    it('provides line numbers for issues', () => {
      const files = [
        { path: 'a.ts', content: 'const a = 1;\nconst b: any = 2;\nconst c = 3;' },
      ];
      const result = analyzeTypeSafety(files);
      const issue = result.files[0].issues.find(i => i.description.includes('any'));
      assert.ok(issue);
      assert.ok(issue.line > 0);
    });

    it('provides severity levels', () => {
      const files = [
        { path: 'a.ts', content: '// @ts-nocheck\nconst x: any = 1 as any;' },
      ];
      const result = analyzeTypeSafety(files);
      for (const issue of result.files[0].issues) {
        assert.ok(['low', 'medium', 'high'].includes(issue.severity));
      }
    });
  });

  describe('multiple files aggregation', () => {
    it('aggregates across multiple TS files', () => {
      const files = [
        { path: 'a.ts', content: 'const x: any = 1;' },
        { path: 'b.ts', content: '// @ts-ignore\nconst y = 1;' },
        { path: 'c.ts', content: 'export function f(): void {}' },
      ];
      const result = analyzeTypeSafety(files);
      assert.equal(result.totalFiles, 3);
      assert.ok(result.summary.anyUsage >= 1);
      assert.ok(result.summary.tsIgnore >= 1);
    });

    it('only includes files with issues in files array', () => {
      const files = [
        { path: 'a.ts', content: 'const x: any = 1;' },
        { path: 'b.ts', content: 'export function f(): void {}' },
      ];
      const result = analyzeTypeSafety(files);
      // b.ts has no issues
      const withIssues = result.files.filter(f => f.issues.length > 0);
      assert.ok(withIssues.length === 1);
      assert.equal(withIssues[0].path, 'a.ts');
    });
  });

  describe('TypeScript file detection', () => {
    it('processes .ts files', () => {
      const result = analyzeTypeSafety([{ path: 'a.ts', content: 'const x = 1;' }]);
      assert.equal(result.totalFiles, 1);
    });

    it('processes .tsx files', () => {
      const result = analyzeTypeSafety([{ path: 'a.tsx', content: 'const x = 1;' }]);
      assert.equal(result.totalFiles, 1);
    });

    it('skips .js files', () => {
      const result = analyzeTypeSafety([{ path: 'a.js', content: 'const x = 1;' }]);
      assert.equal(result.totalFiles, 0);
    });

    it('skips .mjs files', () => {
      const result = analyzeTypeSafety([{ path: 'a.mjs', content: 'const x = 1;' }]);
      assert.equal(result.totalFiles, 0);
    });
  });
});

describe('F65: formatTypeSafetyReport()', () => {
  it('returns a string', () => {
    const result = analyzeTypeSafety([{ path: 'a.ts', content: 'const x: number = 1;' }]);
    const report = formatTypeSafetyReport(result);
    assert.equal(typeof report, 'string');
  });

  it('includes grade and score', () => {
    const result = analyzeTypeSafety([{ path: 'a.ts', content: 'const x: any = 1;' }]);
    const report = formatTypeSafetyReport(result);
    assert.match(report, /Grade/);
    assert.match(report, /Type Safety/);
  });

  it('includes summary counts', () => {
    const result = analyzeTypeSafety([{ path: 'a.ts', content: 'const x: any = 1;' }]);
    const report = formatTypeSafetyReport(result);
    assert.match(report, /any/i);
  });

  it('handles null/undefined result', () => {
    const report = formatTypeSafetyReport(null);
    assert.match(report, /No data/);
  });

  it('lists file issues', () => {
    const files = [{ path: 'a.ts', content: '// @ts-nocheck\nconst x: any = 1;' }];
    const result = analyzeTypeSafety(files);
    const report = formatTypeSafetyReport(result);
    assert.match(report, /a\.ts/);
  });
});
