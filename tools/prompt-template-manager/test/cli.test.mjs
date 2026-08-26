#!/usr/bin/env node
// Hermetic test suite for ptm CLI — HOME is overridden to a temp dir.
// Run: node --test test/cli.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const CLI = join(dirname(fileURLToPath(import.meta.url)), '..', 'cli.mjs');

function freshHome() {
  const home = mkdtempSync(join(tmpdir(), 'ptm-'));
  return { home, tdir: join(home, '.openclaw/workspace/tools/prompt-template-manager/templates') };
}

function ptm(home, args, opts = {}) {
  return spawnSync(process.execPath, [CLI, ...args], {
    env: { ...process.env, HOME: home },
    encoding: 'utf-8',
    timeout: 5000,
    ...opts,
  });
}

function seed(home, name, content) {
  const tdir = join(home, '.openclaw/workspace/tools/prompt-template-manager/templates');
  mkdirSync(tdir, { recursive: true });
  writeFileSync(join(tdir, name + '.md'), content, 'utf-8');
}

// ─── help / usage ────────────────────────────────────

test('no command → help text, exit 0', () => {
  const { home } = freshHome();
  const r = ptm(home, []);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Usage: ptm <command>/);
  assert.match(r.stdout, /\{\{variable\}\}/);
});

test('unknown command → help text, exit 0', () => {
  const { home } = freshHome();
  const r = ptm(home, ['frobnicate']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Usage: ptm <command>/);
});

// ─── list ────────────────────────────────────────────

test('list on empty store → friendly empty message', () => {
  const { home } = freshHome();
  const r = ptm(home, ['list']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /No templates found/);
});

test('ls alias works like list', () => {
  const { home } = freshHome();
  seed(home, 'greet', '# Greet\nhi');
  const r = ptm(home, ['ls']);
  assert.match(r.stdout, /1 templates?/);
  assert.match(r.stdout, /greet/);
});

test('list shows name, heading-derived description, sorted alphabetically', () => {
  const { home } = freshHome();
  seed(home, 'zeta', '# Last template\nbody');
  seed(home, 'alpha', '# First template\nbody');
  seed(home, 'noheading', 'just plain text');
  const r = ptm(home, ['list']);
  const iA = r.stdout.indexOf('alpha');
  const iN = r.stdout.indexOf('noheading');
  const iZ = r.stdout.indexOf('zeta');
  assert.ok(iA < iN && iN < iZ, 'alphabetical order');
  assert.match(r.stdout, /First template/);
  assert.match(r.stdout, /Last template/);
  assert.match(r.stdout, /\(no description\)/);
  assert.match(r.stdout, /3 templates/);
});

// ─── add ─────────────────────────────────────────────

test('add with inline content writes the template', () => {
  const { home } = freshHome();
  const r = ptm(home, ['add', 'review', '# Code Review', 'Review {{lang}} code.']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Added template: review/);
  assert.equal(readFileSync(join(freshHomeTdir(home), 'review.md'), 'utf-8'), '# Code Review Review {{lang}} code.');
});

function freshHomeTdir(home) {
  return join(home, '.openclaw/workspace/tools/prompt-template-manager/templates');
}

test('add without content reads from stdin', () => {
  const { home } = freshHome();
  const r = spawnSync(process.execPath, [CLI, 'add', 'stdin-tpl'], {
    env: { ...process.env, HOME: home },
    input: '# From stdin\nhello',
    encoding: 'utf-8',
    timeout: 5000,
  });
  assert.equal(r.status, 0);
  assert.equal(readFileSync(join(freshHomeTdir(home), 'stdin-tpl.md'), 'utf-8'), '# From stdin\nhello');
});

test('add without name exits 1 with usage', () => {
  const { home } = freshHome();
  const r = ptm(home, ['add']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Usage: ptm add/);
});

// ─── show ────────────────────────────────────────────

test('show prints raw template content', () => {
  const { home } = freshHome();
  seed(home, 't1', '# T1\nline2');
  const r = ptm(home, ['show', 't1']);
  assert.equal(r.status, 0);
  assert.equal(r.stdout, '# T1\nline2\n');
});

test('show missing template exits 1', () => {
  const { home } = freshHome();
  const r = ptm(home, ['show', 'ghost']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Template not found: ghost/);
});

test('show without name exits 1 with usage', () => {
  const { home } = freshHome();
  const r = ptm(home, ['show']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Usage: ptm show/);
});

// ─── render ──────────────────────────────────────────

test('render substitutes provided variables', () => {
  const { home } = freshHome();
  seed(home, 'r1', 'Hello {{name}}, you are {{role}}.');
  const r = ptm(home, ['render', 'r1', 'name=Ada', 'role=reviewer']);
  assert.equal(r.stdout, 'Hello Ada, you are reviewer.\n');
});

test('render leaves missing variables visible as {{var}}', () => {
  const { home } = freshHome();
  seed(home, 'r2', 'Hello {{name}} and {{missing}}.');
  const r = ptm(home, ['render', 'r2', 'name=Ada']);
  assert.equal(r.stdout, 'Hello Ada and {{missing}}.\n');
});

