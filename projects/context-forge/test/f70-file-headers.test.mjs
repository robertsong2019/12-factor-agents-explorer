import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeFileHeaders, formatFileHeadersReport } from '../context-forge.mjs';

const makeFile = (path, content) => ({ path, content });

describe('F70: analyzeFileHeaders', () => {
  it('returns 100 for empty input', () => {
    const r = analyzeFileHeaders([]);
    assert.equal(r.score, 100);
  });

  it('detects license header', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/** @license MIT */\nconst x = 1;')]);
    assert.equal(r.stats.filesWithLicense, 1);
    assert.ok(r.files[0].hasLicense);
  });

  it('detects SPDX license', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '// SPDX-License-Identifier: MIT\nconst x = 1;')]);
    assert.ok(r.files[0].hasLicense);
  });

  it('detects @module tag', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/** @module utils */\nconst x = 1;')]);
    assert.equal(r.stats.filesWithModuleTag, 1);
    assert.ok(r.files[0].hasModuleTag);
  });

  it('detects file description', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/**\n * Utility functions for string manipulation.\n */')]);
    assert.ok(r.files[0].hasDescription);
  });

  it('skips short lines as non-descriptions', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/**\n * @author Me\n */')]);
    assert.equal(r.files[0].hasDescription, false);
  });

  it('detects missing header', () => {
    const r = analyzeFileHeaders([makeFile('a.js', 'const x = 1;')]);
    assert.ok(!r.files[0].hasAnyHeader);
    assert.equal(r.stats.filesWithoutAnyHeader, 1);
  });

  it('skips shebang when checking header', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '#!/usr/bin/env node\n/** @license MIT */')]);
    assert.ok(r.files[0].hasLicense);
  });

  it('detects JSDoc header style', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/** @module a */')]);
    assert.equal(r.files[0].headerStyle, 'jsdoc');
  });

  it('detects hash comment header style', () => {
    const r = analyzeFileHeaders([makeFile('a.py', '# This is a Python module\n# License: MIT')]);
    assert.equal(r.files[0].headerStyle, 'hash');
  });

  it('detects line comment header style', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '// File header\n// License: MIT')]);
    assert.equal(r.files[0].headerStyle, 'line-comment');
  });

  it('scores based on header coverage', () => {
    const r = analyzeFileHeaders([
      makeFile('a.js', '/** @license MIT */'),
      makeFile('b.js', 'const x = 1;'),
      makeFile('c.js', 'const y = 2;'),
      makeFile('d.js', '/** @module d */'),
    ]);
    assert.equal(r.stats.filesWithHeaders, 2);
    assert.equal(r.score, 50); // 2/4 = 50%
  });

  it('flags missing license when required', () => {
    const r = analyzeFileHeaders([makeFile('a.js', 'const x = 1;')], { requireLicense: true });
    assert.ok(r.files[0].issues.some(i => i.category === 'license'));
    assert.equal(r.stats.totalIssues, 1);
  });

  it('does not flag license when not required', () => {
    const r = analyzeFileHeaders([makeFile('a.js', 'const x = 1;')], { requireLicense: false });
    assert.equal(r.stats.totalIssues, 0);
  });

  it('supports custom license patterns', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '// PROPRIETARY\nconst x = 1;')], { licensePatterns: ['PROPRIETARY'] });
    assert.ok(r.files[0].hasLicense);
  });

  it('respects headerLines option', () => {
    const r = analyzeFileHeaders([makeFile('a.js', Array(10).fill('').join('\n') + '/** @license MIT */')], { headerLines: 3 });
    assert.ok(!r.files[0].hasLicense);
  });
});

describe('F70: formatFileHeadersReport', () => {
  it('includes score and coverage', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/** @license MIT */'), makeFile('b.js', 'x=1')]);
    const report = formatFileHeadersReport(r);
    assert.ok(report.includes('File Header Analysis'));
    assert.ok(report.includes('50/100'));
  });

  it('includes header style distribution', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/** @module a */')]);
    const report = formatFileHeadersReport(r);
    assert.ok(report.includes('Header Style Distribution'));
    assert.ok(report.includes('jsdoc'));
  });

  it('lists files without headers', () => {
    const r = analyzeFileHeaders([makeFile('missing.js', 'x=1')]);
    const report = formatFileHeadersReport(r);
    assert.ok(report.includes('Files Without Headers'));
    assert.ok(report.includes('missing.js'));
  });

  it('handles fully covered project', () => {
    const r = analyzeFileHeaders([makeFile('a.js', '/** @license MIT */')]);
    const report = formatFileHeadersReport(r);
    assert.ok(!report.includes('Files Without Headers'));
  });
});
