import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'sbe-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

describe('searchByEntity', () => {
  it('finds memories by exact entity', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Met Alice at conference', entities: ['Alice', 'conference'] });
    await svc.add({ content: 'Had lunch with Bob', entities: ['Bob'] });
    await svc.add({ content: 'No entities here' });
    try {
      const result = await svc.searchByEntity('Alice');
      assert.strictEqual(result.total, 1);
      assert.strictEqual(result.results[0].content, 'Met Alice at conference');
      assert.ok(result.results[0].entities.includes('Alice'));
    } finally { cleanup(); }
  });

  it('finds with fuzzy matching', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Project alpha', entities: ['ProjectAlpha'] });
    await svc.add({ content: 'Project beta', entities: ['ProjectBeta'] });
    try {
      const result = await svc.searchByEntity('project', { fuzzy: true });
      assert.strictEqual(result.total, 2);
    } finally { cleanup(); }
  });

  it('filters by layer', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Alice core', entities: ['Alice'], layer: 'core' });
    await svc.add({ content: 'Alice long', entities: ['Alice'], layer: 'long' });
    try {
      const result = await svc.searchByEntity('Alice', { layer: 'core' });
      assert.strictEqual(result.total, 1);
      assert.strictEqual(result.results[0].content, 'Alice core');
    } finally { cleanup(); }
  });

  it('paginates results', async () => {
    const { svc, cleanup } = createService();
    for (let i = 0; i < 5; i++) {
      await svc.add({ content: `item ${i}`, entities: ['shared'], weight: 1 - i * 0.1 });
    }
    try {
      const p1 = await svc.searchByEntity('shared', { limit: 2, offset: 0 });
      const p2 = await svc.searchByEntity('shared', { limit: 2, offset: 2 });
      assert.strictEqual(p1.results.length, 2);
      assert.strictEqual(p2.results.length, 2);
      assert.strictEqual(p1.results[0].id !== p2.results[0].id, true);
    } finally { cleanup(); }
  });

  it('throws for missing entity', async () => {
    const { svc, cleanup } = createService();
    try {
      await assert.rejects(() => svc.searchByEntity(''), /requires an entity string/);
      await assert.rejects(() => svc.searchByEntity(), /requires an entity string/);
    } finally { cleanup(); }
  });

  it('returns empty for non-existent entity', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'hello', entities: ['Bob'] });
    try {
      const result = await svc.searchByEntity('Nobody');
      assert.strictEqual(result.total, 0);
      assert.strictEqual(result.results.length, 0);
    } finally { cleanup(); }
  });
});
