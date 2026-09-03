import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('branchDiff()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-branchdiff-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('returns null for non-existent memory', async () => {
    const result = await svc.branchDiff('no-such-id');
    assert.equal(result, null);
  });

  it('returns null for memory with no branch link', async () => {
    const m = await svc.add({ content: 'Standalone' });
    const result = await svc.branchDiff(m.id);
    assert.equal(result, null);
  });

  it('compares branch to source with identical content', async () => {
    const src = await svc.add({ content: 'Original', tags: ['a', 'b'], entities: ['x'] });
    const { branch } = await svc.contentBranch(src.id);
    const diff = await svc.branchDiff(branch.id);
    assert.ok(diff);
    assert.equal(diff.content.diff, 'identical');
    assert.equal(diff.content.similarity, 1);
    assert.deepEqual(diff.tags.added, []);
    assert.deepEqual(diff.tags.removed, []);
    assert.deepEqual(diff.tags.common, ['a', 'b']);
    assert.deepEqual(diff.entities.added, []);
    assert.deepEqual(diff.entities.common, ['x']);
  });

  it('detects content modification after branch', async () => {
    const src = await svc.add({ content: 'Original content here' });
    const { branch } = await svc.contentBranch(src.id, { content: 'Modified content here' });
    const diff = await svc.branchDiff(branch.id);
    assert.equal(diff.content.diff, 'modified');
    assert.ok(diff.content.similarity < 1);
    assert.ok(diff.content.similarity > 0);
    assert.equal(diff.content.branchLength, 'Modified content here'.length);
    assert.equal(diff.content.sourceLength, 'Original content here'.length);
  });

  it('detects tag changes', async () => {
    const src = await svc.add({ content: 'Test', tags: ['a', 'b'] });
    const { branch } = await svc.contentBranch(src.id, { tags: ['b', 'c'] });
    const diff = await svc.branchDiff(branch.id);
    assert.deepEqual(diff.tags.added, ['c']);
    assert.deepEqual(diff.tags.removed, ['a']);
    assert.deepEqual(diff.tags.common, ['b']);
  });

  it('detects entity changes', async () => {
    const src = await svc.add({ content: 'Test', entities: ['e1', 'e2'] });
    const { branch } = await svc.contentBranch(src.id, { entities: ['e2', 'e3'] });
    const diff = await svc.branchDiff(branch.id);
    assert.deepEqual(diff.entities.added, ['e3']);
    assert.deepEqual(diff.entities.removed, ['e1']);
    assert.deepEqual(diff.entities.common, ['e2']);
  });

  it('returns source and branch metadata', async () => {
    const src = await svc.add({ content: 'Source', tags: ['s'], entities: ['se'] });
    const { branch } = await svc.contentBranch(src.id, { content: 'Branch', tags: ['b'], entities: ['be'] });
    const diff = await svc.branchDiff(branch.id);
    assert.equal(diff.branch.id, branch.id);
    assert.equal(diff.source.id, src.id);
    assert.equal(diff.branch.content, 'Branch');
    assert.equal(diff.source.content, 'Source');
  });

  it('works with chained branches', async () => {
    const src = await svc.add({ content: 'L0', tags: ['t0'] });
    const b1 = await svc.contentBranch(src.id, { content: 'L1', tags: ['t1'] });
    const b2 = await svc.contentBranch(b1.branch.id, { content: 'L2', tags: ['t2'] });
    const diff = await svc.branchDiff(b2.branch.id);
    assert.equal(diff.source.content, 'L1');
    assert.equal(diff.branch.content, 'L2');
    assert.deepEqual(diff.tags.added, ['t2']);
    assert.deepEqual(diff.tags.removed, ['t1']);
  });
});
