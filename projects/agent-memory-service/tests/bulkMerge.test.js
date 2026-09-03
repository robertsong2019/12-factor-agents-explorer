import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('bulkMerge()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-bm-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('merges multiple pairs in sequence', async () => {
    const a = await svc.add({ content: 'Alpha', tags: ['x'] });
    const b = await svc.add({ content: 'Beta', tags: ['y'] });
    const c = await svc.add({ content: 'Gamma', tags: ['z'] });
    const d = await svc.add({ content: 'Delta', tags: ['w'] });

    const result = await svc.bulkMerge([[a.id, b.id], [c.id, d.id]]);
    assert.equal(result.merged, 2);
    assert.equal(result.failed, 0);
    // b and d should be deleted
    assert.equal(await svc.get(b.id), undefined);
    assert.equal(await svc.get(d.id), undefined);
    // a and c should have merged content
    const aMerged = await svc.get(a.id);
    const cMerged = await svc.get(c.id);
    assert.ok(aMerged.content.includes('Alpha'));
    assert.ok(aMerged.content.includes('Beta'));
    assert.ok(cMerged.content.includes('Gamma'));
    assert.ok(cMerged.content.includes('Delta'));
  });

  it('reports errors for already-merged memories', async () => {
    const a = await svc.add({ content: 'A' });
    const b = await svc.add({ content: 'B' });
    const c = await svc.add({ content: 'C' });

    // First merge a+b, then try merging b+c (b is deleted)
    const result = await svc.bulkMerge([[a.id, b.id], [b.id, c.id]]);
    assert.equal(result.merged, 1);
    assert.equal(result.failed, 1);
    assert.ok(result.errors[0].error.includes('not found'));
  });

  it('passes options through to memoryMerge', async () => {
    const a = await svc.add({ content: 'Short' });
    const b = await svc.add({ content: 'Much longer content here' });
    const result = await svc.bulkMerge([[a.id, b.id]], { contentStrategy: 'keep-longer' });
    assert.equal(result.merged, 1);
    const merged = await svc.get(a.id);
    assert.equal(merged.content, 'Much longer content here');
  });

  it('handles empty pairs array', async () => {
    const result = await svc.bulkMerge([]);
    assert.equal(result.merged, 0);
    assert.equal(result.failed, 0);
  });

  it('handles all invalid pairs gracefully', async () => {
    const result = await svc.bulkMerge([['fake1', 'fake2'], ['fake3', 'fake4']]);
    assert.equal(result.merged, 0);
    assert.equal(result.failed, 2);
  });
});
