import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectEnvVars, formatEnvVarsReport } from '../context-forge.mjs';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const TEST_DIR = join(tmpdir(), 'cf-f29-test-' + Date.now());

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

test('F29: detectEnvVars finds process.env in JS', async () => {
  await setup({
    'app.js': `
const port = process.env.PORT;
const key = process.env.API_KEY;
const secret = process.env['JWT_SECRET'];
`,
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 3);
    const names = vars.map(v => v.name);
    assert.ok(names.includes('PORT'));
    assert.ok(names.includes('API_KEY'));
    assert.ok(names.includes('JWT_SECRET'));
  } finally { await cleanup(); }
});

test('F29: finds env vars in Python files', async () => {
  await setup({
    'app.py': `
import os
db = os.environ.get('DATABASE_URL')
key = os.getenv('SECRET_KEY')
host = os.environ['REDIS_HOST']
`,
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 3);
    const names = vars.map(v => v.name);
    assert.ok(names.includes('DATABASE_URL'));
    assert.ok(names.includes('SECRET_KEY'));
    assert.ok(names.includes('REDIS_HOST'));
  } finally { await cleanup(); }
});

test('F29: finds env vars in Go files', async () => {
  await setup({
    'main.go': `
package main
import "os"
func main() {
  port := os.Getenv("SERVER_PORT")
}
`,
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 1);
    assert.equal(vars[0].name, 'SERVER_PORT');
    assert.equal(vars[0].source, 'go');
  } finally { await cleanup(); }
});

test('F29: finds env vars in Rust files', async () => {
  await setup({
    'main.rs': `
fn main() {
  let key = std::env::var("OPENAI_API_KEY").unwrap();
  let url = env::var("DATABASE_URL").unwrap();
}
`,
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 2);
    const names = vars.map(v => v.name);
    assert.ok(names.includes('OPENAI_API_KEY'));
    assert.ok(names.includes('DATABASE_URL'));
  } finally { await cleanup(); }
});

test('F29: detects .env files', async () => {
  await setup({
    '.env': `
PORT=3000
DATABASE_URL=postgres://localhost
REDIS_URL=redis://localhost:6379
`,
    'app.js': 'const p = process.env.PORT;',
  });
  try {
    const { vars, envFiles } = await detectEnvVars(TEST_DIR);
    assert.ok(envFiles.includes('.env'));
    // PORT should be found (from .env, first encountered)
    assert.ok(vars.some(v => v.name === 'PORT'));
    assert.ok(vars.some(v => v.name === 'DATABASE_URL'));
    assert.ok(vars.some(v => v.name === 'REDIS_URL'));
  } finally { await cleanup(); }
});

test('F29: deduplicates env vars (first occurrence wins)', async () => {
  await setup({
    'a.js': 'const x = process.env.SHARED_VAR;',
    'b.js': 'const y = process.env.SHARED_VAR;',
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    const shared = vars.filter(v => v.name === 'SHARED_VAR');
    assert.equal(shared.length, 1);
  } finally { await cleanup(); }
});

test('F29: skips node_modules and .git', async () => {
  await setup({
    'real.js': 'const x = process.env.REAL_VAR;',
    'node_modules/lib.js': 'const y = process.env.FAKE_VAR;',
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 1);
    assert.equal(vars[0].name, 'REAL_VAR');
  } finally { await cleanup(); }
});

test('F29: handles empty project', async () => {
  await setup({ 'empty.js': 'const x = 1;\n' });
  try {
    const { vars, envFiles } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 0);
    assert.equal(envFiles.length, 0);
  } finally { await cleanup(); }
});

test('F29: respects maxDepth', async () => {
  await setup({
    'top.js': 'const a = process.env.TOP_VAR;',
    'deep/nested/file.js': 'const b = process.env.DEEP_VAR;',
  });
  try {
    const { vars: shallow } = await detectEnvVars(TEST_DIR, 0);
    const { vars: deep } = await detectEnvVars(TEST_DIR, 3);
    assert.ok(shallow.length < deep.length, `shallow=${shallow.length} deep=${deep.length}`);
  } finally { await cleanup(); }
});

test('F29: sorts vars alphabetically', async () => {
  await setup({
    'app.js': `
const z = process.env.ZEBRA;
const a = process.env.APPLE;
const m = process.env.MANGO;
`,
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars[0].name, 'APPLE');
    assert.equal(vars[1].name, 'MANGO');
    assert.equal(vars[2].name, 'ZEBRA');
  } finally { await cleanup(); }
});

test('F29: formatEnvVarsReport produces valid markdown', () => {
  const data = {
    vars: [
      { name: 'PORT', source: 'javascript', file: 'app.js', line: 5 },
      { name: 'API_KEY', source: 'dotenv', file: '.env' },
    ],
    envFiles: ['.env'],
  };
  const report = formatEnvVarsReport(data);
  assert.ok(report.includes('### Environment Variables (2 found)'));
  assert.ok(report.includes('**Dotenv files found:**'));
  assert.ok(report.includes('`.env`'));
  assert.ok(report.includes('| Variable | Source | File |'));
  assert.ok(report.includes('`PORT`'));
  assert.ok(report.includes('`API_KEY`'));
});

test('F29: formatEnvVarsReport handles empty', () => {
  const report = formatEnvVarsReport({ vars: [], envFiles: [] });
  assert.ok(report.includes('No environment variables'));
});

test('F29: ignores lowercase env var patterns', async () => {
  await setup({
    'app.js': `
const x = process.env.debug;  // lowercase, should be ignored
const y = process.env.VALID_VAR;
`,
  });
  try {
    const { vars } = await detectEnvVars(TEST_DIR);
    assert.equal(vars.length, 1);
    assert.equal(vars[0].name, 'VALID_VAR');
  } finally { await cleanup(); }
});
