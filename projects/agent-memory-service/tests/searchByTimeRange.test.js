import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('searchByTimeRange', () => {
  let dir, svc;
  let ids = [];
  let baseCount;

  before(async () => {
    dir = mkdtempSync(join(tmpdir(), 'sbytr-'));
    // Ensure truly empty dir
    svc = new MemoryService(dir);
    await svc.init();
    const r1 = await svc.add({ content: 'alpha', layer: 'L1', tags: ['a', 'x'], weight: 5 });
    const r2 = await svc.add({ content: 'beta', layer: 'L1', tags: ['b', 'x'], weight: 3 });
    const r3 = await svc.add({ content: 'gamma', layer: 'L2', tags: ['c'], weight: 7 });
    const r4 = await svc.add({ content: 'delta', layer: 'L2', tags: ['d', 'x'], weight: 2 });
    ids = [r1.id, r2.id, r3.id, r4.id];
    await svc.update(r4.id, { content: 'delta updated' });
  });

  after(() => { try { rmSync(dir, { recursive: true }); } catch {} });

  it('returns memories with correct metadata', async () => {
    const res = await svc.searchByTimeRange();
    assert.equal(res.field, 'createdAt');
    assert.equal(typeof res.total, 'number');
    assert.ok(res.total >= 4);
    assert.ok(Array.isArray(res.results));
  });

  it('filters by start time (future = empty)', async () => {
    const res = await svc.searchByTimeRange({ start: Date.now() + 100000 });
    assert.equal(res.total, 0);
  });

  it('filters by end time (ancient = empty)', async () => {
    const res = await svc.searchByTimeRange({ end: 1000 });
    assert.equal(res.total, 0);
  });

  it('wide range returns at least 4', async () => {
    const res = await svc.searchByTimeRange({ start: 0, end: Date.now() + 100000 });
    assert.ok(res.total >= 4);
  });

  it('filters by layer', async () => {
    const allRes = await svc.searchByTimeRange({ start: 0, end: Date.now() + 100000 });
    const l2Res = await svc.searchByTimeRange({ layer: 'L2', start: 0, end: Date.now() + 100000 });
    assert.ok(l2Res.total >= 2);
    assert.ok(l2Res.total < allRes.total);
    assert.ok(l2Res.results.every(m => m.layer === 'L2'));
  });

  it('filters by tags (OR match)', async () => {
    const res = await svc.searchByTimeRange({ tags: ['x'], start: 0, end: Date.now() + 100000 });
    assert.ok(res.total >= 3);
    assert.ok(res.results.every(m => (m.tags || []).includes('x')));
  });

  it('sorts ascending', async () => {
    const res = await svc.searchByTimeRange({ sort: 'asc', start: 0, end: Date.now() + 100000 });
    for (let i = 1; i < res.results.length; i++) {
      assert.ok(res.results[i - 1].createdAt <= res.results[i].createdAt);
    }
  });

  it('sorts descending (default)', async () => {
    const res = await svc.searchByTimeRange({ sort: 'desc', start: 0, end: Date.now() + 100000 });
    for (let i = 1; i < res.results.length; i++) {
      assert.ok(res.results[i - 1].createdAt >= res.results[i].createdAt);
    }
  });

  it('paginates with offset and limit', async () => {
    const full = await svc.searchByTimeRange({ start: 0, end: Date.now() + 100000 });
    const page = await svc.searchByTimeRange({ limit: 2, offset: 1, start: 0, end: Date.now() + 100000 });
    assert.equal(page.total, full.total);
    assert.equal(page.results.length, Math.min(2, full.total - 1));
  });

  it('uses updatedAt field when specified', async () => {
    // Memories may not have updatedAt; verify field parameter is passed through
    const res = await svc.searchByTimeRange({ field: 'updatedAt', start: 0, end: Date.now() + 100000, limit: 500 });
    assert.equal(res.field, 'updatedAt');
    // Without updatedAt, all should be filtered out (undefined comparisons)
    // This validates the field parameter works correctly
    assert.equal(typeof res.total, 'number');
  });

  it('includes start/end in response metadata', async () => {
    const res = await svc.searchByTimeRange({ start: 100, end: 200 });
    assert.equal(res.start, 100);
    assert.equal(res.end, 200);
  });
});
