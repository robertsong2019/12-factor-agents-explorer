#!/usr/bin/env node
// Hermetic tests for agent-memory-kit (amk) CLI.
// Each test builds an isolated fake workspace and invokes cli.mjs
// as a child process with OPENCLAW_WORKSPACE overridden.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CLI = new URL('../cli.mjs', import.meta.url).pathname;

function mkWorkspace() {
  const ws = mkdtempSync(join(tmpdir(), 'amk-test-'));
  mkdirSync(join(ws, 'memory'));
  return ws;
}

function amk(ws, ...args) {
  const r = spawnSync(process.execPath, [CLI, ...args], {
    env: { ...process.env, OPENCLAW_WORKSPACE: ws },
    encoding: 'utf-8',
  });
  return { code: r.status, out: r.stdout, err: r.stderr };
}

function localDate(offsetDays = 0) {
  const d = new Date(Date.now() - offsetDays * 86400000);
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// ---------- search ----------
test('search: no query → usage error, exit 1', () => {
  const { code, err } = amk(mkWorkspace(), 'search');
  assert.equal(code, 1);
  assert.match(err, /Usage: amk search/);
});

test('search: matches in MEMORY.md and daily files, case-insensitive', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'MEMORY.md'), '# Long-term\nKey insight about entropy.\n');
  writeFileSync(join(ws, 'memory', localDate() + '.md'), 'Worked on ENTROPY gate today.\nnothing else\n');
  const { out } = amk(ws, 'search', 'entropy');
  assert.match(out, /MEMORY\.md \(1 matches\)/);
  assert.match(out, /Key insight about entropy/);
  assert.match(out, new RegExp(localDate() + '\\.md \\(1 matches\\)'));
  assert.match(out, /Total: 2 files, 2 matches/);
});

test('search: caps display at 5 lines with and-N-more', () => {
  const ws = mkWorkspace();
  const lines = Array.from({ length: 8 }, (_, i) => `hit-${i}`).join('\n');
  writeFileSync(join(ws, 'memory', localDate() + '.md'), lines + '\n');
  const { out } = amk(ws, 'search', 'hit-');
  assert.match(out, /\(8 matches\)/);
  assert.match(out, /and 3 more/);
  assert.doesNotMatch(out, /hit-7/); // only first 5 displayed
});

test('search: no matches message', () => {
  const { out } = amk(mkWorkspace(), 'search', 'zzzznomatch');
  assert.match(out, /No matches found/);
});

// ---------- summary ----------
test('summary: includes today file (local date, not UTC)', () => {
  const ws = mkWorkspace();
  const today = localDate() + '.md';
  const yesterday = localDate(1) + '.md';
  writeFileSync(join(ws, 'memory', today), 'Today heading line one\nsecond line\n');
  writeFileSync(join(ws, 'memory', yesterday), 'Yesterday activity\n');
  const { out } = amk(ws, 'summary');
  assert.match(out, /Memory Summary \(Last 7 Days\)/);
  assert.match(out, /Today heading line one/);
  // counts non-blank lines only
  assert.match(out, /\(2 lines\)/);
});

test('summary: empty workspace message + MEMORY.md stats', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'MEMORY.md'), 'a\nb\n');
  const { out } = amk(ws, 'summary');
  assert.match(out, /No memory files found for the last 7 days/);
  // non-blank line count (trailing newline does not inflate)
  assert.match(out, /MEMORY\.md: 2 lines, 4 bytes/);
});

// ---------- stats ----------
test('stats: file count, sizes, earliest/latest ordering', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', '2026-01-02.md'), 'x\n');
  writeFileSync(join(ws, 'memory', '2026-03-05.md'), 'y\n');
  writeFileSync(join(ws, 'MEMORY.md'), 'z\n');
  const { out } = amk(ws, 'stats');
  assert.match(out, /Daily files:    2/);
  assert.match(out, /Daily lines:\s+2/);
  assert.match(out, /Earliest:       2026-01-02\.md/);
  assert.match(out, /Latest:         2026-03-05\.md/);
  assert.match(out, /Total:          0\.0 KB/);
});

test('stats: empty memory dir', () => {
  const { out } = amk(mkWorkspace(), 'stats');
  assert.match(out, /Daily files:    0/);
  assert.doesNotMatch(out, /Earliest/);
});

