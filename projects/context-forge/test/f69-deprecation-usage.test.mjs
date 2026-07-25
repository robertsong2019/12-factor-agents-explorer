import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeDeprecationUsage, formatDeprecationUsageReport } from '../context-forge.mjs';

const makeFile = (path, content) => ({ path, content });

describe('F69: analyzeDeprecationUsage', () => {
  it('returns empty result for empty input', () => {
    const r = analyzeDeprecationUsage([]);
    assert.equal(r.score, 100);
    assert.equal(r.stats.totalIssues, 0);
  });

  it('detects new Buffer()', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'const buf = new Buffer(10);')]);
    assert.ok(r.stats.totalIssues >= 1);
    assert.ok(r.files[0].issues[0].description.includes('Buffer.alloc'));
    assert.equal(r.files[0].issues[0].severity, 'high');
  });

  it('detects fs.exists()', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'fs.exists(path, () => {});')]);
    assert.ok(r.files[0].issues.some(i => i.description.includes('fs.stat')));
    assert.equal(r.files[0].issues[0].severity, 'high');
  });

  it('detects .substr()', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'const s = str.substr(1, 3);')]);
    assert.ok(r.files[0].issues.some(i => i.description.includes('.slice()')));
    assert.equal(r.files[0].issues[0].severity, 'medium');
  });

  it('detects escape()', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'const e = escape(str);')]);
    assert.ok(r.files[0].issues.some(i => i.description.includes('encodeURIComponent')));
  });

  it('detects util.isXxx', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'if (util.isArray(x)) {}\nif (util.isString(y)) {}')]);
    assert.ok(r.stats.totalIssues >= 2);
  });

  it('detects deprecated crypto methods', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'const c = crypto.createCipher(algo, key);')]);
    assert.ok(r.files[0].issues.some(i => i.severity === 'high' && i.description.includes('createCipheriv')));
  });

  it('detects moment.js imports', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', "const moment = require('moment');")]);
    assert.ok(r.files[0].issues.some(i => i.description.includes('moment.js')));
    assert.equal(r.files[0].issues[0].category, 'package');
  });

  it('detects full lodash import', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', "import _ from 'lodash';")]);
    assert.ok(r.files[0].issues.some(i => i.description.includes('lodash-es')));
  });

  it('detects with statement', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'with (obj) { x; }')]);
    assert.ok(r.files[0].issues.some(i => i.severity === 'high' && i.description.includes('with')));
  });

  it('detects .trimLeft() and .trimRight()', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 's.trimLeft();\ns.trimRight();')]);
    assert.ok(r.stats.totalIssues >= 2);
    assert.ok(r.files[0].issues.some(i => i.description.includes('trimStart')));
  });

  it('skips // comments', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', '// new Buffer(10)\nconst s = str.slice(0, 3);')]);
    assert.equal(r.stats.totalIssues, 0);
  });

  it('respects maxIssuesPerFile', () => {
    const manyLines = Array.from({ length: 30 }, (_, i) => `const x${i} = new Buffer(1);`).join('\n');
    const r = analyzeDeprecationUsage([makeFile('src/a.js', manyLines)], { maxIssuesPerFile: 5 });
    assert.ok(r.files[0].issues.length <= 5);
  });

  it('tracks severity counts', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'new Buffer(1);\nfs.exists(p);\nstr.substr(0,1);\nconst x = 1; // no issue')]);
    assert.ok(r.stats.severityCounts.high >= 2);
    assert.ok(r.stats.severityCounts.medium >= 1);
  });

  it('tracks category counts', () => {
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'new Buffer(1);\nif (util.isArray(x)) {}')]);
    assert.ok(r.stats.categories.nodejs);
    assert.ok(r.stats.categories.nodejs.count >= 2);
  });

  it('supports custom deprecation patterns', () => {
    const custom = [['myOldApi(', 'Use myNewApi', 'high', 'custom']];
    const r = analyzeDeprecationUsage([makeFile('src/a.js', 'myOldApi(1);')], { additionalDeprecations: custom });
    assert.ok(r.files[0].issues.some(i => i.description.includes('myNewApi')));
    assert.equal(r.files[0].issues[0].category, 'custom');
  });

  it('score decreases with issues', () => {
    const clean = analyzeDeprecationUsage([makeFile('src/a.js', 'const x = 1;')]);
    const dirty = analyzeDeprecationUsage([makeFile('src/a.js', 'new Buffer(1);\nfs.exists(p);\nstr.substr(0,1);')]);
    assert.ok(clean.score > dirty.score);
  });

  it('counts files with issues', () => {
    const r = analyzeDeprecationUsage([
      makeFile('src/good.js', 'const x = 1;'),
      makeFile('src/bad.js', 'new Buffer(1);'),
      makeFile('src/good2.js', 'const y = 2;'),
    ]);
    assert.equal(r.stats.filesWithIssues, 1);
  });
});

describe('F69: formatDeprecationUsageReport', () => {
  it('produces markdown with score', () => {
    const r = analyzeDeprecationUsage([makeFile('a.js', 'const x = 1;')]);
    const report = formatDeprecationUsageReport(r);
    assert.ok(report.includes('Deprecation Usage Analysis'));
    assert.ok(report.includes('Score:'));
  });

  it('includes severity breakdown', () => {
    const r = analyzeDeprecationUsage([makeFile('a.js', 'new Buffer(1);')]);
    const report = formatDeprecationUsageReport(r);
    assert.ok(report.includes('Severity Breakdown'));
    assert.ok(report.includes('high'));
  });

  it('includes category breakdown', () => {
    const r = analyzeDeprecationUsage([makeFile('a.js', 'new Buffer(1);')]);
    const report = formatDeprecationUsageReport(r);
    assert.ok(report.includes('Category Breakdown'));
    assert.ok(report.includes('nodejs'));
  });

  it('handles clean project', () => {
    const r = analyzeDeprecationUsage([makeFile('a.js', 'const x = 1;')]);
    const report = formatDeprecationUsageReport(r);
    assert.ok(!report.includes('Top Files'));
  });
});
