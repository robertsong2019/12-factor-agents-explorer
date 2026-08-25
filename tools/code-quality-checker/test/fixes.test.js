import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs-extra';
import os from 'os';
import path from 'path';
import { spawnSync } from 'node:child_process';
import {
  findJavaScriptFiles,
  runComplexityCheck,
  runDependencyCheck,
  globToRegex,
  loadComplexityConfig
} from '../index.js';

const INDEX = path.resolve('index.js');

// node --test IPC protocol corruption guard (same failure family as 2026-08-18 agent-task-orchestrator):
// in-process check functions console.log heavily; interleaved stdout corrupts the runner's
// structured-clone channel ("Unable to deserialize cloned data"). Silence here — CLI spawn
// tests capture child output via spawnSync, unaffected.
console.log = () => {};

async function mkProject(files) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-fix-'));
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(dir, rel);
    await fs.ensureDir(path.dirname(full));
    await fs.writeFile(full, content);
  }
  return dir;
}

describe('fix1: findJavaScriptFiles skips node_modules', () => {
  it('does not return vendor files from node_modules', async () => {
    const dir = await mkProject({
      'src/app.js': 'const a = 1;',
      'node_modules/left-pad/index.js': 'module.exports = 1;',
      'node_modules/x/y/deep.ts': 'export const y = 2;'
    });
    const files = (await findJavaScriptFiles(dir)).map(f => path.relative(dir, f));
    assert.deepEqual(files, [path.join('src', 'app.js')]);
    await fs.remove(dir);
  });

  it('still finds files in regular subdirectories', async () => {
    const dir = await mkProject({
      'lib/a.js': 'const a = 1;',
      'lib/nested/b.js': 'const b = 2;'
    });
    const files = await findJavaScriptFiles(dir);
    assert.equal(files.length, 2);
    await fs.remove(dir);
  });
});

describe('fix3: npm outdated exit-1 stdout salvage', () => {
  let stubDir, oldPath;

  before(async () => {
    stubDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-npmstub-'));
    const stub = [
      '#!/bin/bash',
      `echo '{"lodash":{"current":"1.0.0","wanted":"2.0.0","latest":"2.0.0"},"chalk":{"current":"4.0.0","wanted":"5.0.0","latest":"5.0.0"}}'`,
      'exit 1'
    ].join('\n');
    await fs.writeFile(path.join(stubDir, 'npm'), stub, { mode: 0o755 });
    oldPath = process.env.PATH;
    process.env.PATH = `${stubDir}:${oldPath}`;
  });

  after(() => {
    process.env.PATH = oldPath;
    return fs.remove(stubDir);
  });

  it('parses outdated list from stdout even when npm exits 1', async () => {
    const dir = await mkProject({
      'package.json': JSON.stringify({ name: 'x', dependencies: { lodash: '^1.0.0', chalk: '^4.0.0' } })
    });
    const result = await runDependencyCheck(dir);
    assert.equal(result.status, 'completed');
    assert.equal(result.totalDependencies, 2);
    assert.deepEqual(result.outdated.sort(), ['chalk', 'lodash']);
    await fs.remove(dir);
  });

  it('health score can now penalize outdated deps', async () => {
    const dir = await mkProject({
      'package.json': JSON.stringify({ name: 'x', dependencies: { lodash: '^1.0.0' } })
    });
    const result = await runDependencyCheck(dir);
    assert.equal(result.outdatedDependencies, 2);
    await fs.remove(dir);
  });

  it('returns [] when npm is missing entirely (ENOENT)', async () => {
    const emptyDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-nopath-'));
    const dir = await mkProject({
      'package.json': JSON.stringify({ name: 'x', dependencies: { lodash: '^1.0.0' } })
    });
    const savedPath = process.env.PATH;
    process.env.PATH = emptyDir; // no node/npm binaries here
    const result = await runDependencyCheck(dir);
    process.env.PATH = savedPath;
    assert.equal(result.status, 'completed');
    assert.deepEqual(result.outdated, []);
    await Promise.all([fs.remove(dir), fs.remove(emptyDir)]);
  });
});

describe('fix2: CLI parses via bin symlink', () => {
  it('symlinked bin invocation prints usage instead of silent no-op', async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-bin-'));
    const link = path.join(tmp, 'cqc');
    await fs.ensureSymlink(INDEX, link);
    const res = spawnSync(process.execPath, [link, '--help'], { encoding: 'utf8' });
    assert.equal(res.status, 0, `stderr: ${res.stderr}`);
    assert.match(res.stdout, /Usage: cqc/);
    await fs.remove(tmp);
  });

  it('direct path invocation still works', () => {
    const res = spawnSync(process.execPath, [INDEX, '--help'], { encoding: 'utf8' });
    assert.equal(res.status, 0);
    assert.match(res.stdout, /Usage: cqc/);
  });
});