test('render only matches \\w+ keys, not arbitrary braces', () => {
  const { home } = freshHome();
  seed(home, 'r3', 'JSON: {"a":1} — {{ ok }} stays');
  const r = ptm(home, ['render', 'r3', 'ok=X']);
  assert.equal(r.stdout, 'JSON: {"a":1} — {{ ok }} stays\n');
});

test('render value containing "=" is preserved', () => {
  const { home } = freshHome();
  seed(home, 'r4', 'expr={{e}}');
  const r = ptm(home, ['render', 'r4', 'e=a=b']);
  assert.equal(r.stdout, 'expr=a=b\n');
});

test('render with empty-string value substitutes empty (not {{var}})', () => {
  const { home } = freshHome();
  seed(home, 'r5', '[{{v}}]');
  const r = ptm(home, ['render', 'r5', 'v=']);
  assert.equal(r.stdout, '[]\n');
});

test('render missing template exits 1', () => {
  const { home } = freshHome();
  const r = ptm(home, ['render', 'ghost', 'a=1']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Template not found: ghost/);
});

// ─── export ──────────────────────────────────────────

test('export writes rendered output without trailing newline', () => {
  const { home } = freshHome();
  seed(home, 'e1', 'prompt: {{x}}');
  const r = ptm(home, ['export', 'e1', 'x=y']);
  assert.equal(r.status, 0);
  assert.ok(!r.stdout.endsWith('\n'), 'export must not append newline');
  assert.equal(r.stdout, 'prompt: y');
});

test('export missing template exits 1 with usage on stderr', () => {
  const { home } = freshHome();
  const r = ptm(home, ['export']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Usage: ptm export/);
});

// ─── regression: real store templates render ─────────

test('shipped templates dir is created under overridden HOME (hermetic)', () => {
  const { home } = freshHome();
  ptm(home, ['list']);
  assert.ok(existsSync(freshHomeTdir(home)), 'templates dir auto-created');
});

// ─── round 2: overwrite guard, name validation, edit command ──────

test('add refuses to overwrite existing template without --force', () => {
  const { home } = freshHome();
  seed(home, 't', '# One');
  const r = ptm(home, ['add', 't', '# Two']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /already exists/i);
  assert.match(r.stderr, /--force/);
  // content must be untouched
  assert.match(readFileSync(join(home, '.openclaw/workspace/tools/prompt-template-manager/templates/t.md'), 'utf-8'), /One/);
});

test('add --force overwrites existing template', () => {
  const { home } = freshHome();
  seed(home, 't', '# One');
  const r = ptm(home, ['add', 't', '--force', '# Two']);
  assert.equal(r.status, 0);
  assert.match(readFileSync(join(home, '.openclaw/workspace/tools/prompt-template-manager/templates/t.md'), 'utf-8'), /Two/);
});

test('add name containing "/" exits 1 clean, no stack trace', () => {
  const { home } = freshHome();
  const r = ptm(home, ['add', 'a/b', 'content']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /invalid template name/i);
  assert.doesNotMatch(r.stderr, /at /); // no "at fn (file:line)" stack frames
});

test('add name with "../" traversal is refused', () => {
  const { home } = freshHome();
  const r = ptm(home, ['add', '../evil', 'stolen']);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /invalid template name/i);
});

test('edit opens template in $EDITOR', () => {
  const { home } = freshHome();
  seed(home, 'doc', '# Editable');
  const r = ptm(home, ['edit', 'doc'], { env: { ...process.env, HOME: home, EDITOR: 'cat' } });
  assert.equal(r.status, 0);
  assert.match(r.stdout, /# Editable/);
});

test('edit without $EDITOR exits 1 with clear message', () => {
  const { home } = freshHome();
  seed(home, 'doc', '# X');
  const env = { ...process.env, HOME: home };
  delete env.EDITOR;
  const r = ptm(home, ['edit', 'doc'], { env });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /EDITOR/);
});

test('edit missing template exits 1', () => {
  const { home } = freshHome();
  const r = ptm(home, ['edit', 'nope'], { env: { ...process.env, HOME: home, EDITOR: 'cat' } });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /not found/i);
});

test('render documents: CJK variable names are NOT substituted (\\w+ only)', () => {
  const { home } = freshHome();
  seed(home, 'cjk', '你好 {{名字}} end');
  const r = ptm(home, ['render', 'cjk', '名字=值']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /\{\{名字\}\}/); // stays visible — documented \w+ limitation
});

test('parseVars ignores stray args without "=" or leading "="', () => {
  const { home } = freshHome();
  seed(home, 'v', 'X={{a}} Y={{b}}');
  const r = ptm(home, ['render', 'v', 'a=1', '-flag', '=odd']);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /X=1/);
  assert.match(r.stdout, /Y=\{\{b\}\}/); // =odd doesn't bind key '' 
});
