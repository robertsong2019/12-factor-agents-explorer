import { test } from 'node:test';
import assert from 'node:assert';
import { analyzeTestCoverage, formatTestCoverageReport } from '../context-forge.mjs';

test('analyzeTestCoverage — empty files returns safe result', () => {
  const result = analyzeTestCoverage([]);
  assert.equal(result.testFileCount, 0);
  assert.equal(result.sourceFileCount, 0);
});

test('analyzeTestCoverage — null input safe', () => {
  const result = analyzeTestCoverage(null);
  assert.equal(result.testFileCount, 0);
});

test('analyzeTestCoverage — separates test and source files', () => {
  const files = [
    { path: 'src/add.js', content: 'export const add = (a,b) => a+b;' },
    { path: 'test/add.test.js', content: 'import { test } from "node:test"; test("add", () => {});' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.sourceFileCount, 1);
  assert.equal(result.testFileCount, 1);
});

test('analyzeTestCoverage — maps test to source via .test. pattern', () => {
  const files = [
    { path: 'src/utils.js', content: 'export const x = 1;' },
    { path: 'src/utils.test.js', content: 'import { test } from "node:test"; test("x", () => {});' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.testedCount, 1);
  assert.equal(result.untestedCount, 0);
});

test('analyzeTestCoverage — maps test to source via .spec. pattern', () => {
  const files = [
    { path: 'src/api.ts', content: 'export function fetch() {}' },
    { path: 'src/api.spec.ts', content: 'import { describe } from "vitest";' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.testedCount, 1);
});

test('analyzeTestCoverage — detects untested files', () => {
  const files = [
    { path: 'src/a.js', content: 'export const a = 1;' },
    { path: 'src/b.js', content: 'export const b = 2;' },
    { path: 'src/a.test.js', content: 'test("a", () => {});' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.testedCount, 1);
  assert.equal(result.untestedCount, 1);
  assert.ok(result.untested.some(u => u.path.includes('b.js')));
});

test('analyzeTestCoverage — detects node:test framework', () => {
  const files = [
    { path: 'test/x.test.mjs', content: 'import { test } from "node:test";' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.frameworks.includes('node_test'));
});

test('analyzeTestCoverage — detects jest framework', () => {
  const files = [
    { path: 'test/y.test.js', content: 'describe("suite", () => { it("works", () => {}); });' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.frameworks.includes('jest'));
});

test('analyzeTestCoverage — detects vitest framework', () => {
  const files = [
    { path: 'test/z.test.ts', content: 'import { describe, it } from "vitest";' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.frameworks.includes('vitest'));
});

test('analyzeTestCoverage — detects pytest framework', () => {
  const files = [
    { path: 'test/test_foo.py', content: 'import pytest\\ndef test_foo():\\n    assert True' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.frameworks.includes('pytest'));
});

test('analyzeTestCoverage — detects go test framework', () => {
  const files = [
    { path: 'main_test.go', content: 'func TestSomething(t *testing.T) {}' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.frameworks.includes('go_test'));
});

test('analyzeTestCoverage — detects __tests__ directory pattern', () => {
  const files = [
    { path: 'src/app.js', content: 'const x = 1;' },
    { path: 'src/__tests__/app.test.js', content: 'test("app", () => {});' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.testFileCount >= 1);
});

test('analyzeTestCoverage — coverage ratio correct', () => {
  const files = [
    { path: 'a.js', content: 'x' },
    { path: 'b.js', content: 'x' },
    { path: 'c.js', content: 'x' },
    { path: 'd.js', content: 'x' },
    { path: 'a.test.js', content: 'test()' },
    { path: 'b.test.js', content: 'test()' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.coverageRatio, 0.5);
});

test('analyzeTestCoverage — high coverage gets good grade', () => {
  const files = [
    { path: 'a.js', content: 'x' },
    { path: 'a.test.js', content: 'import { test } from "node:test"; test()' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.score >= 90, `expected >= 90, got ${result.score}`);
  assert.equal(result.grade, 'A');
});

test('analyzeTestCoverage — low coverage gets poor grade', () => {
  const files = [
    { path: 'a.js', content: 'x' },
    { path: 'b.js', content: 'x' },
    { path: 'c.js', content: 'x' },
    { path: 'd.js', content: 'x' },
    { path: 'e.js', content: 'x' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.score < 50, `expected < 50, got ${result.score}`);
});

test('analyzeTestCoverage — flags low coverage issue', () => {
  const files = [];
  for (let i = 0; i < 10; i++) files.push({ path: `src${i}.js`, content: 'x' });
  files.push({ path: 'src0.test.js', content: 'test()' });
  const result = analyzeTestCoverage(files);
  assert.ok(result.issues.some(i => i.type === 'low_coverage'));
});

test('analyzeTestCoverage — flags unknown framework', () => {
  const files = [
    { path: 'src/x.js', content: 'x' },
    { path: 'src/x.test.js', content: 'assertEqual(1,1)' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.issues.some(i => i.type === 'unknown_framework'));
});

test('analyzeTestCoverage — untested list sorted by size descending', () => {
  const files = [
    { path: 'big.js', content: 'a\\n'.repeat(100) },
    { path: 'small.js', content: 'a' },
    { path: 'big.test.js', content: 'test()' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.untested[0].path, 'small.js');
});

test('analyzeTestCoverage — non-source files ignored', () => {
  const files = [
    { path: 'README.md', content: '# readme' },
    { path: 'config.json', content: '{}' },
    { path: 'app.js', content: 'x' },
  ];
  const result = analyzeTestCoverage(files);
  assert.equal(result.sourceFileCount, 1);
});

test('analyzeTestCoverage — mappings show test-to-source', () => {
  const files = [
    { path: 'lib.ts', content: 'x' },
    { path: 'lib.test.ts', content: 'test()' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.mappings.some(m => m.source === 'lib.ts'));
});

test('analyzeTestCoverage — test with no source match gets null', () => {
  const files = [
    { path: 'orphan.test.js', content: 'test()' },
  ];
  const result = analyzeTestCoverage(files);
  assert.ok(result.mappings.some(m => m.source === null));
});

test('formatTestCoverageReport — null returns warning', () => {
  const report = formatTestCoverageReport(null);
  assert.ok(report.includes('No file data'));
});

test('formatTestCoverageReport — includes grade and frameworks', () => {
  const result = analyzeTestCoverage([
    { path: 'x.js', content: 'x' },
    { path: 'x.test.js', content: 'import { test } from "node:test"; test()' },
  ]);
  const report = formatTestCoverageReport(result);
  assert.ok(report.includes('Grade'));
  assert.ok(report.includes('node_test'));
});

test('formatTestCoverageReport — includes untested files table', () => {
  const result = analyzeTestCoverage([
    { path: 'tested.js', content: 'x' },
    { path: 'untested.js', content: 'y' },
    { path: 'tested.test.js', content: 'test()' },
  ]);
  const report = formatTestCoverageReport(result);
  assert.ok(report.includes('Untested'));
  assert.ok(report.includes('untested.js'));
});

test('formatTestCoverageReport — includes mappings section', () => {
  const result = analyzeTestCoverage([
    { path: 'a.js', content: 'x' },
    { path: 'a.test.js', content: 'test()' },
  ]);
  const report = formatTestCoverageReport(result);
  assert.ok(report.includes('Mappings') || report.includes('→'));
});
