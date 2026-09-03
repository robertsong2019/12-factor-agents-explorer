import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('searchByBranch()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-sbb-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('returns empty for non-existent root', async () => {
    const result = await svc.searchByBranch('no-such-id');
    assert.deepEqual(result.branches, []);
  });

  it('returns empty when root has no branches', async () => {
    const src = await svc.add({ content: 'No branches' });
    const result = await svc.searchByBranch(src.id);
    assert.deepEqual(result.branches, []);
  });

  it('finds direct branches', async () => {
    const src = await svc.add({ content: 'Root' });
    const b1 = await svc.contentBranch(src.id, { content: 'Branch 1' });
    const b2 = await svc.contentBranch(src.id, { content: 'Branch 2' });
    const result = await svc.searchByBranch(src.id);
    assert.equal(result.branches.length, 2);
    const contents = result.branches.map(b => b.memory.content).sort();
    assert.deepEqual(contents, ['Branch 1', 'Branch 2']);
    assert.ok(result.branches.every(b => b.depth === 1));
  });

  it('finds nested branches (branch of branch)', async () => {
    const src = await svc.add({ content: 'Root' });
    const b1 = await svc.contentBranch(src.id, { content: 'L1' });
    const b2 = await svc.contentBranch(b1.branch.id, { content: 'L2' });
    const result = await svc.searchByBranch(src.id);
    assert.equal(result.branches.length, 2);
    const l1 = result.branches.find(b => b.depth === 1);
    const l2 = result.branches.find(b => b.depth === 2);
    assert.ok(l1);
    assert.ok(l2);
    assert.equal(l1.memory.content, 'L1');
    assert.equal(l2.memory.content, 'L2');
  });

  it('respects depth limit', async () => {
    const src = await svc.add({ content: 'Root' });
    const b1 = await svc.contentBranch(src.id, { content: 'L1' });
    await svc.contentBranch(b1.branch.id, { content: 'L2' });
    const result = await svc.searchByBranch(src.id, { depth: 1 });
    assert.equal(result.branches.length, 1);
    assert.equal(result.branches[0].depth, 1);
  });

  it('includes self when includeSelf is true', async () => {
    const src = await svc.add({ content: 'Root' });
    await svc.contentBranch(src.id, { content: 'Branch' });
    const result = await svc.searchByBranch(src.id, { includeSelf: true });
    assert.equal(result.branches.length, 2);
    const self = result.branches.find(b => b.depth === 0);
    assert.ok(self);
    assert.equal(self.memory.content, 'Root');
  });
});
