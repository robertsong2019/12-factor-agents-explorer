import { test } from 'node:test';
import assert from 'node:assert';
import { analyzeLoggingHealth, formatLoggingHealthReport } from '../context-forge.mjs';

test('analyzeLoggingHealth — empty files returns safe result', () => {
  const result = analyzeLoggingHealth([]);
  assert.equal(result.totalFiles, 0);
  assert.equal(result.score, 100);
  assert.equal(result.grade, 'A');
});

test('analyzeLoggingHealth — null input safe', () => {
  const result = analyzeLoggingHealth(null);
  assert.equal(result.totalFiles, 0);
  assert.equal(result.grade, 'A');
});

test('analyzeLoggingHealth — detects console.log in production code', () => {
  const files = [
    { path: 'src/app.js', content: 'console.log("hello world");\nconst x = 1;' },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleLog, 1);
  assert.equal(result.files.length, 1);
  assert.equal(result.files[0].consoleLogCount, 1);
  assert.equal(result.files[0].issues[0].type, 'console_log');
  assert.equal(result.files[0].issues[0].severity, 'medium');
});

test('analyzeLoggingHealth — skips console.log in comments', () => {
  const files = [
    { path: 'src/app.js', content: '// console.log("commented out");\nconst x = 1;' },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleLog, 0);
});

