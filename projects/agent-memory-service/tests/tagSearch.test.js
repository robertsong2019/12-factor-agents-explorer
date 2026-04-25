/**
 * Agent Memory Service — tagSearch() Tests
 */
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-ts-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

describe('tagSearch()', () => {
  let svc, cleanup;

  before(async () => {
    ({ svc, cleanup } = createService());
    await svc.add({ content: 'Python tips', layer: 'L0', tags: ['programming', 'python', 'tips'] });
    await svc.add({ content: 'Python ML', layer: 'L0', tags: ['programming', 'python', 'machine-learning'] });
    await svc.add({ content: 'Rust guide', layer: 'L1', tags: ['programming', 'rust', 'guide'] });
    await svc.add({ content: 'Cooking', layer: 'L0', tags: ['cooking', 'recipes'] });
  });

  it('finds exact match with score 1.0', async () => {
    const results = await svc.tagSearch('python');
    const py = results.find(r => r.tag === 'python');
    assert.ok(py);
    assert.equal(py.score, 1.0);
  });

  it('finds prefix matches with score 0.9', async () => {
    const results = await svc.tagSearch('prog');
    const prog = results.find(r => r.tag === 'programming');
    assert.ok(prog);
    assert.equal(prog.score, 0.9);
  });

  it('finds substring matches', async () => {
    const results = await svc.tagSearch('chine');
    const ml = results.find(r => r.tag === 'machine-learning');
    assert.ok(ml);
    assert.ok(ml.score >= 0.7);
  });

  it('returns empty for no query', async () => {
    const results = await svc.tagSearch('');
    assert.deepEqual(results, []);
  });

  it('respects limit option', async () => {
    const results = await svc.tagSearch('p', { limit: 2 });
    assert.ok(results.length <= 2);
  });

  it('respects minScore filter', async () => {
    const results = await svc.tagSearch('z', { minScore: 0.8 });
    // 'z' is weak match, unlikely to score >= 0.8
    assert.ok(results.length === 0 || results.every(r => r.score >= 0.8));
  });
});
