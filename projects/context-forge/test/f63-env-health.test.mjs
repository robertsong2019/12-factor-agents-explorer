import { test } from 'node:test';
import assert from 'node:assert';
import { analyzeEnvHealth, formatEnvHealthReport } from '../context-forge.mjs';

test('analyzeEnvHealth — empty files returns safe result', () => {
  const result = analyzeEnvHealth([]);
  assert.equal(result.totalSourceEnvVars, 0);
  assert.equal(result.score, 100);
  assert.equal(result.grade, 'A');
});

test('analyzeEnvHealth — null input safe', () => {
  const result = analyzeEnvHealth(null);
  assert.equal(result.totalSourceEnvVars, 0);
  assert.equal(result.grade, 'A');
});

test('analyzeEnvHealth — detects process.env usage in JS', () => {
  const files = [
    { path: 'src/config.js', content: "const apiKey = process.env.API_KEY;\nconst port = process.env.PORT;" },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.totalSourceEnvVars, 2);
  assert.ok(result.undocumented.includes('API_KEY'));
  assert.ok(result.undocumented.includes('PORT'));
});

test('analyzeEnvHealth — detects process.env usage in Python', () => {
  const files = [
    { path: 'src/app.py', content: "api_key = os.environ.get('API_KEY')\n# Actually uses process.env style" },
    { path: 'src/config.js', content: 'const x = process.env.SECRET_TOKEN;' },
  ];
  const result = analyzeEnvHealth(files);
  // Python os.environ is NOT process.env — only JS process.env detected
  assert.equal(result.totalSourceEnvVars, 1);
  assert.ok(result.undocumented.includes('SECRET_TOKEN'));
});

