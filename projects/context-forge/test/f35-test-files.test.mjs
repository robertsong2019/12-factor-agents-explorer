import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { detectTestFiles, formatTestFilesReport } from '../context-forge.mjs';

function makeFixture() {
  const dir = mkdtempSync(join(tmpdir(), 'cf-test-f35-'));
  writeFileSync(join(dir, 'app.test.js'), 'test("adds", () => { expect(1+1).toBe(2) });');
  writeFileSync(join(dir, 'utils.spec.ts'), 'it("works", () => {});');
  writeFileSync(join(dir, 'test_main.py'), 'def test_hello(): pass');
  writeFileSync(join(dir, 'helpers_test.py'), 'def test_helper(): pass');
  writeFileSync(join(dir, 'conftest.py'), 'import pytest');
  writeFileSync(join(dir, 'handler_test.go'), 'func TestHandler(t *testing.T) {}');
  writeFileSync(join(dir, 'index.js'), 'console.log("hello");');
  writeFileSync(join(dir, 'README.md'), '# Project');
  mkdirSync(join(dir, 'src'));
  writeFileSync(join(dir, 'src', 'api.test.js'), 'test("api", () => {});');
  writeFileSync(join(dir, 'src', 'logic.js'), 'export function add(a,b) { return a+b; }');
  return dir;
}

describe('F35: detectTestFiles', () => {
  it('finds all test files in a project', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      assert.ok(result.files.length >= 6, `Expected >= 6 test files, got ${result.files.length}`);
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('detects jest framework for .test.js files', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const jestFiles = result.files.filter(f => f.framework === 'jest');
      assert.ok(jestFiles.length >= 2, `Expected >= 2 jest files, got ${jestFiles.length}`);
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('detects pytest framework for test_*.py files', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const pytestFiles = result.files.filter(f => f.framework === 'pytest');
      assert.ok(pytestFiles.length >= 2, `Expected >= 2 pytest files`);
      assert.ok(pytestFiles.some(f => f.name === 'test_main.py'));
      assert.ok(pytestFiles.some(f => f.name === 'helpers_test.py'));
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('detects conftest.py as pytest', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const conftest = result.files.find(f => f.name === 'conftest.py');
      assert.ok(conftest, 'conftest.py should be detected');
      assert.equal(conftest.framework, 'pytest');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('detects go test files', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const goFiles = result.files.filter(f => f.framework === 'go_test');
      assert.ok(goFiles.length >= 1, 'Expected at least 1 go test file');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('finds nested test files', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const nested = result.files.find(f => f.name === 'api.test.js' && f.path.includes('src'));
      assert.ok(nested, 'Should find nested test file in src/');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('does not classify non-test files', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const nonTest = result.files.find(f => f.name === 'index.js' || f.name === 'README.md');
      assert.ok(!nonTest, 'Non-test files should not appear in results');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('returns empty for directory with no tests', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'cf-empty-'));
    writeFileSync(join(dir, 'index.js'), 'console.log("hi")');
    try {
      const result = await detectTestFiles(dir);
      assert.equal(result.files.length, 0);
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('respects maxDepth parameter', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'cf-depth-'));
    mkdirSync(join(dir, 'a', 'b', 'c'), { recursive: true });
    writeFileSync(join(dir, 'a', 'b', 'c', 'deep.test.js'), 'test("deep", () => {});');
    try {
      const shallow = await detectTestFiles(dir, 2);
      const deep = await detectTestFiles(dir, 5);
      assert.equal(shallow.files.length, 0, 'Should not find deeply nested test at depth 2');
      assert.ok(deep.files.length >= 1, 'Should find deeply nested test at depth 5');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('skips node_modules and dist directories', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'cf-skip-'));
    mkdirSync(join(dir, 'node_modules'), { recursive: true });
    mkdirSync(join(dir, 'dist'), { recursive: true });
    writeFileSync(join(dir, 'node_modules', 'lib.test.js'), 'test("skip", () => {});');
    writeFileSync(join(dir, 'dist', 'bundle.test.js'), 'test("skip", () => {});');
    writeFileSync(join(dir, 'real.test.js'), 'test("keep", () => {});');
    try {
      const result = await detectTestFiles(dir);
      assert.equal(result.files.length, 1, 'Should only find real.test.js');
      assert.equal(result.files[0].name, 'real.test.js');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });
});

describe('F35: formatTestFilesReport', () => {
  it('formats a report with multiple frameworks', async () => {
    const dir = makeFixture();
    try {
      const result = await detectTestFiles(dir);
      const report = formatTestFilesReport(result);
      assert.ok(report.includes('🧪'), 'Should have test emoji');
      assert.ok(report.includes('jest'), 'Should mention jest');
      assert.ok(report.includes('pytest'), 'Should mention pytest');
    } finally { rmSync(dir, { recursive: true, force: true }); }
  });

  it('handles empty result gracefully', () => {
    const report = formatTestFilesReport({ files: [] });
    assert.ok(report.includes('No test files'), 'Should warn about missing tests');
  });

  it('handles null/undefined result', () => {
    const report = formatTestFilesReport(null);
    assert.ok(report.includes('No test files'), 'Should handle null');
  });

  it('truncates long file lists', () => {
    const files = Array.from({ length: 25 }, (_, i) => ({ path: `/t${i}.test.js`, name: `t${i}.test.js`, framework: 'jest' }));
    const report = formatTestFilesReport({ files });
    assert.ok(report.includes('more'), 'Should show truncation message');
  });
});
