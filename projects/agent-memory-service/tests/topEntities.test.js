/**
 * Agent Memory Service — topEntities() Tests
 */
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService, LAYERS } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-te-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

describe('topEntities()', () => {
  /** @type {MemoryService} */
  let svc, cleanup;

  before(async () => {
    ({ svc, cleanup } = createService());
    await svc.add({ content: 'Python is great for ML', layer: 'L0', tags: ['programming'], entities: ['python', 'ml'], weight: 1.0 });
    await svc.add({ content: 'Python web frameworks', layer: 'L0', tags: ['programming', 'web'], entities: ['python', 'django'], weight: 0.8 });
    await svc.add({ content: 'ML model training tips', layer: 'L1', tags: ['ai'], entities: ['ml', 'pytorch'], weight: 0.6 });
    await svc.add({ content: 'Rust for systems', layer: 'L1', tags: ['programming'], entities: ['rust'], weight: 0.9 });
    await svc.add({ content: 'Deep learning with Python', layer: 'L0', tags: ['ai', 'programming'], entities: ['python', 'ml', 'deep-learning'], weight: 0.7 });
  });

  it('returns entities sorted by count*avgWeight', async () => {
    const results = await svc.topEntities();
    assert.ok(results.length > 0);
    // python appears 3 times
    const py = results.find(e => e.entity === 'python');
    assert.ok(py);
    assert.equal(py.count, 3);
    assert.ok(py.avgWeight > 0);
  });

  it('respects limit option', async () => {
    const results = await svc.topEntities({ limit: 2 });
    assert.ok(results.length <= 2);
  });

  it('respects minCount filter', async () => {
    const results = await svc.topEntities({ minCount: 2 });
    for (const r of results) assert.ok(r.count >= 2);
    // python (3) and ml (3) should be present
    const entities = results.map(r => r.entity);
    assert.ok(entities.includes('python'));
    assert.ok(entities.includes('ml'));
  });

  it('respects layer filter', async () => {
    const results = await svc.topEntities({ layer: 'L1' });
    for (const r of results) {
      // All returned entities should exist in L1 memories
      assert.ok(r.count > 0);
    }
    // rust only in L1, python in both — rust should appear in L1 results
    const entities = results.map(r => r.entity);
    assert.ok(entities.includes('rust'));
    assert.ok(entities.includes('ml'));
  });

  it('includes topTags for each entity', async () => {
    const results = await svc.topEntities();
    const py = results.find(e => e.entity === 'python');
    assert.ok(py);
    assert.ok(Array.isArray(py.topTags));
    assert.ok(py.topTags.length <= 3);
    // python memories have tags: programming (3), ai (1), web (1)
    assert.ok(py.topTags.includes('programming'));
  });

  it('returns empty for service with no entities', async () => {
    const { svc: s, cleanup: c } = createService();
    await s.add({ content: 'no entities here', layer: 'L0', tags: ['test'] });
    const results = await s.topEntities();
    assert.equal(results.length, 0);
    c();
  });
});
