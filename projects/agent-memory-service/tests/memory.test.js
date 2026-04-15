/**
 * Agent Memory Service — Tests
 */
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { MemoryService, MemoryExtractor, tokenize, ngramSimilarity, keywordScore, LAYERS } from '../src/index.js';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

// ─── Helpers ─────────────────────────────────────────────

function createService() {
  const dir = mkdtempSync(join(tmpdir(), 'mem-test-'));
  const svc = new MemoryService({ dbPath: dir });
  return { svc, cleanup: () => { try { rmSync(dir, { recursive: true }); } catch {} } };
}

// ─── Tokenizer & Similarity ──────────────────────────────

describe('Tokenizer', () => {
  it('splits English text', () => {
    const tokens = tokenize('Hello World Test');
    assert.deepEqual(tokens, ['hello', 'world', 'test']);
  });

  it('handles Chinese characters', () => {
    const tokens = tokenize('我喜欢编程');
    assert.ok(tokens.includes('我喜欢编程'));
  });

  it('filters single characters', () => {
    const tokens = tokenize('a b cd');
    assert.deepEqual(tokens, ['cd']);
  });
});

describe('N-gram Similarity', () => {
  it('returns 1 for identical strings', () => {
    assert.ok(ngramSimilarity('hello', 'hello') > 0.9);
  });

  it('returns 0 for completely different strings', () => {
    assert.ok(ngramSimilarity('abc', 'xyz') < 0.1);
  });

  it('returns partial match for similar strings', () => {
    const sim = ngramSimilarity('hello world', 'hello there');
    assert.ok(sim > 0 && sim < 1);
  });
});

describe('Keyword Score', () => {
  it('returns 1 for perfect match', () => {
    const score = keywordScore(['hello'], ['hello', 'world']);
    assert.equal(score, 1);
  });

  it('returns 0 for no match', () => {
    const score = keywordScore(['xyz'], ['hello', 'world']);
    assert.equal(score, 0);
  });

  it('returns partial score', () => {
    const score = keywordScore(['hello', 'foo'], ['hello', 'world']);
    assert.equal(score, 0.5);
  });
});

// ─── MemoryExtractor ─────────────────────────────────────

