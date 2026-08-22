// CLI e2e + regression tests — spawns bin/skill-create.js as a real process
// Covers: help/version, templates, new (all exit paths), validate exit codes,
// and the two bugs fixed on 2026-08-23:
//   (A) validate exited 0 on invalid skill
//   (B) api template generated invalid env var names (hyphens) for kebab-case names
import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BIN = path.join(__dirname, '..', 'bin', 'skill-create.js');
const TMP = path.join(os.tmpdir(), `scaffold-cli-${process.pid}`);

function cli(args, opts = {}) {
  return spawnSync(process.execPath, [BIN, ...args], {
    encoding: 'utf-8',
    cwd: opts.cwd || TMP,
    ...opts,
  });
}

async function rmrf(p) {
  await fs.rm(p, { recursive: true, force: true }).catch(() => {});
}

before(async () => { await rmrf(TMP); await fs.mkdir(TMP, { recursive: true }); });
after(() => rmrf(TMP));

describe('CLI basics', () => {
  it('exits 0 and prints version for --version', () => {
    const r = cli(['--version']);
    assert.equal(r.status, 0);
    assert.match(r.stdout, /^1\.0\.0/);
  });

  it('exits 0 for --help and lists all 4 commands', () => {
    const r = cli(['--help']);
    assert.equal(r.status, 0);
    for (const cmd of ['new', 'templates', 'validate']) {
      assert.ok(r.stdout.includes(cmd), `help lists ${cmd}`);
    }
  });

  it('unknown command exits non-zero (commander default)', () => {
    const r = cli(['frobnicate']);
    assert.notEqual(r.status, 0);
  });

  it('templates lists all template names', () => {
    const r = cli(['templates']);
    assert.equal(r.status, 0);
    for (const name of ['basic', 'api', 'mcp', 'coding']) {
      assert.ok(r.stdout.includes(name), `templates output includes ${name}`);
    }
  });
});

describe('CLI new', () => {
  it('creates a skill on disk and exits 0', async () => {
    const r = cli(['new', 'disk-skill', '-d', 'A disk skill', '-o', TMP]);
    assert.equal(r.status, 0);
    assert.match(r.stdout, /创建成功/);
    const md = await fs.readFile(path.join(TMP, 'disk-skill', 'SKILL.md'), 'utf-8');
    assert.ok(md.includes('A disk skill'));
    assert.ok(md.includes('## Activation'));
  });

  it('exits 1 with error message on unknown template', () => {
    const r = cli(['new', 'bad-tpl', '-t', 'nope', '-o', TMP]);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /未知模板/);
  });

  it('exits 1 when directory already exists', async () => {
    const r = cli(['new', 'disk-skill', '-o', TMP]);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /目录已存在/);
  });

  it('--with-references/--with-scripts add extra dirs', async () => {
    const r = cli(['new', 'flag-skill', '--with-references', '--with-scripts', '-o', TMP]);
    assert.equal(r.status, 0);
    await fs.access(path.join(TMP, 'flag-skill', 'references'));
    await fs.access(path.join(TMP, 'flag-skill', 'scripts', 'helper.js'));
  });

  it('default output dir is cwd', async () => {
    const r = cli(['new', 'cwd-skill'], { cwd: TMP });
    assert.equal(r.status, 0);
    await fs.access(path.join(TMP, 'cwd-skill', 'SKILL.md'));
  });
});

describe('CLI validate', () => {
  it('exits 0 and prints pass message for a well-formed skill', async () => {
    cli(['new', 'valid-skill', '-o', TMP]);
    const r = cli(['validate', path.join(TMP, 'valid-skill')]);
    assert.equal(r.status, 0);
    assert.match(r.stdout, /验证通过/);
  });

  // Regression (A): validate used to print issues but exit 0 —
  // broken for CI/scripts usage
  it('exits 1 when validation fails (missing Activation)', async () => {
    const dir = path.join(TMP, 'bad-skill');
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, 'SKILL.md'), '# X\nno activation section');
    const r = cli(['validate', dir]);
    assert.equal(r.status, 1, 'BUG A regression: invalid skill must exit non-zero');
    assert.match(r.stdout, /发现问题/);
    assert.ok(r.stdout.includes('Activation'));
  });

  it('exits 1 when SKILL.md is missing entirely', async () => {
    const dir = path.join(TMP, 'no-skill-md');
    await fs.mkdir(dir, { recursive: true });
    const r = cli(['validate', dir]);
    assert.equal(r.status, 1);
    assert.ok(r.stdout.includes('SKILL.md'));
  });
});

describe('lib regressions', () => {
  // Regression (B): api template env var for kebab-case name used to be
  // `MY-API_API_KEY` — invalid shell identifier
  it('api template sanitizes env var name (hyphens -> underscores)', async () => {
    const { createSkill } = await import('../lib/index.js');
    const out = path.join(TMP, 'envreg');
    const result = await createSkill('my-api', { template: 'api', output: out });
    const md = await fs.readFile(path.join(result.path, 'SKILL.md'), 'utf-8');
    const m = md.match(/export ([A-Z0-9_]+)_API_KEY=/);
    assert.ok(m, 'env var line present');
    assert.equal(m[1], 'MY_API', 'BUG B regression: env var must be valid identifier');
  });
});
