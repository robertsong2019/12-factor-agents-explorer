import { describe, it, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { mkdtempSync, rmSync } from 'node:fs';
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

// ─── compareMemories(id1, id2) ────────────────────────
describe('compareMemories()', () => {
it('compareMemories — detailed comparison', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-cmp-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  const m1 = await svc.add({ content: 'Agent memory architecture patterns', tags: ['agent', 'memory'], layer: 'core', weight: 0.9 });
  const m2 = await svc.add({ content: 'Agent memory design patterns overview', tags: ['agent', 'design'], layer: 'core', weight: 0.7 });

  const result = await svc.compareMemories(m1.id, m2.id);

  assert.equal(result.id1, m1.id);
  assert.equal(result.id2, m2.id);
  assert.ok(result.contentSimilarity > 0.3, `Expected similarity > 0.3, got ${result.contentSimilarity}`);
  assert.deepEqual(result.sharedTags, ['agent']);
  assert.deepEqual(result.uniqueTags1, ['memory']);
  assert.deepEqual(result.uniqueTags2, ['design']);
  assert.equal(result.sameLayer, true);
  assert.equal(result.layer1, 'core');
  assert.ok(result.weightDiff > 0);
  assert.ok(['keep_both', 'merge', 'consolidate', 'link'].includes(result.mergeRecommendation));

  rmSync(tmp, { recursive: true, force: true });
});

it('compareMemories — identical content suggests merge', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-cmp2-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  const m1 = await svc.add({ content: 'exact same content here', layer: 'long' });
  const m2 = await svc.add({ content: 'exact same content here', layer: 'long' });

  const result = await svc.compareMemories(m1.id, m2.id);
  assert.equal(result.contentSimilarity, 1);
  assert.equal(result.mergeRecommendation, 'merge');

  rmSync(tmp, { recursive: true, force: true });
});

it('compareMemories — different content keep both', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-cmp3-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  const m1 = await svc.add({ content: 'Python web framework comparison' });
  const m2 = await svc.add({ content: 'Rust systems programming guide' });

  const result = await svc.compareMemories(m1.id, m2.id);
  assert.equal(result.mergeRecommendation, 'keep_both');

  rmSync(tmp, { recursive: true, force: true });
});

it('compareMemories — throws for missing id', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-cmp4-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  const m = await svc.add({ content: 'test' });
  await assert.rejects(() => svc.compareMemories(m.id, 'nonexistent'), /Memory not found/);

  rmSync(tmp, { recursive: true, force: true });
});

it('compareMemories — respects different layers', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-cmp5-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  const m1 = await svc.add({ content: 'same content here', layer: 'core' });
  const m2 = await svc.add({ content: 'same content here', layer: 'short' });

  const result = await svc.compareMemories(m1.id, m2.id);
  assert.equal(result.sameLayer, false);
  // Identical content but different layers → not 'merge' (merge requires sameLayer)
  assert.notEqual(result.mergeRecommendation, 'merge');

  rmSync(tmp, { recursive: true, force: true });
});
});

// ─── tagHierarchy(opts) ────────────────────────
describe('tagHierarchy()', () => {
it('builds hierarchy from co-occurring tags', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-th-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  // agent appears 3x with memory, design, architecture
  await svc.add({ content: 'c1', tags: ['agent', 'memory'] });
  await svc.add({ content: 'c2', tags: ['agent', 'design'] });
  await svc.add({ content: 'c3', tags: ['agent', 'architecture'] });
  // standalone
  await svc.add({ content: 'c4', tags: ['unrelated'] });

  const result = await svc.tagHierarchy({ minCoOccurrence: 1 });
  assert.ok(result.hierarchy.agent, 'agent should be a parent');
  assert.ok(result.hierarchy.agent.includes('memory'));
  assert.ok(result.hierarchy.agent.includes('design'));
  assert.ok(result.roots.includes('agent'));
  assert.equal(result.stats.totalTags, 5);
  assert.ok(result.stats.depth >= 1);

  rmSync(tmp, { recursive: true, force: true });
});

it('respects minCoOccurrence threshold', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-th2-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  await svc.add({ content: 'c1', tags: ['a', 'b'] }); // co-occur once
  await svc.add({ content: 'c2', tags: ['a', 'c'] }); // co-occur once
  await svc.add({ content: 'c3', tags: ['a', 'b'] }); // a+b now co-occur twice

  const result = await svc.tagHierarchy({ minCoOccurrence: 2 });
  assert.ok(result.hierarchy.a, 'a should be parent at threshold 2');
  assert.ok(result.hierarchy.a.includes('b'));
  assert.ok(!result.hierarchy.a.includes('c'), 'c should not appear (only co-occurs once)');

  rmSync(tmp, { recursive: true, force: true });
});

it('returns empty for no tags', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-th3-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  await svc.add({ content: 'no tags here' });

  const result = await svc.tagHierarchy();
  assert.deepEqual(result.hierarchy, {});
  assert.deepEqual(result.roots, []);
  assert.equal(result.stats.totalTags, 0);

  rmSync(tmp, { recursive: true, force: true });
});

it('respects layer filter', async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'ams-th4-'));
  const svc = new MemoryService({ dbPath: tmp });
  await svc.init();

  await svc.add({ content: 'c1', tags: ['a', 'b'], layer: 'core' });
  await svc.add({ content: 'c2', tags: ['a', 'b'], layer: 'core' });
  await svc.add({ content: 'c3', tags: ['x', 'y'], layer: 'short' });

  const result = await svc.tagHierarchy({ layer: 'core' });
  assert.ok(result.hierarchy.a);
  assert.ok(!result.hierarchy.x, 'short layer tags should be excluded');

  rmSync(tmp, { recursive: true, force: true });
});
});
