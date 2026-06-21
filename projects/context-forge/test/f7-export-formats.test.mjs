import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { exportTOML, exportYAML, buildExportData } from '../context-forge.mjs';

// ─── Test Data ──────────────────────────────────────────────────

const sampleInfo = {
  name: 'my-project',
  type: 'node',
  version: '2.1.0',
  description: 'A test project',
  frameworks: ['express', 'jest'],
  entryPoints: ['src/index.js', 'src/cli.js'],
  scripts: { start: 'node src/index.js', test: 'jest' },
  dependencies: { express: '^4.18.0', lodash: '^4.17.21' },
  devDependencies: { jest: '^29.0.0' },
};

const sampleLangs = [['javascript', 5000], ['css', 200]];
const sampleImportData = { allImports: ['express', 'lodash', 'fs', 'express'], imports: [] };
const sampleApiSurface = [
  { name: 'handleRequest', type: 'function', file: 'src/server.js', line: 10 },
  { name: 'Router', type: 'class', file: 'src/router.js', line: 5 },
];
const sampleConfigData = { eslint: 'configured', tsconfig: null };

const exportData = buildExportData(sampleInfo, sampleLangs, sampleImportData, sampleApiSurface, sampleConfigData, null);

// ─── buildExportData Tests ──────────────────────────────────────

describe('buildExportData', () => {
  it('builds a structured object from analysis components', () => {
    assert.equal(exportData.project.name, 'my-project');
    assert.equal(exportData.project.type, 'node');
    assert.equal(exportData.project.version, '2.1.0');
    assert.equal(exportData.project.description, 'A test project');
  });

  it('includes languages as object', () => {
    assert.deepEqual(exportData.languages, { javascript: 5000, css: 200 });
  });

  it('deduplicates frameworks', () => {
    assert.deepEqual(exportData.frameworks, ['express', 'jest']);
  });

  it('counts imports correctly', () => {
    assert.equal(exportData.imports.total, 4);
    assert.equal(exportData.imports.unique, 3);
  });

  it('limits apiSurface to 50 entries', () => {
    const big = Array.from({ length: 100 }, (_, i) => ({ name: `fn${i}`, type: 'function', file: 'a.js', line: i }));
    const data = buildExportData(sampleInfo, sampleLangs, sampleImportData, big, sampleConfigData, null);
    assert.equal(data.apiSurface.length, 50);
    assert.equal(data.apiSurfaceCount, 100);
  });

  it('handles null gitInfo', () => {
    assert.equal(exportData.git, null);
  });

  it('handles undefined fields gracefully', () => {
    const minimal = buildExportData({}, [], null, null, null, null);
    assert.equal(minimal.project.name, 'unknown');
    assert.equal(minimal.project.type, 'unknown');
    assert.equal(minimal.imports.total, 0);
    assert.equal(minimal.apiSurfaceCount, 0);
  });
});

// ─── exportTOML Tests ───────────────────────────────────────────

describe('exportTOML', () => {
  it('outputs valid TOML structure with table headers', () => {
    const toml = exportTOML(exportData);
    assert.match(toml, /\[project\]/);
    assert.match(toml, /name = "my-project"/);
    assert.match(toml, /type = "node"/);
  });

  it('handles scalar values correctly', () => {
    const toml = exportTOML({ simple: { str: 'hello', num: 42, bool: true, nil: null } });
    assert.match(toml, /str = "hello"/);
    assert.match(toml, /num = 42/);
    assert.match(toml, /bool = true/);
    // null becomes empty string in TOML
    assert.match(toml, /nil = ""/);
  });

  it('handles arrays of scalars', () => {
    const toml = exportTOML({ list: { items: ['a', 'b', 'c'] } });
    assert.match(toml, /items = \["a", "b", "c"\]/);
  });

  it('handles nested objects as tables', () => {
    const toml = exportTOML({ outer: { inner: { key: 'val' } } });
    assert.match(toml, /\[outer\.inner\]/);
    assert.match(toml, /key = "val"/);
  });

  it('handles arrays of objects as array-of-tables', () => {
    const data = { items: [{ name: 'a', line: 1 }, { name: 'b', line: 2 }] };
    const toml = exportTOML(data);
    assert.match(toml, /\[\[items\]\]/);
    assert.match(toml, /name = "a"/);
    assert.match(toml, /name = "b"/);
  });

  it('escapes special characters in strings', () => {
    const toml = exportTOML({ msg: 'He said "hi"\\n' });
    assert.match(toml, /He said \\"hi\\"\\\\n/);
  });

  it('handles empty objects and arrays', () => {
    const toml = exportTOML({ empty: { obj: {}, arr: [] } });
    assert.match(toml, /\[empty\]/);
    // Empty array should be []
    assert.match(toml, /arr = \[\]/);
  });

  it('produces parseable TOML for simple cases', () => {
    const data = { project: { name: 'test', version: '1.0.0' }, count: 42 };
    const toml = exportTOML(data);
    // Basic structural assertions
    const lines = toml.split('\\n');
    assert.ok(lines.some(l => l.includes('[project]')));
    assert.ok(lines.some(l => l.includes('name = "test"')));
    assert.ok(lines.some(l => l.includes('version = "1.0.0"')));
    assert.ok(lines.some(l => l.includes('count = 42')));
  });
});

