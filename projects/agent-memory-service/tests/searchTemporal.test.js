import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'ams-st-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

describe('searchTemporal', () => {
  it('ranks newer memories higher', async () => {
    const { svc, cleanup } = createService();
    const now = Date.now();
    // Both added at same time, same weight. Use referenceTime to test decay.
    await svc.add({ content: 'A', weight: 1.0 });
    await svc.add({ content: 'B', weight: 1.0 });
    const result = await svc.searchTemporal({ referenceTime: now + 86400000 }); // 1 day later
    try {
      assert.ok(result.results.length >= 2);
      assert.ok(result.results[0].decayScore >= result.results[1].decayScore);
    } finally { cleanup(); }
  });

  it('higher weight can compensate for age', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Heavy', weight: 5.0 });
    await svc.add({ content: 'Light', weight: 0.5 });
    const result = await svc.searchTemporal();
    try {
      assert.equal(result.results[0].content, 'Heavy');
    } finally { cleanup(); }
  });

  it('respects halfLife — shorter halfLife gives lower decayScore', async () => {
    const { svc, cleanup } = createService();
    const now = Date.now();
    await svc.add({ content: 'A', weight: 1.0 });
    // With very short halfLife, memory 1 day old decays more
    const short = await svc.searchTemporal({ halfLife: 1000, referenceTime: now + 86400000 });
    const long = await svc.searchTemporal({ halfLife: 864000000, referenceTime: now + 86400000 });
    try {
      assert.ok(short.results[0].decayScore < long.results[0].decayScore,
        `short=${short.results[0].decayScore} should be < long=${long.results[0].decayScore}`);
    } finally { cleanup(); }
  });

  it('filters by layer', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Core', layer: 'core', weight: 1.0 });
    await svc.add({ content: 'Short', layer: 'short', weight: 1.0 });
    const result = await svc.searchTemporal({ layer: 'core' });
    try {
      assert.ok(result.results.every(r => r.layer === 'core'));
    } finally { cleanup(); }
  });

  it('filters by tags', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Tagged', tags: ['important'], weight: 1.0 });
    await svc.add({ content: 'Untagged', tags: [], weight: 1.0 });
    const result = await svc.searchTemporal({ tags: ['important'] });
    try {
      assert.ok(result.results.some(r => r.content === 'Tagged'));
      assert.ok(!result.results.some(r => r.content === 'Untagged'));
    } finally { cleanup(); }
  });

  it('filters by minScore', async () => {
    const { svc, cleanup } = createService();
    const now = Date.now();
    await svc.add({ content: 'Heavy', weight: 5.0 });
    await svc.add({ content: 'Light', weight: 0.1 });
    // 100 days later with 1-day halfLife, light one decays heavily
    const result = await svc.searchTemporal({ referenceTime: now + 8640000000, halfLife: 86400000, minScore: 0.01 });
    try {
      assert.ok(result.results.every(r => r.decayScore >= 0.01));
    } finally { cleanup(); }
  });

  it('respects limit and offset', async () => {
    const { svc, cleanup } = createService();
    for (let i = 0; i < 5; i++) {
      await svc.add({ content: `M${i}`, weight: 1.0 });
    }
    const p1 = await svc.searchTemporal({ limit: 2, offset: 0 });
    const p2 = await svc.searchTemporal({ limit: 2, offset: 2 });
    try {
      assert.equal(p1.results.length, 2);
      assert.equal(p2.results.length, 2);
      assert.equal(p1.total, p2.total);
      const ids1 = new Set(p1.results.map(r => r.id));
      assert.ok(!p2.results.some(r => ids1.has(r.id)));
    } finally { cleanup(); }
  });

  it('returns age and decayScore for each result', async () => {
    const { svc, cleanup } = createService();
    await svc.add({ content: 'Test', weight: 1.0 });
    const result = await svc.searchTemporal();
    try {
      assert.ok(result.results[0].age >= 0);
      assert.ok(result.results[0].decayScore > 0);
    } finally { cleanup(); }
  });

  it('returns correct metadata', async () => {
    const { svc, cleanup } = createService();
    const now = Date.now();
    await svc.add({ content: 'A', weight: 1.0 });
    const result = await svc.searchTemporal({ referenceTime: now, halfLife: 3600000 });
    try {
      assert.equal(result.halfLife, 3600000);
      assert.equal(result.referenceTime, now);
    } finally { cleanup(); }
  });

  it('returns empty for no memories', async () => {
    const { svc, cleanup } = createService();
    const result = await svc.searchTemporal();
    try {
      assert.equal(result.results.length, 0);
      assert.equal(result.total, 0);
    } finally { cleanup(); }
  });
});
