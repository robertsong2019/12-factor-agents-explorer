import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import path from 'path';
import { createSkill, listTemplates, validateSkill } from '../lib/index.js';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TMP = path.join(__dirname, '__tmp_test__');

// Helper: rm -rf
async function rmrf(p) {
  await fs.rm(p, { recursive: true, force: true }).catch(() => {});
}

// ── createSkill ─────────────────────────────────────────
describe('createSkill', () => {
  before(() => rmrf(TMP));
  after(() => rmrf(TMP));

  it('creates a basic skill with SKILL.md', async () => {
    const result = await createSkill('my-skill', { template: 'basic', output: TMP });
    assert.ok(result.path);
    assert.ok(result.files.includes('SKILL.md'));
    const content = await fs.readFile(path.join(result.path, 'SKILL.md'), 'utf-8');
    assert.ok(content.includes('# my-skill'));
    assert.ok(content.includes('## Activation'));
  });

  it('throws on unknown template', async () => {
    await assert.rejects(
      () => createSkill('x', { template: 'unknown', output: TMP }),
      { message: /未知模板/ }
    );
  });

  it('throws if directory already exists', async () => {
    await createSkill('exists-test', { template: 'basic', output: TMP });
    await assert.rejects(
      () => createSkill('exists-test', { template: 'basic', output: TMP }),
      { message: /目录已存在/ }
    );
  });

  it('creates api template with references and scripts dirs', async () => {
    const result = await createSkill('api-skill', { template: 'api', output: TMP });
    assert.ok(result.files.includes('references/'));
    assert.ok(result.files.includes('scripts/'));
    assert.ok(result.files.includes('scripts/helper.js'));
    assert.ok(result.files.includes('references/README.md'));
    // Check API-specific content
    const md = await fs.readFile(path.join(result.path, 'SKILL.md'), 'utf-8');
    assert.ok(md.includes('## API Reference'));
    assert.ok(md.includes('## Authentication'));
  });

  it('creates mcp template with scripts dir', async () => {
    const result = await createSkill('mcp-skill', { template: 'mcp', output: TMP });
    assert.ok(result.files.includes('scripts/'));
    const md = await fs.readFile(path.join(result.path, 'SKILL.md'), 'utf-8');
    assert.ok(md.includes('## MCP Tools'));
  });

  it('creates coding template with references and scripts', async () => {
    const result = await createSkill('code-skill', { template: 'coding', output: TMP });
    const md = await fs.readFile(path.join(result.path, 'SKILL.md'), 'utf-8');
    assert.ok(md.includes('## Code Patterns'));
    assert.ok(md.includes('## Style Guide'));
  });

  it('respects --with-references flag for basic template', async () => {
    const result = await createSkill('extra-refs', {
      template: 'basic', output: TMP, withReferences: true,
    });
    assert.ok(result.files.includes('references/'));
  });

  it('respects --with-scripts flag for basic template', async () => {
    const result = await createSkill('extra-scripts', {
      template: 'basic', output: TMP, withScripts: true,
    });
    assert.ok(result.files.includes('scripts/'));
  });

  it('uses custom description in SKILL.md', async () => {
    const result = await createSkill('desc-skill', {
      template: 'basic', output: TMP, description: 'A custom description here',
    });
    const md = await fs.readFile(path.join(result.path, 'SKILL.md'), 'utf-8');
    assert.ok(md.includes('A custom description here'));
  });
});

// ── listTemplates ───────────────────────────────────────
describe('listTemplates', () => {
  it('returns all 4 templates', () => {
    const list = listTemplates();
    assert.equal(list.length, 4);
    const names = list.map(t => t.name).sort();
    assert.deepEqual(names, ['api', 'basic', 'coding', 'mcp']);
  });

  it('each template has name and description', () => {
    const list = listTemplates();
    for (const t of list) {
      assert.ok(t.name, 'template has name');
      assert.ok(t.description, 'template has description');
      assert.equal(typeof t.description, 'string');
    }
  });
});

// ── validateSkill ───────────────────────────────────────
describe('validateSkill', () => {
  before(() => rmrf(TMP));
  after(() => rmrf(TMP));

  it('validates a well-formed basic skill', async () => {
    await createSkill('good-skill', { template: 'basic', output: TMP });
    const result = await validateSkill(path.join(TMP, 'good-skill'));
    assert.equal(result.valid, true);
    assert.equal(result.issues.length, 0);
  });

  it('reports missing SKILL.md', async () => {
    const dir = path.join(TMP, 'no-md');
    await fs.mkdir(dir, { recursive: true });
    const result = await validateSkill(dir);
    assert.equal(result.valid, false);
    assert.ok(result.issues.some(i => i.includes('SKILL.md')));
  });

  it('reports missing Activation section', async () => {
    const dir = path.join(TMP, 'no-activation');
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, 'SKILL.md'), '# Test\nNo activation here');
    const result = await validateSkill(dir);
    assert.equal(result.valid, false);
    assert.ok(result.issues.some(i => i.includes('Activation')));
  });

  it('warns on empty references dir', async () => {
    const dir = path.join(TMP, 'empty-refs');
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, 'SKILL.md'), '# X\n## Activation\nfoo');
    await fs.mkdir(path.join(dir, 'references'), { recursive: true });
    const result = await validateSkill(dir);
    assert.ok(result.issues.some(i => i.includes('references') && i.includes('空')));
  });

  it('warns on empty scripts dir', async () => {
    const dir = path.join(TMP, 'empty-scripts');
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, 'SKILL.md'), '# X\n## Activation\nfoo');
    await fs.mkdir(path.join(dir, 'scripts'), { recursive: true });
    const result = await validateSkill(dir);
    assert.ok(result.issues.some(i => i.includes('scripts') && i.includes('空')));
  });
});
