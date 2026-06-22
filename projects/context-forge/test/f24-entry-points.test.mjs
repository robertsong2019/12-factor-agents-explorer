import { test } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeEntryPoints, formatEntryPointAnalysis } from '../context-forge.mjs';

test('F24: analyzeEntryPoints — classifies entry point types', () => {
  const info = { entryPoints: ['bin/cli.js', 'src/server.js', 'index.js'] };
  const importData = { imports: new Map(), allImports: [] };
  const analysis = analyzeEntryPoints(info, importData, []);

  const types = analysis.map(a => a.type);
  assert.ok(types.includes('cli'));
  assert.ok(types.includes('server'));
  assert.ok(types.includes('library'));
});

test('F24: analyzeEntryPoints — finds importedBy', () => {
  const info = { entryPoints: ['src/utils.js'] };
  const importData = {
    imports: new Map([
      ['src/a.js', ['src/utils.js', 'react']],
      ['src/b.js', ['src/utils.js']],
    ]),
    allImports: ['react'],
  };
  const analysis = analyzeEntryPoints(info, importData, []);

  assert.equal(analysis[0].importedByCount, 2);
  assert.ok(analysis[0].importedBy.includes('src/a.js'));
  assert.ok(analysis[0].importedBy.includes('src/b.js'));
});

test('F24: analyzeEntryPoints — detects exports', () => {
  const info = { entryPoints: ['src/index.js'] };
  const importData = { imports: new Map(), allImports: [] };
  const apiSurface = [
    { name: 'foo', file: 'src/index.js' },
    { name: 'bar', file: 'src/index.js' },
    { name: 'baz', file: 'src/other.js' },
  ];
  const analysis = analyzeEntryPoints(info, importData, apiSurface);

  assert.equal(analysis[0].exportCount, 2);
  assert.ok(analysis[0].exports.includes('foo'));
  assert.ok(analysis[0].exports.includes('bar'));
  assert.ok(!analysis[0].exports.includes('baz'));
});

test('F24: analyzeEntryPoints — marks orphaned entry points', () => {
  const info = { entryPoints: ['src/orphan.js'] };
  const importData = { imports: new Map(), allImports: [] };
  const analysis = analyzeEntryPoints(info, importData, []);

  assert.ok(analysis[0].isOrphan);
});

test('F24: analyzeEntryPoints — non-orphaned with imports', () => {
  const info = { entryPoints: ['src/core.js'] };
  const importData = {
    imports: new Map([['src/app.js', ['src/core.js']]]),
    allImports: [],
  };
  const analysis = analyzeEntryPoints(info, importData, []);

  assert.ok(!analysis[0].isOrphan);
});

test('F24: analyzeEntryPoints — empty entry points', () => {
  const info = { entryPoints: [] };
  const importData = { imports: new Map(), allImports: [] };
  const analysis = analyzeEntryPoints(info, importData, []);

  assert.equal(analysis.length, 0);
});

test('F24: analyzeEntryPoints — normalizes paths', () => {
  const info = { entryPoints: ['./src/main.js'] };
  const importData = {
    imports: new Map([['src/app.js', ['src/main.js']]]),
    allImports: [],
  };
  const analysis = analyzeEntryPoints(info, importData, []);

  assert.ok(analysis[0].importedByCount > 0, 'Should match after normalization');
});

test('F24: formatEntryPointAnalysis — valid markdown', () => {
  const info = { entryPoints: ['index.js', 'bin/cli.js'] };
  const importData = {
    imports: new Map([['src/app.js', ['index.js']]]),
    allImports: [],
  };
  const apiSurface = [{ name: 'main', file: 'index.js' }];
  const analysis = analyzeEntryPoints(info, importData, apiSurface);
  const md = formatEntryPointAnalysis(analysis);

  assert.ok(md.includes('# Entry Point Analysis'));
  assert.ok(md.includes('## index.js'));
  assert.ok(md.includes('**Type:**'));
  assert.ok(md.includes('**Imported by:**'));
  assert.ok(md.includes('**Exports:**'));
});

test('F24: formatEntryPointAnalysis — orphan warning', () => {
  const info = { entryPoints: ['orphan.js'] };
  const importData = { imports: new Map(), allImports: [] };
  const analysis = analyzeEntryPoints(info, importData, []);
  const md = formatEntryPointAnalysis(analysis);

  assert.ok(md.includes('⚠️'));
  assert.ok(md.includes('Orphaned'));
});

test('F24: analyzeEntryPoints — multiple entry points', () => {
  const info = { entryPoints: ['bin/serve.js', 'bin/build.js', 'index.js', 'test/runner.js'] };
  const importData = { imports: new Map(), allImports: [] };
  const analysis = analyzeEntryPoints(info, importData, []);

  assert.equal(analysis.length, 4);
  const types = analysis.map(a => a.type);
  assert.equal(types[0], 'cli');
  assert.equal(types[1], 'cli');
  assert.equal(types[2], 'library');
  assert.equal(types[3], 'test');
});
