import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const ROOT = path.resolve(import.meta.dirname, '..');
const BIN = path.join(ROOT, 'bin', 'mcpt.js');

function tmp() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'mcpt-gen-'));
}

function mcpt(args, cwd) {
  return spawnSync(process.execPath, [BIN, ...args], { encoding: 'utf8', cwd, timeout: 30000 });
}

const VALID = {
  name: 'gen-server',
  version: '2.1.0',
  transport: 'stdio',
  tools: [
    { name: 'echo', description: '回显', inputSchema: { type: 'object', properties: { text: { type: 'string' } } } },
    { name: 'fetch_url', description: '抓取' },
  ],
  resources: [{ uri: 'file:///logs/app.log', name: '应用日志' }],
  prompts: [{ name: 'summarize', description: '总结' }],
};

test('generate: creates dist/index.ts with declared tools/resources/prompts', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.json'), JSON.stringify(VALID));
  const r = mcpt(['generate'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);

  const out = fs.readFileSync(path.join(dir, 'dist', 'index.ts'), 'utf8');
  assert.match(out, /name: 'gen-server'/);
  assert.match(out, /'2\.1\.0'/);
  assert.match(out, /"echo"/);
  assert.match(out, /fetch_url/);
  assert.match(out, /file:\/\/\/logs\/app\.log/);
  assert.match(out, /summarize/);
  // handler wiring present
  assert.match(out, /ListToolsRequestSchema/);
  assert.match(out, /CallToolRequestSchema/);
  assert.match(out, /StdioServerTransport/);
});

test('generate: defaults to mcp-server.json (same file init writes)', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.json'), JSON.stringify(VALID));
  const r = mcpt(['generate'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(fs.existsSync(path.join(dir, 'dist', 'index.ts')));
});

test('generate: yaml config works via -f', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'cfg.yaml'), [
    'name: y-server',
    'version: 1.0.0',
    'transport: stdio',
    'tools:',
    '  - name: ping',
    'resources: []',
    'prompts: []',
    '',
  ].join('\n'));
  const r = mcpt(['generate', '-f', 'cfg.yaml'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = fs.readFileSync(path.join(dir, 'dist', 'index.ts'), 'utf8');
  assert.match(out, /ping/);
});

test('generate: missing config exits 1', () => {
  const r = mcpt(['generate'], tmp());
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('不存在'));
});

test('generate: invalid config refuses generation (validation gate)', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.json'), JSON.stringify({ name: 'x', transport: 'grpc' }));
  const r = mcpt(['generate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('拒绝生成'), r.stdout);
  assert.ok(!fs.existsSync(path.join(dir, 'dist')), 'must not write output on invalid config');
});

test('generate: refuses to overwrite existing output', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.json'), JSON.stringify(VALID));
  assert.equal(mcpt(['generate'], dir).status, 0);
  const r = mcpt(['generate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('已存在'));
});

test('generate: -o custom output dir', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.json'), JSON.stringify(VALID));
  const r = mcpt(['generate', '-o', 'build/out'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(fs.existsSync(path.join(dir, 'build', 'out', 'index.ts')));
});

test('generate: sse transport honest unsupported exit 1', () => {
  const dir = tmp();
  const cfg = { ...VALID, transport: 'sse' };
  fs.writeFileSync(path.join(dir, 'mcp-server.json'), JSON.stringify(cfg));
  const r = mcpt(['generate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('尚未支持'));
  assert.ok(!fs.existsSync(path.join(dir, 'dist')));
});

test('generate: init -> generate pipeline works end to end', () => {
  const dir = tmp();
  assert.equal(mcpt(['init', 'pipe-proj', '-e'], dir).status, 0);
  const proj = path.join(dir, 'pipe-proj');
  // init 产出的空 tools 配置合法，generate 应能直接跑
  const r = mcpt(['generate'], proj);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = fs.readFileSync(path.join(proj, 'dist', 'index.ts'), 'utf8');
  assert.match(out, /pipe-proj/);
  assert.match(out, /tools: \[\]/);
});