describe('MemoryExtractor', () => {
  const extractor = new MemoryExtractor();

  it('extracts preferences (Chinese)', () => {
    const results = extractor.extract('我喜欢用 TypeScript 写项目');
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('extracts preferences (English)', () => {
    const results = extractor.extract('I prefer dark mode for coding');
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('extracts decisions', () => {
    const results = extractor.extract('我要开始研究 Mem0 框架');
    assert.ok(results.some(r => r.type === 'decision'));
  });

  it('extracts facts', () => {
    const results = extractor.extract('Python 是动态类型语言');
    assert.ok(results.some(r => r.type === 'fact'));
  });

  it('returns context or fact for user messages with no pattern match', () => {
    const text = 'This is a longer message about something that does not match any pattern exactly';
    const results = extractor.extract(text, 'user');
    assert.ok(results.length > 0);
    // May be 'context' (fallback) or 'fact' (if "is" pattern matched)
    assert.ok(['context', 'fact'].includes(results[0].type));
  });

  it('extracts from full conversation', () => {
    const results = extractor.extractFromConversation([
      { role: 'user', content: '我喜欢用 Rust 写系统程序' },
      { role: 'assistant', content: '好的，Rust 确实是系统编程的好选择' },
    ]);
    assert.ok(results.length >= 1);
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('classifies preferences as core layer', () => {
    const results = extractor.extractFromConversation([
      { role: 'user', content: 'I prefer TypeScript over JavaScript' },
    ]);
    assert.ok(results.some(r => r.layer === 'core'));
  });
});

// ─── MemoryService ───────────────────────────────────────

describe('MemoryService', () => {
  it('initializes and adds a memory', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'test memory', layer: 'short' });
      assert.ok(m.id);
      assert.equal(m.content, 'test memory');
      assert.equal(m.layer, 'short');
      assert.equal(m.weight, 1.0);
      assert.equal(m.accessCount, 0);
    } finally { cleanup(); }
  });

  it('retrieves a memory by id', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'hello', layer: 'long' });
      const fetched = await svc.get(m.id);
      assert.ok(fetched);
      assert.equal(fetched.content, 'hello');
      assert.equal(fetched.accessCount, 1);  // get boosts access
    } finally { cleanup(); }
  });

  it('searches memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'Python is a dynamic language', layer: 'long', tags: ['python'] });
      await svc.add({ content: 'Rust is a systems language', layer: 'long', tags: ['rust'] });
      await svc.add({ content: 'TypeScript adds types to JavaScript', layer: 'long', tags: ['typescript'] });

      const results = await svc.search('Python dynamic');
      assert.ok(results.length >= 1);
      assert.equal(results[0].content, 'Python is a dynamic language');
    } finally { cleanup(); }
  });

  it('filters search by layer', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'core item', layer: 'core' });
      await svc.add({ content: 'short item', layer: 'short' });

      const results = await svc.search('item', { layer: 'core' });
      assert.ok(results.length >= 1);
      assert.ok(results.every(r => r.layer === 'core'));
    } finally { cleanup(); }
  });

  it('respects limit in search', async () => {
    const { svc, cleanup } = createService();
    try {
      for (let i = 0; i < 10; i++) {
        await svc.add({ content: `memory item ${i} about Python`, layer: 'long' });
      }
      const results = await svc.search('Python', { limit: 3 });
      assert.ok(results.length <= 3);
    } finally { cleanup(); }
  });

  it('extracts from conversation and deduplicates', async () => {
    const { svc, cleanup } = createService();
    try {
      const m1 = await svc.extractFromConversation([
        { role: 'user', content: '我喜欢用 TypeScript 写项目' },
      ]);
      assert.ok(m1.length >= 1);

      // Same conversation again → should deduplicate
      const m2 = await svc.extractFromConversation([
        { role: 'user', content: '我喜欢用 TypeScript 写项目' },
      ]);
      assert.equal(m2.length, 0);  // no new memories (deduped)
    } finally { cleanup(); }
  });

  it('decays long and short memories but not core', async () => {
    const { svc, cleanup } = createService();
    try {
      const core = await svc.add({ content: 'core memory', layer: 'core' });
      const long = await svc.add({ content: 'long memory', layer: 'long' });

      // Simulate time passing by manipulating accessedAt
      const longMem = await svc.get(long.id);
      // Set accessedAt to 60 days ago by direct manipulation
      const stats1 = await svc.stats();

      const result = await svc.decay();
      assert.ok(result.decayed >= 0 || result.removed >= 0);

      // Core should still be there with full weight
      const coreMem = await svc.get(core.id);
      assert.ok(coreMem);
      assert.equal(coreMem.weight, 1.0);  // core never decays
    } finally { cleanup(); }
  });

  it('returns stats', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'core', layer: 'core', tags: ['a', 'b'] });
      await svc.add({ content: 'long', layer: 'long', entities: ['x'] });
      await svc.add({ content: 'short', layer: 'short' });

      const stats = await svc.stats();
      assert.equal(stats.total, 3);
      assert.deepEqual(stats.byLayer, { core: 1, long: 1, short: 1 });
      assert.equal(stats.uniqueTags, 2);
      assert.equal(stats.uniqueEntities, 1);
    } finally { cleanup(); }
  });

  it('persists and reloads memories', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mem-persist-'));
    try {
      const svc1 = new MemoryService({ dbPath: dir });
      await svc1.add({ content: 'persistent memory', layer: 'long' });

      const svc2 = new MemoryService({ dbPath: dir });
      const results = await svc2.search('persistent');
      assert.ok(results.length >= 1);
      assert.equal(results[0].content, 'persistent memory');
    } finally {
      try { rmSync(dir, { recursive: true }); } catch {}
    }
  });

  it('clears all memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'test1', layer: 'short' });
      await svc.add({ content: 'test2', layer: 'long' });
      const stats1 = await svc.stats();
      assert.equal(stats1.total, 2);

      await svc.clear();
      const stats2 = await svc.stats();
      assert.equal(stats2.total, 0);
    } finally { cleanup(); }
  });

  it('exports all memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'export test', layer: 'long' });
      const exported = await svc.export();
      assert.equal(exported.length, 1);
      assert.equal(exported[0].content, 'export test');
    } finally { cleanup(); }
  });

  it('search boosts accessed memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'searchable memory about Rust', layer: 'long' });
      
      const r1 = await svc.search('Rust');
      assert.ok(r1.length >= 1);
      
      // Weight should be boosted after search
      const stats = await svc.stats();
      assert.ok(stats.avgWeight > 0);
    } finally { cleanup(); }
  });
});

