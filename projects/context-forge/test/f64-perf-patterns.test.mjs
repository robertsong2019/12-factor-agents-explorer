import { test } from 'node:test';
import assert from 'node:assert';
import { analyzePerformancePatterns, formatPerformanceReport } from '../context-forge.mjs';

test('analyzePerformancePatterns — empty files returns safe result', () => {
  const result = analyzePerformancePatterns([]);
  assert.equal(result.totalFiles, 0);
  assert.equal(result.score, 100);
  assert.equal(result.grade, 'A');
});

test('analyzePerformancePatterns — null input safe', () => {
  const result = analyzePerformancePatterns(null);
  assert.equal(result.totalFiles, 0);
  assert.equal(result.grade, 'A');
});

test('analyzePerformancePatterns — detects readFileSync', () => {
  const files = [
    { path: 'src/io.js', content: "const data = fs.readFileSync('/path/to/file', 'utf8');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.syncIO, 1);
  assert.ok(result.files[0].issues.some(i => i.type === 'sync_io'));
  assert.equal(result.files[0].issues[0].severity, 'medium');
});

test('analyzePerformancePatterns — detects writeFileSync', () => {
  const files = [
    { path: 'src/io.js', content: "fs.writeFileSync('/path', 'content');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.syncIO, 1);
});

test('analyzePerformancePatterns — detects execSync', () => {
  const files = [
    { path: 'src/exec.js', content: "const out = execSync('ls -la');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.syncIO, 1);
});

test('analyzePerformancePatterns — detects nested for loops', () => {
  const files = [
    {
      path: 'src/matrix.js',
      content: [
        'for (let i = 0; i < n; i++) {',
        '  for (let j = 0; j < m; j++) {',
        '    sum += arr[i][j];',
        '  }',
        '}',
      ].join('\n'),
    },
  ];
  const result = analyzePerformancePatterns(files);
  assert.ok(result.summary.nestedLoops >= 1);
});

test('analyzePerformancePatterns — detects .map inside .forEach', () => {
  const files = [
    {
      path: 'src/transform.js',
      content: [
        'items.forEach(item => {',
        '  const mapped = subitems.map(sub => sub * 2);',
        '});',
      ].join('\n'),
    },
  ];
  const result = analyzePerformancePatterns(files);
  assert.ok(result.summary.nestedLoops >= 1);
});

test('analyzePerformancePatterns — single loop is NOT flagged', () => {
  const files = [
    {
      path: 'src/loop.js',
      content: [
        'const result = items.map(item => item * 2);',
      ].join('\n'),
    },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.nestedLoops, 0);
});

test('analyzePerformancePatterns — detects missing await on fetch', () => {
  const files = [
    { path: 'src/api.js', content: "const data = api.fetch('https://api.example.com');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.ok(result.summary.missingAwait >= 1);
});

test('analyzePerformancePatterns — detects missing await on axios', () => {
  const files = [
    { path: 'src/api.js', content: "const res = axios.get('/users');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.ok(result.summary.missingAwait >= 1);
});

test('analyzePerformancePatterns — await fetch is NOT flagged', () => {
  const files = [
    { path: 'src/api.js', content: "const data = await api.fetch('https://api.example.com');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.missingAwait, 0);
});

test('analyzePerformancePatterns — skips test files', () => {
  const files = [
    { path: 'src/app.test.js', content: "fs.readFileSync('test');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.totalFiles, 0);
});

test('analyzePerformancePatterns — non-JS files ignored', () => {
  const files = [
    { path: 'README.md', content: 'fs.readFileSync("x");' },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.totalFiles, 0);
});

test('analyzePerformancePatterns — sync I/O in comments skipped', () => {
  const files = [
    { path: 'src/app.js', content: '// fs.readFileSync("commented");\nconst x = 1;' },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.syncIO, 0);
});

test('analyzePerformancePatterns — multiple patterns in one file', () => {
  const files = [
    {
      path: 'src/bad.js',
      content: [
        'const fs = require("fs");',
        'const data = fs.readFileSync("file.txt");',
        'for (let i = 0; i < n; i++) {',
        '  for (let j = 0; j < m; j++) {',
        '    console.log(arr[i][j]);',
        '  }',
        '}',
        'const res = client.fetch("/api");',
      ].join('\n'),
    },
  ];
  const result = analyzePerformancePatterns(files);
  assert.ok(result.summary.syncIO >= 1);
  assert.ok(result.summary.nestedLoops >= 1);
  assert.ok(result.summary.missingAwait >= 1);
});

test('analyzePerformancePatterns — grade decreases with many issues', () => {
  const files = [
    {
      path: 'src/terrible.js',
      content: Array.from({ length: 10 }, () =>
        "const d = fs.readFileSync('x');"
      ).join('\n'),
    },
  ];
  const result = analyzePerformancePatterns(files);
  // 10 sync_io * 3 = 30 deducted → 70 → C
  assert.equal(result.score, 70);
  assert.equal(result.grade, 'C');
});

test('formatPerformanceReport — null input returns warning', () => {
  const report = formatPerformanceReport(null);
  assert.ok(report.includes('No data'));
});

test('formatPerformanceReport — includes grade and summary', () => {
  const files = [
    { path: 'src/app.js', content: "fs.readFileSync('x');" },
  ];
  const result = analyzePerformancePatterns(files);
  const report = formatPerformanceReport(result);
  assert.ok(report.includes('**Grade:**'));
  assert.ok(report.includes('Sync I/O'));
  assert.ok(report.includes('src/app.js'));
});

test('formatPerformanceReport — clean result still has header', () => {
  const result = analyzePerformancePatterns([]);
  const report = formatPerformanceReport(result);
  assert.ok(report.includes('Performance Patterns'));
  assert.ok(report.includes('Grade:** A'));
});

test('analyzePerformancePatterns — existsSync is detected', () => {
  const files = [
    { path: 'src/check.js', content: "if (fs.existsSync(path)) { load(); }" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.syncIO, 1);
});

test('analyzePerformancePatterns — readdirSync is detected', () => {
  const files = [
    { path: 'src/scan.js', content: "const files = fs.readdirSync('.');" },
  ];
  const result = analyzePerformancePatterns(files);
  assert.equal(result.summary.syncIO, 1);
});