// ---------- tags / extract-tags ----------
test('tags: filters stop words and short words, counts frequency', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', localDate() + '.md'), 'the agent memory agent agent tools\nab xx agent\n');
  const { out } = amk(ws, 'tags');
  assert.match(out, /agent\s+4/);
  assert.match(out, /Top Terms/);
  assert.doesNotMatch(out, /\bthe\s+\d/);
  assert.doesNotMatch(out, /\bab\s+\d/);
  assert.doesNotMatch(out, /\bxx\s+\d/);
});

test('tags: alias command works', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'MEMORY.md'), 'catalyst catalyst\n');
  const { out } = amk(ws, 'extract-tags');
  assert.match(out, /catalyst\s+2/);
});

// ---------- timeline ----------
test('timeline: lists files and first 3 headings', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', '2026-05-01.md'), '# H1\n## H2\n### H3\n#### H4\nbody\n');
  const { out } = amk(ws, 'timeline');
  assert.match(out, /2026-05-01\.md — \d+ lines|May 1, 2026 — \d+ lines/);
  assert.match(out, /→ H1/);
  assert.match(out, /→ H4|→ H3/); // shows up to 3 headings
});

// ---------- merge ----------
test('merge: appends source into dest with separator', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', 'a.md'), 'source body\n');
  writeFileSync(join(ws, 'memory', 'b.md'), 'dest body\n');
  const { out } = amk(ws, 'merge', 'a.md', 'b.md');
  assert.match(out, /Merged a\.md into b\.md/);
  const merged = readFileSync(join(ws, 'memory', 'b.md'), 'utf-8');
  assert.match(merged, /dest body/);
  assert.match(merged, /---/);
  assert.match(merged, /source body/);
});

test('merge: dest missing → becomes copy of source', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', 'a.md'), 'only source\n');
  const { code } = amk(ws, 'merge', 'a.md', 'new.md');
  assert.equal(code, 0);
  assert.equal(readFileSync(join(ws, 'memory', 'new.md'), 'utf-8'), 'only source\n');
});

test('merge: missing source → error exit 1', () => {
  const ws = mkWorkspace();
  const { code, err } = amk(ws, 'merge', 'ghost.md', 'b.md');
  assert.equal(code, 1);
  assert.match(err, /Source not found/);
});

test('merge: missing args → usage exit 1', () => {
  const { code, err } = amk(mkWorkspace(), 'merge', 'a.md');
  assert.equal(code, 1);
  assert.match(err, /Usage: amk merge/);
});

// ---------- prune ----------
test('prune: dry-run lists old files but keeps them', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', '2026-01-01.md'), 'old\n');
  writeFileSync(join(ws, 'memory', localDate() + '.md'), 'fresh\n');
  const { out } = amk(ws, 'prune', '30');
  assert.match(out, /2026-01-01\.md/);
  assert.match(out, /Dry run/);
  assert.ok(existsSync(join(ws, 'memory', '2026-01-01.md')));
});

test('prune: --apply removes only old files', () => {
  const ws = mkWorkspace();
  const fresh = localDate() + '.md';
  writeFileSync(join(ws, 'memory', '2026-01-01.md'), 'old\n');
  writeFileSync(join(ws, 'memory', fresh), 'fresh\n');
  const { out } = amk(ws, 'prune', '30', '--apply');
  assert.match(out, /Removed 1 files/);
  assert.ok(!existsSync(join(ws, 'memory', '2026-01-01.md')));
  assert.ok(existsSync(join(ws, 'memory', fresh)));
});

test('prune: nothing old → clean message', () => {
  const { out } = amk(mkWorkspace(), 'prune', '365');
  assert.match(out, /No files older than 365 days/);
});

test('prune: no/invalid days → usage exit 1', () => {
  const ws = mkWorkspace();
  assert.match(amk(ws, 'prune').err, /Usage: amk prune/);
  assert.equal(amk(ws, 'prune', 'NaN').code, 1);
});

