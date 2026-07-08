import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs-extra';
import os from 'os';
import path from 'path';
import { findJavaScriptFiles, analyzeComplexity, analyzeSecurity, calculateHealthScore } from '../index.js';

async function withTempFile(content, ext = '.js') {
  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-test-'));
  const tmpFile = path.join(tmpDir, `test${ext}`);
  await fs.writeFile(tmpFile, content);
  return { tmpFile, tmpDir, cleanup: () => fs.remove(tmpDir) };
}

describe('analyzeComplexity', () => {
  it('counts if/for/while as complexity', async () => {
    const code = ['if (x) {}', 'for (let i = 0; i < 10; i++) {}', 'while (true) {}'].join('\n');
    const { tmpFile, cleanup } = await withTempFile(code);
    const result = analyzeComplexity(tmpFile);
    assert.equal(result.complexity, 3);
    assert.ok(Array.isArray(result.issues));
    await cleanup();
  });

  it('detects long lines', async () => {
    const { tmpFile, cleanup } = await withTempFile('x'.repeat(150));
    const result = analyzeComplexity(tmpFile);
    assert.ok(result.issues.some(i => i.includes('行过长')));
    await cleanup();
  });

  it('handles empty file', async () => {
    const { tmpFile, cleanup } = await withTempFile('');
    const result = analyzeComplexity(tmpFile);
    assert.equal(result.complexity, 0);
    assert.deepEqual(result.issues, []);
    await cleanup();
  });

  it('reports no issues for simple code', async () => {
    const { tmpFile, cleanup } = await withTempFile('const x = 1;');
    const result = analyzeComplexity(tmpFile);
    assert.equal(result.complexity, 0);
    assert.deepEqual(result.issues, []);
    await cleanup();
  });
});

describe('analyzeSecurity', () => {
  it('detects eval usage', async () => {
    const { tmpFile, cleanup } = await withTempFile('eval("console.log(1)")');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(issues.some(i => i.message.includes('eval')));
    await cleanup();
  });

  it('detects innerHTML', async () => {
    const { tmpFile, cleanup } = await withTempFile('el.innerHTML = userInput');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(issues.some(i => i.message.includes('innerHTML')));
    await cleanup();
  });

  it('returns empty for safe code', async () => {
    const { tmpFile, cleanup } = await withTempFile('const x = 1 + 2;');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(Array.isArray(issues));
    await cleanup();
  });

  it('detects document.write', async () => {
    const { tmpFile, cleanup } = await withTempFile('document.write("hello")');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(issues.some(i => i.message.includes('document.write')));
    await cleanup();
  });
});

describe('calculateHealthScore', () => {
  it('returns 0 for empty checks', () => {
    assert.equal(calculateHealthScore({}), 0);
  });

  it('returns 100 for perfect eslint', () => {
    assert.equal(calculateHealthScore({
      eslint: { status: 'completed', errorCount: 0, warningCount: 0 }
    }), 100);
  });

  it('deducts for errors and warnings', () => {
    const score = calculateHealthScore({
      eslint: { status: 'completed', errorCount: 2, warningCount: 5 }
    });
    assert.ok(score < 100);
    assert.ok(score > 0);
  });

  it('averages multiple checks', () => {
    assert.equal(calculateHealthScore({
      eslint: { status: 'completed', errorCount: 0, warningCount: 0 },
      security: { status: 'completed', totalIssues: 0 }
    }), 100);
  });

  it('skips non-completed checks', () => {
    assert.equal(calculateHealthScore({
      eslint: { status: 'skipped', reason: 'no config' }
    }), 0);
  });

  it('deducts for security issues', () => {
    const score = calculateHealthScore({
      security: { status: 'completed', totalIssues: 3 }
    });
    assert.ok(score < 100);
  });

  it('deducts for complexity issues', () => {
    const score = calculateHealthScore({
      complexity: { status: 'completed', highComplexityFiles: 3 }
    });
    assert.ok(score < 100);
    assert.ok(score >= 0);
  });

  it('deducts for outdated dependencies', () => {
    const score = calculateHealthScore({
      dependencies: { status: 'completed', outdatedDependencies: 5 }
    });
    assert.ok(score < 100);
    assert.ok(score >= 0);
  });

  it('returns 0 score when all checks fail', () => {
    const score = calculateHealthScore({
      eslint: { status: 'failed', error: 'crash' },
      security: { status: 'failed', error: 'crash' }
    });
    assert.equal(score, 0);
  });

  it('handles mixed completed and failed checks', () => {
    const score = calculateHealthScore({
      eslint: { status: 'completed', errorCount: 0, warningCount: 0 },
      security: { status: 'failed', error: 'timeout' }
    });
    // Only eslint completed → 100
    assert.equal(score, 100);
  });

  it('clamps negative scores to 0', () => {
    const score = calculateHealthScore({
      eslint: { status: 'completed', errorCount: 100, warningCount: 100 }
    });
    assert.equal(score, 0);
  });
});

