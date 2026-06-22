import { test } from 'node:test';
import assert from 'node:assert/strict';
import { computeProjectStats, formatProjectStats } from '../context-forge.mjs';

test('F23: computeProjectStats — basic stats', () => {
  const info = {
    dependencies: { react: '^18.0.0', express: '^4.0.0' },
    devDependencies: { jest: '^29.0.0' },
    scripts: { test: 'jest', build: 'vite build' },
    entryPoints: ['index.js'],
    configFiles: ['tsconfig.json', '.eslintrc'],
  };
  const langs = new Map([['JavaScript', 20], ['TypeScript', 5]]);
  const importData = {
    imports: new Map([
      ['src/app.js', ['react']],
      ['test/app.test.js', ['jest']],
    ]),
    allImports: ['react', 'jest'],
  };
  const stats = computeProjectStats(info, langs, importData, [{ name: 'foo' }], { tsconfig: {} });

  assert.equal(stats.fileStats.total, 25);
  assert.equal(stats.depStats.production, 2);
  assert.equal(stats.depStats.dev, 1);
  assert.equal(stats.scriptCount, 2);
  assert.equal(stats.entryCount, 1);
  assert.equal(stats.apiSurfaceCount, 1);
});

test('F23: computeProjectStats — test-to-code ratio', () => {
  const info = { dependencies: {}, scripts: {}, entryPoints: [] };
  const langs = new Map([['JavaScript', 10]]);
  const importData = {
    imports: new Map([
      ['src/a.js', ['react']],
      ['src/b.js', ['react']],
      ['test/a.test.js', ['react']],
      ['test/b.test.js', ['react']],
      ['test/c.test.js', ['react']],
    ]),
    allImports: ['react'],
  };
  const stats = computeProjectStats(info, langs, importData, [], {});

  assert.equal(stats.fileStats.tests, 3);
  assert.equal(stats.fileStats.code, 7); // max(10-3, 1)
  assert.ok(stats.fileStats.testToCodeRatio > 0);
});

test('F23: computeProjectStats — maturity scoring', () => {
  const info = { configFiles: ['README.md', 'LICENSE', 'Dockerfile'] };
  const langs = new Map([['JavaScript', 5]]);
  const importData = {
    imports: new Map([['test/a.test.js', ['jest']]]),
    allImports: ['jest'],
  };
  const stats = computeProjectStats(info, langs, importData, [], {'.github/workflows': {ci: true}});

  assert.ok(stats.maturity.hasReadme);
  assert.ok(stats.maturity.hasLicense);
  assert.ok(stats.maturity.hasTests);
  assert.ok(stats.maturity.hasDocker);
  assert.ok(stats.maturity.hasCI);
  assert.equal(stats.maturity.score, 1);
  assert.equal(stats.maturity.grade, 'A');
});

test('F23: computeProjectStats — low maturity', () => {
  const info = { configFiles: [] };
  const langs = new Map([['JavaScript', 5]]);
  const importData = { imports: new Map(), allImports: [] };
  const stats = computeProjectStats(info, langs, importData, [], {});

  assert.equal(stats.maturity.hasReadme, false);
  assert.equal(stats.maturity.hasTests, false);
  assert.ok(stats.maturity.score < 0.4);
  assert.equal(stats.maturity.grade, 'D');
});

test('F23: computeProjectStats — top languages', () => {
  const info = { dependencies: {}, scripts: {}, entryPoints: [] };
  const langs = new Map([['JavaScript', 30], ['TypeScript', 15], ['Python', 5]]);
  const importData = { imports: new Map(), allImports: [] };
  const stats = computeProjectStats(info, langs, importData, [], {});

  assert.equal(stats.topLanguages[0].language, 'JavaScript');
  assert.equal(stats.topLanguages[0].files, 30);
  assert.equal(stats.topLanguages[0].pct, 60); // 30/50
});

test('F23: computeProjectStats — dep-to-file ratio', () => {
  const info = { dependencies: { a: '1', b: '2', c: '3', d: '4', e: '5' } };
  const langs = new Map([['JavaScript', 10]]);
  const importData = { imports: new Map(), allImports: [] };
  const stats = computeProjectStats(info, langs, importData, [], {});

  assert.equal(stats.depStats.production, 5);
  assert.equal(stats.depStats.depToFileRatio, 0.5); // 5/10
});

test('F23: formatProjectStats — valid markdown', () => {
  const info = { dependencies: { react: '^18.0.0' }, scripts: { test: 'jest' }, entryPoints: ['index.js'], configFiles: ['README.md'] };
  const langs = new Map([['JavaScript', 10]]);
  const importData = {
    imports: new Map([['test/a.test.js', ['jest']]]),
    allImports: ['jest'],
  };
  const stats = computeProjectStats(info, langs, importData, [], {});
  const md = formatProjectStats(stats);

  assert.ok(md.includes('# Project Statistics'));
  assert.ok(md.includes('## Files'));
  assert.ok(md.includes('## Dependencies'));
  assert.ok(md.includes('## Maturity'));
  assert.ok(md.includes('## Top Languages'));
});

test('F23: formatProjectStats — maturity emoji rendering', () => {
  const info = { configFiles: ['README.md', 'LICENSE'] };
  const langs = new Map([['JavaScript', 5]]);
  const importData = { imports: new Map(), allImports: [] };
  const stats = computeProjectStats(info, langs, importData, [], {});
  const md = formatProjectStats(stats);

  assert.ok(md.includes('✅') || md.includes('❌'));
});

test('F23: computeProjectStats — config coverage', () => {
  const info = { configFiles: ['tsconfig.json', '.eslintrc', 'Dockerfile'] };
  const langs = new Map([['JavaScript', 5]]);
  const importData = { imports: new Map(), allImports: [] };
  const configData = { 'tsconfig.json': {}, 'Dockerfile': {} };
  const stats = computeProjectStats(info, langs, importData, [], configData);

  assert.ok(stats.configCoverage > 0);
});

test('F23: computeProjectStats — empty project', () => {
  const info = {};
  const langs = new Map();
  const importData = { imports: new Map(), allImports: [] };
  const stats = computeProjectStats(info, langs, importData, [], {});

  assert.equal(stats.fileStats.total, 0);
  assert.equal(stats.depStats.total, 0);
  assert.equal(stats.scriptCount, 0);
});
