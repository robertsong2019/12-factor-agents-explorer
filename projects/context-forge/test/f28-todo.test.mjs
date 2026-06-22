import { test } from 'node:test';
import assert from 'node:assert/strict';
import { extractTODOComments, formatTODOReport } from '../context-forge.mjs';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const TEST_DIR = join(tmpdir(), 'cf-f28-test-' + Date.now());

async function setup(files) {
  await mkdir(TEST_DIR, { recursive: true });
  for (const [path, content] of Object.entries(files)) {
    const full = join(TEST_DIR, path);
    await mkdir(join(full, '..'), { recursive: true });
    await writeFile(full, content);
  }
}

async function cleanup() {
  await rm(TEST_DIR, { recursive: true, force: true });
}

test('F28: extractTODOComments finds TODO comments in JS files', async () => {
  await setup({
    'app.js': `
// TODO: implement caching
const x = 1;
// FIXME: this is broken
function foo() {
  // HACK: temporary workaround
}
`,
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 3);
    assert.equal(results[0].type, 'FIXME'); // high priority first
    assert.equal(results[1].type, 'HACK');
    assert.equal(results[2].type, 'TODO');
    assert.equal(results[0].file, 'app.js');
    assert.ok(results[0].line > 0);
    assert.ok(results[0].text.length > 0);
  } finally { await cleanup(); }
});

test('F28: finds BUG, XXX, NOTE comments', async () => {
  await setup({
    'main.py': `
# BUG: crashes on empty input
# XXX: needs review
# NOTE: this is intentional
x = 1
`,
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 3);
    const types = results.map(r => r.type);
    assert.ok(types.includes('BUG'));
    assert.ok(types.includes('XXX'));
    assert.ok(types.includes('NOTE'));
    // BUG should be first (critical priority)
    assert.equal(results[0].type, 'BUG');
  } finally { await cleanup(); }
});

test('F28: respects maxDepth parameter', async () => {
  await setup({
    'a.js': '// TODO: top level',
    'sub/b.js': '// TODO: nested',
    'sub/deep/c.js': '// TODO: deep',
  });
  try {
    const depth1 = await extractTODOComments(TEST_DIR, 1);
    const depth2 = await extractTODOComments(TEST_DIR, 2);
    assert.ok(depth1.length < depth2.length, `depth1=${depth1.length} should be < depth2=${depth2.length}`);
  } finally { await cleanup(); }
});

test('F28: skips node_modules and .git', async () => {
  await setup({
    'real.js': '// TODO: real file',
    'node_modules/fake.js': '// TODO: should be ignored',
    '.git/config.js': '// TODO: ignored',
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 1);
    assert.equal(results[0].file, 'real.js');
  } finally { await cleanup(); }
});

test('F28: only scans known file extensions', async () => {
  await setup({
    'code.js': '// TODO: found me',
    'readme.md': '# TODO: should not find this',
    'data.json': '{"TODO": "not a comment"}',
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 1);
    assert.equal(results[0].file, 'code.js');
  } finally { await cleanup(); }
});

test('F28: handles empty project gracefully', async () => {
  await setup({ 'empty.js': 'const x = 1;\n' });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 0);
  } finally { await cleanup(); }
});

test('F28: sorts by priority then file then line', async () => {
  await setup({
    'a.js': `
// TODO: later
// FIXME: urgent
`,
    'b.js': `
// BUG: critical
// NOTE: info
`,
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 4);
    assert.equal(results[0].type, 'BUG');
    assert.equal(results[1].type, 'FIXME');
    assert.equal(results[2].type, 'TODO');
    assert.equal(results[3].type, 'NOTE');
  } finally { await cleanup(); }
});

test('F28: formatTODOReport produces markdown output', async () => {
  const todos = [
    { file: 'src/app.js', line: 10, type: 'FIXME', priority: 'high', text: 'fix this' },
    { file: 'src/lib.js', line: 5, type: 'TODO', priority: 'medium', text: 'add feature' },
    { file: 'src/util.js', line: 20, type: 'BUG', priority: 'critical', text: 'crashes' },
    { file: 'src/old.js', line: 1, type: 'NOTE', priority: 'low', text: 'legacy' },
  ];
  const report = formatTODOReport(todos);
  assert.ok(report.includes('### TODO/FIXME Report (4 items)'));
  assert.ok(report.includes('🐛 BUG'));
  assert.ok(report.includes('🔧 FIXME'));
  assert.ok(report.includes('📝 TODO'));
  assert.ok(report.includes('💡 NOTE'));
  assert.ok(report.includes('`src/app.js:10`'));
  assert.ok(report.includes('fix this'));
});

test('F28: formatTODOReport handles empty list', () => {
  const report = formatTODOReport([]);
  assert.ok(report.includes('No TODO/FIXME'));
  assert.ok(report.includes('✅'));
});

test('F28: formatTODOReport truncates long text', () => {
  const longText = 'A'.repeat(120);
  const todos = [
    { file: 'a.js', line: 1, type: 'TODO', priority: 'medium', text: longText },
  ];
  const report = formatTODOReport(todos);
  assert.ok(report.includes('...'));
  // Should be truncated to 80 chars
  assert.ok(!report.includes(longText));
});

test('F28: detects TODOs in multiple language files', async () => {
  await setup({
    'app.py': '# TODO: python todo',
    'main.go': '// TODO: go todo',
    'lib.rs': '// TODO: rust todo',
    'server.ts': '// TODO: ts todo',
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 4);
    const files = results.map(r => r.file).sort();
    assert.deepEqual(files, ['app.py', 'lib.rs', 'main.go', 'server.ts']);
  } finally { await cleanup(); }
});

test('F28: respects gitignore patterns', async () => {
  await setup({
    'keep.js': '// TODO: keep this',
    'dist/bundle.js': '// TODO: ignore this',
  });
  try {
    const results = await extractTODOComments(TEST_DIR, 3, 0, ['dist']);
    assert.equal(results.length, 1);
    assert.equal(results[0].file, 'keep.js');
  } finally { await cleanup(); }
});

test('F28: one match per line (no double counting)', async () => {
  await setup({
    'a.js': '// TODO: FIXME: should count once',
  });
  try {
    const results = await extractTODOComments(TEST_DIR);
    assert.equal(results.length, 1);
    // TODO pattern is checked first, so it wins
    assert.ok(['TODO', 'FIXME'].includes(results[0].type));
  } finally { await cleanup(); }
});
