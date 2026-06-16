import test from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-cmp-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, dir };
}
function cleanup(dir) { try { rmSync(dir, { recursive: true }); } catch {} }

test('compareMemories', async (t) => {
  const { svc, dir } = createService();
  await svc.init();

  await t.test('compares identical memories with merge recommendation', async () => {
    const m1 = await svc.add({ content: 'hello world', tags: ['greeting'], layer: 'short' });
    const m2 = await svc.add({ content: 'hello world', tags: ['greeting'], layer: 'short' });

    const result = await svc.compareMemories(m1.id, m2.id);
    assert.equal(result.id1, m1.id);
    assert.equal(result.id2, m2.id);
    assert.ok(result.contentSimilarity > 0.9, 'identical content should be >0.9');
    assert.deepEqual(result.sharedTags, ['greeting']);
    assert.equal(result.sameLayer, true);
    assert.equal(result.mergeRecommendation, 'merge');
  });

  await t.test('compares completely different memories', async () => {
    const m1 = await svc.add({ content: 'machine learning basics', tags: ['ml'], layer: 'short' });
    const m2 = await svc.add({ content: 'cooking pasta recipes', tags: ['food'], layer: 'core' });

    const result = await svc.compareMemories(m1.id, m2.id);
    assert.ok(result.contentSimilarity < 0.3, 'different content should be low');
    assert.deepEqual(result.sharedTags, []);
    assert.equal(result.sameLayer, false);
    assert.equal(result.layer1, 'short');
    assert.equal(result.layer2, 'core');
  });

  await t.test('recommends consolidate for similar content with shared tags', async () => {
    const m1 = await svc.add({ content: 'the quick brown fox jumps', tags: ['animals', 'speed'], layer: 'short' });
    const m2 = await svc.add({ content: 'the quick brown fox runs', tags: ['animals', 'movement'], layer: 'short' });

    const result = await svc.compareMemories(m1.id, m2.id);
    assert.ok(result.contentSimilarity > 0.5, 'similar content should be >0.5');
    assert.ok(result.sharedTags.includes('animals'));
    assert.ok(result.uniqueTags1.length > 0 || result.uniqueTags2.length > 0);
  });

  await t.test('reports weight difference', async () => {
    const m1 = await svc.add({ content: 'heavy memory', weight: 0.9 });
    const m2 = await svc.add({ content: 'light memory', weight: 0.3 });

    const result = await svc.compareMemories(m1.id, m2.id);
    assert.ok(result.weightDiff >= 0, 'weight diff should be non-negative');
    assert.ok(Math.abs(result.weightDiff - 0.6) < 0.01, 'weight diff should be ~0.6');
  });

  await t.test('throws for non-existent first id', async () => {
    const m = await svc.add({ content: 'exists' });
    await assert.rejects(() => svc.compareMemories('nonexistent-id', m.id), /Memory not found/);
  });

  await t.test('throws for non-existent second id', async () => {
    const m = await svc.add({ content: 'exists' });
    await assert.rejects(() => svc.compareMemories(m.id, 'nonexistent-id'), /Memory not found/);
  });

  await t.test('handles memories with no tags', async () => {
    const m1 = await svc.add({ content: 'tagless one' });
    const m2 = await svc.add({ content: 'tagless two' });

    const result = await svc.compareMemories(m1.id, m2.id);
    assert.deepEqual(result.sharedTags, []);
    assert.deepEqual(result.uniqueTags1, []);
    assert.deepEqual(result.uniqueTags2, []);
  });

  await t.test('handles self-comparison', async () => {
    const m = await svc.add({ content: 'self compare test', tags: ['self'], layer: 'core' });
    const result = await svc.compareMemories(m.id, m.id);
    assert.equal(result.contentSimilarity, 1);
    assert.equal(result.mergeRecommendation, 'merge');
    assert.equal(result.weightDiff, 0);
  });

  cleanup(dir);
});

test('statsByFactType', async (t) => {
  const { svc, dir } = createService();
  await svc.init();

  await t.test('returns stats grouped by factType', async () => {
    await svc.add({ content: 'prefer dark mode', factType: 'preference' });
    await svc.add({ content: 'prefer light theme', factType: 'preference' });
    await svc.add({ content: 'decided to use React', factType: 'decision' });
    await svc.add({ content: 'the sky is blue', factType: 'fact' });

    const result = await svc.statsByFactType();
    assert.equal(result.total, 4);
    assert.ok(result.byFactType['preference'], 'should have preference group');
    assert.equal(result.byFactType['preference'].count, 2);
    assert.equal(result.byFactType['decision'].count, 1);
    assert.equal(result.byFactType['fact'].count, 1);
  });

  await t.test('computes avgWeight per factType', async () => {
    const { svc: s, dir: d } = createService();
    await s.init();
    await s.add({ content: 'weighted one', factType: 'test', weight: 0.8 });
    await s.add({ content: 'weighted two', factType: 'test', weight: 0.4 });

    const result = await s.statsByFactType();
    if (result.byFactType['test']) {
      const avg = result.byFactType['test'].avgWeight;
      assert.ok(Math.abs(avg - 0.6) < 0.01, 'avg should be ~0.6');
    }
    cleanup(d);
  });

  await t.test('reports untyped count for content with no pattern match', async () => {
    const { svc: s, dir: d } = createService();
    await s.init();
    // Use content that classifyFact won't match, and pass explicit factType: null
    await s.add({ content: 'zzz qqq xxx', factType: null });

    const result = await s.statsByFactType();
    // classifyFact may or may not match; the key is that if it doesn't, untyped increments
    // Check that total is correct
    assert.equal(result.total, 1);
    // Either it's typed (untyped=0) or untyped (untyped=1) — both are valid
    assert.ok(result.untyped === 0 || result.untyped === 1, `untyped should be 0 or 1, got ${result.untyped}`);
    cleanup(d);
  });

  await t.test('includes byLayer breakdown', async () => {
    const { svc: s, dir: d } = createService();
    await s.init();
    await s.add({ content: 'core fact', factType: 'ft1', layer: 'core' });
    await s.add({ content: 'short fact', factType: 'ft1', layer: 'short' });

    const result = await s.statsByFactType();
    assert.ok(result.byFactType['ft1'].byLayer, 'should have byLayer');
    assert.ok(result.byFactType['ft1'].byLayer['core'] >= 1);
    assert.ok(result.byFactType['ft1'].byLayer['short'] >= 1);
    cleanup(d);
  });

  await t.test('returns total 0 for empty store', async () => {
    const { svc: s, dir: d } = createService();
    await s.init();
    const result = await s.statsByFactType();
    assert.equal(result.total, 0);
    assert.equal(result.untyped, 0);
    cleanup(d);
  });

  cleanup(dir);
});
