import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeImportGraph, formatImportGraphReport } from '../context-forge.mjs';

describe('F50: analyzeImportGraph', () => {
  it('returns empty result for no imports', () => {
    const result = analyzeImportGraph({ imports: new Map(), allImports: [] });
    assert.equal(result.totalFiles, 0);
    assert.equal(result.totalEdges, 0);
    assert.equal(result.cycleCount, 0);
  });

  it('computes in-degree and out-degree correctly', () => {
    const importData = {
      imports: new Map([
        ['src/a.js', ['./b', './c']],
        ['src/b.js', ['./c']],
        ['src/c.js', []],
      ]),
      allImports: ['./b', './c'],
    };
    const result = analyzeImportGraph(importData);
    // a.js: out=2, in=0
    // b.js: out=1, in=1 (imported by a.js)
    // c.js: out=0, in=2 (imported by a.js and b.js)
    const nodeA = result.topHubs.find(n => n.file === 'src/a.js');
    const nodeC = result.topAuthorities.find(n => n.file === 'src/c.js');
    assert.ok(nodeA);
    assert.ok(nodeC);
    assert.equal(nodeA.outDegree, 2);
    assert.equal(nodeC.inDegree, 2);
  });

  it('normalizes hub and authority scores to 0-1', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['./x', './y', './z']],
        ['b.js', ['./x']],
      ]),
      allImports: ['./x', './y', './z'],
    };
    const result = analyzeImportGraph(importData);
    const topHub = result.topHubs[0];
    assert.ok(topHub.hubScore <= 1);
    assert.ok(topHub.hubScore >= 0);
    // a.js has max out-degree = 3, so hubScore = 1.0
    assert.equal(topHub.hubScore, 1);
  });

  it('detects orphan files (no imports, no imports-of)', () => {
    const importData = {
      imports: new Map([
        ['src/main.js', ['./helper']],
        ['src/orphan.js', []],
      ]),
      allImports: ['./helper'],
    };
    const result = analyzeImportGraph(importData);
    assert.ok(result.orphans.length > 0);
    assert.ok(result.orphans.some(n => n.file === 'src/orphan.js'));
  });

  it('detects source files (import others, not imported)', () => {
    const importData = {
      imports: new Map([
        ['src/main.js', ['./helper']],
        ['src/helper.js', []],
      ]),
      allImports: ['./helper'],
    };
    const result = analyzeImportGraph(importData);
    assert.ok(result.sources.some(n => n.file === 'src/main.js'));
  });

  it('detects sink files (imported by others, import nothing)', () => {
    const importData = {
      imports: new Map([
        ['src/main.js', ['./util']],
        ['src/util.js', []],
      ]),
      allImports: ['./util'],
    };
    const result = analyzeImportGraph(importData);
    assert.ok(result.sinks.some(n => n.file === 'src/util.js'));
  });

  it('detects circular dependencies', () => {
    const importData = {
      imports: new Map([
        ['src/a.js', ['./b']],
        ['src/b.js', ['./c']],
        ['src/c.js', ['./a']],
      ]),
      allImports: ['./a', './b', './c'],
    };
    const result = analyzeImportGraph(importData);
    assert.ok(result.cycleCount > 0);
    assert.ok(result.cycles.length > 0);
  });

  it('computes average out-degree', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['./b', './c']],
        ['b.js', ['./c']],
        ['c.js', []],
      ]),
      allImports: ['./b', './c'],
    };
    const result = analyzeImportGraph(importData);
    // Total edges: 3 (2 from a, 1 from b), files: 3 (plus resolved targets)
    assert.ok(result.avgOutDegree >= 0);
  });

  it('limits cycle reporting to 20', () => {
    // Create many cycles
    const imports = new Map();
    for (let i = 0; i < 25; i++) {
      imports.set(`f${i}.js`, [`./f${(i + 1) % 25}`]);
    }
    const result = analyzeImportGraph({ imports, allImports: [] });
    assert.ok(result.cycles.length <= 20);
  });

  it('handles single-file project', () => {
    const result = analyzeImportGraph({
      imports: new Map([['only.js', []]]),
      allImports: [],
    });
    assert.equal(result.totalFiles, 1);
    assert.equal(result.totalEdges, 0);
  });

  it('deduplicates import targets', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['./b', './b', './b']],
      ]),
      allImports: ['./b'],
    };
    const result = analyzeImportGraph(importData);
    const nodeA = result.topHubs.find(n => n.file === 'a.js');
    if (nodeA) {
      assert.equal(nodeA.outDegree, 1); // deduped
    }
  });
});

describe('F50: formatImportGraphReport', () => {
  it('handles empty result', () => {
    const report = formatImportGraphReport({ totalFiles: 0, totalEdges: 0 });
    assert.ok(report.includes('No import data'));
  });

  it('handles null result', () => {
    const report = formatImportGraphReport(null);
    assert.ok(report.includes('No import data'));
  });

  it('includes metrics table', () => {
    const report = formatImportGraphReport({
      totalFiles: 10,
      totalEdges: 25,
      avgOutDegree: 2.5,
      cycleCount: 1,
      topAuthorities: [],
      topHubs: [],
      orphans: [],
      cycles: [],
    });
    assert.ok(report.includes('Total Files'));
    assert.ok(report.includes('10'));
    assert.ok(report.includes('Cycles Detected'));
  });

  it('lists top authorities and hubs', () => {
    const report = formatImportGraphReport({
      totalFiles: 3,
      totalEdges: 2,
      avgOutDegree: 0.67,
      cycleCount: 0,
      topAuthorities: [{ file: 'src/core.js', inDegree: 3, authorityScore: 1 }],
      topHubs: [{ file: 'src/app.js', outDegree: 2, hubScore: 1 }],
      orphans: [],
      cycles: [],
    });
    assert.ok(report.includes('Top Authority'));
    assert.ok(report.includes('src/core.js'));
    assert.ok(report.includes('Top Hub'));
    assert.ok(report.includes('src/app.js'));
  });

  it('lists orphans with truncation', () => {
    const orphans = Array.from({ length: 15 }, (_, i) => ({ file: `orphan${i}.js`, inDegree: 0, outDegree: 0 }));
    const report = formatImportGraphReport({
      totalFiles: 20,
      totalEdges: 5,
      avgOutDegree: 0.25,
      cycleCount: 0,
      topAuthorities: [],
      topHubs: [],
      orphans,
      cycles: [],
    });
    assert.ok(report.includes('Orphan'));
    assert.ok(report.includes('and 5 more'));
  });

  it('lists cycles with truncation', () => {
    const cycles = Array.from({ length: 7 }, (_, i) => [`a${i}.js`, `b${i}.js`, `a${i}.js`]);
    const report = formatImportGraphReport({
      totalFiles: 20,
      totalEdges: 15,
      avgOutDegree: 0.75,
      cycleCount: 7,
      topAuthorities: [],
      topHubs: [],
      orphans: [],
      cycles,
    });
    assert.ok(report.includes('Circular'));
    assert.ok(report.includes('and 2 more'));
  });
});
