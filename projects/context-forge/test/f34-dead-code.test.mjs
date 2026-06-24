import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { detectDeadCode, formatDeadCodeReport } from '../context-forge.mjs';

describe('detectDeadCode', () => {
  test('returns empty for null/undefined inputs', () => {
    const r = detectDeadCode(null, null);
    assert.equal(r.dead.length, 0);
    assert.equal(r.total, 0);
    assert.equal(r.unused, 0);
  });

  test('returns empty for empty objects', () => {
    const r = detectDeadCode({}, {});
    assert.equal(r.dead.length, 0);
  });

  test('detects unused exports', () => {
    const importData = {
      'src/a.ts': [{ name: 'used1' }],
    };
    const apiSurface = {
      'src/mod.ts': [
        { name: 'used1', type: 'function' },
        { name: 'unused1', type: 'function' },
        { name: 'unused2', type: 'class' },
      ],
    };
    const r = detectDeadCode(importData, apiSurface);
    assert.equal(r.total, 3);
    assert.equal(r.unused, 2);
    assert.equal(r.used, 1);
    const names = r.dead.map(d => d.symbol).sort();
    assert.deepEqual(names, ['unused1', 'unused2']);
  });

  test('handles string exports', () => {
    const r = detectDeadCode({}, { 'mod.ts': ['foo', 'bar'] });
    assert.equal(r.total, 2);
    assert.equal(r.unused, 2);
  });

  test('marks referenced symbol as used', () => {
    const importData = {
      'consumer.ts': [{ name: 'foo' }],
    };
    const apiSurface = {
      'lib.ts': [{ name: 'foo' }, { name: 'bar' }],
    };
    const r = detectDeadCode(importData, apiSurface);
    assert.equal(r.used, 1);
    assert.equal(r.unused, 1);
    assert.equal(r.dead[0].symbol, 'bar');
  });

  test('handles destructured import strings', () => {
    const importData = {
      'c.ts': [{ imported: '{ a, b, c }' }],
    };
    const apiSurface = {
      'lib.ts': [{ name: 'a' }, { name: 'b' }, { name: 'c' }, { name: 'd' }],
    };
    const r = detectDeadCode(importData, apiSurface);
    assert.equal(r.used, 3);
    assert.equal(r.unused, 1);
    assert.equal(r.dead[0].symbol, 'd');
  });

  test('skips entries without names', () => {
    const apiSurface = {
      'mod.ts': [{ type: 'function' }, null, { name: 'x' }],
    };
    const r = detectDeadCode({}, apiSurface);
    assert.equal(r.total, 3);
    assert.equal(r.unused, 1); // only 'x' has a name
  });

  test('handles imp.imported field', () => {
    const importData = {
      'c.ts': [{ imported: 'myFunc' }],
    };
    const apiSurface = {
      'lib.ts': [{ name: 'myFunc' }, { name: 'other' }],
    };
    const r = detectDeadCode(importData, apiSurface);
    assert.equal(r.used, 1);
    assert.equal(r.dead[0].symbol, 'other');
  });

  test('groups dead by file correctly', () => {
    const apiSurface = {
      'a.ts': [{ name: 'x' }],
      'b.ts': [{ name: 'y' }],
    };
    const r = detectDeadCode({}, apiSurface);
    const files = r.dead.map(d => d.file).sort();
    assert.deepEqual(files, ['a.ts', 'b.ts']);
  });

  test('handles non-array imports gracefully', () => {
    const importData = { 'bad.ts': 'not-an-array' };
    const apiSurface = { 'mod.ts': [{ name: 'x' }] };
    const r = detectDeadCode(importData, apiSurface);
    assert.equal(r.unused, 1);
  });

  test('handles non-array exports gracefully', () => {
    const r = detectDeadCode({}, { 'bad.ts': 'not-an-array' });
    assert.equal(r.total, 0);
    assert.equal(r.unused, 0);
  });
});

describe('formatDeadCodeReport', () => {
  test('no dead code message', () => {
    const msg = formatDeadCodeReport({ dead: [], total: 5, used: 5, unused: 0 });
    assert.ok(msg.includes('✅'));
    assert.ok(msg.includes('No dead code'));
  });

  test('null input returns safe message', () => {
    const msg = formatDeadCodeReport(null);
    assert.ok(msg.includes('✅'));
  });

  test('formats dead code with file grouping', () => {
    const result = {
      dead: [
        { file: 'a.ts', symbol: 'unused1', type: 'function' },
        { file: 'a.ts', symbol: 'unused2', type: 'class' },
        { file: 'b.ts', symbol: 'unused3', type: 'function' },
      ],
      total: 5,
      used: 2,
      unused: 3,
    };
    const msg = formatDeadCodeReport(result);
    assert.ok(msg.includes('3/5 exports unused'));
    assert.ok(msg.includes('**a.ts** (2 unused):'));
    assert.ok(msg.includes('`unused1`'));
    assert.ok(msg.includes('`unused3`'));
    assert.ok(msg.includes('2 used / 3 unused / 5 total'));
  });

  test('includes summary line', () => {
    const result = {
      dead: [{ file: 'x.ts', symbol: 'foo' }],
      total: 2,
      used: 1,
      unused: 1,
    };
    const msg = formatDeadCodeReport(result);
    assert.ok(msg.includes('**Summary:**'));
  });
});
