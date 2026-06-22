import { test } from 'node:test';
import assert from 'node:assert/strict';
import { findDuplicateImports, formatDuplicateReport } from '../context-forge.mjs';

test('F22: findDuplicateImports — basic shared import detection', () => {
  const importData = {
    imports: new Map([
      ['src/a.js', ['react', 'lodash']],
      ['src/b.js', ['react', 'axios']],
      ['src/c.js', ['lodash']],
    ]),
    allImports: ['react', 'lodash', 'axios'],
  };
  const result = findDuplicateImports(importData);

  // 'react' is used by 2 files, 'lodash' by 2 files
  assert.equal(result.stats.sharedCount, 2);
  assert.equal(result.sharedImports[0].fileCount, 2);
});

test('F22: findDuplicateImports — finds files with identical import sets', () => {
  const importData = {
    imports: new Map([
      ['src/a.js', ['react', 'lodash']],
      ['src/b.js', ['react', 'lodash']], // identical to a.js
      ['src/c.js', ['react']],           // different
    ]),
    allImports: ['react', 'lodash'],
  };
  const result = findDuplicateImports(importData);

  assert.ok(result.duplicateSignatures.length >= 1);
  const group = result.duplicateSignatures[0];
  assert.equal(group.files.length, 2);
  assert.ok(group.files.includes('src/a.js'));
  assert.ok(group.files.includes('src/b.js'));
});

test('F22: findDuplicateImports — shared import ranking', () => {
  const importData = {
    imports: new Map([
      ['a.js', ['shared', 'unique1']],
      ['b.js', ['shared', 'unique2']],
      ['c.js', ['shared', 'unique3']],
      ['d.js', ['other']],
    ]),
    allImports: ['shared', 'unique1', 'unique2', 'unique3', 'other'],
  };
  const result = findDuplicateImports(importData);

  assert.equal(result.sharedImports[0].package, 'shared');
  assert.equal(result.sharedImports[0].fileCount, 3);
});

test('F22: findDuplicateImports — empty data', () => {
  const importData = { imports: new Map(), allImports: [] };
  const result = findDuplicateImports(importData);

  assert.equal(result.stats.totalTracked, 0);
  assert.equal(result.stats.sharedCount, 0);
  assert.equal(result.stats.duplicateGroups, 0);
});

test('F22: findDuplicateImports — max usage tracking', () => {
  const importData = {
    imports: new Map([
      ['a.js', ['popular']],
      ['b.js', ['popular']],
      ['c.js', ['popular']],
      ['d.js', ['popular']],
      ['e.js', ['rare']],
    ]),
    allImports: ['popular', 'rare'],
  };
  const result = findDuplicateImports(importData);

  assert.equal(result.stats.maxSharedUsage, 4);
});

test('F22: findDuplicateImports — no false positives for single-use', () => {
  const importData = {
    imports: new Map([
      ['a.js', ['unique-a']],
      ['b.js', ['unique-b']],
    ]),
    allImports: ['unique-a', 'unique-b'],
  };
  const result = findDuplicateImports(importData);

  assert.equal(result.stats.sharedCount, 0);
});

test('F22: formatDuplicateReport — valid markdown output', () => {
  const importData = {
    imports: new Map([
      ['src/a.js', ['react', 'lodash']],
      ['src/b.js', ['react']],
    ]),
    allImports: ['react', 'lodash'],
  };
  const result = findDuplicateImports(importData);
  const md = formatDuplicateReport(result);

  assert.ok(md.includes('# Import Analysis'));
  assert.ok(md.includes('Tracked Packages'));
  assert.ok(md.includes('Shared Packages'));
});

test('F22: formatDuplicateReport — empty results', () => {
  const importData = { imports: new Map(), allImports: [] };
  const result = findDuplicateImports(importData);
  const md = formatDuplicateReport(result);

  assert.ok(md.includes('# Import Analysis'));
  assert.ok(md.includes('| Tracked Packages | 0 |'));
});

test('F22: findDuplicateImports — files list in shared imports', () => {
  const importData = {
    imports: new Map([
      ['src/x.js', ['shared-lib']],
      ['src/y.js', ['shared-lib']],
      ['src/z.js', ['shared-lib']],
    ]),
    allImports: ['shared-lib'],
  };
  const result = findDuplicateImports(importData);

  assert.equal(result.sharedImports[0].files.length, 3);
  assert.ok(result.sharedImports[0].files.includes('src/x.js'));
  assert.ok(result.sharedImports[0].files.includes('src/y.js'));
  assert.ok(result.sharedImports[0].files.includes('src/z.js'));
});
