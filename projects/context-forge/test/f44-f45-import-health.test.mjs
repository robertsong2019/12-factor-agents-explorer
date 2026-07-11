import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeImportHealth, formatImportHealthReport } from '../context-forge.mjs';

describe('F44: analyzeImportHealth', () => {
  it('identifies unused dependencies', () => {
    const info = {
      pkg: {
        dependencies: { express: '^4.0.0', lodash: '^4.0.0', unused: '^1.0.0' },
        devDependencies: {},
      },
    };
    const importData = {
      allImports: ['express', 'lodash', 'lodash'],
      imports: new Map([
        ['app.js', ['express', 'lodash']],
        ['utils.js', ['lodash']],
      ]),
    };
    const result = analyzeImportHealth(info, importData);
    assert.ok(result.unusedDeps.includes('unused'));
    assert.ok(!result.unusedDeps.includes('express'));
    assert.ok(!result.unusedDeps.includes('lodash'));
  });

  it('counts import frequency correctly', () => {
    const info = { pkg: { dependencies: {}, devDependencies: {} } };
    const importData = {
      allImports: ['react', 'react', 'react', 'axios', 'lodash', 'lodash'],
      imports: new Map(),
    };
    const result = analyzeImportHealth(info, importData);
    assert.equal(result.totalImports, 6);
    assert.equal(result.uniqueImports, 3);
    assert.equal(result.mostImported[0].name, 'react');
    assert.equal(result.mostImported[0].count, 3);
    assert.equal(result.mostImported[1].name, 'lodash');
    assert.equal(result.mostImported[1].count, 2);
  });

  it('calculates diversity score correctly', () => {
    const info = { pkg: { dependencies: {}, devDependencies: {} } };
    // 4 unique out of 8 total = 0.5
    const importData = {
      allImports: ['a', 'a', 'b', 'b', 'c', 'c', 'd', 'd'],
      imports: new Map(),
    };
    const result = analyzeImportHealth(info, importData);
    assert.equal(result.diversityScore, 0.5);
  });

  it('handles scoped packages (@scope/name)', () => {
    const info = { pkg: { dependencies: {}, devDependencies: {} } };
    const importData = {
      allImports: ['@myorg/utils', '@myorg/utils/helpers', '@other/lib'],
      imports: new Map(),
    };
    const result = analyzeImportHealth(info, importData);
    assert.equal(result.uniqueImports, 2); // @myorg/utils and @other/lib
    assert.equal(result.mostImported[0].name, '@myorg/utils');
    assert.equal(result.mostImported[0].count, 2);
  });

  it('returns empty unused when all deps are used', () => {
    const info = {
      pkg: {
        dependencies: { express: '^4.0.0' },
        devDependencies: {},
      },
    };
    const importData = {
      allImports: ['express'],
      imports: new Map([['app.js', ['express']]]),
    };
    const result = analyzeImportHealth(info, importData);
    assert.deepEqual(result.unusedDeps, []);
  });

  it('ignores @types/* packages in unused detection', () => {
    const info = {
      pkg: {
        dependencies: {},
        devDependencies: { '@types/node': '^18.0.0' },
      },
    };
    const importData = { allImports: [], imports: new Map() };
    const result = analyzeImportHealth(info, importData);
    assert.deepEqual(result.unusedDeps, []);
  });

  it('handles empty imports', () => {
    const info = { pkg: { dependencies: {}, devDependencies: {} } };
    const importData = { allImports: [], imports: new Map() };
    const result = analyzeImportHealth(info, importData);
    assert.equal(result.totalImports, 0);
    assert.equal(result.uniqueImports, 0);
    assert.equal(result.diversityScore, 0);
    assert.equal(result.avgImportsPerFile, 0);
    assert.deepEqual(result.unusedDeps, []);
  });

  it('calculates avg imports per file', () => {
    const info = { pkg: { dependencies: {}, devDependencies: {} } };
    const importData = {
      allImports: ['a', 'b', 'c', 'd', 'e'],
      imports: new Map([
        ['f1.js', ['a', 'b']],
        ['f2.js', ['c', 'd', 'e']],
      ]),
    };
    const result = analyzeImportHealth(info, importData);
    assert.equal(result.filesWithImports, 2);
    assert.equal(result.avgImportsPerFile, 2.5);
  });
});

describe('F45: formatImportHealthReport', () => {
  it('formats null result gracefully', () => {
    const report = formatImportHealthReport(null);
    assert.ok(report.includes('No import data available'));
  });

  it('includes key metrics in header', () => {
    const data = {
      unusedDeps: [],
      mostImported: [{ name: 'react', count: 5 }],
      totalImports: 10,
      uniqueImports: 3,
      diversityScore: 0.3,
      avgImportsPerFile: 2.5,
      filesWithImports: 4,
      declaredCount: 3,
    };
    const report = formatImportHealthReport(data);
    assert.ok(report.includes('**Total imports:** 10'));
    assert.ok(report.includes('**Unique packages:** 3'));
    assert.ok(report.includes('**Diversity score:** 0.3'));
  });

  it('shows unused deps section when deps are unused', () => {
    const data = {
      unusedDeps: ['old-lib', 'unused-pkg'],
      mostImported: [],
      totalImports: 0,
      uniqueImports: 0,
      diversityScore: 0,
      avgImportsPerFile: 0,
      filesWithImports: 0,
      declaredCount: 2,
    };
    const report = formatImportHealthReport(data);
    assert.ok(report.includes('Potentially Unused'));
    assert.ok(report.includes('old-lib'));
    assert.ok(report.includes('unused-pkg'));
  });

  it('shows all-used message when no unused deps', () => {
    const data = {
      unusedDeps: [],
      mostImported: [],
      totalImports: 0,
      uniqueImports: 0,
      diversityScore: 0,
      avgImportsPerFile: 0,
      filesWithImports: 0,
      declaredCount: 0,
    };
    const report = formatImportHealthReport(data);
    assert.ok(report.includes('All dependencies are used'));
  });

  it('includes top imported packages table', () => {
    const data = {
      unusedDeps: [],
      mostImported: [
        { name: 'react', count: 10 },
        { name: 'axios', count: 5 },
        { name: 'lodash', count: 3 },
      ],
      totalImports: 18,
      uniqueImports: 3,
      diversityScore: 0.17,
      avgImportsPerFile: 3.6,
      filesWithImports: 5,
      declaredCount: 3,
    };
    const report = formatImportHealthReport(data);
    assert.ok(report.includes('| `react` | 10 |'));
    assert.ok(report.includes('| `axios` | 5 |'));
    assert.ok(report.includes('| `lodash` | 3 |'));
  });
});
