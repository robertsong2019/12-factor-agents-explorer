import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('contentBranch()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-branch-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('creates a new memory as branch of source', async () => {
    const src = await svc.add({ content: 'Original content', tags: ['a'], entities: ['x'] });
    const result = await svc.contentBranch(src.id);
    assert.ok(result);
    assert.ok(result.branch);
    assert.equal(result.branch.content, 'Original content');
    assert.notEqual(result.branch.id, src.id);
    assert.deepEqual(result.branch.tags, ['a']);
    assert.deepEqual(result.branch.entities, ['x']);
  });

  it('creates bidirectional links', async () => {
    const src = await svc.add({ content: 'Source' });
    const result = await svc.contentBranch(src.id);
    assert.ok(result.linkIds);
    assert.equal(result.linkIds.length, 2);
    // Verify links exist via getLinks
    const srcLinks = await svc.getLinks(src.id);
    const branchLinks = await svc.getLinks(result.branch.id);
    // Each has 2 links: one outgoing, one incoming
    assert.ok(srcLinks.length >= 1, 'source should have at least 1 link');
    assert.ok(branchLinks.length >= 1, 'branch should have at least 1 link');
    const allLinks = [...srcLinks, ...branchLinks];
    assert.ok(allLinks.every(l => l.type === 'derived_from'), 'all links should be derived_from');
  });

  it('allows overriding content', async () => {
    const src = await svc.add({ content: 'Original' });
    const result = await svc.contentBranch(src.id, { content: 'Modified branch' });
    assert.equal(result.branch.content, 'Modified branch');
    // Source unchanged
    const srcCheck = await svc.get(src.id);
    assert.equal(srcCheck.content, 'Original');
  });

  it('allows overriding layer and tags', async () => {
    const src = await svc.add({ content: 'Original', layer: 'core', tags: ['root'] });
    const result = await svc.contentBranch(src.id, { layer: 'short', tags: ['fork'] });
    assert.equal(result.branch.layer, 'short');
    assert.deepEqual(result.branch.tags, ['fork']);
  });

  it('sets source metadata to branch:originalId', async () => {
    const src = await svc.add({ content: 'Source' });
    const result = await svc.contentBranch(src.id);
    assert.equal(result.branch.source, `branch:${src.id}`);
  });

  it('returns null for non-existent memory', async () => {
    const result = await svc.contentBranch('non-existent-id');
    assert.equal(result, null);
  });

  it('branch evolves independently from source', async () => {
    const src = await svc.add({ content: 'Shared start' });
    const result = await svc.contentBranch(src.id);
    await svc.update(result.branch.id, { content: 'Branch diverged' });
    const srcAfter = await svc.get(src.id);
    const branchAfter = await svc.get(result.branch.id);
    assert.equal(srcAfter.content, 'Shared start');
    assert.equal(branchAfter.content, 'Branch diverged');
  });

  it('can branch a branch (chained branches)', async () => {
    const src = await svc.add({ content: 'Level 0' });
    const b1 = await svc.contentBranch(src.id, { content: 'Level 1' });
    const b2 = await svc.contentBranch(b1.branch.id, { content: 'Level 2' });
    assert.equal(b2.branch.content, 'Level 2');
    assert.equal(b2.branch.source, `branch:${b1.branch.id}`);
  });
});
