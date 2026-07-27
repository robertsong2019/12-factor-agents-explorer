import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { analyzeResourceLeaks, formatResourceLeaksReport } from '../context-forge.mjs';

describe('F80: analyzeResourceLeaks()', () => {
  let tmpDir;

  before(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'f80-'));
  });

  after(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function writeFile(name, content) {
    const p = path.join(tmpDir, name);
    fs.writeFileSync(p, content);
    return p;
  }

  it('detects setInterval without clearInterval', () => {
    const file = writeFile('interval.js', `
      const timer = setInterval(() => {
        console.log('tick');
      }, 1000);
    `);
    const result = analyzeResourceLeaks([file]);
    assert.ok(result.issues.some(i => i.type === 'uncleared-interval'));
    assert.ok(result.summary.high >= 1);
  });

  it('does not flag setInterval when clearInterval is present', () => {
    const file = writeFile('interval-ok.js', `
      const timer = setInterval(() => {}, 1000);
      clearInterval(timer);
    `);
    const result = analyzeResourceLeaks([file]);
    const intervalIssues = result.issues.filter(i => i.type === 'uncleared-interval');
    assert.equal(intervalIssues.length, 0);
  });

  it('flags setInterval without assignment as high severity', () => {
    const file = writeFile('bare-interval.js', `
      setInterval(() => { doSomething(); }, 5000);
    `);
    const result = analyzeResourceLeaks([file]);
    assert.ok(result.issues.some(i => i.type === 'uncleared-interval' && i.severity === 'high'));
  });

  it('detects addEventListener without removeEventListener', () => {
    const file = writeFile('listener.js', `
      button.addEventListener('click', handler);
      element.addEventListener('submit', onSubmit);
    `);
    const result = analyzeResourceLeaks([file]);
    assert.ok(result.issues.some(i => i.type === 'listener-accumulation'));
  });

  it('does not flag listeners when removeEventListener exists', () => {
    const file = writeFile('listener-ok.js', `
      button.addEventListener('click', handler);
      button.removeEventListener('click', handler);
    `);
    const result = analyzeResourceLeaks([file]);
    const listenerIssues = result.issues.filter(i => i.type === 'listener-accumulation');
    assert.equal(listenerIssues.length, 0);
  });

  it('detects unclosed file handles', () => {
    const file = writeFile('streams.js', `
      const stream = fs.createReadStream('input.txt');
      const ws = fs.createWriteStream('output.txt');
    `);
    const result = analyzeResourceLeaks([file]);
    assert.ok(result.issues.some(i => i.type === 'unclosed-handle'));
  });

  it('detects database connection leaks', () => {
    const file = writeFile('db.js', `
      const conn = mongoose.connect('mongodb://localhost/test');
      const pool = createPool({ host: 'localhost' });
    `);
    const result = analyzeResourceLeaks([file]);
    assert.ok(result.issues.some(i => i.type === 'db-connection-leak'));
  });

  it('returns grade A for clean files', () => {
    const file = writeFile('clean.js', `
      const timer = setInterval(() => {}, 1000);
      clearInterval(timer);
      stream.close();
    `);
    const result = analyzeResourceLeaks([file]);
    assert.equal(result.summary.grade, 'A');
    assert.equal(result.summary.totalIssues, 0);
  });

  it('skips unreadable files gracefully', () => {
    const result = analyzeResourceLeaks(['/nonexistent/path.js']);
    assert.equal(result.summary.filesScanned, 0);
    assert.equal(result.issues.length, 0);
  });

  it('calculates score and grade correctly', () => {
    const file = writeFile('messy.js', `
      setInterval(() => {}, 1000);
      const t = setInterval(() => {}, 2000);
      fs.createReadStream('a.txt');
      db.connect();
      el.addEventListener('click', fn);
    `);
    const result = analyzeResourceLeaks([file]);
    assert.ok(result.summary.score < 100);
    assert.ok(['B', 'C', 'D', 'F'].includes(result.summary.grade));
    assert.ok(result.summary.totalIssues >= 3);
  });

  it('formatResourceLeaksReport produces markdown', () => {
    const file = writeFile('report-test.js', `
      setInterval(() => {}, 1000);
    `);
    const result = analyzeResourceLeaks([file]);
    const report = formatResourceLeaksReport(result);
    assert.ok(report.includes('## 🔧 Resource Leak Analysis'));
    assert.ok(report.includes('**Grade:'));
    assert.ok(report.includes('Grade:') || report.includes('grade'));
  });

  it('formatResourceLeaksReport shows ✅ for clean results', () => {
    const report = formatResourceLeaksReport({
      issues: [],
      summary: { totalIssues: 0, high: 0, medium: 0, filesScanned: 1, score: 100, grade: 'A' }
    });
    assert.ok(report.includes('✅'));
  });
});