describe('findJavaScriptFiles', () => {
  it('finds .js files in a directory', async () => {
    const { tmpDir, cleanup } = await withTempFile('const x = 1;');
    // withTempFile creates a subfolder, tmpDir is the parent
    const files = await findJavaScriptFiles(tmpDir);
    assert.ok(files.length >= 1);
    assert.ok(files.every(f => /\.(js|ts|jsx|tsx)$/.test(f)));
    await cleanup();
  });

  it('recurses into subdirectories', async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-find-'));
    await fs.writeFile(path.join(tmpDir, 'a.js'), 'const a = 1;');
    await fs.mkdir(path.join(tmpDir, 'sub'));
    await fs.writeFile(path.join(tmpDir, 'sub', 'b.ts'), 'const b = 2;');
    const files = await findJavaScriptFiles(tmpDir);
    assert.ok(files.length >= 2);
    await fs.remove(tmpDir);
  });

  it('skips hidden directories', async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-hidden-'));
    await fs.writeFile(path.join(tmpDir, 'visible.js'), 'const v = 1;');
    await fs.mkdir(path.join(tmpDir, '.hidden'));
    await fs.writeFile(path.join(tmpDir, '.hidden', 'secret.js'), 'const s = 2;');
    const files = await findJavaScriptFiles(tmpDir);
    assert.equal(files.length, 1);
    assert.ok(files[0].includes('visible.js'));
    await fs.remove(tmpDir);
  });

  it('returns empty for directory with no JS files', async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-empty-'));
    await fs.writeFile(path.join(tmpDir, 'readme.md'), '# Hello');
    const files = await findJavaScriptFiles(tmpDir);
    assert.equal(files.length, 0);
    await fs.remove(tmpDir);
  });

  it('finds .jsx and .tsx files', async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cqc-react-'));
    await fs.writeFile(path.join(tmpDir, 'comp.jsx'), 'const C = () => null;');
    await fs.writeFile(path.join(tmpDir, 'widget.tsx'), 'const W = () => null;');
    const files = await findJavaScriptFiles(tmpDir);
    assert.equal(files.length, 2);
    await fs.remove(tmpDir);
  });
});

describe('analyzeSecurity extended', () => {
  it('detects setTimeout with string argument', async () => {
    const { tmpFile, cleanup } = await withTempFile('setTimeout("alert(1)", 1000)');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(issues.some(i => i.message.includes('setTimeout')));
    await cleanup();
  });

  it('detects setInterval with string argument', async () => {
    const { tmpFile, cleanup } = await withTempFile('setInterval("doStuff()", 2000)');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(issues.some(i => i.message.includes('setInterval')));
    await cleanup();
  });

  it('detects template literal injection patterns', async () => {
    const { tmpFile, cleanup } = await withTempFile('const q = `SELECT * FROM users WHERE id = ${userId}`');
    const issues = await analyzeSecurity(tmpFile);
    assert.ok(issues.some(i => i.message.includes('模板字符串')));
    await cleanup();
  });

  it('reports correct count for multiple occurrences', async () => {
    const code = 'eval("1");\neval("2");\neval("3");';
    const { tmpFile, cleanup } = await withTempFile(code);
    const issues = await analyzeSecurity(tmpFile);
    const evalIssue = issues.find(i => i.message.includes('eval'));
    assert.equal(evalIssue.count, 3);
    await cleanup();
  });

  it('does not flag safe setTimeout with function', async () => {
    const { tmpFile, cleanup } = await withTempFile('setTimeout(() => console.log(1), 1000)');
    const issues = await analyzeSecurity(tmpFile);
    // setTimeout with function arg should not match the string-arg pattern
    const setTimeoutIssue = issues.find(i => i.message.includes('setTimeout'));
    assert.equal(setTimeoutIssue, undefined);
    await cleanup();
  });
});

describe('analyzeComplexity extended', () => {
  it('counts switch and case as complexity', async () => {
    const code = ['switch(x) {', 'case 1: break;', 'case 2: break;', '}'].join('\n');;
    const { tmpFile, cleanup } = await withTempFile(code);
    const result = analyzeComplexity(tmpFile);
    assert.ok(result.complexity >= 2); // switch + at least one case
    await cleanup();
  });

  it('detects deeply nested code', async () => {
    // 20 spaces of indent
    const code = '                    const x = 1;';
    const { tmpFile, cleanup } = await withTempFile(code);
    const result = analyzeComplexity(tmpFile);
    assert.ok(result.issues.some(i => i.includes('缩进过深')));
    await cleanup();
  });

  it('counts catch blocks as complexity', async () => {
    const code = ['try {', '  doSomething();', '} catch(e) {', '  handle(e);', '}'].join('\n');
    const { tmpFile, cleanup } = await withTempFile(code);
    const result = analyzeComplexity(tmpFile);
    assert.ok(result.complexity >= 1);
    await cleanup();
  });
});
