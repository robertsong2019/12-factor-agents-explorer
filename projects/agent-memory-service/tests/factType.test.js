import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'ams-ft-'));
  const svc = new MemoryService({ dbPath: dir });
  return {
    svc,
    cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} },
  };
}

describe('factType — Hindsight-inspired classification', () => {
  it('classifyFact returns correct type for opinion content', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'I think React is the best framework' });
      assert.equal(m.factType, 'opinion');
    } finally { cleanup(); }
  });

  it('classifyFact returns experience for personal events', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'I went to the store yesterday' });
      assert.equal(m.factType, 'experience');
    } finally { cleanup(); }
  });

  it('classifyFact returns world for factual statements', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'Python is a programming language' });
      assert.equal(m.factType, 'world');
    } finally { cleanup(); }
  });

  it('classifyFact returns observation as default', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'The server is running on port 3000' });
      assert.equal(m.factType, 'observation');
    } finally { cleanup(); }
  });

  it('allows manual override of factType', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'Some random content', factType: 'world' });
      assert.equal(m.factType, 'world');
    } finally { cleanup(); }
  });

  it('searchByFactType filters correctly', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await svc.add({ content: 'I love TypeScript', factType: 'opinion' });
      await svc.add({ content: 'Node.js is a runtime', factType: 'world' });
      await svc.add({ content: 'I built a CLI tool', factType: 'experience' });
      await svc.add({ content: 'CPU usage at 45%', factType: 'observation' });
      await svc.add({ content: 'I prefer dark mode', factType: 'opinion' });

      const opinions = await svc.searchByFactType('opinion');
      assert.equal(opinions.total, 2);
      assert.ok(opinions.results.every(m => m.factType === 'opinion'));

      const worlds = await svc.searchByFactType('world');
      assert.equal(worlds.total, 1);

      const experiences = await svc.searchByFactType('experience');
      assert.equal(experiences.total, 1);
    } finally { cleanup(); }
  });

  it('searchByFactType throws on invalid type', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await assert.rejects(() => svc.searchByFactType('invalid'), /Invalid factType/);
    } finally { cleanup(); }
  });

  it('searchByFactType supports pagination and sorting', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      for (let i = 0; i < 5; i++) {
        await svc.add({ content: `Opinion ${i}`, factType: 'opinion' });
      }
      const page1 = await svc.searchByFactType('opinion', { limit: 2, offset: 0 });
      assert.equal(page1.results.length, 2);
      assert.equal(page1.total, 5);

      const page2 = await svc.searchByFactType('opinion', { limit: 2, offset: 2 });
      assert.equal(page2.results.length, 2);

      // No overlap
      const ids1 = new Set(page1.results.map(m => m.id));
      assert.ok(!page2.results.some(m => ids1.has(m.id)));
    } finally { cleanup(); }
  });

  it('existing memories without factType are handled gracefully', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      // searchByFactType on empty or memories without factType should return 0
      const result = await svc.searchByFactType('world');
      assert.equal(result.total, 0);
      assert.equal(result.results.length, 0);
    } finally { cleanup(); }
  });

  it('statsByFactType returns grouped statistics', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await svc.add({ content: 'I love cats', factType: 'opinion' });
      await svc.add({ content: 'I hate dogs', factType: 'opinion' });
      await svc.add({ content: 'Paris is the capital of France', factType: 'world' });
      await svc.add({ content: 'I built a house', factType: 'experience' });

      const stats = await svc.statsByFactType();
      assert.equal(stats.total, 4);
      assert.equal(stats.byFactType.opinion.count, 2);
      assert.equal(stats.byFactType.world.count, 1);
      assert.equal(stats.byFactType.experience.count, 1);
      assert.ok(stats.byFactType.opinion.avgWeight > 0);
      assert.ok(stats.byFactType.opinion.byLayer.short > 0);
      assert.equal(stats.untyped, 0);
    } finally { cleanup(); }
  });

  it('statsByFactType counts untyped memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      // All memories get auto-classified now, so untyped should be 0
      await svc.add({ content: 'Hello world' });
      const stats = await svc.statsByFactType();
      assert.equal(stats.total, 1);
      assert.equal(stats.untyped, 0);
      // The memory should be classified as something
      const types = Object.keys(stats.byFactType);
      assert.equal(types.length, 1);
    } finally { cleanup(); }
  });

  it('reclassifyFact auto-reclassifies based on content', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'I think this is great', factType: 'world' });
      assert.equal(m.factType, 'world');

      const result = await svc.reclassifyFact(m.id);
      assert.equal(result.oldType, 'world');
      assert.equal(result.newType, 'opinion'); // 'I think' → opinion
    } finally { cleanup(); }
  });

  it('reclassifyFact accepts explicit override', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'Hello world' });
      const result = await svc.reclassifyFact(m.id, 'world');
      assert.equal(result.newType, 'world');
    } finally { cleanup(); }
  });

  it('reclassifyFact throws on missing id', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await assert.rejects(() => svc.reclassifyFact('nonexistent'), /Memory not found/);
    } finally { cleanup(); }
  });

  it('bulkReclassify changes factType for matching memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await svc.add({ content: 'Test A', factType: 'observation' });
      await svc.add({ content: 'Test B', factType: 'observation' });
      await svc.add({ content: 'Test C', factType: 'world' });

      const result = await svc.bulkReclassify({ factType: 'observation', newType: 'experience' });
      assert.equal(result.reclassified, 2);
      assert.ok(result.results.every(r => r.newType === 'experience'));

      // Verify persistence
      const obs = await svc.searchByFactType('observation');
      assert.equal(obs.total, 0);
      const exp = await svc.searchByFactType('experience');
      assert.equal(exp.total, 2);
    } finally { cleanup(); }
  });

  it('bulkReclassify skips already-correct types', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await svc.add({ content: 'A', factType: 'world' });
      await svc.add({ content: 'B', factType: 'world' });
      const result = await svc.bulkReclassify({ factType: 'world', newType: 'world' });
      assert.equal(result.reclassified, 0);
    } finally { cleanup(); }
  });

  it('bulkReclassify filters by layer', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await svc.add({ content: 'A', layer: 'short', factType: 'observation' });
      await svc.add({ content: 'B', layer: 'long', factType: 'observation' });
      const result = await svc.bulkReclassify({ layer: 'short', newType: 'experience' });
      assert.equal(result.reclassified, 1);
    } finally { cleanup(); }
  });

  it('bulkReclassify requires newType', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      await assert.rejects(() => svc.bulkReclassify({}), /newType is required/);
    } finally { cleanup(); }
  });
});
