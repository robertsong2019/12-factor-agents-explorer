import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { detectNamingConventions, formatNamingReport } from "../context-forge.mjs";

describe('F40: detectNamingConventions', () => {
  let tmpDir;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), 'cf-f40-'));
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it('should return empty for empty directory', async () => {
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.totalFiles, 0);
    assert.equal(result.conventions.length, 0);
    assert.equal(result.dominant, 'none');
  });

  it('should detect camelCase files', async () => {
    await writeFile(join(tmpDir, 'myFile.js'), 'x');
    await writeFile(join(tmpDir, 'anotherFile.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.dominant, 'camelCase');
    assert.ok(result.conventions.find(c => c.convention === 'camelCase'));
  });

  it('should detect snake_case files', async () => {
    await writeFile(join(tmpDir, 'my_file.js'), 'x');
    await writeFile(join(tmpDir, 'another_file.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.dominant, 'snake_case');
  });

  it('should detect kebab_case files', async () => {
    await writeFile(join(tmpDir, 'my-file.js'), 'x');
    await writeFile(join(tmpDir, 'another-file.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.dominant, 'kebab_case');
  });

  it('should detect PascalCase files', async () => {
    await writeFile(join(tmpDir, 'MyComponent.js'), 'x');
    await writeFile(join(tmpDir, 'AnotherComponent.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.dominant, 'PascalCase');
  });

  it('should detect CONST_CASE files', async () => {
    await writeFile(join(tmpDir, 'CONSTANTS.js'), 'x');
    await writeFile(join(tmpDir, 'CONFIG.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.dominant, 'CONST_CASE');
  });

  it('should identify inconsistencies', async () => {
    await writeFile(join(tmpDir, 'camelCase.js'), 'x');
    await writeFile(join(tmpDir, 'anotherCamel.js'), 'x');
    await writeFile(join(tmpDir, 'snake_case.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    // Two camelCase, one snake_case → snake_case is inconsistency
    assert.ok(result.inconsistencies.length > 0);
    assert.ok(result.inconsistencies.some(i => i.file === 'snake_case.js'));
  });

  it('should report percentage correctly', async () => {
    await writeFile(join(tmpDir, 'aaa.js'), 'x');
    await writeFile(join(tmpDir, 'bbb.js'), 'x');
    await writeFile(join(tmpDir, 'CCC.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    const camel = result.conventions.find(c => c.convention === 'camelCase');
    assert.equal(camel.percentage, 66.7);
  });

  it('should group by directory', async () => {
    await mkdir(join(tmpDir, 'src'), { recursive: true });
    await mkdir(join(tmpDir, 'tests'), { recursive: true });
    await writeFile(join(tmpDir, 'src', 'myFile.js'), 'x');
    await writeFile(join(tmpDir, 'src', 'otherFile.js'), 'x');
    await writeFile(join(tmpDir, 'tests', 'test_file.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.ok(result.byDirectory.length >= 2);
    const srcDir = result.byDirectory.find(d => d.dir === 'src');
    assert.equal(srcDir.convention, 'camelCase');
    const testDir = result.byDirectory.find(d => d.dir === 'tests');
    assert.equal(testDir.convention, 'snake_case');
  });

  it('should skip dotfiles and node_modules', async () => {
    await writeFile(join(tmpDir, '.hidden'), 'x');
    await mkdir(join(tmpDir, 'node_modules'), { recursive: true });
    await writeFile(join(tmpDir, 'node_modules', 'dep.js'), 'x');
    await writeFile(join(tmpDir, 'app.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    assert.equal(result.totalFiles, 1);
  });

  it('should respect maxDepth', async () => {
    await writeFile(join(tmpDir, 'top.js'), 'x');
    await mkdir(join(tmpDir, 'deep'), { recursive: true });
    await writeFile(join(tmpDir, 'deep', 'nested.js'), 'x');
    const result = await detectNamingConventions(tmpDir, { maxDepth: 0 });
    assert.equal(result.totalFiles, 1);
  });

  it('should provide examples for each convention', async () => {
    await writeFile(join(tmpDir, 'myFile.js'), 'x');
    await writeFile(join(tmpDir, 'MyClass.js'), 'x');
    const result = await detectNamingConventions(tmpDir);
    for (const c of result.conventions) {
      assert.ok(c.examples.length > 0);
    }
  });
});

describe('F40: formatNamingReport', () => {
  it('should handle empty analysis', () => {
    const report = formatNamingReport({ totalFiles: 0 });
    assert.ok(report.includes('No files'));
  });

  it('should include dominant convention and table', () => {
    const analysis = {
      totalFiles: 5,
      dominant: 'camelCase',
      conventions: [
        { convention: 'camelCase', count: 4, percentage: 80, examples: ['myFile.js', 'otherFile.js'] },
        { convention: 'snake_case', count: 1, percentage: 20, examples: ['legacy_file.js'] },
      ],
      inconsistencies: [{ file: 'legacy_file.js', convention: 'snake_case' }],
      byDirectory: [{ dir: 'src', convention: 'camelCase', count: 4 }],
    };
    const report = formatNamingReport(analysis);
    assert.ok(report.includes('Naming Convention Analysis'));
    assert.ok(report.includes('camelCase'));
    assert.ok(report.includes('Inconsistencies'));
    assert.ok(report.includes('legacy_file.js'));
  });

  it('should truncate inconsistencies list at 10', () => {
    const inconsistencies = Array.from({ length: 15 }, (_, i) => ({ file: `file_${i}.js`, convention: 'snake_case' }));
    const analysis = {
      totalFiles: 20,
      dominant: 'camelCase',
      conventions: [{ convention: 'camelCase', count: 5, percentage: 25, examples: ['a.js'] }],
      inconsistencies,
      byDirectory: [],
    };
    const report = formatNamingReport(analysis);
    assert.ok(report.includes('and 5 more'));
  });
});
