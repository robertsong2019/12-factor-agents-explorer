import test from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-hier-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, dir };
}
function cleanup(dir) { try { rmSync(dir, { recursive: true }); } catch {} }

async function seed(svc, items) {
  const ids = [];
  for (const item of items) {
    const m = await svc.add(item);
    ids.push(m.id);
  }
  return ids;
}

test('tagHierarchy', async (t) => {
  await t.test('builds hierarchy from co-occurring tags', async () => {
    const { svc, dir } = createService();
    await svc.init();
    await seed(svc, [
      { content: 'item one', tags: ['ai', 'ml', 'python'] },
      { content: 'item two', tags: ['ai', 'ml', 'pytorch'] },
      { content: 'item three', tags: ['ai', 'nlp'] },
      { content: 'item four', tags: ['web', 'react'] },
    ]);

    const result = await svc.tagHierarchy({ minCoOccurrence: 2 });
    assert.ok(result.hierarchy, 'should have hierarchy');
    assert.ok(result.roots, 'should have roots');
    assert.ok(result.stats, 'should have stats');
    assert.ok(result.stats.totalTags >= 4, 'should detect at least 4 tags');
    cleanup(dir);
  });

  await t.test('returns empty hierarchy when no co-occurrences meet threshold', async () => {
    const { svc, dir } = createService();
    await svc.init();
    await seed(svc, [
      { content: 'solo one', tags: ['solo-a'] },
      { content: 'solo two', tags: ['solo-b'] },
    ]);

    const result = await svc.tagHierarchy({ minCoOccurrence: 5 });
    assert.deepEqual(result.roots, []);
    assert.equal(result.stats.depth, 0);
    cleanup(dir);
  });

  await t.test('filters by layer', async () => {
    const { svc, dir } = createService();
    await svc.init();
    await seed(svc, [
      { content: 'core item', tags: ['ai', 'ml'], layer: 'core' },
      { content: 'short item', tags: ['ai', 'ml'], layer: 'short' },
      { content: 'short item 2', tags: ['ai', 'ml'], layer: 'short' },
    ]);

    const coreResult = await svc.tagHierarchy({ layer: 'core', minCoOccurrence: 1 });
    const shortResult = await svc.tagHierarchy({ layer: 'short', minCoOccurrence: 1 });
    assert.ok(coreResult.stats.totalTags <= 2);
    assert.ok(shortResult.stats.totalTags >= 2);
    cleanup(dir);
  });

  await t.test('returns empty for truly empty store', async () => {
    const { svc, dir } = createService();
    await svc.init();

    const result = await svc.tagHierarchy();
    assert.equal(result.stats.totalTags, 0);
    assert.equal(result.stats.totalPairs, 0);
    assert.deepEqual(result.roots, []);
    cleanup(dir);
  });

  await t.test('respects minCoOccurrence parameter', async () => {
    const { svc, dir } = createService();
    await svc.init();
    await seed(svc, [
      { content: 'a', tags: ['x', 'y'] },
      { content: 'b', tags: ['x', 'y'] },
      { content: 'c', tags: ['x', 'y'] },
    ]);

    const lowThreshold = await svc.tagHierarchy({ minCoOccurrence: 2 });
    const highThreshold = await svc.tagHierarchy({ minCoOccurrence: 5 });
    assert.ok(Object.keys(lowThreshold.hierarchy).length > 0, 'should find pairs at threshold=2');
    assert.deepEqual(highThreshold.roots, [], 'should find nothing at threshold=5');
    cleanup(dir);
  });

  await t.test('computes max depth correctly', async () => {
    const { svc, dir } = createService();
    await svc.init();
    await seed(svc, [
      { content: 'd1', tags: ['a', 'b'] },
      { content: 'd2', tags: ['a', 'b'] },
      { content: 'd3', tags: ['b', 'c'] },
      { content: 'd4', tags: ['b', 'c'] },
    ]);

    const result = await svc.tagHierarchy({ minCoOccurrence: 2 });
    assert.ok(result.stats.depth >= 1, 'should have at least depth 1');
    cleanup(dir);
  });
});