test('analyzeLoggingHealth — detects catch block without logging', () => {
  const files = [
    {
      path: 'src/api.js',
      content: [
        'try {',
        '  doSomething();',
        '} catch (err) {',
        '  // do nothing',
        '}',
      ].join('\n'),
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.catchWithoutLog, 1);
  assert.ok(result.files[0].issues.some(i => i.type === 'catch_without_log'));
  assert.equal(result.files[0].issues[0].severity, 'high');
});

test('analyzeLoggingHealth — catch block with console.error is NOT flagged', () => {
  const files = [
    {
      path: 'src/api.js',
      content: [
        'try {',
        '  doSomething();',
        '} catch (err) {',
        '  console.error("failed", err);',
        '}',
      ].join('\n'),
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.catchWithoutLog, 0);
});

test('analyzeLoggingHealth — catch block with logger is NOT flagged', () => {
  const files = [
    {
      path: 'src/api.js',
      content: [
        'try {',
        '  doSomething();',
        '} catch (err) {',
        '  logger.error("failed", err);',
        '}',
      ].join('\n'),
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.catchWithoutLog, 0);
});

test('analyzeLoggingHealth — detects console.warn and console.error', () => {
  const files = [
    { path: 'src/warn.js', content: 'console.warn("warning!");\nconsole.error("oops");' },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleWarn, 1);
  assert.equal(result.summary.consoleError, 1);
});

test('analyzeLoggingHealth — detects console.info and console.debug', () => {
  const files = [
    { path: 'src/debug.js', content: 'console.info("info");\nconsole.debug("debug");' },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleInfo, 1);
  assert.equal(result.summary.consoleDebug, 1);
});

test('analyzeLoggingHealth — skips test files', () => {
  const files = [
    { path: 'src/app.test.js', content: 'console.log("test logging");' },
    { path: 'src/app.spec.js', content: 'console.log("spec logging");' },
    { path: 'tests/helpers.js', content: 'console.log("helper");' },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleLog, 0);
  assert.equal(result.totalFiles, 0);
});

test('analyzeLoggingHealth — non-JS files are ignored', () => {
  const files = [
    { path: 'README.md', content: 'console.log("not code");' },
    { path: 'data.json', content: '{"key": "console.log(\\"fake\\")"}' },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.totalFiles, 0);
});

test('analyzeLoggingHealth — score decreases with console.log', () => {
  const files = [
    { path: 'src/a.js', content: 'console.log("1");\nconsole.log("2");\nconsole.log("3");' },
  ];
  const result = analyzeLoggingHealth(files);
  // 3 * 3 = 9 points deducted → score 91 → A
  assert.equal(result.score, 91);
  assert.equal(result.grade, 'A');
});

test('analyzeLoggingHealth — score decreases heavily with catch without log', () => {
  const files = [
    {
      path: 'src/big.js',
      content: Array.from({ length: 10 }, (_, i) =>
        `try { f${i}(); } catch(e) { /* nothing */ }`
      ).join('\n'),
    },
  ];
  const result = analyzeLoggingHealth(files);
  // 10 * 5 = 50 deducted → score 50 → F
  assert.equal(result.score, 50);
  assert.equal(result.grade, 'F');
});

test('analyzeLoggingHealth — multiple files aggregated correctly', () => {
  const files = [
    { path: 'src/a.js', content: 'console.log("a");' },
    { path: 'src/b.js', content: 'console.log("b");\nconsole.error("e");' },
    {
      path: 'src/c.js',
      content: 'try { x(); } catch(e) { /* nada */ }',
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleLog, 2);
  assert.equal(result.summary.consoleError, 1);
  assert.equal(result.summary.catchWithoutLog, 1);
  assert.equal(result.files.length, 3);
});

test('analyzeLoggingHealth — grade boundaries correct', () => {
  // 4 console.log = 12 deducted → 88 → B
  const filesB = [
    { path: 'src/b.js', content: 'console.log("1");\nconsole.log("2");\nconsole.log("3");\nconsole.log("4");' },
  ];
  const resultB = analyzeLoggingHealth(filesB);
  assert.equal(resultB.score, 88);
  assert.equal(resultB.grade, 'B');

  // 7 console.log = 21 deducted → 79 → C
  const filesC = [
    { path: 'src/c.js', content: Array.from({length: 7}, (_, i) => `console.log("${i}");`).join('\n') },
  ];
  const resultC = analyzeLoggingHealth(filesC);
  assert.equal(resultC.score, 79);
  assert.equal(resultC.grade, 'C');
});

test('formatLoggingHealthReport — null input returns warning', () => {
  const report = formatLoggingHealthReport(null);
  assert.ok(report.includes('⚠️'));
});

test('formatLoggingHealthReport — includes grade and score', () => {
  const files = [{ path: 'src/a.js', content: 'console.log("x");' }];
  const result = analyzeLoggingHealth(files);
  const report = formatLoggingHealthReport(result);
  assert.ok(report.includes('**Grade:**'));
  assert.ok(report.includes('console.log'));
  assert.ok(report.includes('src/a.js'));
});

test('formatLoggingHealthReport — includes summary table', () => {
  const files = [{ path: 'src/a.js', content: 'console.log("x");\nconsole.warn("w");' }];
  const result = analyzeLoggingHealth(files);
  const report = formatLoggingHealthReport(result);
  assert.ok(report.includes('| Metric |'));
  assert.ok(report.includes('| console.log |'));
  assert.ok(report.includes('| console.warn |'));
});

test('formatLoggingHealthReport — empty result still produces report', () => {
  const result = analyzeLoggingHealth([]);
  const report = formatLoggingHealthReport(result);
  assert.ok(report.includes('Logging Health'));
  assert.ok(report.includes('Grade:** A'));
});

test('analyzeLoggingHealth — console.log with complex arguments detected', () => {
  const files = [
    {
      path: 'src/complex.js',
      content: 'console.log("data:", { key: "value", nested: { a: 1 } }, extraVar);',
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.consoleLog, 1);
  assert.ok(result.files[0].issues[0].code.includes('console.log'));
});

test('analyzeLoggingHealth — catch with debug() is NOT flagged', () => {
  const files = [
    {
      path: 'src/api.js',
      content: [
        'try { x(); } catch(e) { debug(e); }',
      ].join('\n'),
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.catchWithoutLog, 0);
});

test('analyzeLoggingHealth — catch with winston is NOT flagged', () => {
  const files = [
    {
      path: 'src/api.js',
      content: [
        'try { x(); } catch(e) { winston.error(e); }',
      ].join('\n'),
    },
  ];
  const result = analyzeLoggingHealth(files);
  assert.equal(result.summary.catchWithoutLog, 0);
});