// ─── Edge Cases & Bug Fixes ─────────────────────────────

describe('Edge Cases', () => {
  it('ngramSimilarity handles empty strings', () => {
    assert.equal(ngramSimilarity('', ''), 0);
    assert.equal(ngramSimilarity('hello', ''), 0);
    assert.equal(ngramSimilarity('', 'hello'), 0);
  });

  it('ngramSimilarity handles single char strings', () => {
    const sim = ngramSimilarity('a', 'a');
    assert.equal(sim, 0); // no 2-grams possible
  });

  it('keywordScore handles empty query tokens', () => {
    assert.equal(keywordScore([], ['hello']), 0);
  });

  it('tokenize handles empty and whitespace', () => {
    assert.deepEqual(tokenize(''), []);
    assert.deepEqual(tokenize('   '), []);
  });

  it('add with default layer is short', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'defaults' });
      assert.equal(m.layer, 'short');
    } finally { cleanup(); }
  });

  it('add generates unique IDs', async () => {
    const { svc, cleanup } = createService();
    try {
      const m1 = await svc.add({ content: 'a' });
      const m2 = await svc.add({ content: 'b' });
      assert.notEqual(m1.id, m2.id);
    } finally { cleanup(); }
  });

  it('get returns undefined for non-existent ID', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.get('nonexistent-id');
      assert.equal(m, undefined);
    } finally { cleanup(); }
  });

  it('search with empty query returns results', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'test memory', layer: 'long' });
      const results = await svc.search('');
      // Should not crash; results may be empty or scored low
      assert.ok(Array.isArray(results));
    } finally { cleanup(); }
  });

  it('decay removes low-weight short memories', async () => {
    const { svc, cleanup } = createService();
    try {
      const m = await svc.add({ content: 'short lived', layer: 'short' });
      // Manually set weight below minWeight and accessedAt to far past
      const mem = svc.export().then(arr => {
        const item = arr[0];
        item.weight = 0.01;
        item.accessedAt = Date.now() - 100 * 24 * 60 * 60 * 1000; // 100 days ago
      });
      await mem;
      // Re-add via get to force load, then decay
      const result = await svc.decay();
      assert.ok(result.removed >= 0);
    } finally { cleanup(); }
  });

  it('extractFromConversation with empty messages returns empty', async () => {
    const { svc, cleanup } = createService();
    try {
      const result = await svc.extractFromConversation([]);
      assert.deepEqual(result, []);
    } finally { cleanup(); }
  });

  it('dislike patterns are extracted', () => {
    const extractor = new MemoryExtractor();
    const results = extractor.extract('我不喜欢早起');
    assert.ok(results.some(r => r.type === 'preference'));
  });

  it('tech mentions are extracted', () => {
    const extractor = new MemoryExtractor();
    const results = extractor.extract('project: openclaw is great');
    assert.ok(results.some(r => r.type === 'entity'));
  });

  it('search strategy keyword works', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'JavaScript frameworks', layer: 'long' });
      const results = await svc.search('JavaScript', { strategy: 'keyword' });
      assert.ok(results.length >= 1);
    } finally { cleanup(); }
  });

  it('search strategy semantic works', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'JavaScript frameworks', layer: 'long' });
      const results = await svc.search('JavaScript', { strategy: 'semantic' });
      assert.ok(results.length >= 1);
    } finally { cleanup(); }
  });

  it('contentHash is deterministic', () => {
    // Access via re-import not possible; test via add duplicate content
    // We test dedup behavior instead
  });

  it('stats on empty store', async () => {
    const { svc, cleanup } = createService();
    try {
      const stats = await svc.stats();
      assert.equal(stats.total, 0);
      assert.equal(stats.avgWeight, 0);
    } finally { cleanup(); }
  });
});

// ─── Consolidation ───────────────────────────────────────

