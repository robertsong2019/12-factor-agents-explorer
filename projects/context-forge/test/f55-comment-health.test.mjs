import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeCommentHealth, formatCommentHealthReport } from '../context-forge.mjs';

describe('F55: analyzeCommentHealth', () => {

  it('should return proper structure with grade and healthScore', () => {
    const files = [
      { path: 'a.js', content: '// A comment\nconst x = 1;\nconst y = 2;\nconst z = 3;\nconst w = 4;\n' },
    ];
    const result = analyzeCommentHealth(files);
    assert.ok(result.files);
    assert.ok(typeof result.healthScore === 'number');
    assert.ok(['A','B','C','D','F'].includes(result.grade));
    assert.equal(result.fileCount, 1);
  });

  it('should count code lines vs comment lines correctly', () => {
    const files = [
      {
        path: 'test.js',
        content: [
          '// Comment line 1',
          '// Comment line 2',
          'const a = 1;',
          'const b = 2;',
          'const c = 3;',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    assert.equal(result.files[0].commentLines, 2);
    assert.equal(result.files[0].codeLines, 3);
  });

  it('should handle block comments', () => {
    const files = [
      {
        path: 'block.js',
        content: [
          '/* Block comment */',
          'const x = 1;',
          '/*',
          ' * Multi-line',
          ' * block comment',
          ' */',
          'const y = 2;',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    // Line 1: single-line block → comment
    // Line 2: code
    // Lines 3-6: multi-line block → comment (4 lines)
    // Line 7: code
    assert.ok(result.files[0].commentLines >= 5);
    assert.equal(result.files[0].codeLines, 2);
  });

  it('should detect TODO and FIXME markers', () => {
    const files = [
      {
        path: 'todo.js',
        content: [
          '// TODO: implement this',
          '// FIXME: broken logic',
          'const x = 1;',
          'const y = 2;',
          'const z = 3;',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    assert.ok(result.totalTodoFixme >= 2);
    const todoFile = result.files[0];
    assert.ok(todoFile.issues.some(i => i.type === 'todo'));
    assert.ok(todoFile.issues.some(i => i.type === 'fixme'));
  });

  it('should detect HACK and @deprecated markers', () => {
    const files = [
      {
        path: 'hack.js',
        content: [
          '// HACK: workaround for bug',
          '// @deprecated use newFunc instead',
          'const old = 1;',
          'const val2 = 2;',
          'const val3 = 3;',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    const issues = result.files[0].issues;
    assert.ok(issues.some(i => i.type === 'hack'));
    assert.ok(issues.some(i => i.type === 'deprecated'));
  });

  it('should calculate doc coverage for exported symbols', () => {
    const files = [
      {
        path: 'exports.js',
        content: [
          '/**',
          ' * Adds two numbers.',
          ' */',
          'export function add(a, b) { return a + b; }',
          '',
          'export function sub(a, b) { return a - b; }',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    assert.equal(result.totalExportedSymbols, 2);
    assert.equal(result.totalDocumentedExports, 1);
    assert.ok(result.overallDocCoverage === 50);
  });

  it('should flag low comment ratio', () => {
    const lines = ['const a = 1;'];
    for (let i = 2; i <= 60; i++) lines.push(`const v${i} = ${i};`);
    const files = [{ path: 'sparse.js', content: lines.join('\n') }];
    const result = analyzeCommentHealth(files);
    assert.ok(result.files[0].issues.some(i => i.type === 'low_comment_ratio'));
  });

  it('should handle files with no content gracefully', () => {
    const files = [{ path: 'empty.js', content: '' }, { path: 'noop.js' }];
    const result = analyzeCommentHealth(files);
    assert.equal(result.fileCount, 0);
  });

  it('should skip files below minFileLines threshold', () => {
    const files = [{ path: 'tiny.js', content: 'const x = 1;\n' }];
    const result = analyzeCommentHealth(files);
    assert.equal(result.fileCount, 0);
  });

  it('should handle hash-style comments (#)', () => {
    const files = [
      {
        path: 'script.py',
        content: [
          '# Python comment',
          '# Another comment',
          'x = 1',
          'y = 2',
          'z = 3',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    assert.equal(result.files[0].commentLines, 2);
    assert.equal(result.files[0].codeLines, 3);
  });

  it('should produce non-empty markdown report', () => {
    const files = [
      {
        path: 'doc.js',
        content: [
          '/** Doc */',
          'export function foo() {',
          '  // TODO: finish',
          '  return 1;',
          '}',
        ].join('\n'),
      },
    ];
    const result = analyzeCommentHealth(files);
    const report = formatCommentHealthReport(result);
    assert.ok(report.includes('## Comment Health Analysis'));
    assert.ok(report.length > 100);
  });

  it('should handle empty results in report', () => {
    const report = formatCommentHealthReport(null);
    assert.ok(report.includes('⚠️'));
  });

  it('should compute aggregate stats across multiple files', () => {
    const files = [
      { path: 'a.js', content: '// hello\nconst x = 1;\nconst y = 2;\nconst z = 3;\nconst w = 4;\n' },
      { path: 'b.js', content: '// world\nconst a = 1;\nconst b = 2;\nconst c = 3;\nconst d = 4;\n' },
    ];
    const result = analyzeCommentHealth(files);
    assert.equal(result.fileCount, 2);
    assert.ok(result.totalCodeLines >= 8);
    assert.ok(result.totalCommentLines >= 2);
  });
});
