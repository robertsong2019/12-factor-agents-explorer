import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

describe('mergePreview()', () => {
  let dir, svc;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), 'mem-mp-'));
    svc = new MemoryService({ dbPath: dir });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true });
  });

  it('returns null for non-existent memory', async () => {
    const a = await svc.add({ content: 'Alpha' });
    const result = await svc.mergePreview(a.id, 'no-such-id');
    assert.equal(result, null);
  });

  it('returns null for same id', async () => {
    const a = await svc.add({ content: 'Alpha' });
    const result = await svc.mergePreview(a.id, a.id);
    assert.equal(result, null);
  });

  it('shows concat content by default', async () => {
    const a = await svc.add({ content: 'Hello', tags: ['a'], entities: ['x'] });
    const b = await svc.add({ content: 'World', tags: ['b'], entities: ['y'] });
    const result = await svc.mergePreview(a.id, b.id);
    assert.equal(result.preview.content, 'Hello\nWorld');
    assert.deepEqual(result.preview.tags, ['a', 'b']);
    assert.deepEqual(result.preview.entities, ['x', 'y']);
  });

  it('shows keep-longer content strategy', async () => {
    const a = await svc.add({ content: 'Hi', tags: ['a'] });
    const b = await svc.add({ content: 'Hello World Longer', tags: ['b'] });
    const result = await svc.mergePreview(a.id, b.id, { contentStrategy: 'keep-longer' });
    assert.equal(result.preview.content, 'Hello World Longer');
  });

  it('shows keep-newer content strategy', async () => {
    const a = await svc.add({ content: 'Old' });
    const b = await svc.add({ content: 'New' });
    const result = await svc.mergePreview(a.id, b.id, { contentStrategy: 'keep-newer' });
    // b was added later so its updatedAt is >= a's
    assert.equal(result.preview.content, 'New');
  });

  it('detects conflicts with unique entities and tags', async () => {
    const a = await svc.add({ content: 'Hello', tags: ['shared', 'only-a'], entities: ['e1', 'e2'] });
    const b = await svc.add({ content: 'Hello', tags: ['shared', 'only-b'], entities: ['e2', 'e3'] });
    const result = await svc.mergePreview(a.id, b.id);
    assert.deepEqual(result.conflicts.uniqueEntities1, ['e1']);
    assert.deepEqual(result.conflicts.uniqueEntities2, ['e3']);
    assert.deepEqual(result.conflicts.uniqueTags1, ['only-a']);
    assert.deepEqual(result.conflicts.uniqueTags2, ['only-b']);
    assert.ok(result.conflicts.contentOverlap > 0);
  });

  it('computes risk score between 0 and 1', async () => {
    const a = await svc.add({ content: 'Alpha beta gamma', tags: ['x'] });
    const b = await svc.add({ content: 'Alpha beta gamma', tags: ['x'] });
    const result = await svc.mergePreview(a.id, b.id);
    // Identical content → high overlap → low risk
    assert.ok(result.risk < 0.5);
  });

  it('does not modify memories', async () => {
    const a = await svc.add({ content: 'Alpha', tags: ['a'] });
    const b = await svc.add({ content: 'Beta', tags: ['b'] });
    await svc.mergePreview(a.id, b.id);
    // Both should still exist
    assert.equal((await svc.get(a.id)).content, 'Alpha');
    assert.equal((await svc.get(b.id)).content, 'Beta');
  });

  it('shows primary tag strategy', async () => {
    const a = await svc.add({ content: 'A', tags: ['x'] });
    const b = await svc.add({ content: 'B', tags: ['y'] });
    const result = await svc.mergePreview(a.id, b.id, { tagStrategy: 'primary' });
    assert.deepEqual(result.preview.tags, ['x']);
  });
});
