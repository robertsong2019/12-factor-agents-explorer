import test from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-test-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, dir };
}
function cleanup(dir) { try { rmSync(dir, { recursive: true }); } catch {} }

async function seed(svc, items) {
  const ids = [];
  for (const item of items) {
    const id = await svc.add(item);
    ids.push(id);
  }
  return ids;
}

test('query returns paginated results', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long' },
    { content: 'b', layer: 'long' },
    { content: 'c', layer: 'long' },
  ]);
  const res = await svc.query({ limit: 2 });
  assert.equal(res.results.length, 2);
  assert.equal(res.total, 3);
  assert.equal(res.limit, 2);
  cleanup(dir);
});

test('query filters by layer', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'core' },
    { content: 'b', layer: 'long' },
  ]);
  const res = await svc.query({ layer: 'core' });
  assert.equal(res.total, 1);
  assert.equal(res.results[0].content, 'a');
  cleanup(dir);
});

test('query filters by tags with AND', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long', tags: ['x'] },
    { content: 'b', layer: 'long', tags: ['x', 'y'] },
    { content: 'c', layer: 'long', tags: ['y'] },
  ]);
  const res = await svc.query({ tags: ['x', 'y'], tagsOp: 'and' });
  assert.equal(res.total, 1);
  assert.equal(res.results[0].content, 'b');
  cleanup(dir);
});

test('query sorts ascending', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [{ content: 'first', layer: 'long', weight: 0.1 }]);
  await seed(svc, [{ content: 'second', layer: 'long', weight: 0.9 }]);
  const res = await svc.query({ sortBy: 'weight', sortOrder: 'asc' });
  assert.equal(res.results[0].content, 'first');
  cleanup(dir);
});

test('query filters by weight range', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long', weight: 0.2 },
    { content: 'b', layer: 'long', weight: 0.5 },
    { content: 'c', layer: 'long', weight: 0.8 },
  ]);
  const res = await svc.query({ minWeight: 0.4, maxWeight: 0.6 });
  assert.equal(res.total, 1);
  assert.equal(res.results[0].content, 'b');
  cleanup(dir);
});

test('query filters by entity', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long', entities: ['alice'] },
    { content: 'b', layer: 'long', entities: ['bob'] },
  ]);
  const res = await svc.query({ entities: ['bob'] });
  assert.equal(res.total, 1);
  assert.equal(res.results[0].content, 'b');
  cleanup(dir);
});

test('query offset pagination works', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long' },
    { content: 'b', layer: 'long' },
    { content: 'c', layer: 'long' },
  ]);
  const p1 = await svc.query({ limit: 1, offset: 0 });
  const p2 = await svc.query({ limit: 1, offset: 1 });
  assert.notEqual(p1.results[0].id, p2.results[0].id);
  cleanup(dir);
});
