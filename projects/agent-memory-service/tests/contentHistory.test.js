import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'chist-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

describe('contentHistory()', () => {
  it('returns single version for memory with no updates', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'initial content', layer: 'core' });
      const h = await svc.contentHistory(m.id);
      assert.equal(h.found, true);
      assert.equal(h.versions.length, 1);
      assert.equal(h.versions[0].current, true);
      assert.equal(h.versions[0].content, 'initial content');
    } finally { cleanup(); }
  });

  it('tracks content versions on update', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'v1', layer: 'core' });
      await svc.update(m.id, { content: 'v2' });
      await svc.update(m.id, { content: 'v3' });
      const h = await svc.contentHistory(m.id);
      assert.equal(h.versions.length, 3);
      assert.equal(h.versions[0].content, 'v1');
      assert.equal(h.versions[0].current, false);
      assert.equal(h.versions[1].content, 'v2');
      assert.equal(h.versions[1].current, false);
      assert.equal(h.versions[2].content, 'v3');
      assert.equal(h.versions[2].current, true);
    } finally { cleanup(); }
  });

  it('does not snapshot when content unchanged', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'same', layer: 'core' });
      await svc.update(m.id, { content: 'same' });
      const h = await svc.contentHistory(m.id);
      assert.equal(h.versions.length, 1);
    } finally { cleanup(); }
  });

  it('returns found:false for non-existent memory', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const h = await svc.contentHistory('no-such-id');
      assert.equal(h.found, false);
      assert.equal(h.versions.length, 0);
    } finally { cleanup(); }
  });
});

describe('contentVersionDiff()', () => {
  it('diffs two versions of the same memory', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'hello world', layer: 'core' });
      await svc.update(m.id, { content: 'hello universe' });
      const diff = await svc.contentVersionDiff(m.id);
      assert.equal(diff.found, true);
      assert.equal(diff.from.content, 'hello world');
      assert.equal(diff.to.content, 'hello universe');
      assert.ok(diff.similarity > 0);
      assert.ok(diff.similarity < 1);
    } finally { cleanup(); }
  });

  it('diffs specific version indices', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'a', layer: 'core' });
      await svc.update(m.id, { content: 'b' });
      await svc.update(m.id, { content: 'c' });
      const diff = await svc.contentVersionDiff(m.id, { from: 1, to: 2 });
      assert.equal(diff.from.content, 'b');
      assert.equal(diff.to.content, 'c');
    } finally { cleanup(); }
  });

  it('returns similarity 1 for identical versions', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.init();
      const m = await svc.add({ content: 'unique text', layer: 'core' });
      const diff = await svc.contentVersionDiff(m.id);
      assert.equal(diff.similarity, 1);
    } finally { cleanup(); }
  });
});