test('analyzeEnvHealth — parses .env.example correctly', () => {
  const files = [
    { path: '.env.example', content: '# Comment\nAPI_KEY=abc123\nPORT=3000\nDATABASE_URL=postgres://localhost\n' },
    { path: 'src/app.js', content: 'process.env.API_KEY;\nprocess.env.PORT;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.ok(result.hasEnvExample);
  assert.equal(result.totalExampleVars, 3);
  assert.equal(result.undocumented.length, 0);
});

test('analyzeEnvHealth — detects undocumented env vars', () => {
  const files = [
    { path: '.env.example', content: 'API_KEY=xxx\n' },
    { path: 'src/app.js', content: 'process.env.API_KEY;\nprocess.env.SECRET;\nprocess.env.DATABASE_URL;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.undocumented.length, 2);
  assert.ok(result.undocumented.includes('SECRET'));
  assert.ok(result.undocumented.includes('DATABASE_URL'));
});

test('analyzeEnvHealth — detects stale env vars', () => {
  const files = [
    { path: '.env.example', content: 'OLD_VAR=xxx\nAPI_KEY=xxx\n' },
    { path: 'src/app.js', content: 'process.env.API_KEY;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.stale.length, 1);
  assert.ok(result.stale.includes('OLD_VAR'));
});

test('analyzeEnvHealth — detects hardcoded secrets', () => {
  const files = [
    { path: 'src/secrets.js', content: 'const API_KEY = "sk-1234567890abcdef";' },
  ];
  const result = analyzeEnvHealth(files);
  assert.ok(result.hardcodedSecrets.length > 0);
  assert.equal(result.hardcodedSecrets[0].severity, 'high');
});

test('analyzeEnvHealth — detects hardcoded DATABASE_URL', () => {
  const files = [
    { path: 'src/db.js', content: 'const DATABASE_URL = "postgres://user:pass@host:5432/db";' },
  ];
  const result = analyzeEnvHealth(files);
  assert.ok(result.hardcodedSecrets.length > 0);
});

test('analyzeEnvHealth — skips test files', () => {
  const files = [
    { path: 'src/app.test.js', content: 'process.env.TEST_VAR;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.totalSourceEnvVars, 0);
});

test('analyzeEnvHealth — skips .env files for source scanning', () => {
  const files = [
    { path: '.env', content: 'API_KEY=secret123' },
    { path: '.env.example', content: 'API_KEY=xxx' },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.totalSourceEnvVars, 0);
});

test('analyzeEnvHealth — score drops without .env.example', () => {
  const files = [
    { path: 'src/app.js', content: 'process.env.API_KEY;\nprocess.env.SECRET;' },
  ];
  const result = analyzeEnvHealth(files);
  // 2 undocumented * 5 + 20 (no .env.example) = 30 deducted → 70 → C
  assert.equal(result.score, 70);
  assert.equal(result.grade, 'C');
});

test('analyzeEnvHealth — score is A when everything documented', () => {
  const files = [
    { path: '.env.example', content: 'API_KEY=xxx\nPORT=3000' },
    { path: 'src/app.js', content: 'process.env.API_KEY;\nprocess.env.PORT;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.score, 100);
  assert.equal(result.grade, 'A');
});

test('analyzeEnvHealth — comment lines with process.env are skipped', () => {
  const files = [
    { path: 'src/app.js', content: '// process.env.COMMENTED_OUT;\nconst x = 1;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.equal(result.totalSourceEnvVars, 0);
});

test('analyzeEnvHealth — .env.sample is also recognized', () => {
  const files = [
    { path: '.env.sample', content: 'API_KEY=xxx' },
    { path: 'src/app.js', content: 'process.env.API_KEY;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.ok(result.hasEnvExample);
  assert.equal(result.totalExampleVars, 1);
});

test('analyzeEnvHealth — .env.template is also recognized', () => {
  const files = [
    { path: '.env.template', content: 'SECRET=xxx' },
    { path: 'src/app.js', content: 'process.env.SECRET;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.ok(result.hasEnvExample);
});

test('analyzeEnvHealth — hardcoded secret lowers score significantly', () => {
  const files = [
    { path: '.env.example', content: 'API_KEY=xxx' },
    { path: 'src/app.js', content: 'const API_KEY = "sk-1234567890abcdef";' },
  ];
  const result = analyzeEnvHealth(files);
  // 1 hardcoded * 15 = 15 deducted → 85 → B
  assert.equal(result.score, 85);
  assert.equal(result.grade, 'B');
});

test('formatEnvHealthReport — null input returns warning', () => {
  const report = formatEnvHealthReport(null);
  assert.ok(report.includes('No data'));
});

test('formatEnvHealthReport — includes grade and score', () => {
  const files = [
    { path: 'src/app.js', content: 'process.env.API_KEY;' },
  ];
  const result = analyzeEnvHealth(files);
  const report = formatEnvHealthReport(result);
  assert.ok(report.includes('**Grade:**'));
  assert.ok(report.includes('API_KEY'));
});

test('formatEnvHealthReport — includes undocumented section when vars missing', () => {
  const files = [
    { path: '.env.example', content: 'EXISTING=xxx' },
    { path: 'src/app.js', content: 'process.env.EXISTING;\nprocess.env.MISSING;' },
  ];
  const result = analyzeEnvHealth(files);
  const report = formatEnvHealthReport(result);
  assert.ok(report.includes('Undocumented'));
  assert.ok(report.includes('MISSING'));
});

test('formatEnvHealthReport — shows all clear when healthy', () => {
  const files = [
    { path: '.env.example', content: 'API_KEY=xxx' },
    { path: 'src/app.js', content: 'process.env.API_KEY;' },
  ];
  const result = analyzeEnvHealth(files);
  const report = formatEnvHealthReport(result);
  assert.ok(report.includes('properly documented'));
});

test('analyzeEnvHealth — multiple files aggregate correctly', () => {
  const files = [
    { path: '.env.example', content: 'SHARED=xxx\nUNIQUE_A=xxx' },
    { path: 'src/a.js', content: 'process.env.SHARED;\nprocess.env.UNIQUE_A;' },
    { path: 'src/b.js', content: 'process.env.SHARED;\nprocess.env.UNIQUE_B;' },
  ];
  const result = analyzeEnvHealth(files);
  assert.ok(result.totalSourceEnvVars >= 3);
  assert.ok(result.undocumented.includes('UNIQUE_B'));
  assert.ok(!result.undocumented.includes('SHARED'));
});

test('formatEnvHealthReport — renders stale vars section', () => {
  const report = formatEnvHealthReport({
    grade: 'B', score: 85, hasEnvExample: true, envExampleFile: '.env.example',
    totalSourceEnvVars: 3, totalExampleVars: 2,
    undocumented: ['MISSING_VAR'], stale: ['OLD_VAR'], hardcodedSecrets: [],
  });
  assert.ok(report.includes('### Stale Environment Variables'));
  assert.ok(report.includes('`OLD_VAR`'));
  assert.ok(report.includes('`MISSING_VAR`'));
});

test('formatEnvHealthReport — renders hardcoded secrets capped at 10', () => {
  const secrets = Array.from({ length: 12 }, (_, i) => ({
    file: `sec${i}.js`, line: i + 1, description: 'API key literal',
  }));
  const report = formatEnvHealthReport({
    grade: 'F', score: 10, hasEnvExample: false,
    totalSourceEnvVars: 0, totalExampleVars: 0,
    undocumented: [], stale: [], hardcodedSecrets: secrets,
  });
  assert.ok(report.includes('🔴 Hardcoded Secrets (12)'));
  assert.equal((report.match(/sec\d+\.js/g) || []).length, 10);
  assert.ok(!report.includes('sec10.js'));
  assert.ok(!report.includes('sec11.js'));
});

test('formatEnvHealthReport — all-clear message when nothing to report', () => {
  const report = formatEnvHealthReport({
    grade: 'A', score: 100, hasEnvExample: true, envExampleFile: '.env.example',
    totalSourceEnvVars: 2, totalExampleVars: 2,
    undocumented: [], stale: [], hardcodedSecrets: [],
  });
  assert.ok(report.includes('✅ All environment variables are properly documented.'));
});
