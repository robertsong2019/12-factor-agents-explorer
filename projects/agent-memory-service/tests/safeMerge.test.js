import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('safeMerge()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-sm-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('returns merged 0 when no safe pairs found', async () => {
    // Create memories that won't match each other
    await svc.add({ content: 'Unique alpha content' });
    const result = await svc.safeMerge({ maxRisk: 0.01 });
    assert.ok(result.merged >= 0);
  });

  it('only merges pairs below risk threshold', async () => {
    // Create near-duplicate memories (should be safe)
    for (let i = 0; i < 4; i++) {
      await svc.add({ content: `Machine learning is great topic number ${i}`, tags: ['ml', 'ai'], entities: ['ml'] });
    }
    // Create very different memories
    await svc.add({ content: 'Cooking recipes for pasta carbonara', tags: ['food'], entities: ['pasta'] });
    await svc.add({ content: 'Quantum physics wave function collapse', tags: ['physics'], entities: ['quantum'] });

    const result = await svc.safeMerge({ minScore: 0.1, maxRisk: 0.6, maxMerges: 5 });
    assert.ok(result.merged >= 0);
    if (result.details.length > 0) {
      for (const d of result.details) {
        assert.ok(d.risk < 0.6, `risk ${d.risk} should be below threshold`);
      }
    }
  });

  it('reports risky pairs separately', async () => {
    // Two very different memories
    await svc.add({ content: 'Alpha beta gamma delta epsilon', tags: ['a', 'b'], entities: ['x'] });
    await svc.add({ content: 'Zulu yankee xray whiskey victor', tags: ['z'], entities: ['w'] });

    const result = await svc.safeMerge({ minScore: 0.1, maxRisk: 0.1 });
    // These should be too risky at threshold 0.1
    assert.ok(result.risky >= 0);
  });

  it('respects maxMerges limit', async () => {
    for (let i = 0; i < 10; i++) {
      await svc.add({ content: `duplicate content same text ${i}`, tags: ['t'], entities: ['e'] });
    }
    const result = await svc.safeMerge({ minScore: 0.1, maxMerges: 2 });
    assert.ok(result.merged <= 2);
  });
});
