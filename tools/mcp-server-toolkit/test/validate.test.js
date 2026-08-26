import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const ROOT = path.resolve(import.meta.dirname, '..');
const BIN = path.join(ROOT, 'bin', 'mcpt.js');

function tmp() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'mcpt-val-'));
}

function mcpt(args, cwd) {
  return spawnSync(process.execPath, [BIN, ...args], { encoding: 'utf8', cwd, timeout: 30000 });
}

function write(dir, file, obj) {
  const p = path.join(dir, file);
  fs.writeFileSync(p, typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2));
  return p;
}

const VALID = {
  name: 'demo-server',
  version: '1.0.0',
  transport: 'stdio',
  tools: [{ name: 'echo', description: 'echo text', inputSchema: { type: 'object', properties: { text: { type: 'string' } } } }],
  resources: [{ uri: 'file:///data', name: 'data' }],
  prompts: [{ name: 'greet' }],
};

test('validate: valid config exits 0 with summary', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', VALID);
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(r.stdout.includes('配置有效'));
  assert.ok(r.stdout.includes('tools:     1'));
});

test('validate: missing file exits 1', () => {
  const r = mcpt(['validate'], tmp());
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('不存在'));
});

test('validate: malformed JSON exits 1 with parse error', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', '{ broken');
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('JSON 解析失败'));
});

test('validate: missing name + bad transport + bad version all reported', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', { version: 'one', transport: 'grpc' });
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('name'), 'should report missing name');
  assert.ok(r.stdout.includes('grpc'));
  assert.ok(r.stdout.includes('version'), 'should report bad version');
});

test('validate: duplicate tool names detected with first index', () => {
  const dir = tmp();
  const cfg = { ...VALID, tools: [{ name: 'echo' }, { name: 'echo' }, { name: 'echo' }] };
  write(dir, 'mcp-server.json', cfg);
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('重复的工具名'), r.stdout);
  assert.ok(r.stdout.includes('tools[0]'), 'should cite first occurrence index');
});

test('validate: inputSchema.type must be object', () => {
  const dir = tmp();
  const cfg = { ...VALID, tools: [{ name: 't', inputSchema: { type: 'string' } }] };
  write(dir, 'mcp-server.json', cfg);
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('inputSchema'), r.stdout);
});

test('validate: resource uri must be scheme or absolute path', () => {
  const dir = tmp();
  const cfg = { ...VALID, resources: [{ uri: 'not-a-uri' }] };
  write(dir, 'mcp-server.json', cfg);
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('无效 URI'));
});

test('validate: yaml config supported', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.yaml'), [
    'name: yaml-server',
    'version: 1.2.3',
    'transport: sse',
    'tools:',
    '  - name: fetch',
    '    description: fetch url',
    'resources: []',
    'prompts: []',
    '',
  ].join('\n'));
  const r = mcpt(['validate', 'mcp-server.yaml'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(r.stdout.includes('sse'));
});

test('validate: broken yaml exits 1', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, 'mcp-server.yaml'), 'name: [unclosed');
  const r = mcpt(['validate', 'mcp-server.yaml'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('YAML 解析失败'));
});

test('validate: --schema custom schema failure exits 1', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', { ...VALID, transport: 'sse' });
  const schema = write(dir, 'schema.json', {
    type: 'object',
    properties: { transport: { enum: ['stdio'] } },
    required: ['transport'],
  });
  const r = mcpt(['validate', '--schema', 'schema.json'], dir);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.ok(r.stdout.includes('schema'));
});

test('validate: --schema pass exits 0', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', VALID);
  write(dir, 'schema.json', { type: 'object', required: ['name', 'transport'] });
  const r = mcpt(['validate', '-s', 'schema.json'], dir);
  assert.equal(r.status, 0, r.stdout + r.stderr);
});

test('validate: --schema missing file exits 1', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', VALID);
  const r = mcpt(['validate', '-s', 'nope.json'], dir);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('schema 文件不存在'));
});

test('validate: multiple errors counted', () => {
  const dir = tmp();
  write(dir, 'mcp-server.json', {});
  const r = mcpt(['validate'], dir);
  assert.equal(r.status, 1);
  assert.match(r.stdout, /3 处错误/); // name + version + transport
});
