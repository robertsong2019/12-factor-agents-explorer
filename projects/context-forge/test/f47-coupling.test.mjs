import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeFileCoupling, formatCouplingReport } from '../context-forge.mjs';

describe('F47: analyzeFileCoupling', () => {
  it('detects files sharing dependencies', () => {
    const importData = {
      imports: new Map([
        ['src/a.js', ['react', 'lodash', 'axios']],
        ['src/b.js', ['react', 'lodash', 'express']],
        ['src/c.js', ['vue', 'axios']],
      ]),
      allImports: ['react', 'lodash', 'axios', 'express', 'vue'],
    };
    const result = analyzeFileCoupling(importData);
    // a.js and b.js share react + lodash = 2
    const pair = result.couples.find(c =>
      (c.fileA === 'src/a.js' && c.fileB === 'src/b.js') ||
      (c.fileA === 'src/b.js' && c.fileB === 'src/a.js')
    );
    assert.ok(pair, 'should find a.js and b.js coupled');
    assert.ok(pair.sharedCount >= 2);
    assert.ok(pair.jaccard > 0);
  });

  it('returns empty for no imports', () => {
    const importData = { imports: new Map(), allImports: [] };
    const result = analyzeFileCoupling(importData);
    assert.equal(result.totalFiles, 0);
    assert.equal(result.couples.length, 0);
  });

  it('skips pairs with < 2 shared deps', () => {
    const importData = {
      imports: new Map([
        ['x.js', ['react']],
        ['y.js', ['react']],
      ]),
      allImports: ['react'],
    };
    const result = analyzeFileCoupling(importData);
    // Only 1 shared dep → filtered out
    assert.equal(result.couples.length, 0);
  });

  it('computes Jaccard similarity correctly', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['lib1', 'lib2', 'lib3']],
        ['b.js', ['lib1', 'lib2', 'lib4']],
      ]),
      allImports: ['lib1', 'lib2', 'lib3', 'lib4'],
    };
    const result = analyzeFileCoupling(importData);
    const pair = result.couples[0];
    // intersection = 2 (lib1, lib2), union = 4 → Jaccard = 0.5
    assert.equal(pair.sharedCount, 2);
    assert.equal(pair.jaccard, 0.5);
  });

  it('calculates per-file coupling score', () => {
    const importData = {
      imports: new Map([
        ['hub.js', ['react', 'lodash', 'axios']],
        ['spoke1.js', ['react', 'lodash', 'axios']],
        ['spoke2.js', ['react', 'lodash', 'axios']],
      ]),
      allImports: ['react', 'lodash', 'axios'],
    };
    const result = analyzeFileCoupling(importData);
    // hub.js shares 3 deps with both spoke1 and spoke2
    const hub = result.mostCoupled.find(f => f.file === 'hub.js');
    assert.ok(hub);
    assert.ok(hub.couplingScore >= 6, `expected >= 6, got ${hub.couplingScore}`);
  });

  it('sorts couples by shared count descending', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['lib1', 'lib2', 'lib3', 'lib4']],
        ['b.js', ['lib1', 'lib2', 'lib3', 'lib4']],
        ['c.js', ['lib1', 'lib2']],
      ]),
      allImports: ['lib1', 'lib2', 'lib3', 'lib4'],
    };
    const result = analyzeFileCoupling(importData);
    assert.ok(result.couples[0].sharedCount >= result.couples[result.couples.length - 1].sharedCount);
  });

  it('computes coupling ratio', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['x', 'y']],
        ['b.js', ['x', 'y']],
      ]),
      allImports: ['x', 'y'],
    };
    const result = analyzeFileCoupling(importData);
    // 2 files, 1 possible pair, 1 coupled pair → ratio = 1
    assert.equal(result.avgCoupling, 1);
  });

  it('tracks shared dependencies', () => {
    const importData = {
      imports: new Map([
        ['a.js', ['react', 'lodash']],
        ['b.js', ['react', 'lodash']],
        ['c.js', ['react', 'lodash']],
      ]),
      allImports: ['react', 'lodash'],
    };
    const result = analyzeFileCoupling(importData);
    assert.ok(result.sharedDeps.length > 0);
    const react = result.sharedDeps.find(d => d.dep === 'react');
    assert.ok(react, 'react should be in shared deps');
    assert.ok(react.coupledPairs >= 1);
  });

  it('limits couples to top 15', () => {
    const imports = new Map();
    const allImports = [];
    // Create 10 files all sharing same deps → 45 pairs
    for (let i = 0; i < 10; i++) {
      imports.set(`file${i}.js`, ['react', 'lodash', 'axios']);
      allImports.push('react', 'lodash', 'axios');
    }
    const result = analyzeFileCoupling({ imports, allImports });
    assert.ok(result.couples.length <= 15);
    assert.ok(result.totalCouples === 45);
  });

  it('handles single file', () => {
    const importData = {
      imports: new Map([['solo.js', ['react', 'lodash']]]),
      allImports: ['react', 'lodash'],
    };
    const result = analyzeFileCoupling(importData);
    assert.equal(result.totalFiles, 1);
    assert.equal(result.couples.length, 0);
    assert.equal(result.avgCoupling, 0);
  });
});

describe('F47: formatCouplingReport', () => {
  it('formats a complete report', () => {
    const analysis = {
      couples: [
        { fileA: 'src/a.js', fileB: 'src/b.js', sharedCount: 5, jaccard: 0.8 },
        { fileA: 'src/c.js', fileB: 'src/d.js', sharedCount: 3, jaccard: 0.5 },
      ],
      totalFiles: 10,
      totalCouples: 15,
      avgCoupling: 0.3,
      mostCoupled: [
        { file: 'src/a.js', couplingScore: 20 },
        { file: 'src/b.js', couplingScore: 15 },
      ],
      sharedDeps: [
        { dep: 'react', coupledPairs: 8 },
        { dep: 'lodash', coupledPairs: 5 },
      ],
    };
    const report = formatCouplingReport(analysis);
    assert.ok(report.includes('### File Coupling'));
    assert.ok(report.includes('| Files analyzed | 10 |'));
    assert.ok(report.includes('#### Most Coupled Files'));
    assert.ok(report.includes('#### Top Coupled Pairs'));
    assert.ok(report.includes('#### Shared Dependencies'));
    assert.ok(report.includes('`react`'));
    assert.ok(report.includes('`src/a.js`'));
  });

  it('handles empty analysis', () => {
    const report = formatCouplingReport({ couples: [] });
    assert.ok(report.includes('No coupled files detected'));
  });

  it('handles null input', () => {
    const report = formatCouplingReport(null);
    assert.ok(report.includes('No coupled files detected'));
  });

  it('omits shared deps section when none', () => {
    const analysis = {
      couples: [{ fileA: 'a.js', fileB: 'b.js', sharedCount: 2, jaccard: 0.5 }],
      totalFiles: 2,
      totalCouples: 1,
      avgCoupling: 1,
      mostCoupled: [{ file: 'a.js', couplingScore: 2 }],
      sharedDeps: [],
    };
    const report = formatCouplingReport(analysis);
    assert.ok(!report.includes('#### Shared Dependencies'));
  });
});