// ---------- context ----------
test('context: assembles identity/user/soul + recent memory + long-term (with caps)', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'IDENTITY.md'), 'I am Catalyst.');
  writeFileSync(join(ws, 'USER.md'), 'Human: Luosong.');
  writeFileSync(join(ws, 'SOUL.md'), 'Be sharp.');
  writeFileSync(join(ws, 'MEMORY.md'), 'M'.repeat(2000));
  const { out } = amk(ws, 'context');
  assert.match(out, /## Identity\nI am Catalyst\./);
  assert.match(out, /## User\nHuman: Luosong\./);
  assert.match(out, /## Soul\nBe sharp\./);
  assert.match(out, /## Long-term Memory\nM+/);
  assert.match(out, /Total: \d+ chars/);
});

test('context: daily file capped at 500 chars', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', localDate() + '.md'), 'Z'.repeat(800));
  const { out } = amk(ws, 'context');
  const m = out.match(/## Memory\/[^\n]+\n(Z+)/);
  assert.ok(m, 'memory section present');
  assert.equal(m[1].length, 500);
});

test('context: empty workspace → only total line', () => {
  const { out } = amk(mkWorkspace(), 'context');
  assert.match(out, /Total: 0 chars/);
});

// ---------- default / help ----------
test('unknown command → help text', () => {
  const { out, code } = amk(mkWorkspace(), 'frobnicate');
  assert.equal(code, 0);
  assert.match(out, /agent-memory-kit \(amk\) v1\.0\.0/);
  assert.match(out, /Usage: amk <command>/);
});

test('no command → help text', () => {
  const { out } = amk(mkWorkspace());
  assert.match(out, /Usage: amk <command>/);
});

// ---------- context path isolation ----------
test('context <path>: memory files come from target workspace, not global', () => {
  const mainWs = mkWorkspace();
  writeFileSync(join(mainWs, 'MEMORY.md'), 'GLOBALONLYMARKER global memory\n');
  writeFileSync(join(mainWs, 'memory', localDate() + '.md'), 'global daily GLOBALDAILY\n');

  const target = mkdtempSync(join(tmpdir(), 'amk-ctx-'));
  mkdirSync(join(target, 'memory'));
  writeFileSync(join(target, 'IDENTITY.md'), 'target identity\n');
  writeFileSync(join(target, 'MEMORY.md'), 'TARGETMEMMARKER target memory\n');
  writeFileSync(join(target, 'memory', '2026-01-05.md'), 'TARGETDAILY target daily note\n');

  const { code, out } = amk(mainWs, 'context', target);
  assert.equal(code, 0);
  assert.match(out, /target identity/);
  assert.match(out, /TARGETMEMMARKER/);
  assert.match(out, /TARGETDAILY/);
  assert.doesNotMatch(out, /GLOBALONLYMARKER/);
  assert.doesNotMatch(out, /GLOBALDAILY/);
});

// ---------- tags CJK tokenization ----------
function writeTagsWs() {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', '2026-02-01.md'),
    '记忆 图谱 很重要。记忆 系统 值得。memory graph matters\n');
  return ws;
}

test('tags: CJK runs split into bigrams, not one mega-token', () => {
  const { out } = amk(writeTagsWs(), 'tags');
  // no token should glue 3+ consecutive CJK chars together
  const tokens = out.split('\n').filter(l => l.trim() && !l.startsWith('🏷')).map(l => l.trim().split(/\s+/)[0]);
  for (const t of tokens) {
    assert.ok(!/[\u4e00-\u9fff]{3,}/.test(t), `mega-token leaked: ${t}`);
  }
});

test('tags: CJK bigrams counted across occurrences', () => {
  const { out } = amk(writeTagsWs(), 'tags');
  assert.match(out, /记忆\s+2/);
});

test('tags: mixed latin+CJK token does not vanish or glue', () => {
  const ws = mkWorkspace();
  writeFileSync(join(ws, 'memory', '2026-02-02.md'), '使用了amk工具，amk很好用。tools\n');
  const { out } = amk(ws, 'tags');
  assert.ok(!/[\u4e00-\u9fff]{3,}/.test(out.replace(/[^\u4e00-\u9fff\s]/g, ' ')), 'mega-token leaked');
  assert.match(out, /tools/); // latin part survives
});

// ---------- package wiring ----------
test('package.json wires npm test to the suite', () => {
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf-8'));
  assert.ok(pkg.scripts && pkg.scripts.test, 'scripts.test missing — npm test is DOA');
});
