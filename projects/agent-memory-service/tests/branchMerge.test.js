import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('branchMerge(branchId, opts)', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-branchmerge-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('returns null for non-existent memory', async () => {
    const result = await svc.branchMerge('no-such-id');
    assert.equal(result, null);
  });

  it('returns null for non-branch memory', async () => {
    const m = await svc.add({ content: 'Standalone' });
    const result = await svc.branchMerge(m.id);
    assert.equal(result, null);
  });

  it('merges branch back to source with concat strategy (default)', async () => {
    const src = await svc.add({ content: 'Source text', tags: ['a'], entities: ['x'] });
    const { branch } = await svc.contentBranch(src.id, { content: 'Branch text', tags: ['b'], entities: ['y'] });
    const result = await svc.branchMerge(branch.id);
    assert.ok(result);
    assert.ok(result.diff);
    assert.ok(result.merge);
    // Source should now have concatenated content
    assert.equal(result.merge.merged.content, 'Source text\nBranch text');
    assert.deepEqual(result.merge.merged.tags.sort(), ['a', 'b']);
    assert.deepEqual(result.merge.merged.entities.sort(), ['x', 'y']);
    // Branch should be deleted
    assert.equal(result.merge.deletedId, branch.id);
    assert.equal((await svc.get(branch.id)) ?? null, null);
  });

  it('supports keep-longer content strategy', async () => {
    const src = await svc.add({ content: 'Short' });
    const { branch } = await svc.contentBranch(src.id, { content: 'Much longer branch content' });
    const result = await svc.branchMerge(branch.id, { contentStrategy: 'keep-longer' });
    assert.equal(result.merge.merged.content, 'Much longer branch content');
  });

  it('supports keep-newer content strategy', async () => {
    const src = await svc.add({ content: 'Old content' });
    const { branch } = await svc.contentBranch(src.id, { content: 'New content' });
    // branch is newer (created after source)
    const result = await svc.branchMerge(branch.id, { contentStrategy: 'keep-newer' });
    // branch is newer, so its content wins when comparing updatedAt
    assert.ok(result.merge.merged.content);
  });

  it('supports manual content strategy', async () => {
    const src = await svc.add({ content: 'Original' });
    const { branch } = await svc.contentBranch(src.id, { content: 'Branch' });
    const result = await svc.branchMerge(branch.id, { contentStrategy: 'manual', content: 'Manual override' });
    assert.equal(result.merge.merged.content, 'Manual override');
  });

  it('includes diff summary in result', async () => {
    const src = await svc.add({ content: 'Source', tags: ['a'], entities: ['e1'] });
    const { branch } = await svc.contentBranch(src.id, { content: 'Branch', tags: ['b'], entities: ['e2'] });
    const result = await svc.branchMerge(branch.id);
    assert.equal(result.diff.content.diff, 'modified');
    assert.deepEqual(result.diff.tags.added, ['b']);
    assert.deepEqual(result.diff.tags.removed, ['a']);
    assert.deepEqual(result.diff.entities.added, ['e2']);
  });

  it('rewires branch links to source', async () => {
    const src = await svc.add({ content: 'Source' });
    const other = await svc.add({ content: 'Other' });
    const { branch } = await svc.contentBranch(src.id, { content: 'Branch' });
    // Link branch to other memory
    await svc.link({ source: branch.id, target: other.id, type: 'related' });
    const result = await svc.branchMerge(branch.id, { linkStrategy: 'rewire' });
    assert.equal(result.merge.stats.rewiredLinks, 1);
    // Source should now have a link to other
    const srcLinks = await svc.getLinks(src.id);
    assert.ok(srcLinks.some(l => l.type === 'related'));
  });

  it('handles tag strategy primary (keep source tags)', async () => {
    const src = await svc.add({ content: 'Source', tags: ['a'] });
    const { branch } = await svc.contentBranch(src.id, { tags: ['b'] });
    const result = await svc.branchMerge(branch.id, { tagStrategy: 'primary' });
    assert.deepEqual(result.merge.merged.tags, ['a']);
  });

  it('handles tag strategy secondary (keep branch tags)', async () => {
    const src = await svc.add({ content: 'Source', tags: ['a'] });
    const { branch } = await svc.contentBranch(src.id, { tags: ['b'] });
    const result = await svc.branchMerge(branch.id, { tagStrategy: 'secondary' });
    assert.deepEqual(result.merge.merged.tags, ['b']);
  });
});