describe('fix4: .complexityrc.json is honored', () => {
  it('loadComplexityConfig returns {} when absent', async () => {
    const dir = await mkProject({ 'a.js': 'const a = 1;' });
    assert.deepEqual(await loadComplexityConfig(dir), {});
    await fs.remove(dir);
  });

  it('loadComplexityConfig swallows broken JSON', async () => {
    const dir = await mkProject({ '.complexityrc.json': '{broken' });
    assert.deepEqual(await loadComplexityConfig(dir), {});
    await fs.remove(dir);
  });

  it('ignoreFiles excludes test files via **/*.test.js glob', async () => {
    const dir = await mkProject({
      'src/app.js': 'const a = 1;',
      'src/app.test.js': 'if (1) {} if (2) {}',
      '.complexityrc.json': JSON.stringify({ ignoreFiles: ['**/*.test.js'] })
    });
    const result = await runComplexityCheck(dir);
    assert.equal(result.filesAnalyzed, 1);
    assert.ok(result.results.every(r => !r.file.includes('.test.js')));
    await fs.remove(dir);
  });

  it('fileExtensions narrows analysis within the scanned JS family', async () => {
    const dir = await mkProject({
      'a.js': 'const a = 1;',
      'b.ts': 'const b = 2;',
      'c.jsx': 'const c = 3;',
      '.complexityrc.json': JSON.stringify({ fileExtensions: ['.ts'] })
    });
    const result = await runComplexityCheck(dir);
    assert.equal(result.filesAnalyzed, 1);
    assert.ok(result.results[0].file.endsWith('.ts'));
    await fs.remove(dir);
  });

  it('maxComplexity raises the high-complexity bar', async () => {
    const branchy = Array.from({ length: 15 }, (_, i) => `if (x${i}) {}`).join('\n');
    const dir = await mkProject({
      'a.js': branchy
    });
    const strict = await runComplexityCheck(dir);
    assert.equal(strict.highComplexityFiles, 1); // 15 > 10 default
    await fs.writeFile(path.join(dir, '.complexityrc.json'), JSON.stringify({ maxComplexity: 20 }));
    const lenient = await runComplexityCheck(dir);
    assert.equal(lenient.highComplexityFiles, 0); // 15 <= 20
    await fs.remove(dir);
  });
});

describe('globToRegex', () => {
  it('**/*.test.js matches nested test files', () => {
    const re = globToRegex('**/*.test.js');
    assert.ok(re.test('a.test.js'));
    assert.ok(re.test('src/a.test.js'));
    assert.ok(re.test('src/deep/a.test.js'));
    assert.ok(!re.test('src/a.js'));
  });

  it('**/node_modules/** matches anything under node_modules', () => {
    const re = globToRegex('**/node_modules/**');
    assert.ok(re.test('node_modules/x/index.js'));
    assert.ok(re.test('a/node_modules/x/y.js'));
    assert.ok(!re.test('src/app.js'));
  });

  it('plain * stays within one segment', () => {
    const re = globToRegex('*.js');
    assert.ok(re.test('a.js'));
    assert.ok(!re.test('sub/a.js'));
  });

  it('? matches exactly one char', () => {
    const re = globToRegex('a?c.js');
    assert.ok(re.test('abc.js'));
    assert.ok(!re.test('ac.js'));
  });

  it('dots are literal', () => {
    const re = globToRegex('a.js');
    assert.ok(!re.test('aXjs'));
  });
});

describe('fix5: CI gating (--fail-on / --min-score)', () => {
  function cqc(args, cwd) {
    return spawnSync(process.execPath, [INDEX, 'check', ...args], { encoding: 'utf8', cwd });
  }

  it('clean project exits 0 with --fail-on error', async () => {
    const dir = await mkProject({ 'a.js': 'const a = 1;' });
    const res = cqc([dir, '--security', '--fail-on', 'error']);
    assert.equal(res.status, 0, `stderr: ${res.stderr}`);
    await fs.remove(dir);
  });

  it('security issue triggers exit 1 with --fail-on error', async () => {
    const dir = await mkProject({ 'a.js': 'eval("1")' });
    const res = cqc([dir, '--security', '--fail-on', 'error']);
    assert.equal(res.status, 1);
    assert.match(res.stderr, /--fail-on error 触发/);
    await fs.remove(dir);
  });

  it('high complexity alone does NOT trigger --fail-on error but does trigger warning', async () => {
    const branchy = Array.from({ length: 15 }, (_, i) => `if (x${i}) {}`).join('\n');
    const dir = await mkProject({ 'a.js': branchy });
    const errLevel = cqc([dir, '--complexity', '--fail-on', 'error']);
    assert.equal(errLevel.status, 0);
    const warnLevel = cqc([dir, '--complexity', '--fail-on', 'warning']);
    assert.equal(warnLevel.status, 1);
    await fs.remove(dir);
  });

  it('skipped checks do not trigger failures', async () => {
    const dir = await mkProject({ 'a.js': 'const a = 1;' }); // no .eslintrc → eslint skipped
    const res = cqc([dir, '--eslint', '--fail-on', 'warning']);
    assert.equal(res.status, 0);
    await fs.remove(dir);
  });

  it('invalid --fail-on level exits 1 with message', async () => {
    const dir = await mkProject({ 'a.js': 'const a = 1;' });
    const res = cqc([dir, '--security', '--fail-on', 'bogus']);
    assert.equal(res.status, 1);
    assert.match(res.stderr, /无效的 --fail-on/);
    await fs.remove(dir);
  });

  it('--min-score 100 passes clean project, fails eval project', async () => {
    const clean = await mkProject({ 'a.js': 'const a = 1;' });
    assert.equal(cqc([clean, '--security', '--min-score', '100']).status, 0);
    await fs.remove(clean);
    const dirty = await mkProject({ 'a.js': 'eval("1")' });
    const res = cqc([dirty, '--security', '--min-score', '100']);
    assert.equal(res.status, 1);
    assert.match(res.stderr, /低于阈值/);
    await fs.remove(dirty);
  });

  it('invalid --min-score range exits 1', async () => {
    const dir = await mkProject({ 'a.js': 'const a = 1;' });
    const res = cqc([dir, '--security', '--min-score', '150']);
    assert.equal(res.status, 1);
    await fs.remove(dir);
  });
});
