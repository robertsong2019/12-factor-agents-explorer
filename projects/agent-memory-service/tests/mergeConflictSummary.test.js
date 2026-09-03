import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('mergeConflictSummary()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-mcs-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('returns empty for empty pairs', async () => {
    const result = await svc.mergeConflictSummary([]);
    assert.equal(result.summaries.length, 0);
    assert.equal(result.safeCount, 0);
  });

  it('summarizes single pair', async () => {
    const a = await svc.add({ content: 'Hello world', tags: ['x'], entities: ['e1'] });
    const b = await svc.add({ content: 'Hello world', tags: ['x'], entities: ['e1'] });
    const result = await svc.mergeConflictSummary([{ id1: a.id, id2: b.id }]);
    assert.equal(result.summaries.length, 1);
    assert.equal(result.summaries[0].id1, a.id);
    assert.ok(typeof result.summaries[0].risk === 'number');
  });

  it('counts safe and risky pairs', async () => {
    // Safe: identical
    const a = await svc.add({ content: 'Same same', tags: ['t'], entities: ['e'] });
    const b = await svc.add({ content: 'Same same', tags: ['t'], entities: ['e'] });
    // Risky: very different
    const c = await svc.add({ content: 'Completely different alpha', tags: ['z1', 'z2'], entities: ['x1', 'x2'] });
    const d = await svc.add({ content: 'Totally unrelated beta gamma', tags: ['y1', 'y2', 'y3'], entities: ['w1'] });

    const result = await svc.mergeConflictSummary([
      { id1: a.id, id2: b.id },
      { id1: c.id, id2: d.id },
    ]);
    assert.equal(result.summaries.length, 2);
    assert.ok(result.safeCount >= 1);
  });

  it('skips pairs with non-existent ids', async () => {
    const a = await svc.add({ content: 'Alpha' });
    const result = await svc.mergeConflictSummary([
      { id1: a.id, id2: 'no-such-id' },
    ]);
    assert.equal(result.summaries.length, 0);
  });

  it('computes avgRisk', async () => {
    const a = await svc.add({ content: 'A', tags: ['t'] });
    const b = await svc.add({ content: 'A', tags: ['t'] });
    const result = await svc.mergeConflictSummary([{ id1: a.id, id2: b.id }]);
    assert.ok(result.avgRisk >= 0 && result.avgRisk <= 1);
  });
});
