import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const ROOT = path.resolve(import.meta.dirname, '..');
const BIN = path.join(ROOT, 'bin', 'mcpt.js');

function tmp() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'mcpt-'));
}

function mcpt(args, cwd) {
  return spawnSync(process.execPath, [BIN, ...args], {
    encoding: 'utf8',
    cwd,
    timeout: 30000,
  });
}

test('help exits 0 and lists all five commands', () => {
  const r = mcpt(['--help']);
  assert.equal(r.status, 0, r.stderr);
  for (const cmd of ['init', 'validate', 'generate', 'test', 'serve']) {
    assert.ok(r.stdout.includes(cmd), `help should list ${cmd}`);
  }
});

test('version exits 0', () => {
  const r = mcpt(['--version']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /\d+\.\d+\.\d+/);
});

test('init creates full project structure', () => {
  const dir = tmp();
  const r = mcpt(['init', 'demo-server', '-d', 'A demo'], dir);
  assert.equal(r.status, 0, r.stderr);

  const p = path.join(dir, 'demo-server');
  for (const f of ['package.json', 'tsconfig.json', 'mcp-server.json', 'src/index.ts', 'README.md', '.gitignore']) {
    assert.ok(fs.existsSync(path.join(p, f)), `${f} should exist`);
  }
  for (const d of ['src', 'test', 'examples']) {
    assert.ok(fs.statSync(path.join(p, d)).isDirectory(), `dir ${d} should exist`);
  }

  const pkg = JSON.parse(fs.readFileSync(path.join(p, 'package.json'), 'utf8'));
  assert.equal(pkg.name, 'demo-server');
  assert.equal(pkg.type, 'module');
  assert.equal(pkg.description, 'A demo');
  assert.ok(pkg.bin['demo-server']);
  assert.ok(pkg.scripts.build && pkg.scripts.start);

  const cfg = JSON.parse(fs.readFileSync(path.join(p, 'mcp-server.json'), 'utf8'));
  assert.equal(cfg.name, 'demo-server');
  assert.equal(cfg.transport, 'stdio'); // CLI default
});

test('init emits a working test wiring in generated project (no dead jest)', () => {
  const dir = tmp();
  assert.equal(mcpt(['init', 'wired', '-e'], dir).status, 0);
  const p = path.join(dir, 'wired');

  const pkg = JSON.parse(fs.readFileSync(path.join(p, 'package.json'), 'utf8'));
  // 旧病：test:'jest' 无配置无 ts-jest、test/ 被 tsconfig 排除、零测试文件 -> 子项目 npm test 天生 DOA
  assert.match(pkg.scripts.test, /^tsc && node --test dist\/test\/\*\.test\.js$/);
  assert.ok(!pkg.devDependencies.jest, 'jest should not be emitted');

  const ts = JSON.parse(fs.readFileSync(path.join(p, 'tsconfig.json'), 'utf8'));
  assert.ok(ts.include.includes('test/**/*'), 'test dir must compile');
  assert.ok(!ts.exclude.includes('test'), 'test dir must not be excluded');

  const smoke = fs.readFileSync(path.join(p, 'test', 'smoke.test.ts'), 'utf8');
  assert.match(smoke, /mcp-server\.json/);
  // 冒烟测试不得 import 服务器代码 —— src/index.ts 顶层 main() 会连接 stdio，导入即挂起
  assert.doesNotMatch(smoke, /from '\.\.\/src/);
});

test('init duplicate dir exits 1', () => {
  const dir = tmp();
  const first = mcpt(['init', 'dup', '-e'], dir);
  assert.equal(first.status, 0, first.stderr);
  const second = mcpt(['init', 'dup', '-e'], dir);
  assert.equal(second.status, 1);
  assert.ok(second.stdout.includes('已存在'), `stderr: ${second.stdout}${second.stderr}`);
});

test('init rejects invalid names (uppercase / underscore)', () => {
  for (const bad of ['BadName', 'under_score']) {
    const r = mcpt(['init', bad]);
    assert.equal(r.status, 1, `${bad} should be rejected`);
    assert.ok(r.stdout.includes('项目名称'));
  }
});

test('init rejects invalid transport type', () => {
  const dir = tmp();
  const r = mcpt(['init', 'typed', '-t', 'grpc'], dir);
  assert.equal(r.status, 1, 'invalid --type must exit 1');
  assert.ok(r.stdout.includes('stdio') || r.stdout.includes('sse') || r.stdout.includes('stdlib'));
  assert.ok(!fs.existsSync(path.join(dir, 'typed')), 'must not create project on invalid type');
});

test('init -e generates echo example tool; default has empty tool list', () => {
  const dir = tmp();
  const r = mcpt(['init', 'with-example', '-e'], dir);
  assert.equal(r.status, 0, r.stderr);
  const code = fs.readFileSync(path.join(dir, 'with-example', 'src', 'index.ts'), 'utf8');
  assert.match(code, /name:\s*'echo'/);
  assert.match(code, /Echo:/);

  const r2 = mcpt(['init', 'no-example'], dir);
  assert.equal(r2.status, 0, r2.stderr);
  const code2 = fs.readFileSync(path.join(dir, 'no-example', 'src', 'index.ts'), 'utf8');
  assert.match(code2, /tools: \[\]/);
  assert.doesNotMatch(code2, /'echo'/);
});

test('init -t sse records transport in mcp-server.json', () => {
  const dir = tmp();
  const r = mcpt(['init', 'sse-server', '-t', 'sse'], dir);
  assert.equal(r.status, 0, r.stderr);
  const cfg = JSON.parse(fs.readFileSync(path.join(dir, 'sse-server', 'mcp-server.json'), 'utf8'));
  assert.equal(cfg.transport, 'sse');
});

test('placeholder commands exit 1 with honest message', () => {
  for (const cmd of ['test', 'serve']) {
    const r = mcpt([cmd], tmp());
    assert.equal(r.status, 1, `${cmd} placeholder must exit 1`);
    assert.ok(r.stderr.includes('尚未实现'), `${cmd} stderr should say not implemented: ${r.stderr}`);
  }
});

test('validate is implemented: no longer a placeholder', () => {
  const r = mcpt(['validate'], tmp());
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('不存在'), 'validate should run for real now');
  assert.ok(!r.stderr.includes('尚未实现'));
});
