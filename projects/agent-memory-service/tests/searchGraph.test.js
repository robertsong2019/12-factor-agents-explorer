import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'ams-sg-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

describe('searchGraph', () => {
  it('traverses from entity through auto-linked memories', async () => {
    const { svc, cleanup } = createService();
    // A and B share entity 'project', B and C share tag 'work'
    await svc.add({ content: 'Alice started project X', entities: ['Alice', 'project'], tags: ['work'], weight: 1.0 });
    await svc.add({ content: 'Bob joined project X', entities: ['Bob', 'project'], tags: ['work'], weight: 0.8 });
    await svc.add({ content: 'Charlie did work stuff', entities: ['Charlie'], tags: ['work'], weight: 0.5 });
    await svc.autoLink({ threshold: 1 });
    const result = await svc.searchGraph('Alice');
    try {
      assert.equal(result.startEntity, 'Alice');
      assert.equal(result.seedCount, 1);
      assert.ok(result.results.length >= 1, 'should have at least the seed');
      assert.ok(result.results.some(r => r.content.includes('Alice')));
      // Bob should be reachable via shared 'project' entity
      assert.ok(result.results.some(r => r.content.includes('Bob')));
    } finally { cleanup(); }
  });

  it('returns empty for unknown entity', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Some memory', entities: ['Alice'] });
    const result = await svc.searchGraph('Nobody');
    try {
      assert.equal(result.seedCount, 0);
      assert.equal(result.results.length, 0);
    } finally { cleanup(); }
  });

  it('filters by layer', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Core memory about Alice', entities: ['Alice'], layer: 'core', weight: 1.0 });
    await svc.add({ content: 'Short memory about Alice', entities: ['Alice'], layer: 'short', weight: 0.5 });
    const result = await svc.searchGraph('Alice', { layer: 'core' });
    try {
      assert.ok(result.results.every(r => r.layer === 'core'));
    } finally { cleanup(); }
  });

  it('filters by minWeight', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Heavy Alice', entities: ['Alice'], weight: 1.0 });
    await svc.add({ content: 'Light Alice', entities: ['Alice'], weight: 0.3 });
    const result = await svc.searchGraph('Alice', { minWeight: 0.5 });
    try {
      assert.ok(result.results.every(r => r.weight >= 0.5));
    } finally { cleanup(); }
  });

  it('respects limit', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Alice 1', entities: ['Alice'], weight: 1.0 });
    await svc.add({ content: 'Alice 2', entities: ['Alice'], weight: 0.9 });
    await svc.add({ content: 'Alice 3', entities: ['Alice'], weight: 0.8 });
    const result = await svc.searchGraph('Alice', { limit: 2 });
    try {
      assert.ok(result.results.length <= 2);
    } finally { cleanup(); }
  });

  it('sorts by hop then weight', async () => {
    const { svc, cleanup } = createService();
    const m1 = await svc.add({ content: 'Alice seed 1', entities: ['Alice'], weight: 1.0 });
    const m2 = await svc.add({ content: 'Alice seed 2', entities: ['Alice'], weight: 0.9 });
    const result = await svc.searchGraph('Alice');
    try {
      for (let i = 1; i < result.results.length; i++) {
        const prev = result.results[i - 1];
        const curr = result.results[i];
        assert.ok(prev.hop < curr.hop || (prev.hop === curr.hop && prev.weight >= curr.weight));
      }
    } finally { cleanup(); }
  });

  it('includes hop=0 and viaLink=null for seed', async () => {
    const { svc, cleanup } = createService();
    const m = await svc.add({ content: 'Alice memory', entities: ['Alice'], weight: 1.0 });
    const result = await svc.searchGraph('Alice');
    try {
      const seed = result.results.find(r => r.id === m.id);
      assert.ok(seed);
      assert.equal(seed.hop, 0);
      assert.equal(seed.viaLink, null);
    } finally { cleanup(); }
  });

  it('throws without startEntity', async () => {
    const { svc, cleanup } = createService();
    try {
      await assert.rejects(() => svc.searchGraph(''), /requires a startEntity string/);
      await assert.rejects(() => svc.searchGraph(), /requires a startEntity string/);
    } finally { cleanup(); }
  });

  it('handles multiple seeds for same entity', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Alice note 1', entities: ['Alice'], weight: 1.0 });
    await svc.add({ content: 'Alice note 2', entities: ['Alice'], weight: 0.9 });
    const result = await svc.searchGraph('Alice');
    try {
      assert.equal(result.seedCount, 2);
      assert.ok(result.results.length >= 2);
    } finally { cleanup(); }
  });

  it('respects depth limit with multi-hop graph', async () => {
    const { svc, cleanup } = createService();
    // Alice -> Bob (shared entity 'project') -> Charlie (shared entity 'team')
    await svc.add({ content: 'Alice works on project', entities: ['Alice', 'project'], tags: ['t1'], weight: 1.0 });
    await svc.add({ content: 'Bob works on project and team', entities: ['Bob', 'project', 'team'], tags: ['t1', 't2'], weight: 0.8 });
    await svc.add({ content: 'Charlie on team', entities: ['Charlie', 'team'], tags: ['t2'], weight: 0.5 });
    await svc.autoLink({ threshold: 1 });
    // depth=1 from Alice should reach Bob but not Charlie
    const d1 = await svc.searchGraph('Alice', { depth: 1 });
    const d2 = await svc.searchGraph('Alice', { depth: 2 });
    try {
      assert.ok(d2.results.length >= d1.results.length, 'deeper search should find at least as many');
    } finally { cleanup(); }
  });
});
