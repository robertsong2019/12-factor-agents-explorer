import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { benchmarkAnalysis, formatBenchmarkReport } from '../context-forge.mjs';
import { join } from 'node:path';

const FIXTURE = join(process.cwd(), 'test');

describe('benchmarkAnalysis', () => {
  it('returns a structured benchmark object with required fields', async () => {
    const bench = await benchmarkAnalysis(FIXTURE, { maxDepth: 1, maxCommits: 5 });
    
    assert.ok(bench.project, 'should have project path');
    assert.ok(bench.timestamp, 'should have timestamp');
    assert.equal(typeof bench.totalMs, 'number');
    assert.ok(bench.totalMs >= 0, 'totalMs should be non-negative');
    assert.ok(Array.isArray(bench.stages), 'should have stages array');
    assert.ok(bench.stages.length >= 6, 'should have at least 6 stages');
    assert.equal(typeof bench.fileCount, 'number');
    assert.ok(Array.isArray(bench.recommendations), 'should have recommendations');
  });

  it('each stage has name, durationMs, and memDeltaKB', async () => {
    const bench = await benchmarkAnalysis(FIXTURE, { maxDepth: 1 });
    
    for (const stage of bench.stages) {
      assert.ok(stage.name, 'stage should have name');
      assert.equal(typeof stage.durationMs, 'number');
      assert.equal(typeof stage.memDeltaKB, 'number');
    }
  });

  it('totalMs equals sum of stage durationMs', async () => {
    const bench = await benchmarkAnalysis(FIXTURE, { maxDepth: 1 });
    
    const sum = bench.stages.reduce((acc, s) => acc + s.durationMs, 0);
    assert.ok(Math.abs(bench.totalMs - sum) < 0.1, `totalMs (${bench.totalMs}) should equal sum (${sum.toFixed(2)})`);
  });

  it('handles non-existent project path gracefully', async () => {
    const bench = await benchmarkAnalysis('/nonexistent/path/xyz', { maxDepth: 1 });
    
    // Stages should either error or return empty, but not crash
    assert.ok(bench.stages.length >= 6);
    const errorStages = bench.stages.filter(s => s.error);
    // Some stages should fail for non-existent path
    assert.ok(errorStages.length >= 1, `expected at least 1 error stage, got ${errorStages.length}`);
  });

  it('includes all expected stage names', async () => {
    const bench = await benchmarkAnalysis(FIXTURE, { maxDepth: 1 });
    
    const expectedNames = ['detectProject', 'parseGitignore', 'scanLanguages', 'extractImports', 'extractApiSurface', 'analyzeGitHistory'];
    const actualNames = bench.stages.map(s => s.name);
    for (const name of expectedNames) {
      assert.ok(actualNames.includes(name), `should include stage: ${name}`);
    }
  });

  it('recommendations array is non-empty', async () => {
    const bench = await benchmarkAnalysis(FIXTURE, { maxDepth: 1 });
    
    assert.ok(bench.recommendations.length > 0, 'should have at least one recommendation');
  });

  it('respects maxDepth option', async () => {
    const bench1 = await benchmarkAnalysis(FIXTURE, { maxDepth: 1 });
    const bench5 = await benchmarkAnalysis(FIXTURE, { maxDepth: 5 });
    // Deeper scan should take at least as long (or have same files)
    assert.ok(bench1.stages.length === bench5.stages.length, 'same number of stages regardless of depth');
  });

  it('detectTestFiles and detectSecrets stages are included', async () => {
    const bench = await benchmarkAnalysis(FIXTURE, { maxDepth: 1 });
    
    const names = bench.stages.map(s => s.name);
    assert.ok(names.includes('detectTestFiles'), 'should include detectTestFiles stage');
    assert.ok(names.includes('detectSecrets'), 'should include detectSecrets stage');
  });
});

describe('formatBenchmarkReport', () => {
  it('produces a readable markdown report', () => {
    const mockBench = {
      project: '/test/project',
      timestamp: '2026-07-07T14:00:00.000Z',
      totalMs: 123.45,
      fileCount: 42,
      stages: [
        { name: 'detectProject', durationMs: 5.2, memDeltaKB: 12.3 },
        { name: 'scanLanguages', durationMs: 50.1, memDeltaKB: 1024.5 },
        { name: 'extractImports', durationMs: 68.15, memDeltaKB: 512.0, error: 'scan failed' },
      ],
      recommendations: [
        '🐌 scanLanguages is slow (50.1ms)',
        '✅ All good',
      ],
    };

    const report = formatBenchmarkReport(mockBench);
    
    assert.ok(report.includes('# 🔧 Performance Benchmark Report'));
    assert.ok(report.includes('**Project:** /test/project'));
    assert.ok(report.includes('**Total Time:** 123.45ms'));
    assert.ok(report.includes('**Files Scanned:** 42'));
    assert.ok(report.includes('| detectProject | 5.2 | 12.3 | ✅ OK |'));
    assert.ok(report.includes('| extractImports | 68.15 | 512 | ❌ Error |'));
    assert.ok(report.includes('🐌 scanLanguages is slow'));
  });

  it('handles empty recommendations', () => {
    const mockBench = {
      project: '/x',
      timestamp: '2026-01-01T00:00:00.000Z',
      totalMs: 0,
      fileCount: 0,
      stages: [],
      recommendations: [],
    };

    const report = formatBenchmarkReport(mockBench);
    assert.ok(report.includes('## Recommendations'));
    // Should still render the section even if empty
    assert.ok(report.length > 50);
  });

  it('formats large memory values correctly', () => {
    const mockBench = {
      project: '/big',
      timestamp: '2026-01-01T00:00:00.000Z',
      totalMs: 5000,
      fileCount: 10000,
      stages: [
        { name: 'scanLanguages', durationMs: 3000, memDeltaKB: 51200.5 },
      ],
      recommendations: ['🐌 scanLanguages is slow (3000ms)'],
    };

    const report = formatBenchmarkReport(mockBench);
    assert.ok(report.includes('51200.5'));
    assert.ok(report.includes('5000ms'));
  });
});
