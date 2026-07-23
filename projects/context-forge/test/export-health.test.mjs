import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeExportHealth, formatExportHealthReport } from '../context-forge.mjs';

describe('F57: analyzeExportHealth()', () => {
  it('returns empty result for no files', () => {
    const result = analyzeExportHealth([]);
    assert.equal(result.fileCount, 0);
    assert.equal(result.grade, 'F');
  });

  it('skips non-JS files', () => {
    const result = analyzeExportHealth([
      { path: 'script.py', content: 'def foo(): pass' },
      { path: 'readme.md', content: '# Title' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('detects named exports (declarations)', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export function foo() {}\nexport const bar = 42;\nexport class Baz {}' },
    ]);
    assert.equal(result.totalNamedExports, 3);
    assert.equal(result.totalDefaultExports, 0);
  });

  it('detects default exports', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export default function main() {}' },
    ]);
    assert.equal(result.totalDefaultExports, 1);
  });

  it('detects namespace re-exports', () => {
    const result = analyzeExportHealth([
      { path: 'index.js', content: "export * from './utils';" },
    ]);
    assert.ok(result.totalNamespaceExports >= 1);
  });

  it('detects barrel files (only re-exports)', () => {
    const result = analyzeExportHealth([
      { path: 'index.js', content: "export { foo } from './foo';\nexport { bar } from './bar';\nexport { baz } from './baz';" },
    ]);
    assert.ok(result.totalBarrelFiles >= 1);
    assert.ok(result.files[0].isBarrelFile);
  });

  it('does not classify files with own exports as barrel', () => {
    const result = analyzeExportHealth([
      { path: 'mod.js', content: "export function ownFunc() {}\nexport { x } from './x';" },
    ]);
    assert.equal(result.totalBarrelFiles, 0);
  });

  it('detects re-export chains', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: "export { foo } from './foo';\nexport { bar } from './bar';" },
    ]);
    assert.equal(result.totalReExports, 2);
  });

  it('flags mixed export style (default + named)', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export const x = 1;\nexport default function() {}' },
    ]);
    assert.ok(result.files[0].issues.some(i => i.type === 'mixed_export_style'));
  });

  it('flags multiple default exports as error', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export default function a() {}\nexport default function b() {}' },
    ]);
    assert.ok(result.files[0].issues.some(i => i.type === 'multiple_defaults'));
  });

  it('detects named export lists: export { a, b, c }', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'const a = 1, b = 2, c = 3;\nexport { a, b, c };' },
    ]);
    assert.equal(result.totalNamedExports, 3);
  });

  it('detects re-export from with rename: export { foo as bar }', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: "export { foo as bar } from './mod';" },
    ]);
    assert.equal(result.totalReExports, 1);
  });

  it('skips comment lines', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: '// export function commented() {}\n// export default foo' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('handles empty content', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: '' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('handles .ts files', () => {
    const result = analyzeExportHealth([
      { path: 'mod.ts', content: 'export interface Foo {}\nexport function bar(): void {}' },
    ]);
    assert.ok(result.totalNamedExports >= 1);
  });

  it('healthScore is 0-100', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export function foo() {}' },
    ]);
    assert.ok(result.healthScore >= 0 && result.healthScore <= 100);
  });

  it('grade is valid letter', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export function foo() {}' },
    ]);
    assert.ok(['A', 'B', 'C', 'D', 'F'].includes(result.grade));
  });

  it('handles export async function', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export async function fetchData() {\n  return await fetch("/api");\n}' },
    ]);
    assert.equal(result.totalNamedExports, 1);
  });

  it('handles export const with arrow function', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export const handler = async (req, res) => {\n  res.json({});\n};' },
    ]);
    assert.equal(result.totalNamedExports, 1);
  });
});

describe('F57: formatExportHealthReport()', () => {
  it('handles empty result', () => {
    const report = formatExportHealthReport({ fileCount: 0 });
    assert.ok(report.includes('No exports'));
  });

  it('includes health grade and stats', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export function foo() {}\nexport const bar = 42;' },
    ]);
    const report = formatExportHealthReport(result);
    assert.ok(report.includes('Health Grade'));
    assert.ok(report.includes('Named exports'));
    assert.ok(report.includes('Barrel files'));
  });

  it('includes barrel files section when present', () => {
    const result = analyzeExportHealth([
      { path: 'index.js', content: "export { a } from './a';\nexport { b } from './b';\nexport { c } from './c';" },
    ]);
    const report = formatExportHealthReport(result);
    assert.ok(report.includes('Barrel Files'));
  });

  it('includes per-file breakdown', () => {
    const result = analyzeExportHealth([
      { path: 'a.js', content: 'export function foo() {}' },
      { path: 'b.js', content: 'export const x = 1;' },
    ]);
    const report = formatExportHealthReport(result);
    assert.ok(report.includes('Per-file Breakdown'));
    assert.ok(report.includes('a.js'));
    assert.ok(report.includes('b.js'));
  });
});
