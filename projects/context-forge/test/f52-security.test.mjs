import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { detectSecurityIssues, formatSecurityReport } from '../context-forge.mjs';

describe('F52: detectSecurityIssues', () => {
  it('returns zero findings for empty input', () => {
    const result = detectSecurityIssues([]);
    assert.equal(result.total, 0);
    assert.equal(result.riskLevel, 'low');
  });

  it('returns zero findings for clean code', () => {
    const result = detectSecurityIssues([
      { path: 'src/safe.js', content: 'function add(a, b) { return a + b; }' },
    ]);
    assert.equal(result.total, 0);
  });

  it('detects SQL injection patterns', () => {
    const result = detectSecurityIssues([
      { path: 'db.js', content: 'db.query("SELECT * FROM users WHERE id = " + userId);' },
    ]);
    assert.ok(result.byType.sql_injection);
    assert.equal(result.byType.sql_injection[0].cwe, 'CWE-89');
    assert.equal(result.byType.sql_injection[0].severity, 'high');
  });

  it('detects XSS via innerHTML', () => {
    const result = detectSecurityIssues([
      { path: 'view.js', content: 'el.innerHTML = userInput;' },
    ]);
    assert.ok(result.byType.xss_reflected);
    assert.equal(result.byType.xss_reflected[0].cwe, 'CWE-79');
  });

  it('detects XSS via document.write', () => {
    const result = detectSecurityIssues([
      { path: 'old.js', content: 'document.write(data);' },
    ]);
    assert.ok(result.byType.xss_reflected);
  });

  it('detects hardcoded credentials', () => {
    const result = detectSecurityIssues([
      { path: 'config.js', content: 'const apiKey = "sk-1234567890abcdef";' },
      { path: 'auth.py', content: 'password = "supersecret123"' },
    ]);
    assert.ok(result.byType.hardcoded_password);
    assert.ok(result.byType.hardcoded_password.length >= 2);
  });

  it('detects eval() usage', () => {
    const result = detectSecurityIssues([
      { path: 'dynamic.js', content: 'eval(userInput);' },
    ]);
    assert.ok(result.byType.eval_usage);
    assert.equal(result.byType.eval_usage[0].severity, 'medium');
  });

  it('detects insecure Math.random()', () => {
    const result = detectSecurityIssues([
      { path: 'token.js', content: 'const token = Math.random().toString(36);' },
    ]);
    assert.ok(result.byType.insecure_random);
    assert.equal(result.byType.insecure_random[0].severity, 'low');
  });

  it('detects HTTP (non-HTTPS) URLs', () => {
    const result = detectSecurityIssues([
      { path: 'api.js', content: 'fetch("http://api.example.com/data");' },
    ]);
    assert.ok(result.byType.http_url);
  });

  it('does not flag localhost HTTP as issue', () => {
    const result = detectSecurityIssues([
      { path: 'dev.js', content: 'const url = "http://localhost:3000";' },
    ]);
    assert.equal(result.total, 0);
  });

  it('detects disabled TLS verification', () => {
    const result = detectSecurityIssues([
      { path: 'client.js', content: 'https.get(url, { rejectUnauthorized: false });' },
    ]);
    assert.ok(result.byType.disabled_tls);
    assert.equal(result.byType.disabled_tls[0].severity, 'high');
  });

  it('detects command injection via exec', () => {
    const result = detectSecurityIssues([
      { path: 'runner.js', content: 'exec(`ls ${userInput}`);' },
    ]);
    assert.ok(result.byType.command_injection);
  });

  it('detects dynamic RegExp construction', () => {
    const result = detectSecurityIssues([
      { path: 'search.js', content: 'const re = new RegExp(".*" + userInput);' },
    ]);
    assert.ok(result.byType.regex_dos);
  });

  it('detects prototype pollution', () => {
    const result = detectSecurityIssues([
      { path: 'merge.js', content: 'obj.__proto__[\'polluted\'] = true;' },
    ]);
    assert.ok(result.byType.prototype_pollution);
  });

  it('aggregates findings across multiple files', () => {
    const result = detectSecurityIssues([
      { path: 'a.js', content: 'eval(x);' },
      { path: 'b.js', content: 'el.innerHTML = x;' },
      { path: 'c.js', content: 'Math.random();' },
    ]);
    assert.ok(result.total >= 3);
    assert.equal(result.fileCount, 3);
    assert.equal(result.riskLevel, 'critical'); // has high-severity XSS
  });

  it('sets risk level to elevated when only medium found', () => {
    const result = detectSecurityIssues([
      { path: 'a.js', content: 'eval(x);' },
    ]);
    assert.equal(result.riskLevel, 'elevated');
  });

  it('handles files without content', () => {
    const result = detectSecurityIssues([{ path: 'null.js', content: null }]);
    assert.equal(result.total, 0);
  });

  it('captures line numbers correctly', () => {
    const result = detectSecurityIssues([
      { path: 'multi.js', content: 'const a = 1;\nconst b = 2;\neval(x);\nconst c = 3;' },
    ]);
    assert.ok(result.byType.eval_usage);
    assert.equal(result.byType.eval_usage[0].line, 3);
  });
});

describe('F52: formatSecurityReport', () => {
  it('shows clean message for no findings', () => {
    const report = formatSecurityReport({ total: 0, riskLevel: 'low' });
    assert.ok(report.includes('✅'));
    assert.ok(report.includes('No security issues'));
  });

  it('handles null result', () => {
    const report = formatSecurityReport(null);
    assert.ok(report.includes('✅'));
  });

  it('includes risk level and counts', () => {
    const report = formatSecurityReport({
      total: 5,
      riskLevel: 'critical',
      fileCount: 3,
      bySeverity: { high: 2, medium: 2, low: 1 },
      byType: {},
    });
    assert.ok(report.includes('CRITICAL'));
    assert.ok(report.includes('🔴'));
  });

  it('includes CWE references', () => {
    const report = formatSecurityReport({
      total: 1,
      riskLevel: 'critical',
      fileCount: 1,
      bySeverity: { high: 1, medium: 0, low: 0 },
      byType: {
        sql_injection: [{
          type: 'sql_injection', severity: 'high', cwe: 'CWE-89',
          file: 'db.js', line: 1, snippet: 'query(...)', description: 'SQL injection',
        }],
      },
    });
    assert.ok(report.includes('CWE-89'));
  });

  it('truncates long finding lists', () => {
    const items = Array.from({ length: 20 }, (_, i) => ({
      type: 'eval_usage', severity: 'medium', cwe: 'CWE-94',
      file: `f${i}.js`, line: i + 1, snippet: `eval(${i})`, description: 'eval',
    }));
    const report = formatSecurityReport({
      total: 20, riskLevel: 'elevated', fileCount: 20,
      bySeverity: { high: 0, medium: 20, low: 0 },
      byType: { eval_usage: items },
    });
    assert.ok(report.includes('and 5 more'));
  });
});
