/**
 * CLI end-to-end tests for `act` — hermetic via HOME override
 * (storage writes to $HOME/.config/agent-cost-tracker, os.homedir() reads $HOME).
 */

const test = require('node:test');
const assert = require('node:assert');
const { spawnSync } = require('node:child_process');
const { mkdtempSync, readFileSync, existsSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');

const ROOT = join(__dirname, '..');
const BIN = join(ROOT, 'bin', 'act.js');

const HOME = mkdtempSync(join(tmpdir(), 'act-cli-'));

function act(...args) {
  const res = spawnSync(process.execPath, [BIN, ...args], {
    env: { ...process.env, HOME, NO_COLOR: '1', CI: '1' },
    encoding: 'utf-8',
    timeout: 30000,
  });
  return { code: res.status, out: strip(res.stdout), err: strip(res.stderr) };
}

function strip(s) {
  return (s || '').replace(/\x1b\[[0-9;]*m/g, '');
}

function exportJson() {
  const file = join(HOME, 'export.json');
  if (existsSync(file)) rmSync(file);  // export 早退不写文件，避免读到旧数据
  const r = act('export', '-p', 'all', '-f', 'json', '-o', file);
  assert.strictEqual(r.code, 0, r.err);
  if (!existsSync(file)) return [];  // "没有数据可导出" 分支
  const parsed = JSON.parse(readFileSync(file, 'utf-8'));
  return Array.isArray(parsed) ? parsed : parsed.data;
}

test('CLI entry parses and shows help', () => {
  const r = act('--help');
  assert.strictEqual(r.code, 0, r.err);
  for (const cmd of ['log', 'stats', 'trend', 'config', 'export', 'budget', 'estimate', 'clear']) {
    assert.ok(r.out.includes(cmd), `help must list ${cmd}`);
  }
});

test('estimate computes cost from token prices (gpt-4)', () => {
  // 1000 in / 500 out @ 30/60 per 1M → 0.03 + 0.03 = 0.06
  const r = act('estimate', '-m', 'gpt-4', '-p', '1000', '-c', '500');
  assert.strictEqual(r.code, 0, r.err);
  assert.ok(r.out.includes('0.0600'), `expected total 0.0600 in: ${r.out}`);
});

test('estimate --total splits 1:2 (input:output)', () => {
  // 3000 total → 1000 in / 2000 out @ 30/60 → 0.03 + 0.12 = 0.15
  const r = act('estimate', '-m', 'gpt-4', '-t', '3000');
  assert.strictEqual(r.code, 0, r.err);
  assert.ok(r.out.includes('0.1500'), `expected total 0.1500 in: ${r.out}`);
});

test('estimate with rate multiplies cost', () => {
  // claude-3-haiku 0.25/1.25: 1000/1000 → 0.00025+0.00125=0.0015 ×10 = 0.015
  const r = act('estimate', '-m', 'claude-3-haiku', '-p', '1000', '-c', '1000', '-r', '10');
  assert.strictEqual(r.code, 0, r.err);
  assert.ok(r.out.includes('0.0150'), `expected total 0.0150 in: ${r.out}`);
});

test('estimate unknown model exits 1', () => {
  const r = act('estimate', '-m', 'no-such-model', '-p', '1000');
  assert.strictEqual(r.code, 1);
  assert.ok(r.err.includes('未知模型') || r.out.includes('未知模型'));
});

test('log → export roundtrip works end to end', () => {
  const r = act('log', '-m', 'gpt-4', '-p', '2000', '-c', '1000', '-s', 'e2e', '-n', 'cli test');
  assert.strictEqual(r.code, 0, r.err);
  const data = exportJson();
  assert.ok(Array.isArray(data) && data.length >= 1, `expected >=1 entry, got ${JSON.stringify(data).slice(0, 200)}`);
  const entry = data.find(e => e.session === 'e2e');
  assert.ok(entry, 'session e2e entry missing');
  assert.strictEqual(entry.model, 'gpt-4');
  assert.strictEqual(entry.promptTokens, 2000);
});

test('clear without -y refuses and keeps data', () => {
  act('log', '-m', 'glm-4', '--cost', '0.01');
  const r = act('clear');
  assert.strictEqual(r.code, 1);
  assert.ok(exportJson().length >= 1, 'data must survive refused clear');
});

test('clear -y wipes all logs', () => {
  const r = act('clear', '-y');
  assert.strictEqual(r.code, 0, r.err);
  assert.strictEqual(exportJson().length, 0);
});

test('clear --before removes only older entries and reports count', () => {
  act('log', '-m', 'glm-4', '--cost', '0.02');
  const r = act('clear', '--before', '2030-01-01', '-y');
  assert.strictEqual(r.code, 0, r.err);
  assert.ok(/已删除.*1 条/.test(r.out), `expected '已删除 ... 1 条' in: ${r.out}`);
  assert.strictEqual(exportJson().length, 0);
});

test('estimate writes nothing to logs', () => {
  const before = exportJson().length;
  act('estimate', '-m', 'glm-4', '-t', '1000');
  assert.strictEqual(exportJson().length, before);
});

test('storage stays under overridden HOME', () => {
  const confFile = join(HOME, '.config', 'config.json');
  assert.ok(existsSync(confFile), 'conf file must live under test HOME');
});
