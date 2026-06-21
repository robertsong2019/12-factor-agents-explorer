import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  detectProject,
  scanLanguages,
  getDirStructure,
  parseGitignore,
  generateAgentsMd,
  generateCursorRules,
  generateCopilotInstructions,
  generateClaudeMd,
  validateContext,
  buildExportData,
  exportTOML,
  exportYAML,
} from '../context-forge.mjs';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ─── Self-integration: analyze context-forge itself ─────────────

describe('F16: Integration — analyze context-forge project', () => {
  const projectRoot = join(__dirname, '..');

  it('detects context-forge project metadata', async () => {
    const info = await detectProject(projectRoot);
    assert.ok(info.pkg);
    assert.equal(info.pkg.name, 'context-forge');
    assert.ok(info.entryPoints);
    assert.ok(info.scripts);
  });

  it('finds JavaScript files', async () => {
    const gitignore = await parseGitignore(projectRoot);
    const langs = await scanLanguages(projectRoot, 2, 0, gitignore);
    const langArr = [...langs];
    assert.ok(langArr.length > 0);
    const langNames = langArr.map(l => l[0]);
    assert.ok(langNames.some(n => /javascript|js|mjs/i.test(n)));
  });

  it('parses .gitignore without errors', async () => {
    const patterns = await parseGitignore(projectRoot);
    assert.ok(Array.isArray(patterns));
  });

  it('generates directory structure', async () => {
    const gitignore = await parseGitignore(projectRoot);
    const structure = await getDirStructure(projectRoot, '', 2, 0, gitignore);
    assert.ok(typeof structure === 'string');
    assert.ok(structure.length > 0);
  });

  it('generates valid AGENTS.md', async () => {
    const info = await detectProject(projectRoot);
    const gitignore = await parseGitignore(projectRoot);
    const langs = await scanLanguages(projectRoot, 2, 0, gitignore);
    const structure = await getDirStructure(projectRoot, '', 2, 0, gitignore);
    const content = generateAgentsMd(info, langs, structure);
    assert.ok(content.length > 100);
  });

  it('generates valid .cursorrules', async () => {
    const info = await detectProject(projectRoot);
    const gitignore = await parseGitignore(projectRoot);
    const langs = await scanLanguages(projectRoot, 2, 0, gitignore);
    const structure = await getDirStructure(projectRoot, '', 2, 0, gitignore);
    const content = generateCursorRules(info, langs, structure);
    assert.ok(content.length > 50);
  });

  it('generates valid copilot instructions', async () => {
    const info = await detectProject(projectRoot);
    const content = generateCopilotInstructions(info);
    assert.ok(content.length > 50);
  });

  it('generates valid CLAUDE.md', async () => {
    const info = await detectProject(projectRoot);
    const gitignore = await parseGitignore(projectRoot);
    const langs = await scanLanguages(projectRoot, 2, 0, gitignore);
    const structure = await getDirStructure(projectRoot, '', 2, 0, gitignore);
    const content = generateClaudeMd(info, langs, structure);
    assert.ok(content.length > 50);
  });
});

// ─── Integration: temp project lifecycle ────────────────────────

describe('F16: Integration — temp project lifecycle', () => {
  const tmpDir = join(__dirname, 'tmp-f16-lifecycle');

  it('creates, analyzes, generates, and validates', async () => {
    mkdirSync(tmpDir, { recursive: true });
    writeFileSync(join(tmpDir, 'package.json'), JSON.stringify({
      name: 'test-lifecycle',
      version: '1.0.0',
      main: 'index.js',
      scripts: { start: 'node index.js', test: 'node --test' },
      dependencies: { express: '^4.18.0' },
    }));
    writeFileSync(join(tmpDir, 'index.js'), 'console.log("hello");');
    writeFileSync(join(tmpDir, 'README.md'), '# Test Project');

    try {
      // Analyze
      const info = await detectProject(tmpDir);
      assert.equal(info.pkg.name, 'test-lifecycle');
      assert.ok(info.entryPoints);

      const langs = [...(await scanLanguages(tmpDir, 1, 0, []))];
      assert.ok(langs.length > 0);

      const structure = await getDirStructure(tmpDir, '', 1, 0, []);
      assert.ok(structure.includes('index.js') || structure.includes('package.json'));

      // Generate
      const agents = generateAgentsMd(info, langs, structure);
      assert.ok(agents.includes('test-lifecycle'));

      // Export data
      const exportData = buildExportData(info, langs, { allImports: [], imports: [] }, [], {}, null);
      assert.equal(exportData.project.name, 'test-lifecycle');

      const toml = exportTOML(exportData);
      assert.match(toml, /\[project\]/);

      const yaml = exportYAML(exportData);
      assert.match(yaml, /project:/);
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('handles minimal project (no package.json)', async () => {
    mkdirSync(tmpDir, { recursive: true });
    writeFileSync(join(tmpDir, 'main.py'), 'print("hello")');

    try {
      const info = await detectProject(tmpDir);
      assert.ok(info); // Should return an object, not throw
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it('handles empty directory gracefully', async () => {
    mkdirSync(tmpDir, { recursive: true });
    try {
      const info = await detectProject(tmpDir);
      assert.ok(info); // Should return an object, not throw
      const langs = [...(await scanLanguages(tmpDir, 1, 0, []))];
      assert.ok(Array.isArray(langs));
    } finally {
      rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});

// ─── Integration: export format cross-validation ────────────────

describe('F16: Integration — export format cross-validation', () => {
  const projectRoot = join(__dirname, '..');

  it('TOML, YAML, and JSON all contain same project name', async () => {
    const info = await detectProject(projectRoot);
    const gitignore = await parseGitignore(projectRoot);
    const langs = await scanLanguages(projectRoot, 2, 0, gitignore);
    const data = buildExportData(info, langs, { allImports: [], imports: [] }, [], {}, null);

    const toml = exportTOML(data);
    const yaml = exportYAML(data);
    const json = JSON.stringify(data);

    const name = info.pkg?.name || 'unknown';
    assert.ok(toml.includes(name));
    assert.ok(yaml.includes(name));
    assert.ok(json.includes(name));
  });

  it('all export formats are non-empty', async () => {
    const info = await detectProject(projectRoot);
    const data = buildExportData(info, [], { allImports: [], imports: [] }, [], {}, null);

    const toml = exportTOML(data);
    const yaml = exportYAML(data);
    const json = JSON.stringify(data);

    assert.ok(toml.length > 20);
    assert.ok(yaml.length > 20);
    assert.ok(json.length > 20);
  });
});