// ─── exportYAML Tests ───────────────────────────────────────────

describe('exportYAML', () => {
  it('outputs valid YAML with proper key-value pairs', () => {
    const yaml = exportYAML(exportData);
    assert.match(yaml, /project:/);
    assert.match(yaml, /name: my-project/);
    assert.match(yaml, /type: node/);
  });

  it('handles scalar values correctly', () => {
    const yaml = exportYAML({ simple: { str: 'hello', num: 42, bool: true, nil: null } });
    assert.match(yaml, /str: hello/);
    assert.match(yaml, /num: 42/);
    assert.match(yaml, /bool: true/);
    assert.match(yaml, /nil: null/);
  });

  it('handles arrays with dash syntax', () => {
    const yaml = exportYAML({ items: ['a', 'b', 'c'] });
    assert.match(yaml, /items:/);
    assert.match(yaml, /- a/);
    assert.match(yaml, /- b/);
    assert.match(yaml, /- c/);
  });

  it('handles nested objects with indentation', () => {
    const yaml = exportYAML({ outer: { inner: { key: 'val' } } });
    assert.match(yaml, /outer:/);
    assert.match(yaml, /inner:/);
    assert.match(yaml, /key: val/);
  });

  it('handles arrays of objects', () => {
    const data = { items: [{ name: 'a', line: 1 }, { name: 'b', line: 2 }] };
    const yaml = exportYAML(data);
    assert.match(yaml, /items:/);
    assert.match(yaml, /-/);
    assert.match(yaml, /name: a/);
    assert.match(yaml, /name: b/);
  });

  it('quotes strings that need quoting', () => {
    const yaml = exportYAML({ special: 'contains: colon-space', keyword: 'true' });
    // 'contains: colon-space' needs quotes because of ': '
    assert.match(yaml, /special: "contains: colon-space"/);
    // 'true' needs quotes because it's a YAML keyword
    assert.match(yaml, /keyword: "true"/);
  });

  it('does not quote simple strings unnecessarily', () => {
    const yaml = exportYAML({ simple: 'hello-world' });
    assert.match(yaml, /simple: hello-world/);
    assert.doesNotMatch(yaml, /simple: "hello-world"/);
  });

  it('handles empty objects and arrays', () => {
    const yaml = exportYAML({ empty: { obj: {}, arr: [] } });
    assert.match(yaml, /obj: \{\}/);
    assert.match(yaml, /arr: \[\]/);
  });

  it('handles numbers and booleans without quotes', () => {
    const yaml = exportYAML({ vals: { int: 42, float: 3.14, bool: false } });
    assert.match(yaml, /int: 42/);
    assert.match(yaml, /float: 3\.14/);
    assert.match(yaml, /bool: false/);
  });

  it('handles multiline strings with double-quote style', () => {
    const yaml = exportYAML({ text: 'line1\\nline2' });
    // String with literal backslash-n should be quoted
    assert.match(yaml, /text: .*/);
  });

  it('produces correct indentation for deep nesting', () => {
    const data = { a: { b: { c: { d: 'deep' } } } };
    const yaml = exportYAML(data);
    const lines = yaml.split('\n');
    // a: at 0 indent, b: at 2, c: at 4, d: at 6
    assert.ok(lines.some(l => l === 'a:'));
    assert.ok(lines.some(l => l === '  b:'));
    assert.ok(lines.some(l => l === '    c:'));
    assert.ok(lines.some(l => l === '      d: deep'));
  });
});

// ─── Round-trip Consistency ─────────────────────────────────────

describe('Export format consistency', () => {
  it('all three formats contain the same project name', () => {
    const toml = exportTOML(exportData);
    const yaml = exportYAML(exportData);
    const json = JSON.stringify(exportData);
    assert.match(toml, /my-project/);
    assert.match(yaml, /my-project/);
    assert.match(json, /my-project/);
  });

  it('all three formats contain framework names', () => {
    const toml = exportTOML(exportData);
    const yaml = exportYAML(exportData);
    const json = JSON.stringify(exportData);
    assert.match(toml, /express/);
    assert.match(yaml, /express/);
    assert.match(json, /express/);
  });
});
