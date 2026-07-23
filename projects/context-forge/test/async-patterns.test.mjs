import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeAsyncPatterns, formatAsyncPatternsReport } from '../context-forge.mjs';

describe('F56: analyzeAsyncPatterns()', () => {
  it('returns empty result for no files', () => {
    const result = analyzeAsyncPatterns([]);
    assert.equal(result.fileCount, 0);
    assert.equal(result.totalAsyncFunctions, 0);
    assert.equal(result.grade, 'F');
  });

  it('skips non-JS files', () => {
    const result = analyzeAsyncPatterns([
      { path: 'script.py', content: 'async def foo():\n  pass' },
      { path: 'readme.md', content: '# Title' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('detects async functions', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'async function fetchData() {\n  return await fetch("/api");\n}' },
    ]);
    assert.equal(result.totalAsyncFunctions, 1);
    assert.equal(result.totalAwaitUsage, 1);
  });

  it('detects arrow async functions', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.ts', content: 'const handler = async (req, res) => {\n  const data = await process(req);\n  res.json(data);\n};' },
    ]);
    assert.equal(result.totalAsyncFunctions, 1);
    assert.equal(result.totalAwaitUsage, 1);
  });

  it('detects Promise .then() chains', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'fetch("/api").then(r => r.json()).then(data => console.log(data)).catch(e => console.error(e));' },
    ]);
    assert.ok(result.totalPromiseChains >= 2);
  });

  it('flags unhandled rejection (no .catch)', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'fetch("/api").then(r => r.json()).then(data => console.log(data));' },
    ]);
    assert.ok(result.totalUnhandledRejections >= 1);
    assert.ok(result.files[0].issues.some(i => i.type === 'unhandled_rejection'));
  });

  it('does not flag unhandled rejection when .catch exists', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'fetch("/api").then(r => r.json()).catch(e => console.error(e));' },
    ]);
    assert.equal(result.totalUnhandledRejections, 0);
  });

  it('flags floating promises (new Promise without await/return)', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'new Promise((resolve) => {\n  setTimeout(resolve, 100);\n});\nconsole.log("done");' },
    ]);
    assert.ok(result.totalFloatingPromises >= 1);
    assert.ok(result.files[0].issues.some(i => i.type === 'floating_promise'));
  });

  it('does not flag new Promise with await', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'await new Promise((resolve) => {\n  setTimeout(resolve, 100);\n});' },
    ]);
    assert.equal(result.totalFloatingPromises, 0);
  });

  it('flags missing await on fetch()', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'function load() {\n  fetch("/api");\n}' },
    ]);
    assert.ok(result.totalMissingAwait >= 1);
    assert.ok(result.files[0].issues.some(i => i.type === 'missing_await'));
  });

  it('does not flag fetch with await', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'async function load() {\n  const r = await fetch("/api");\n  return r;\n}' },
    ]);
    assert.equal(result.totalMissingAwait, 0);
  });

  it('flags missing await on *Async function naming', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'function load() {\n  loadDataAsync();\n}' },
    ]);
    assert.ok(result.totalMissingAwait >= 1);
  });

  it('detects callback patterns', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'fs.readFile("path", (err, data) => {\n  if (err) throw err;\n  console.log(data);\n});' },
    ]);
    assert.ok(result.totalCallbacks >= 1);
  });

  it('detects callback hell (3+ nesting levels)', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'a((err, res1) => {\n  b(res1, (err, res2) => {\n    c(res2, (err, res3) => {\n      console.log(res3);\n    });\n  });\n});' },
    ]);
    assert.ok(result.totalCallbackHell >= 1);
  });

  it('skips comment lines', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: '// async function commented() {}\n// await fetch("/api")\n// fetch("/api").then(r => r)' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('handles empty content gracefully', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: '' },
    ]);
    assert.equal(result.fileCount, 0);
  });

  it('handles .mjs files', () => {
    const result = analyzeAsyncPatterns([
      { path: 'mod.mjs', content: 'export async function run() {\n  await Promise.resolve(42);\n}' },
    ]);
    assert.equal(result.totalAsyncFunctions, 1);
    assert.equal(result.totalAwaitUsage, 1);
  });

  it('handles .ts files', () => {
    const result = analyzeAsyncPatterns([
      { path: 'svc.ts', content: 'async function init(): Promise<void> {\n  await setup();\n}' },
    ]);
    assert.equal(result.totalAsyncFunctions, 1);
  });

  it('healthScore is 0-100', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'fetch("/x").then(r => r.json());' },
    ]);
    assert.ok(result.healthScore >= 0 && result.healthScore <= 100);
  });

  it('grade is valid letter', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'async function good() {\n  await fetch("/api");\n}' },
    ]);
    assert.ok(['A', 'B', 'C', 'D', 'F'].includes(result.grade));
  });
});

describe('F56: formatAsyncPatternsReport()', () => {
  it('handles empty result', () => {
    const report = formatAsyncPatternsReport({ fileCount: 0 });
    assert.ok(report.includes('No async code'));
  });

  it('includes health grade and stats', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'async function fn() {\n  await fetch("/api");\n}' },
    ]);
    const report = formatAsyncPatternsReport(result);
    assert.ok(report.includes('Health Grade'));
    assert.ok(report.includes('Async functions'));
    assert.ok(report.includes('Await calls'));
  });

  it('includes risk summary when issues exist', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'fetch("/x").then(r => r.json());' },
    ]);
    const report = formatAsyncPatternsReport(result);
    assert.ok(report.includes('Risk Summary') || report.includes('Critical Issues') || report.includes('Unhandled'));
  });

  it('includes per-file breakdown', () => {
    const result = analyzeAsyncPatterns([
      { path: 'a.js', content: 'async function a() { await x(); }' },
      { path: 'b.js', content: 'fetch("/x").then(r => r);' },
    ]);
    const report = formatAsyncPatternsReport(result);
    assert.ok(report.includes('Per-file Breakdown'));
    assert.ok(report.includes('a.js'));
  });
});