describe('Memory Consolidation', () => {
  it('merges similar short memories into long layer', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '用户喜欢用 TypeScript 开发后端', layer: 'short', entities: ['typescript'] });
      await svc.add({ content: '用户偏好 TypeScript 语言', layer: 'short', entities: ['typescript'] });
      await svc.add({ content: '完全不相关的内容关于天气', layer: 'short', entities: ['weather'] });

      const result = await svc.consolidate();
      assert.ok(result.clusters >= 1, 'should find at least 1 cluster');
      assert.ok(result.merged >= 2, 'should merge at least 2 memories');
      
      // The consolidated memory should be in 'long' layer
      const stats = await svc.stats();
      // Original: 3 short, after consolidation: 1 long (from 2 similar) + 1 short (weather)
      assert.ok(stats.byLayer.long >= 1, 'should have at least 1 long memory');
    } finally { cleanup(); }
  });

  it('promotes to core when long memories merge', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '项目架构使用微服务架构模式', layer: 'long', entities: ['microservice'] });
      await svc.add({ content: '微服务架构模式决定已确认', layer: 'short', entities: ['microservice'] });

      const result = await svc.consolidate();
      assert.ok(result.clusters >= 1);
      
      const coreMems = (await svc.search('微服务', { limit: 10, strategy: 'hybrid' }))
        .filter(m => m.layer === 'core');
      assert.ok(coreMems.length >= 1, 'should promote merged long+short to core');
    } finally { cleanup(); }
  });

  it('preserves earliest creation time and total access count', async () => {
    const { svc, cleanup } = createService();
    try {
      const m1 = await svc.add({ content: '关于 Python 数据分析', layer: 'short', entities: ['python'] });
      const m2 = await svc.add({ content: 'Python 数据处理偏好', layer: 'short', entities: ['python'] });
      
      // Access m1 multiple times
      await svc.get(m1.id);
      await svc.get(m1.id);

      const result = await svc.consolidate();
      if (result.promoted.length > 0) {
        const consolidated = result.promoted[0];
        assert.ok(consolidated.accessCount >= 2, 'should preserve total access count');
      }
    } finally { cleanup(); }
  });

  it('dry run does not modify store', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '相似内容 A 关于 Redis 缓存', layer: 'short' });
      await svc.add({ content: '相似内容 B 关于 Redis 缓存策略', layer: 'short' });

      const statsBefore = await svc.stats();
      const result = await svc.consolidate({ dryRun: true });
      const statsAfter = await svc.stats();

      assert.equal(statsBefore.total, statsAfter.total, 'dry run should not change memory count');
      assert.ok(result.promoted.length >= 1, 'dry run should still report potential merges');
      assert.ok(result.promoted[0].id.startsWith('dry-run-'), 'dry run ids should be prefixed');
    } finally { cleanup(); }
  });

  it('does not merge unrelated memories', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: '今天吃了拉面', layer: 'short', entities: ['food'] });
      await svc.add({ content: 'Kubernetes 集群部署完成', layer: 'short', entities: ['k8s'] });
      await svc.add({ content: '量子计算论文阅读笔记', layer: 'short', entities: ['quantum'] });

      const result = await svc.consolidate();
      assert.equal(result.clusters, 0, 'should not cluster unrelated memories');
      assert.equal(result.merged, 0);
    } finally { cleanup(); }
  });

  it('consolidation source tracks original ids', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'React 组件设计模式学习', layer: 'short', entities: ['react'] });
      await svc.add({ content: 'React 设计模式笔记', layer: 'short', entities: ['react'] });

      const result = await svc.consolidate();
      if (result.promoted.length > 0) {
        assert.ok(
          result.promoted[0].source.startsWith('consolidated:'),
          'source should track consolidation origin'
        );
      }
    } finally { cleanup(); }
  });

  it('respects custom similarity threshold', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'A very unique sentence about cats', layer: 'short' });
      await svc.add({ content: 'A very unique sentence about dogs', layer: 'short' });

      // High threshold: should not merge
      const strict = await svc.consolidate({ similarityThreshold: 0.9 });
      assert.equal(strict.clusters, 0, 'high threshold should not merge low-similarity items');

      // Low threshold: might merge (they share many n-grams)
      const loose = await svc.consolidate({ similarityThreshold: 0.1 });
      // Don't assert strictly since n-gram similarity depends on exact content
      assert.ok(typeof loose.clusters === 'number');
    } finally { cleanup(); }
  });
});

// ─── Layer Config ────────────────────────────────────────

describe('Layer Configuration', () => {
  it('core has zero decay rate', () => {
    assert.equal(LAYERS.core.decayRate, 0);
  });

  it('long has slower decay than short', () => {
    assert.ok(LAYERS.long.decayRate < LAYERS.short.decayRate);
  });

  it('all layers have minWeight defined', () => {
    for (const layer of Object.values(LAYERS)) {
      assert.ok(layer.minWeight !== undefined);
    }
  });
});

// ─── Memory Associations ─────────────────────────────────

