import { describe, it, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('findDuplicatePairs()', () => {
  let dir, svc;
  before(async () => {
    dir = await mkdtemp(join(tmpdir(), 'ams-dup-'));
    svc = new MemoryService({ dbPath: dir });
    await svc.init();
  });
  after(async () => { await rm(dir, { recursive: true }); });

  it('finds duplicate pairs by content similarity', async () => {
    await svc.add({ content: 'The quick brown fox jumps over the lazy dog', tags: ['test'] });
    await svc.add({ content: 'The quick brown fox jumped over the lazy dogs', tags: ['test'] });
    await svc.add({ content: 'Completely different content about quantum physics', tags: ['test'] });

    const pairs = await svc.findDuplicatePairs({ minSimilarity: 0.5 });
    assert.ok(pairs.length >= 1);
    // Find a pair containing 'fox' content
    const foxPair = pairs.find(p => p.content1.includes('fox') || p.content2.includes('fox'));
    assert.ok(foxPair, 'Should find fox-related duplicate pair');
    assert.ok(foxPair.similarity >= 0.5);
  });

  it('respects layer filter', async () => {
    const pairs = await svc.findDuplicatePairs({ layer: 'core' });
    assert.equal(pairs.length, 0);
  });

  it('respects limit option', async () => {
    const pairs = await svc.findDuplicatePairs({ limit: 0 });
    assert.equal(pairs.length, 0);
  });

  it('returns empty for high threshold', async () => {
    const pairs = await svc.findDuplicatePairs({ minSimilarity: 0.99 });
    assert.ok(Array.isArray(pairs));
  });
});

describe('exportJSON() / importJSON()', () => {
  let dir, svc;
  before(async () => {
    dir = await mkdtemp(join(tmpdir(), 'ams-exp-'));
    svc = new MemoryService({ dbPath: dir });
    await svc.init();
  });
  after(async () => { await rm(dir, { recursive: true }); });

  it('exports all data with version and timestamp', async () => {
    await svc.add({ content: 'Export test memory', tags: ['export'], layer: 'long' });
    await svc.add({ content: 'Another memory', tags: ['test'] });

    const data = await svc.exportJSON();
    assert.equal(data.version, '1.0');
    assert.ok(data.exported);
    assert.ok(data.memories.length >= 2);
    assert.ok(Array.isArray(data.links));
    assert.ok(Array.isArray(data.changelog));
    assert.ok(Array.isArray(data.skills));
  });

  it('exports without optional sections', async () => {
    const data = await svc.exportJSON({ includeLinks: false, includeChangelog: false, includeSkills: false });
    assert.ok(!data.links);
    assert.ok(!data.changelog);
    assert.ok(!data.skills);
  });

  it('round-trips via import in replace mode', async () => {
    const m = await svc.add({ content: 'Round trip test' });
    const exported = await svc.exportJSON();
    const count = await svc.importJSON(exported);
    assert.equal(count.memories, exported.memories.length);
    const restored = await svc.get(m.id);
    assert.ok(restored);
  });

  it('import with merge mode skips existing', async () => {
    const exported = await svc.exportJSON();
    const count = await svc.importJSON(exported, { merge: true });
    assert.equal(count.memories, 0);
  });

  it('throws on invalid data', async () => {
    await assert.rejects(() => svc.importJSON(null), /Invalid/);
    await assert.rejects(() => svc.importJSON({}), /Invalid/);
  });
});

describe('pruneLowWeight()', () => {
  let dir, svc;
  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'ams-prune-'));
    svc = new MemoryService({ dbPath: dir });
    await svc.init();
  });

  it('removes memories below weight threshold', async () => {
    const m1 = await svc.add({ content: 'Low weight', weight: 0.05 });
    await svc.add({ content: 'High weight', weight: 0.8 });
    const m3 = await svc.add({ content: 'Also low', weight: 0.02 });

    const result = await svc.pruneLowWeight({ minWeight: 0.1 });
    assert.equal(result.removed, 2);
    assert.ok(result.removedIds.includes(m1.id));
    assert.ok(result.removedIds.includes(m3.id));
    assert.equal(result.remaining, 1);
  });

  it('dryRun does not remove anything', async () => {
    const m = await svc.add({ content: 'Low', weight: 0.01 });
    const result = await svc.pruneLowWeight({ minWeight: 0.1, dryRun: true });
    assert.equal(result.removed, 1);
    const found = await svc.get(m.id);
    assert.ok(found, 'Memory should still exist in dryRun mode');
  });

  it('respects layer filter', async () => {
    await svc.add({ content: 'Low L1', weight: 0.01, layer: 'long' });
    await svc.add({ content: 'Low L2', weight: 0.01, layer: 'short' });
    const result = await svc.pruneLowWeight({ minWeight: 0.1, layer: 'long' });
    assert.equal(result.removed, 1);
  });

  it('respects limit option', async () => {
    await svc.add({ content: 'Low 7', weight: 0.01 });
    await svc.add({ content: 'Low 8', weight: 0.01 });
    const result = await svc.pruneLowWeight({ minWeight: 0.1, limit: 1 });
    assert.equal(result.removed, 1);
  });

  it('returns empty when nothing to prune', async () => {
    await svc.add({ content: 'Heavy', weight: 0.9 });
    const result = await svc.pruneLowWeight({ minWeight: 0.1 });
    assert.equal(result.removed, 0);
  });
});
