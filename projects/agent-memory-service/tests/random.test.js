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

test('random returns 1 item by default', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long' },
    { content: 'b', layer: 'long' },
    { content: 'c', layer: 'long' },
  ]);
  const results = await svc.random();
  assert.equal(results.length, 1);
  assert.ok(['a','b','c'].includes(results[0].content));
  cleanup(dir);
});

test('random returns up to count items', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long' },
    { content: 'b', layer: 'long' },
    { content: 'c', layer: 'long' },
  ]);
  const results = await svc.random({ count: 2 });
  assert.equal(results.length, 2);
  cleanup(dir);
});

test('random respects layer filter', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'core' },
    { content: 'b', layer: 'short' },
  ]);
  const results = await svc.random({ layer: 'core' });
  assert.equal(results.length, 1);
  assert.equal(results[0].content, 'a');
  cleanup(dir);
});

test('random respects tag filter', async () => {
  const { svc, dir } = createService();
  await svc.init();
  await seed(svc, [
    { content: 'a', layer: 'long', tags: ['x'] },
    { content: 'b', layer: 'long', tags: ['y'] },
  ]);
  const results = await svc.random({ tag: 'y' });
  assert.equal(results.length, 1);
  assert.equal(results[0].content, 'b');
  cleanup(dir);
});

test('random returns empty when no matches', async () => {
  const { svc, dir } = createService();
  await svc.init();
  const results = await svc.random();
  assert.equal(results.length, 0);
  cleanup(dir);
});
