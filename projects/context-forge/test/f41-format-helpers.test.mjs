import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  formatScriptsTable,
  formatDepsTable,
  generateDiff,
  formatDiff,
  formatFileSizeReport,
  formatNamingReport,
} from '../context-forge.mjs';

// ─── formatScriptsTable ───────────────────────────

test('F41: formatScriptsTable — empty scripts', () => {
  const result = formatScriptsTable({});
  assert.equal(result, '- (none defined)');
});

test('F41: formatScriptsTable — basic table', () => {
  const result = formatScriptsTable({ test: 'jest', build: 'tsc' });
  assert.ok(result.includes('| Script | Command |'));
  assert.ok(result.includes('`test`'));
  assert.ok(result.includes('jest'));
  assert.ok(result.includes('`build`'));
  assert.ok(result.includes('tsc'));
});

test('F41: formatScriptsTable — respects max limit', () => {
  const scripts = {};
  for (let i = 0; i < 30; i++) scripts[`s${i}`] = `cmd${i}`;
  const result = formatScriptsTable(scripts, 5);
  assert.ok(result.includes('25 more'));
  assert.ok(result.includes('`s0`'));
  assert.ok(!result.includes('`s10`'));
});

// ─── formatDepsTable ──────────────────────────────

test('F41: formatDepsTable — empty deps', () => {
  const result = formatDepsTable({});
  assert.equal(result, '- (none)');
});

test('F41: formatDepsTable — basic table', () => {
  const result = formatDepsTable({ react: '^18.0.0', lodash: '^4.0.0' });
  assert.ok(result.includes('| Package | Version |'));
  assert.ok(result.includes('`react`'));
  assert.ok(result.includes('^18.0.0'));
});

test('F41: formatDepsTable — respects max limit', () => {
  const deps = {};
  for (let i = 0; i < 25; i++) deps[`pkg${i}`] = `^${i}.0.0`;
  const result = formatDepsTable(deps, 3);
  assert.ok(result.includes('22 more'));
  assert.ok(result.includes('`pkg0`'));
  assert.ok(!result.includes('`pkg5`'));
});

// ─── generateDiff ─────────────────────────────────

test('F41: generateDiff — identical text produces no diff', () => {
  const text = 'line1\nline2\nline3';
  const diffs = generateDiff(text, text);
  assert.equal(diffs.length, 0);
});

test('F41: generateDiff — added line', () => {
  const old = 'a\nb';
  const now = 'a\nb\nc';
  const diffs = generateDiff(old, now);
  assert.ok(diffs.some(d => d.type === 'added' && d.line === 'c'));
});

test('F41: generateDiff — removed line', () => {
  const old = 'a\nb\nc';
  const now = 'a\nc';
  const diffs = generateDiff(old, now);
  assert.ok(diffs.some(d => d.type === 'removed' && d.line === 'b'));
});

test('F41: generateDiff — modified line', () => {
  const old = 'hello world';
  const now = 'hello earth';
  const diffs = generateDiff(old, now);
  assert.ok(diffs.some(d => d.type === 'removed' && d.line === 'hello world'));
  assert.ok(diffs.some(d => d.type === 'added' && d.line === 'hello earth'));
});

test('F41: generateDiff — empty strings', () => {
  const diffs = generateDiff('', '');
  assert.equal(diffs.length, 0);
});

// ─── formatDiff ───────────────────────────────────

test('F41: formatDiff — empty diffs', () => {
  assert.equal(formatDiff([]), '(no changes)');
});

test('F41: formatDiff — formats added/removed/context/separator', () => {
  const diffs = [
    { type: 'context', line: 'same' },
    { type: 'removed', line: 'old' },
    { type: 'added', line: 'new' },
    { type: 'separator' },
    { type: 'context', line: 'ctx' },
  ];
  const result = formatDiff(diffs);
  assert.ok(result.includes('  same'));
  assert.ok(result.includes('- old'));
  assert.ok(result.includes('+ new'));
  assert.ok(result.includes('...'));
  assert.ok(result.includes('  ctx'));
});

// ─── formatFileSizeReport ─────────────────────────

test('F41: formatFileSizeReport — empty analysis', () => {
  const result = formatFileSizeReport({ totalFiles: 0 });
  assert.equal(result, 'No files found for size analysis.');
});

test('F41: formatFileSizeReport — full report', () => {
  const analysis = {
    totalFiles: 5,
    totalSizeKB: 102.5,
    avgSizeKB: 20.5,
    medianSizeKB: 15.0,
    p90SizeKB: 40.0,
    p95SizeKB: 45.0,
    p99SizeKB: 50.0,
    largest: [{ file: 'big.js', sizeKB: 50.0 }],
    outliers: [{ file: 'big.js', sizeKB: 50.0, zScore: 2.5 }],
    byExtension: [{ ext: '.js', count: 3, totalKB: 80.0, avgKB: 26.67 }],
  };
  const result = formatFileSizeReport(analysis);
  assert.ok(result.includes('## File Size Analysis'));
  assert.ok(result.includes('| Total files | 5 |'));
  assert.ok(result.includes('### Largest Files'));
  assert.ok(result.includes('`big.js`'));
  assert.ok(result.includes('### Size Outliers'));
  assert.ok(result.includes('z=2.5'));
  assert.ok(result.includes('### By Extension'));
  assert.ok(result.includes('.js'));
});

test('F41: formatFileSizeReport — no outliers section when empty', () => {
  const analysis = {
    totalFiles: 2,
    totalSizeKB: 10,
    avgSizeKB: 5,
    medianSizeKB: 5,
    p90SizeKB: 5,
    p95SizeKB: 5,
    p99SizeKB: 5,
    largest: [],
    outliers: [],
    byExtension: [],
  };
  const result = formatFileSizeReport(analysis);
  assert.ok(!result.includes('Size Outliers'));
});

// ─── formatNamingReport ───────────────────────────

test('F41: formatNamingReport — empty analysis', () => {
  const result = formatNamingReport({ totalFiles: 0 });
  assert.equal(result, 'No files found for naming convention analysis.');
});

test('F41: formatNamingReport — full report', () => {
  const analysis = {
    totalFiles: 10,
    dominant: 'camelCase',
    conventions: [
      { convention: 'camelCase', count: 7, percentage: 70.0, examples: ['foo.js', 'bar.js'] },
      { convention: 'snake_case', count: 3, percentage: 30.0, examples: ['baz_qux.js'] },
    ],
    inconsistencies: [{ file: 'baz_qux.js', convention: 'snake_case' }],
    byDirectory: [{ dir: 'src', convention: 'camelCase', count: 5 }],
  };
  const result = formatNamingReport(analysis);
  assert.ok(result.includes('## Naming Convention Analysis'));
  assert.ok(result.includes('`camelCase`'));
  assert.ok(result.includes('70%'));
  assert.ok(result.includes('`foo.js`'));
});

test('F41: formatNamingReport — no inconsistencies section when empty', () => {
  const analysis = {
    totalFiles: 5,
    dominant: 'PascalCase',
    conventions: [
      { convention: 'PascalCase', count: 5, percentage: 100, examples: ['Foo.js'] },
    ],
    inconsistencies: [],
    byDirectory: [{ dir: '.', convention: 'PascalCase', count: 5 }],
  };
  const result = formatNamingReport(analysis);
  assert.ok(!result.includes('Inconsistencies'));
});
