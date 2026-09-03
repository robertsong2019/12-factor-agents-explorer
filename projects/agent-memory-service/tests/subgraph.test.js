import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('subgraph()', () => {
  let svc, dir;

  beforeEach(async () => {
    dir = mkdtempSync(join(tmpdir(), 'sg-'));
    svc = new MemoryService({ dbPath: dir });
    await svc.init();
  });

  it('returns root null for non-existent start', async () => {
    const result = await svc.subgraph('nonexistent');
    assert.equal(result.root, null);
    assert.deepEqual(result.nodes, []);
    assert.deepEqual(result.edges, []);
  });

  it('returns single node with no links', async () => {
    const m = await svc.add({ content: 'isolated', layer: 'short' });
    const result = await svc.subgraph(m.id);
    assert.equal(result.nodes.length, 1);
    assert.equal(result.edges.length, 0);
    assert.equal(result.root.id, m.id);
    assert.equal(result.depth, 2);
  });

  it('traverses linked neighbors within depth', async () => {
    const a = await svc.add({ content: 'node A', layer: 'long' });
    const b = await svc.add({ content: 'node B', layer: 'long' });
    const c = await svc.add({ content: 'node C', layer: 'long' });
    const l1 = await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
    const l2 = await svc.link({ source: b.id, target: c.id, type: 'relates_to' });

    // Depth 1: only a + b
    const r1 = await svc.subgraph(a.id, { depth: 1 });
    assert.equal(r1.nodes.length, 2);
    assert.equal(r1.edges.length, 1);

    // Depth 2: a + b + c
    const r2 = await svc.subgraph(a.id, { depth: 2 });
    assert.equal(r2.nodes.length, 3);
    assert.equal(r2.edges.length, 2);
  });

  it('respects limit option', async () => {
    const nodes = [];
    for (let i = 0; i < 10; i++) {
      nodes.push(await svc.add({ content: `node ${i}`, layer: 'short' }));
    }
    for (let i = 0; i < 9; i++) {
      await svc.link({ source: nodes[i].id, target: nodes[i + 1].id, type: 'relates_to' });
    }

    const result = await svc.subgraph(nodes[0].id, { limit: 4 });
    assert.ok(result.nodes.length <= 4 && result.nodes.length >= 2, `expected 2-4 nodes, got ${result.nodes.length}`);
    assert.equal(result.nodes[0].id, nodes[0].id);
  });

  it('filters by layer', async () => {
    const a = await svc.add({ content: 'long node', layer: 'long' });
    const b = await svc.add({ content: 'short node', layer: 'short' });
    await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

    const result = await svc.subgraph(a.id, { layer: 'long' });
    assert.equal(result.nodes.length, 1);
    assert.equal(result.nodes[0].layer, 'long');
  });

  it('handles fan-out graph', async () => {
    const center = await svc.add({ content: 'hub', layer: 'core' });
    const leaves = [];
    for (let i = 0; i < 5; i++) {
      leaves.push(await svc.add({ content: `leaf ${i}`, layer: 'long' }));
      await svc.link({ source: center.id, target: leaves[i].id, type: 'relates_to' });
    }

    const result = await svc.subgraph(center.id, { depth: 1 });
    assert.equal(result.nodes.length, 6); // center + 5 leaves
    assert.equal(result.edges.length, 5);
  });
});

describe('shortestPath()', () => {
  let svc, dir;

  beforeEach(async () => {
    dir = mkdtempSync(join(tmpdir(), 'sp-'));
    svc = new MemoryService({ dbPath: dir });
    await svc.init();
  });

  it('returns found false for non-existent nodes', async () => {
    const result = await svc.shortestPath('a', 'b');
    assert.equal(result.found, false);
    assert.equal(result.distance, -1);
  });

  it('returns distance 0 for same node', async () => {
    const m = await svc.add({ content: 'self', layer: 'short' });
    const result = await svc.shortestPath(m.id, m.id);
    assert.equal(result.found, true);
    assert.equal(result.distance, 0);
    assert.equal(result.path.length, 1);
  });

  it('returns found false for disconnected nodes', async () => {
    const a = await svc.add({ content: 'island A', layer: 'short' });
    const b = await svc.add({ content: 'island B', layer: 'short' });
    const result = await svc.shortestPath(a.id, b.id);
    assert.equal(result.found, false);
    assert.equal(result.distance, -1);
  });

  it('finds direct path between linked nodes', async () => {
    const a = await svc.add({ content: 'A', layer: 'long' });
    const b = await svc.add({ content: 'B', layer: 'long' });
    await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

    const result = await svc.shortestPath(a.id, b.id);
    assert.equal(result.found, true);
    assert.equal(result.distance, 1);
    assert.equal(result.path.length, 2);
    assert.equal(result.path[0].memory.id, a.id);
    assert.equal(result.path[1].memory.id, b.id);
    assert.ok(result.path[1].link);
  });

  it('finds multi-hop shortest path', async () => {
    const a = await svc.add({ content: 'A', layer: 'long' });
    const b = await svc.add({ content: 'B', layer: 'long' });
    const c = await svc.add({ content: 'C', layer: 'long' });
    await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
    await svc.link({ source: b.id, target: c.id, type: 'derived_from' });

    const result = await svc.shortestPath(a.id, c.id);
    assert.equal(result.found, true);
    assert.equal(result.distance, 2);
    assert.equal(result.path.length, 3);
  });

  it('picks shorter path when longer exists', async () => {
    const a = await svc.add({ content: 'A', layer: 'long' });
    const b = await svc.add({ content: 'B', layer: 'long' });
    const c = await svc.add({ content: 'C', layer: 'long' });
    const d = await svc.add({ content: 'D', layer: 'long' });
    // Short path: a -> d
    await svc.link({ source: a.id, target: d.id, type: 'relates_to' });
    // Long path: a -> b -> c -> d
    await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
    await svc.link({ source: b.id, target: c.id, type: 'relates_to' });
    await svc.link({ source: c.id, target: d.id, type: 'relates_to' });

    const result = await svc.shortestPath(a.id, d.id);
    assert.equal(result.found, true);
    assert.equal(result.distance, 1);
  });

  it('works bidirectionally', async () => {
    const a = await svc.add({ content: 'A', layer: 'long' });
    const b = await svc.add({ content: 'B', layer: 'long' });
    await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

    // Forward
    const fwd = await svc.shortestPath(a.id, b.id);
    assert.equal(fwd.found, true);
    assert.equal(fwd.distance, 1);

    // Reverse
    const rev = await svc.shortestPath(b.id, a.id);
    assert.equal(rev.found, true);
    assert.equal(rev.distance, 1);
  });
});
