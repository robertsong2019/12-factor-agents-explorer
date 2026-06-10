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

test('count returns total with no filter', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'core', tags: ['x'] },
    { content: 'b', layer: 'long', tags: ['y'] },
    { content: 'c', layer: 'short', tags: ['x', 'y'] },
  ]);
  const n = await svc.count();
  assert.equal(n, 3);
  cleanup(dir);
});

test('count filters by layer', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'core' },
    { content: 'b', layer: 'long' },
    { content: 'c', layer: 'core' },
  ]);
  assert.equal(await svc.count({ layer: 'core' }), 2);
  assert.equal(await svc.count({ layer: 'long' }), 1);
  assert.equal(await svc.count({ layer: 'short' }), 0);
  cleanup(dir);
});

test('count filters by tag', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long', tags: ['alpha'] },
    { content: 'b', layer: 'long', tags: ['beta'] },
    { content: 'c', layer: 'long', tags: ['alpha', 'beta'] },
  ]);
  assert.equal(await svc.count({ tag: 'alpha' }), 2);
  assert.equal(await svc.count({ tag: 'beta' }), 2);
  cleanup(dir);
});

test('count filters by minWeight', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long', weight: 0.3 },
    { content: 'b', layer: 'long', weight: 0.8 },
    { content: 'c', layer: 'long', weight: 0.5 },
  ]);
  assert.equal(await svc.count({ minWeight: 0.5 }), 2);
  assert.equal(await svc.count({ minWeight: 0.9 }), 0);
  cleanup(dir);
});

test('count returns 0 on empty store', async () => {
  const { svc, dir } = createService();
  await svc.init();
  assert.equal(await svc.count(), 0);
  cleanup(dir);
});