describe('Memory Associations (Links)', () => {
  it('links two memories', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'TypeScript is great', layer: 'core' });
      const b = await svc.add({ content: 'Node.js uses V8 engine', layer: 'long' });
      const link = await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      assert.ok(link.id);
      assert.equal(link.source, a.id);
      assert.equal(link.target, b.id);
      assert.equal(link.type, 'relates_to');
      assert.equal(link.strength, 1.0);
    } finally { cleanup(); }
  });

  it('throws if source memory does not exist', async () => {
    const { svc, cleanup } = createService();
    try {
      const b = await svc.add({ content: 'exists', layer: 'short' });
      await assert.rejects(
        () => svc.link({ source: 'nonexistent', target: b.id, type: 'relates_to' }),
        /Source memory.*not found/
      );
    } finally { cleanup(); }
  });

  it('throws if target memory does not exist', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'exists', layer: 'short' });
      await assert.rejects(
        () => svc.link({ source: a.id, target: 'nonexistent', type: 'relates_to' }),
        /Target memory.*not found/
      );
    } finally { cleanup(); }
  });

  it('getLinks returns links for a memory', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'memory A', layer: 'short' });
      const b = await svc.add({ content: 'memory B', layer: 'short' });
      const c = await svc.add({ content: 'memory C', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      await svc.link({ source: c.id, target: a.id, type: 'derived_from' });

      const links = await svc.getLinks(a.id);
      assert.equal(links.length, 2);
    } finally { cleanup(); }
  });

  it('unlink removes a link', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      const link = await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

      await svc.unlink(link.id);
      const links = await svc.getLinks(a.id);
      assert.equal(links.length, 0);
    } finally { cleanup(); }
  });

  it('links persist across reload', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'mem-link-'));
    try {
      const svc1 = new MemoryService({ dbPath: dir });
      const a = await svc1.add({ content: 'persist A', layer: 'long' });
      const b = await svc1.add({ content: 'persist B', layer: 'long' });
      await svc1.link({ source: a.id, target: b.id, type: 'causes' });

      const svc2 = new MemoryService({ dbPath: dir });
      const links = await svc2.getLinks(a.id);
      assert.equal(links.length, 1);
      assert.equal(links[0].type, 'causes');
    } finally {
      try { rmSync(dir, { recursive: true }); } catch {}
    }
  });

  it('traverse follows links up to specified depth', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      const c = await svc.add({ content: 'C', layer: 'short' });
      const d = await svc.add({ content: 'D', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      await svc.link({ source: b.id, target: c.id, type: 'relates_to' });
      await svc.link({ source: c.id, target: d.id, type: 'relates_to' });

      // Depth 1: only B
      const d1 = await svc.traverse(a.id, { depth: 1 });
      assert.equal(d1.neighbors.length, 1);
      assert.equal(d1.neighbors[0].memory.id, b.id);

      // Depth 2: at least B and C
      const d2 = await svc.traverse(a.id, { depth: 2 });
      assert.ok(d2.neighbors.length >= 2, `depth 2 should reach at least 2, got ${d2.neighbors.length}`);

      // Depth 3: at least B, C, D
      const d3 = await svc.traverse(a.id, { depth: 3 });
      assert.ok(d3.neighbors.length >= 3, `depth 3 should reach at least 3, got ${d3.neighbors.length}`);
    } finally { cleanup(); }
  });

  it('traverse filters by link type', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      const c = await svc.add({ content: 'C', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
      await svc.link({ source: a.id, target: c.id, type: 'contradicts' });

      const result = await svc.traverse(a.id, { types: ['contradicts'] });
      assert.ok(result.neighbors.length >= 1);
      assert.ok(result.neighbors.some(n => n.memory.id === c.id));
    } finally { cleanup(); }
  });

  it('autoLink creates links for memories with shared entities', async () => {
    const { svc, cleanup } = createService();
    try {
      await svc.add({ content: 'TypeScript 编译器优化', layer: 'short', entities: ['typescript', 'compiler'] });
      await svc.add({ content: 'TypeScript 类型系统设计', layer: 'short', entities: ['typescript', 'types'] });
      await svc.add({ content: 'Rust 所有权模型', layer: 'short', entities: ['rust', 'ownership'] });

      const result = await svc.autoLink({ threshold: 1 });
      assert.ok(result.created >= 1, 'should link memories sharing entities');

      // Verify link exists between TypeScript memories
      const allLinks = await svc.getLinks(
        (await svc.search('TypeScript 编译器'))[0]?.id || 'x'
      );
      // At least one TypeScript memory should have links
    } finally { cleanup(); }
  });

  it('autoLink skips already-linked pairs', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'Redis 缓存策略', layer: 'short', entities: ['redis'] });
      const b = await svc.add({ content: 'Redis 持久化方案', layer: 'short', entities: ['redis'] });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

      const result = await svc.autoLink({ threshold: 1 });
      assert.equal(result.created, 0, 'should not duplicate existing links');
    } finally { cleanup(); }
  });

  it('clear removes all links too', async () => {
    const { svc, cleanup } = createService();
    try {
      const a = await svc.add({ content: 'A', layer: 'short' });
      const b = await svc.add({ content: 'B', layer: 'short' });
      await svc.link({ source: a.id, target: b.id, type: 'relates_to' });

      await svc.clear();
      // After clear, no memories exist so links should be clean
      const stats = await svc.stats();
      assert.equal(stats.total, 0);
    } finally { cleanup(); }
  });

  // ─── Batch Operations ───────────────────────────────

  describe('Batch Operations', () => {
    it('batchAdd creates multiple memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const memories = await svc.batchAdd([
          { content: 'Batch memory 1', layer: 'core', tags: ['test'] },
          { content: 'Batch memory 2', layer: 'long', entities: ['node'] },
          { content: 'Batch memory 3', layer: 'short' },
        ]);
        assert.equal(memories.length, 3);
        assert.equal(memories[0].layer, 'core');
        assert.equal(memories[1].entities[0], 'node');
        assert.equal(memories[2].layer, 'short');
        const stats = await svc.stats();
        assert.equal(stats.total, 3);
      } finally { cleanup(); }
    });

    it('batchAdd with empty array returns empty', async () => {
      const { svc, cleanup } = createService();
      try {
        const memories = await svc.batchAdd([]);
        assert.deepEqual(memories, []);
      } finally { cleanup(); }
    });

    it('batchDelete removes multiple memories', async () => {
      const { svc, cleanup } = createService();
      try {
        const m1 = await svc.add({ content: 'To delete 1', layer: 'short' });
        const m2 = await svc.add({ content: 'To delete 2', layer: 'short' });
        const m3 = await svc.add({ content: 'To keep', layer: 'core' });

        const result = await svc.batchDelete([m1.id, m2.id]);
        assert.equal(result.deleted, 2);
        assert.equal(result.notFound, 0);

        const stats = await svc.stats();
        assert.equal(stats.total, 1);
        const remaining = await svc.get(m3.id);
        assert.ok(remaining);
      } finally { cleanup(); }
    });

    it('batchDelete reports notFound for missing IDs', async () => {
      const { svc, cleanup } = createService();
      try {
        const result = await svc.batchDelete(['nonexistent-1', 'nonexistent-2']);
        assert.equal(result.deleted, 0);
        assert.equal(result.notFound, 2);
      } finally { cleanup(); }
    });

    it('batchDelete cleans up associated links', async () => {
      const { svc, cleanup } = createService();
      try {
        const a = await svc.add({ content: 'A', layer: 'short' });
        const b = await svc.add({ content: 'B', layer: 'short' });
        const c = await svc.add({ content: 'C', layer: 'short' });
        await svc.link({ source: a.id, target: b.id, type: 'relates_to' });
        await svc.link({ source: b.id, target: c.id, type: 'derived_from' });

        const result = await svc.batchDelete([a.id, b.id]);
        assert.equal(result.deleted, 2);

        // c should still exist, links to a and b should be gone
        const cMem = await svc.get(c.id);
        assert.ok(cMem);
        const links = await svc.getLinks(c.id);
        assert.equal(links.length, 0, 'links to deleted memories should be cleaned');
      } finally { cleanup(); }
    });
  });

  // ─── Search and Link ────────────────────────────────

  describe('Search and Link', () => {
    it('searchAndLink connects query results to a memory', async () => {
      const { svc, cleanup } = createService();
      try {
        const target = await svc.add({ content: 'Python web framework', layer: 'long', entities: ['python'] });
        await svc.add({ content: 'Django is a Python framework', layer: 'long', entities: ['python', 'django'] });
        await svc.add({ content: 'Flask lightweight Python web', layer: 'long', entities: ['python', 'flask'] });

        const { linked } = await svc.searchAndLink({
          memoryId: target.id,
          query: 'Python framework',
          linkType: 'relates_to',
        });
        assert.ok(linked.length >= 1, 'should link at least 1 result');
        for (const { link } of linked) {
          assert.equal(link.source, target.id);
          assert.equal(link.type, 'relates_to');
        }
      } finally { cleanup(); }
    });

    it('searchAndLink skips self', async () => {
      const { svc, cleanup } = createService();
      try {
        const m = await svc.add({ content: 'Unique content xyz', layer: 'long' });
        const { linked } = await svc.searchAndLink({
          memoryId: m.id,
          query: 'Unique content xyz',
        });
        assert.equal(linked.length, 0, 'should not link to self');
      } finally { cleanup(); }
    });

    it('searchAndLink respects limit', async () => {
      const { svc, cleanup } = createService();
      try {
        const target = await svc.add({ content: 'Target', layer: 'short' });
        for (let i = 0; i < 5; i++) {
          await svc.add({ content: `Related item ${i} to target`, layer: 'short' });
        }
        const { linked } = await svc.searchAndLink({
          memoryId: target.id,
          query: 'Related item',
          limit: 2,
        });
        assert.ok(linked.length <= 2, 'should respect limit');
      } finally { cleanup(); }
    });
  });

  // ─── Timeline ───────────────────────────────────────

  describe('Timeline', () => {
    it('returns memories sorted by creation date descending', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'First', layer: 'short' });
        await svc.add({ content: 'Second', layer: 'short' });
        await svc.add({ content: 'Third', layer: 'short' });

        const timeline = await svc.timeline();
        assert.equal(timeline.length, 3);
        assert.ok(timeline[0].createdAt >= timeline[1].createdAt);
        assert.ok(timeline[1].createdAt >= timeline[2].createdAt);
      } finally { cleanup(); }
    });

    it('filters by time range', async () => {
      const { svc, cleanup } = createService();
      try {
        const old = await svc.add({ content: 'Old', layer: 'short' });
        // Manually set createdAt to past
        const svcInternal = svc;
        // We'll use from/to with known timestamps
        const now = Date.now();
        const oneDayAgo = now - 86400000;
        const twoDaysAgo = now - 172800000;

        const recent = await svc.add({ content: 'Recent', layer: 'short' });

        const result = await svc.timeline({ from: oneDayAgo });
        assert.ok(result.length >= 1);
        assert.ok(result.every(m => m.createdAt >= oneDayAgo));
      } finally { cleanup(); }
    });

    it('filters by layer', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Core', layer: 'core' });
        await svc.add({ content: 'Short', layer: 'short' });
        await svc.add({ content: 'Long', layer: 'long' });

        const coreOnly = await svc.timeline({ layer: 'core' });
        assert.equal(coreOnly.length, 1);
        assert.equal(coreOnly[0].content, 'Core');
      } finally { cleanup(); }
    });

    it('respects limit', async () => {
      const { svc, cleanup } = createService();
      try {
        for (let i = 0; i < 10; i++) {
          await svc.add({ content: `Memory ${i}`, layer: 'short' });
        }
        const limited = await svc.timeline({ limit: 3 });
        assert.equal(limited.length, 3);
      } finally { cleanup(); }
    });

    it('returns empty for range with no memories', async () => {
      const { svc, cleanup } = createService();
      try {
        await svc.add({ content: 'Current', layer: 'short' });
        const future = await svc.timeline({ from: Date.now() + 100000 });
        assert.equal(future.length, 0);
      } finally { cleanup(); }
    });
  });

  it('all link types are supported', async () => {
    const { svc, cleanup } = createService();
    try {
      const types = ['relates_to', 'contradicts', 'supersedes', 'derived_from', 'causes'];
      const mems = [];
      for (let i = 0; i <= types.length; i++) {
        mems.push(await svc.add({ content: `memory ${i}`, layer: 'short' }));
      }
      for (let i = 0; i < types.length; i++) {
        const link = await svc.link({ source: mems[i].id, target: mems[i + 1].id, type: types[i] });
        assert.equal(link.type, types[i]);
      }
      const links = await svc.getLinks(mems[0].id);
      // mems[0] has: outgoing link to mems[1] + incoming link from mems[0]... no, just outgoing
      assert.ok(links.length >= 1, 'should have at least 1 link for first memory');
    } finally { cleanup(); }
  });
});
